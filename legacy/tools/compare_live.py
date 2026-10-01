#!/usr/bin/env python
"""Run Octave and Python side by side on (structure, dataset, seed) triples and compare
the results (loop0002 item 06; PLAN.md §7.1).

For each triple, one pool worker:

1. runs ``run_baseline(kind, sind, dind, rundir, seed)`` in its own ``octave-cli`` with the
   ``randperm`` shim (``legacy/matlab/octave_shims``) in pass-through mode, logging every draw
   (``randperm_config('', log)``). ``rand('state', seed)`` precedes the run, as
   ``masterrun.m:63`` does with ``rind``; ``kind`` is ``'rel'`` (``reloutsideinit =
   'overd'``) for relational data, else ``'feat'``;
2. runs Python's ``run.runmodel`` on the same pair with ``ps`` as ``run_baseline`` sets it,
   replaying Octave's draws (:class:`ReplayThenNumpy`). There are no oracles: Python uses
   its own scaled data, scipy's optimizer and its own tie breaking. If a decision differs
   from Octave's, the draws stop matching; the provider then goes on with
   ``NumpyPermutations(seed)`` and the row says where the replay ``diverged``.

Up to ``--jobs`` workers run at once, so Octave and Python runs of different triples
overlap. Every worker and every ``octave-cli`` is pinned to one BLAS/OpenMP thread. The
rows do not depend on ``--jobs`` (``legacy/tests/test_compare_live.py``), apart from the times.

The table has, per triple: Octave and Python final ll, relative difference, ARI of the
two partitions (``tests/helpers.py::adjusted_rand_index``), cluster counts (occupied
clusters and cluster nodes), the draws replayed, the wall time of each side, and the
§7.1 verdict: ``ok`` when the score is within 1e-3 rel, the cluster count is Octave's
and, for a full replay, ARI = 1 (a diverged replay needs ARI >= 0.9; PLAN §7.1 asks that
of the mean over 3 seeds). With seed 1, Octave's ll must also equal the committed baseline
(``tests/test_baseline.py``, ``tests/test_baseline_rel.py``) exactly.

Usage::

    python legacy/tools/compare_live.py                         # 9 feature + 54 relational pairs
    python legacy/tools/compare_live.py --set feat --jobs 9
    python legacy/tools/compare_live.py --pairs chain:demo_chain_feat:2 dirring:4
    python legacy/tools/compare_live.py --json out.json

A pair is ``structure:dataset[:seed]`` (names or 1-based ``ps`` indices, seed default
``--seed``). Per-triple Octave logs go to ``<logdir>/<key>.log``. Exits 1 if a row fails.
"""

import argparse
import json
import multiprocessing
import os
import resource
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from formdiscovery.rng import NumpyPermutations, check_perm, read_queue  # noqa: E402
from tests.conftest import LEGACY_DIR, SHIM_DIR, _configure_octave_env, find_octave  # noqa: E402
from legacy.tools.gen_baselines import GRIDS, serial_pairs  # noqa: E402
from legacy.tools.gen_fixtures import _octstr, _run_octave  # noqa: E402

DEFAULT_LOGDIR = REPO_ROOT / "build" / "compare_live"
E2E_RTOL = 1e-3  # PLAN §7.1
ARI_DIVERGED = 0.9
_ADDPATH = (f"addpath({_octstr(LEGACY_DIR / 'matlab')}); addpath({_octstr(SHIM_DIR)}); "
            "warning('off', 'Octave:shadowed-function'); ")


