#!/usr/bin/env python
"""Regenerate golden fixtures by running the Octave fixture scripts.

Every ``legacy/tests_octave/fx_<name>.m`` is a function ``fx_<name>(outfile)`` that calls the
original MATLAB code and writes ``outfile`` with ``save -v7``. This tool runs each one in a
fresh ``octave-cli`` (with ``legacy/matlab/formdiscovery1.0`` and ``legacy/tests_octave`` on the path)
and writes ``tests/fixtures/<name>.mat``. Other ``.m`` files in ``legacy/tests_octave/`` (e.g.
``smoke_patches.m``) are helpers used by live tests and are not run.

Usage::

    python legacy/tools/gen_fixtures.py                   # all fixtures, cores/2 octave-cli at once
    python legacy/tools/gen_fixtures.py --jobs 1          # one at a time
    python legacy/tools/gen_fixtures.py matlab_compat     # only fx_matlab_compat.m
    python legacy/tools/gen_fixtures.py --outdir D --compare tests/fixtures
    python legacy/tools/gen_fixtures.py --list

Parallel runs (loop0002 item 03). ``--jobs N`` (default: cores/2) runs up to N
``octave-cli`` side by side, one per task, longest expected task first. Tasks are the
fixture scripts, except ``paperlevel``: its 45 ``runmodel`` runs are 45 tasks
(``fx_paperlevel(part, job)``) plus a merge (``paperlevel_merge.m``), as in
``legacy/tools/gen_paperlevel.py``, so ``--jobs 1`` also runs it that way. A script that reads
another fixture (:data:`DEPENDS`, e.g. ``fx_perf.m`` loads ``paperlevel.mat``) starts
after that fixture is written when both are regenerated, as in the serial alphabetical
order. Each output is written to a staging directory and moved into ``--outdir`` in one
``os.replace``, so a reader never sees a half-written file. Every task's output goes to
``<logdir>/<task>.log``; a table of wall and CPU seconds per task ends the run. The output
does not depend on N (``tests/test_gen_fixtures.py``; PROGRESS.md loop0002 iteration 4).

``--compare DIR`` then compares every regenerated ``.mat`` with ``DIR/<name>.mat`` by
content (:func:`compare_fixture`: loaded arrays, not bytes; the header has a timestamp),
skipping the fields that hold wall-clock times (:data:`VOLATILE`) and exits 1 on any
difference.

Each ``octave-cli`` runs one BLAS/OpenMP thread (``formdiscovery.threads.PIN_ENV``), except
for the fixtures in ``tests/conftest.py`` ``BLAS_DEFAULT_FIXTURES`` (ANOMALIES A19).

Octave is found as in ``tests/conftest.py`` (``$OCTAVE_EXECUTABLE``, the ``fd`` env, PATH).
"""

import argparse
import errno
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tests.conftest import (  # noqa: E402
    FIXTURES_DIR,
    MATLAB_DIR,
    OCTAVE_TESTS_DIR,
    _configure_octave_env,
    find_octave,
    fixture_env,
)
from legacy.tools.mat_compare import DEFAULT_IGNORE, compare_mat  # noqa: E402

DEFAULT_LOGDIR = REPO_ROOT / "build" / "gen_fixtures"

# fixture -> fixtures its script loads from tests/fixtures (checked against the scripts
# by tests/test_gen_fixtures.py)
DEPENDS = {
    "glslow": ("dataprob", "dpmiss"),
    "graphlike": ("dataprob", "dpmiss"),
    "perf": ("paperlevel",),
}

# runmodel runs in fx_paperlevel.m (one task each)
PAPERLEVEL_JOBS = 45

# rough serial seconds (loop0002 iteration 1), only to start the long tasks first
EXPECTED_SECONDS = {
    "gibbs": 256, "spr": 209, "dpmiss": 69, "swap": 61, "perf": 60, "runmodel": 50,
    "simplify": 45, "search": 45, "glslow": 45, "structurefit": 40, "masterrun": 40,
}

