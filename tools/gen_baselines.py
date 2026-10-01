#!/usr/bin/env python
"""Regenerate the Octave baselines (``tests/fixtures/baseline/{feat,rel}``) in parallel.

``matlab/run_baseline.m`` runs its (structure, dataset) grid serially in one Octave. This
tool (loop0002 item 04) runs one ``octave-cli`` per pair instead,
``run_baseline(kind, sind, dind, pairdir)``, each writing to its own directory, up to
``--jobs`` at once (longest expected first). A merge then assembles what the serial run
writes:

- ``resultsdemo.mat`` and ``timings.mat``: ``matlab/baseline_merge.m`` replays
  ``run_baseline``'s accumulation over the pairs in the serial run order (structure index
  fastest, then dataset);
- ``results/<struct>out/<data>1/growthhistory*.mat``: each pair's ``results/`` tree, copied
  (the trees do not overlap).

Every run starts with ``rand('state', 1)`` and no state carries from one run to the next,
so the merged output equals the serial one (``--compare``; ``tests/test_gen_baselines.py``;
PROGRESS.md loop0002 iteration 5). The merged output is built in a staging directory next
to ``--outdir`` and swapped in at the end.

Usage::

    python tools/gen_baselines.py --kind feat              # cores/2 octave-cli at once
    python tools/gen_baselines.py --kind rel --jobs 1
    python tools/gen_baselines.py --kind rel --outdir D --compare tests/fixtures/baseline/rel
    python tools/gen_baselines.py --kind feat --struct 2 4 --data 1   # a sub-grid

``--compare DIR`` checks the same file set (all files, not only ``.mat``) and the same
content of every ``.mat`` (``tools/mat_compare.py``: loaded arrays to all digits, without
``timings.seconds``); exits 1 on any difference. Each ``octave-cli`` runs pinned to one
BLAS/OpenMP thread (``fixture_env('baseline')``). Per-pair logs go to
``<logdir>/<kind>/<task>.log``.
"""

import argparse
import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tests.conftest import FIXTURES_DIR, _configure_octave_env, find_octave  # noqa: E402
from tools.gen_fixtures import _octstr, run_tasks, summary_table  # noqa: E402
from tools.mat_compare import compare_dirs  # noqa: E402

DEFAULT_LOGDIR = REPO_ROOT / "build" / "gen_baselines"
# run_baseline.m and baseline_merge.m
_ADDPATH = f"addpath({_octstr(REPO_ROOT / 'matlab')}); "

# run_baseline.m's default grids (ps.structures, ps.data indices, 1-based)
GRIDS = {
    "feat": ([2, 4, 6], [1, 2, 3]),
    "rel": ([1, 9, 10, 11, 12, 13, 3] + list(range(14, 25)), [4, 5, 6]),
}


def serial_pairs(structs, datas):
    """(sind, dind) in ``run_baseline``'s order: ``sindpair(:)`` of
    ``repmat(thisstruct', 1, nd)``, i.e. every structure for dataset 1, then dataset 2..."""
    return [(s, d) for d in datas for s in structs]


def _expected_seconds(refdir):
    """Seconds per run, in run order, from a committed ``timings.mat`` (or [])."""
    try:
        import scipy.io
        t = scipy.io.loadmat(Path(refdir) / "timings.mat", squeeze_me=True)["timings"]
        return [float(r["seconds"]) for r in t.ravel()]
    except Exception:
        return []


def plan_tasks(kind, pairs, stage, merged):
    """Pair tasks plus a ``merge`` task (deps: all pairs), in :func:`gen_fixtures.run_tasks`'
    format. Returns (tasks, pair directories)."""
    secs = _expected_seconds(FIXTURES_DIR / "baseline" / kind)
    if len(secs) != len(pairs):
        secs = [10.0] * len(pairs)
    tasks, dirs = [], []
    for (s, d), sec in zip(pairs, secs):
        key = f"{kind}_s{s:02d}_d{d}"
        pdir = Path(stage) / "pairs" / key
        # made here: Octave's mkdir of a nested path fails ("File exists") when another
        # octave-cli creates the shared parent at the same time (ANOMALIES A20)
        pdir.mkdir(parents=True, exist_ok=True)
        dirs.append(pdir)
        tasks.append(dict(key=key, name="baseline",
                          call=_ADDPATH + f"run_baseline('{kind}', {s}, {d}, {_octstr(pdir)});",
                          stage=pdir / "timings.mat", out=None, deps=(), expected=sec))
    mat = "[" + "; ".join(f"{s} {d}" for s, d in pairs) + "]"
    cell = "{" + ", ".join(_octstr(p) for p in dirs) + "}"
    tasks.append(dict(key=f"{kind}_merge", name="baseline",
                      call=_ADDPATH + f"baseline_merge({_octstr(merged)}, {mat}, {cell});",
                      stage=Path(merged) / "timings.mat", out=None,
                      deps=tuple(t["key"] for t in tasks), expected=1.0))
    return tasks, dirs