class ReplayThenNumpy:
    """Replay ``perms`` (Octave's draws); at the first call that does not fit (queue
    exhausted or wrong length), go on with ``NumpyPermutations(seed)``. ``diverged`` is
    the 0-based call number where that happened (None while the replay holds)."""

    def __init__(self, perms, seed):
        self.queue = [check_perm(p) for p in perms]
        self.seed = seed
        self.consumed = 0
        self.diverged = None
        self.fallback = None

    def randperm(self, n):
        if self.diverged is None:
            if self.consumed < len(self.queue) and self.queue[self.consumed].size == int(n):
                self.consumed += 1
                return self.queue[self.consumed - 1].copy()
            self.diverged = self.consumed
            self.fallback = NumpyPermutations(self.seed)
        return self.fallback.randperm(n)

    def status(self):
        """``full`` (every draw replayed, none left over) or ``diverged@k``."""
        if self.diverged is None and self.consumed == len(self.queue):
            return "full"
        return f"diverged@{self.consumed if self.diverged is None else self.diverged}"


def _ps():
    from formdiscovery.params import Params
    return Params.default()


def parse_pair(text, seed=1, ps=None):
    """``structure:dataset[:seed]`` (names or 1-based indices) -> (sind, dind, seed),
    1-based."""
    ps = ps or _ps()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"bad pair {text!r} (want structure:dataset[:seed])")

    def index(v, names, what):
        if v.isdigit():
            i = int(v)
            if not 1 <= i <= len(names):
                raise ValueError(f"{what} index {i} out of range 1..{len(names)}")
            return i
        if v not in names:
            raise ValueError(f"unknown {what} {v!r}")
        return names.index(v) + 1

    s = index(parts[0], ps.structures, "structure")
    d = index(parts[1], ps.data, "dataset")
    return s, d, int(parts[2]) if len(parts) == 3 else int(seed)


def default_triples(which="all", seed=1):
    """run_baseline's grids in its run order: the 9 feature pairs, then the 54
    relational ones."""
    kinds = ("feat", "rel") if which == "all" else (which,)
    return [(s, d, seed) for k in kinds for s, d in serial_pairs(*GRIDS[k])]


def data_kind(dind):
    """``'rel'`` for relational data (``setrunps``), else ``'feat'``."""
    from formdiscovery.io import load_dataset
    ps = _ps()
    data = load_dataset(ps.data[dind - 1])
    return "rel" if isinstance(data, dict) and "type" in data else "feat"


def baseline_ll(sind, dind):
    """The committed Octave baseline score of a pair (seed 1), or None."""
    from tests.test_baseline import EXPECTED_LL as FEAT_LL
    from tests.test_baseline_rel import EXPECTED_LL as REL_LL
    ps = _ps()
    key = (ps.structures[sind - 1], ps.data[dind - 1])
    return FEAT_LL.get(key, REL_LL.get(key))


def _key(sind, dind, seed):
    return f"s{sind:02d}_d{dind:02d}_r{seed}"


def run_octave(exe, sind, dind, seed, workdir, logfile):
    """Octave side: returns (ll or None, final graph or None, draws, wall s, CPU s, error)."""
    import scipy.io
    from formdiscovery.io import graph_from_mat
    kind = data_kind(dind)
    rundir = Path(workdir) / "octave"
    rundir.mkdir(parents=True, exist_ok=True)  # see ANOMALIES A20
    log = Path(workdir) / "randperm_log.txt"
    call = (_ADDPATH + f"randperm_config('', {_octstr(log)}); "
            f"run_baseline('{kind}', {sind}, {dind}, {_octstr(rundir)}, {seed}); "
            "randperm_config();")
    ok, wall, cpu = _run_octave(exe, "baseline", call, logfile)
    tfile = rundir / "timings.mat"
    if not ok or not tfile.is_file():
        return None, None, [], wall, cpu, f"octave-cli failed (see {logfile})"
    t = scipy.io.loadmat(tfile, simplify_cells=True)["timings"]
    if np.size(t["error"]):
        return None, None, [], wall, cpu, f"Octave crashed: {t['error']}"
    ll = float(t["ll"])
    res = scipy.io.loadmat(rundir / "resultsdemo.mat", mat_dtype=True, simplify_cells=True)
    # structure{sind, dind} is the only non-empty cell (one run in this directory)
    cells = [c for c in np.ravel(np.asarray(res["structure"], dtype=object))
             if isinstance(c, dict) or hasattr(c, "_fieldnames")]
    if len(cells) != 1:
        return None, None, [], wall, cpu, f"resultsdemo.mat holds {len(cells)} graphs"
    g = graph_from_mat(cells[0])
    return ll, g, read_queue(log), wall, cpu, None