# fields holding wall-clock times or timing-driven repeat counts, per fixture (on top of
# mat_compare.DEFAULT_IGNORE, run records' ``seconds``)
VOLATILE = {
    "perf": ("t_fast", "n_fast", "t_slow", "n_slow", "t_dp", "n_dp", "total", "ev"),
    "paperlevel": ("secs",),
}
# perf's sf.ev rows are [kind, sfcall, t, nfast, tfast, nslow, tslow]: the counts are kept
PERF_EV_COUNTS = (0, 1, 3, 5)
# Octave temporary directories (tempname) inside strings, e.g. rng.mat's error messages
_TEMPDIR = re.compile(r"/tmp/oct-[A-Za-z0-9]{6}")


def fixture_scripts():
    """Map fixture name -> script path for every ``legacy/tests_octave/fx_*.m``."""
    return {p.stem[3:]: p for p in sorted(OCTAVE_TESTS_DIR.glob("fx_*.m"))}


def _octstr(path):
    return "'" + str(path).replace("'", "''") + "'"


def _run_octave(exe, name, call, logfile):
    """Run ``call`` in a fresh ``octave-cli`` with ``fixture_env(name)``, stdout and stderr
    to ``logfile``. Returns (ok, wall seconds, CPU seconds of the Octave process)."""
    cmd = f"addpath({_octstr(MATLAB_DIR)}); addpath({_octstr(OCTAVE_TESTS_DIR)}); {call}"
    t0 = time.time()
    with open(logfile, "w") as log:
        log.write(f"# {cmd}\n")
        log.flush()
        p = subprocess.Popen(
            [exe, "--no-gui", "--quiet", "--no-window-system", "--eval", cmd],
            cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=fixture_env(name),
        )
        _, status, ru = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        dt = time.time() - t0
        log.write(f"\n# exit {p.returncode}, {dt:.1f} s wall, "
                  f"{ru.ru_utime + ru.ru_stime:.1f} s CPU\n")
    return p.returncode == 0, dt, ru.ru_utime + ru.ru_stime


def _publish(tmpfile, outfile):
    """Move ``tmpfile`` to ``outfile`` atomically, also when ``outfile`` is on another
    file system than the temporary directory (copy next to it first, then rename)."""
    Path(outfile).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(tmpfile, outfile)
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
        part = f"{outfile}.part"
        shutil.copyfile(tmpfile, part)
        os.replace(part, outfile)
        os.unlink(tmpfile)


def run_one(exe, name, script, outdir, logfile=None):
    """Run ``script`` in a fresh ``octave-cli`` with ``fixture_env(name)``, writing
    ``<outdir>/<name>.mat``."""
    outfile = Path(outdir) / f"{name}.mat"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / f"{name}.mat"
        log = Path(logfile) if logfile else Path(tmp) / f"{name}.log"
        ok, dt, _ = _run_octave(exe, name, f"{script.stem}({_octstr(stage)});", log)
        ok = ok and stage.is_file()
        if not ok:
            sys.stderr.write(f"FAILED {name} ({dt:.1f} s)\n{log.read_text()}\n")
            return False
        _publish(stage, outfile)
    print(f"wrote {outfile.relative_to(REPO_ROOT) if outfile.is_relative_to(REPO_ROOT) else outfile}"
          f" ({dt:.1f} s)")
    return True


def _paperlevel_expected():
    """Seconds per paperlevel job, from the committed fixture's ``secs`` (default 100)."""
    try:
        import scipy.io
        runs = scipy.io.loadmat(FIXTURES_DIR / "paperlevel.mat", squeeze_me=True)["runs"]
        return {int(r["job"]): float(r["secs"]) for r in runs}
    except Exception:
        return {}