def copy_results(pairdirs, merged):
    """Copy every pair's ``results/`` tree into ``merged/results`` (no file twice)."""
    dst = Path(merged) / "results"
    for pdir in pairdirs:
        src = Path(pdir) / "results"
        if not src.is_dir():
            continue
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            out = dst / f.relative_to(src)
            if out.exists():
                raise RuntimeError(f"{out} written by two pairs")
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)


def _swap_in(merged, outdir):
    """Replace ``outdir`` by ``merged`` (same parent directory, so both are renames)."""
    outdir = Path(outdir)
    old = None
    if outdir.exists():
        old = outdir.with_name(outdir.name + f".old{os.getpid()}")
        os.replace(outdir, old)
    os.replace(merged, outdir)
    if old is not None:
        shutil.rmtree(old)


def file_set(d):
    d = Path(d)
    return {p.relative_to(d) for p in d.rglob("*") if p.is_file()}


def compare_baselines(da, db):
    """Differences between two baseline directories: file sets, then ``.mat`` content."""
    fa, fb = file_set(da), file_set(db)
    out = [f"only in {da}: {p}" for p in sorted(fa - fb)]
    out += [f"only in {db}: {p}" for p in sorted(fb - fa)]
    return out + compare_dirs(da, db)


def generate(kind, outdir, jobs, logdir, structs=None, datas=None, exe=None):
    """Run the grid with ``jobs`` Octave processes and write the merged baseline to
    ``outdir``. Returns (ok, {task: (status, wall s, CPU s)})."""
    ds, dd = GRIDS[kind]
    pairs = serial_pairs(structs or ds, datas or dd)
    if exe is None:
        exe = find_octave()
        if exe is None:
            raise RuntimeError("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
        _configure_octave_env(exe)
    outdir = Path(outdir).resolve()
    outdir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".gen_baselines_{kind}_",
                                     dir=outdir.parent) as stage:
        merged = Path(stage) / "merged"
        tasks, dirs = plan_tasks(kind, pairs, stage, merged)
        result = run_tasks(exe, tasks, jobs, Path(logdir) / kind)
        ok = all(s == "ok" for s, _, _ in result.values())
        if ok:
            copy_results(dirs, merged)
            _swap_in(merged, outdir)
    return ok, result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--kind", choices=sorted(GRIDS), required=True)
    ap.add_argument("--outdir", default=None,
                    help="output directory (default tests/fixtures/baseline/<kind>)")
    ap.add_argument("--jobs", "-j", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="octave-cli processes at once (default: cores/2)")
    ap.add_argument("--struct", type=int, nargs="+", default=None,
                    help="ps.structures indices (default: run_baseline's grid)")
    ap.add_argument("--data", type=int, nargs="+", default=None,
                    help="ps.data indices (default: run_baseline's grid)")
    ap.add_argument("--logdir", default=str(DEFAULT_LOGDIR),
                    help="per-pair logs (default: build/gen_baselines)")
    ap.add_argument("--compare", metavar="DIR", default=None,
                    help="compare the merged output with DIR")
    args = ap.parse_args(argv)
    outdir = Path(args.outdir or FIXTURES_DIR / "baseline" / args.kind)
    cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.time()
    ok, result = generate(args.kind, outdir, args.jobs, args.logdir, args.struct, args.data)
    wall = time.time() - t0
    cpu1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (cpu1.ru_utime - cpu0.ru_utime) + (cpu1.ru_stime - cpu0.ru_stime)
    print(summary_table(result, wall, cpu, args.jobs))
    print(f"logs in {Path(args.logdir) / args.kind}")
    if not ok:
        for k, (s, _, _) in result.items():
            if s != "ok":
                sys.stderr.write(f"{s.upper()} {k}\n")
        sys.stderr.write(f"not written: {outdir}\n")
        return 1
    print(f"wrote {outdir}")
    if args.compare:
        diffs = compare_baselines(outdir, args.compare)
        for line in diffs:
            print(line)
        n = len(file_set(outdir))
        print(f"{n} files compared with {args.compare}: {len(diffs)} differences")
        return 1 if diffs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