def run_python(sind, dind, seed, perms):
    """Python side: ``runmodel`` with Octave's draws replayed. Returns (ll, graph, rng,
    wall s, CPU s)."""
    from formdiscovery.params import Params
    from formdiscovery.run import runmodel
    ps = Params.default()
    if data_kind(dind) == "rel":
        ps.reloutsideinit = "overd"
    rng = ReplayThenNumpy(perms, seed)
    t0, c0 = time.perf_counter(), time.process_time()
    ll, g, _, _, _ = runmodel(ps, sind - 1, dind - 1, 1, rng=rng)
    return float(ll), g, rng, time.perf_counter() - t0, time.process_time() - c0


def compare_one(exe, sind, dind, seed, logdir):
    """One triple, Octave then Python. Returns a row dict (JSON-serialisable)."""
    from formdiscovery.run import graph_summary
    from tests.helpers import adjusted_rand_index
    ps = _ps()
    key = _key(sind, dind, seed)
    row = dict(key=key, structure=ps.structures[sind - 1], data=ps.data[dind - 1],
               sind=sind, dind=dind, seed=seed, fail=[])
    with tempfile.TemporaryDirectory(prefix=f"compare_live_{key}_") as tmp:
        oll, og, perms, row["oct_wall"], row["oct_cpu"], err = run_octave(
            exe, sind, dind, seed, tmp, Path(logdir) / f"{key}.log")
    row["draws"] = len(perms)
    if err:
        row["fail"].append(err)
        row["ok"] = False
        return row
    try:
        pll, pg, rng, row["py_wall"], row["py_cpu"] = run_python(sind, dind, seed, perms)
    except Exception as e:  # report it in the table, do not stop the other rows
        row["fail"].append(f"Python failed: {type(e).__name__}: {e}")
        row.update(oct_ll=oll, ok=False)
        return row
    o, p = graph_summary(og), graph_summary(pg)
    row.update(oct_ll=oll, py_ll=pll, rel_diff=abs(pll - oll) / abs(oll),
               ari=float(adjusted_rand_index(p["z"], o["z"])),
               oct_clusters=o["nclusters"], py_clusters=p["nclusters"],
               oct_nodes=o["nnodes"], py_nodes=p["nnodes"], replay=rng.status())
    base = baseline_ll(sind, dind) if seed == 1 else None
    row["baseline_ll"] = base
    if base is not None and oll != base:
        row["fail"].append(f"Octave ll {oll!r} != committed baseline {base!r}")
    if row["rel_diff"] > E2E_RTOL:
        row["fail"].append(f"rel diff {row['rel_diff']:.1e} > {E2E_RTOL:g}")
    if o["nclusters"] != p["nclusters"]:
        row["fail"].append("cluster count")
    need = 1.0 if row["replay"] == "full" else ARI_DIVERGED
    if row["ari"] < need - 1e-12:
        row["fail"].append(f"ARI {row['ari']:.3f} < {need:g}")
    row["ok"] = not row["fail"]
    return row


def _init_worker():
    from formdiscovery.threads import pin_blas_env, pin_process_blas
    pin_blas_env()
    pin_process_blas(1)