def plan_tasks(names, scripts, outdir, stage):
    """Task list for ``names``: dicts with key, fixture name, Octave call, the file it
    writes in ``stage``, the file it publishes (or None), deps (task keys), expected s."""
    tasks = []
    for name in names:
        out = Path(outdir) / f"{name}.mat"
        if name == "paperlevel":
            secs = _paperlevel_expected()
            parts = []
            for j in range(1, PAPERLEVEL_JOBS + 1):
                part = Path(stage) / f"paperlevel_part{j:02d}.mat"
                parts.append(part)
                tasks.append(dict(key=f"paperlevel_job{j:02d}", name=name,
                                  call=f"fx_paperlevel({_octstr(part)}, {j});",
                                  stage=part, out=None, deps=(),
                                  expected=secs.get(j, 100.0)))
            merged = Path(stage) / "paperlevel.mat"
            cell = "{" + ", ".join(_octstr(p) for p in parts) + "}"
            tasks.append(dict(key="paperlevel", name=name,
                              call=f"paperlevel_merge({_octstr(merged)}, {cell});",
                              stage=merged, out=out,
                              deps=tuple(f"paperlevel_job{j:02d}"
                                         for j in range(1, PAPERLEVEL_JOBS + 1)),
                              expected=1.0))
        else:
            st = Path(stage) / f"{name}.mat"
            tasks.append(dict(key=name, name=name,
                              call=f"{scripts[name].stem}({_octstr(st)});",
                              stage=st, out=out,
                              deps=tuple(d for d in DEPENDS.get(name, ()) if d in names),
                              expected=float(EXPECTED_SECONDS.get(name, 10))))
    return tasks


def run_tasks(exe, tasks, jobs, logdir):
    """Run ``tasks`` with up to ``jobs`` ``octave-cli`` at once, each once its deps have
    succeeded, longest expected first. Returns {key: (status, wall s, CPU s)}."""
    Path(logdir).mkdir(parents=True, exist_ok=True)
    by_key = {t["key"]: t for t in tasks}
    result = {}
    lock = threading.Lock()

    def run(t):
        ok, dt, cpu = _run_octave(exe, t["name"], t["call"], Path(logdir) / f"{t['key']}.log")
        ok = ok and t["stage"].is_file()
        if ok and t["out"] is not None:
            _publish(t["stage"], t["out"])
        with lock:
            print(f"{'ok' if ok else 'FAILED':6s} {t['key']:22s} {dt:7.1f} s", flush=True)
        return ok, dt, cpu

    pending = sorted(tasks, key=lambda t: -t["expected"])
    running = {}
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        while pending or running:
            for t in list(pending):
                states = [result.get(d, (None,))[0] for d in t["deps"]]
                if any(s in ("failed", "skipped") for s in states):
                    pending.remove(t)
                    result[t["key"]] = ("skipped", 0.0, 0.0)
                elif all(s == "ok" for s in states) and len(running) < max(1, jobs):
                    pending.remove(t)
                    running[ex.submit(run, t)] = t["key"]
            if not running:
                continue
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for f in done:
                ok, dt, cpu = f.result()
                result[running.pop(f)] = ("ok" if ok else "failed", dt, cpu)
    assert set(result) == set(by_key)
    return result


def summary_table(result, wall, cpu, jobs):
    """Text table of the tasks (longest first) and the totals."""
    lines = [f"{'task':22s} {'status':8s} {'wall s':>8s} {'CPU s':>8s}"]
    for key, (status, dt, c) in sorted(result.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"{key:22s} {status:8s} {dt:8.1f} {c:8.1f}")
    busy = sum(dt for _, dt, _ in result.values())
    lines.append(f"{len(result)} tasks, --jobs {jobs}: {wall:.1f} s wall, {cpu:.1f} s CPU "
                 f"(Octave), {busy:.1f} s summed task wall")
    return "\n".join(lines)