def compare(triples, jobs, logdir=DEFAULT_LOGDIR, exe=None, progress=True):
    """Compare every triple with up to ``jobs`` workers. Returns the rows in the order of
    ``triples``."""
    from formdiscovery.threads import pin_blas_env
    if exe is None:
        exe = find_octave()
        if exe is None:
            raise RuntimeError("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
    _configure_octave_env(exe)
    pin_blas_env()
    Path(logdir).mkdir(parents=True, exist_ok=True)
    # longest first: feature runs (optimizer) before relational ones, as listed
    order = sorted(range(len(triples)), key=lambda i: data_kind(triples[i][1]) != "feat")
    rows = [None] * len(triples)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max(1, jobs), mp_context=ctx, initializer=_init_worker) as ex:
        futs = {ex.submit(compare_one, exe, *triples[i], str(logdir)): i for i in order}
        for f in as_completed(futs):
            r = f.result()
            rows[futs[f]] = r
            if progress:
                print(f"{'ok' if r['ok'] else 'FAIL':4s} {r['structure']:22s} {r['data']:24s} "
                      f"seed {r['seed']}  octave {r['oct_wall']:6.1f} s  python "
                      f"{r.get('py_wall', float('nan')):6.1f} s", flush=True)
    return rows


def _f(r, k, fmt):
    return format(r[k], fmt) if r.get(k) is not None else "-"


def format_table(rows):
    """Markdown table of :func:`compare` rows."""
    out = ["| structure | data | seed | Octave ll | Python ll | rel diff | ARI "
           "| clusters O/P | nodes O/P | draws | replay | Octave s | Python s | ok |",
           "|---|---|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|---|"]
    for r in rows:
        cl = (f"{r['oct_clusters']}/{r['py_clusters']}" if "py_clusters" in r else "-")
        nd = (f"{r['oct_nodes']}/{r['py_nodes']}" if "py_nodes" in r else "-")
        out.append(
            f"| {r['structure']} | {r['data']} | {r['seed']} | {_f(r, 'oct_ll', '.6f')} "
            f"| {_f(r, 'py_ll', '.6f')} | {_f(r, 'rel_diff', '.1e')} | {_f(r, 'ari', '.3f')} "
            f"| {cl} | {nd} | {r['draws']} | {r.get('replay', '-')} "
            f"| {_f(r, 'oct_wall', '.1f')} | {_f(r, 'py_wall', '.1f')} "
            f"| {'yes' if r['ok'] else 'FAIL: ' + '; '.join(r['fail'])} |")
    return "\n".join(out)


def stable(row):
    """The part of a row that must not depend on ``--jobs`` (everything but times)."""
    return {k: v for k, v in row.items() if not k.endswith(("_wall", "_cpu"))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pairs", nargs="+", metavar="S:D[:SEED]",
                    help="structure:dataset[:seed] triples (default: --set)")
    ap.add_argument("--set", choices=("all", "feat", "rel"), default="all",
                    help="default triples: run_baseline's grids (default all: 9 + 54)")
    ap.add_argument("--seed", type=int, default=1, help="seed when a pair has none")
    ap.add_argument("--jobs", "-j", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="worker processes at once (default: cores/2)")
    ap.add_argument("--logdir", default=str(DEFAULT_LOGDIR),
                    help="per-triple Octave logs (default: build/compare_live)")
    ap.add_argument("--json", metavar="FILE", help="also write the rows as JSON")
    args = ap.parse_args(argv)
    try:
        triples = ([parse_pair(p, args.seed) for p in args.pairs] if args.pairs
                   else default_triples(args.set, args.seed))
    except ValueError as e:
        ap.error(str(e))
    t0 = time.time()
    rows = compare(triples, args.jobs, args.logdir)
    wall = time.time() - t0
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(format_table(rows))
    nbad = sum(not r["ok"] for r in rows)
    osum = sum(r["oct_wall"] for r in rows)
    psum = sum(r.get("py_wall", 0.0) for r in rows)
    print(f"\n{len(rows) - nbad}/{len(rows)} rows pass (PLAN §7.1). --jobs {args.jobs}: "
          f"{wall:.1f} s wall, {ru.ru_utime + ru.ru_stime:.1f} s CPU (children); summed "
          f"Octave {osum:.1f} s, Python {psum:.1f} s")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1))
    return 0 if nbad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