def _perf_ev_counts(f):
    """perf's ``sf.ev`` count columns (:data:`PERF_EV_COUNTS`), one array per run."""
    import scipy.io
    sf = scipy.io.loadmat(f)["sf"]
    return [rec["ev"][0, 0][:, PERF_EV_COUNTS] for rec in sf.ravel()]


def _normalize(x):
    return _TEMPDIR.sub("/tmp/oct-XXXXXX", x) if isinstance(x, str) else x


def compare_fixture(name, fa, fb):
    """Differences between two copies of fixture ``name`` (empty: same content). Loaded
    arrays are compared to all digits (``legacy/tools/mat_compare.py``), without the
    :data:`VOLATILE` fields and with Octave temporary directory names masked."""
    import numpy as np
    out = compare_mat(fa, fb, ignore=DEFAULT_IGNORE + VOLATILE.get(name, ()),
                      normalize=_normalize)
    if name == "perf":
        ea, eb = _perf_ev_counts(fa), _perf_ev_counts(fb)
        if len(ea) != len(eb) or not all(
                a.shape == b.shape and np.array_equal(a, b) for a, b in zip(ea, eb)):
            out.append("sf.ev: count columns differ")
    return out


def compare_outputs(names, outdir, refdir):
    """{name: differences} for every fixture in ``names`` (missing files are differences)."""
    diffs = {}
    for name in names:
        fa, fb = Path(outdir) / f"{name}.mat", Path(refdir) / f"{name}.mat"
        if not fa.is_file() or not fb.is_file():
            diffs[name] = [f"missing: {f}" for f in (fa, fb) if not f.is_file()]
        else:
            diffs[name] = compare_fixture(name, fa, fb)
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="fixture names (default: all)")
    ap.add_argument("--list", action="store_true", help="list fixture scripts and exit")
    ap.add_argument("--outdir", default=str(FIXTURES_DIR), help="output directory")
    ap.add_argument("--jobs", "-j", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="octave-cli processes at once (default: cores/2)")
    ap.add_argument("--logdir", default=str(DEFAULT_LOGDIR),
                    help="per-task logs (default: build/gen_fixtures)")
    ap.add_argument("--compare", metavar="DIR", default=None,
                    help="compare each regenerated fixture with DIR/<name>.mat")
    args = ap.parse_args(argv)

    scripts = fixture_scripts()
    if args.list:
        for name, p in scripts.items():
            print(f"{name:24s} {p.relative_to(REPO_ROOT)}")
        return 0
    unknown = [n for n in args.names if n not in scripts]
    if unknown:
        ap.error(f"no legacy/tests_octave/fx_<name>.m for: {', '.join(unknown)}")
    exe = find_octave()
    if exe is None:
        ap.error("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
    _configure_octave_env(exe)
    names = list(args.names or scripts)
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="gen_fixtures_") as stage:
        result = run_tasks(exe, plan_tasks(names, scripts, args.outdir, stage),
                           args.jobs, args.logdir)
    wall = time.time() - t0
    cpu1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (cpu1.ru_utime - cpu0.ru_utime) + (cpu1.ru_stime - cpu0.ru_stime)
    print(summary_table(result, wall, cpu, args.jobs))
    print(f"logs in {args.logdir}")
    failed = [k for k, (s, _, _) in result.items() if s != "ok"]
    for k in failed:
        sys.stderr.write(f"{result[k][0].upper()} {k}: see {Path(args.logdir) / (k + '.log')}\n")
    rc = 1 if failed else 0
    if args.compare:
        diffs = compare_outputs([n for n in names if n not in failed], args.outdir,
                                args.compare)
        for n, d in diffs.items():
            for line in d:
                print(f"{n}: {line}")
        ndiff = sum(1 for d in diffs.values() if d)
        print(f"{len(diffs)} fixtures compared with {args.compare}: "
              f"{len(diffs) - ndiff} identical, {ndiff} differ")
        rc = rc or (1 if ndiff else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
