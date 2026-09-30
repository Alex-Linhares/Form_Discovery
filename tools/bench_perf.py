#!/usr/bin/env python
"""Performance budget (item 35, PLAN.md §7.4): Octave vs Python time per ``graph_like``
call and per ``structurefit`` depth.

The Octave side is ``tests/fixtures/perf.mat`` (``tests/octave/fx_perf.m``; its docstring
lists the benchmark graphs and runs). This tool times the same computations in Python,
checks that they return Octave's values, and prints Markdown tables:

- ``gl``: per call, the median over repeated calls (:func:`timeit`, the same rule as
  ``fx_perf.m``'s ``timeit``) of ``graph_like`` in fast mode, in slow mode (optimiser +
  Laplace, feature data) and of ``dataprobwsig`` with its gradient at the fast-mode start
  point. Checks: fast score, ``dataprobwsig`` value and gradient rtol ``FAST_RTOL``; slow
  score rel ``SLOW_RTOL`` (``tools/compare_runs.py``'s tolerances);
- ``sf``: whole ``runmodel`` runs with identity permutations, with the same spies on
  ``structurefit``, ``choose_node_split`` and ``graph_like`` as the fixture
  (:func:`spied_runmodel`), summarised per run and per ``structurefit`` depth
  (:func:`depth_rows`). The search can take a different path from Octave's where slow
  scores (optimiser-dependent) decide a comparison, so the depth counts and final scores
  are reported side by side rather than required to match.

Usage::

    python tools/bench_perf.py                  # both sections, committed fixture
    python tools/bench_perf.py --sections gl    # graph_like only (about 1 min)
    python tools/bench_perf.py --live           # regenerate the Octave side first
    python tools/bench_perf.py --profile        # cProfile of dataprobwsig on the gl graphs
    python tools/bench_perf.py --json out.json  # also write the raw numbers

Timings depend on the machine and its load: compare Octave and Python from the same
run of this tool (``--live``), or on the machine that generated the fixture.
"""

import argparse
import cProfile
import io
import json
import pstats
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from formdiscovery import likelihood, likelihood_feat, run, search  # noqa: E402
from formdiscovery.io import graph_from_mat, load_fixture  # noqa: E402
from formdiscovery.rng import IdentityPermutations  # noqa: E402
from formdiscovery.threads import blas_threads  # noqa: E402
from formdiscovery.weights import mat2vec  # noqa: E402
from tools.compare_runs import FAST_RTOL, SLOW_RTOL, prep  # noqa: E402

SHOW_FLAGS = ("showtruegraph", "showinferredgraph", "showbestsplit", "showpreclean",
              "showpostclean")
EV_START, EV_DEPTH, EV_END = 1, 2, 3


def timeit(f, mint, minn, maxn=200):
    """Median seconds per call of ``f()`` over ``n`` calls: at least ``minn`` calls and
    ``mint`` seconds in total, at most ``maxn`` calls (``fx_perf.m``'s ``timeit``).
    Returns ``(t, n, value)`` with ``f``'s value on the last call."""
    ts = []
    tot = time.perf_counter()
    while len(ts) < minn or (time.perf_counter() - tot < mint and len(ts) < maxn):
        t1 = time.perf_counter()
        v = f()
        ts.append(time.perf_counter() - t1)
    return float(np.median(ts)), len(ts), v


def _num(v):
    return float(np.asarray(v).ravel()[0]) if np.size(v) else None


def _rel(a, b):
    return abs(a - b) / max(abs(b), np.finfo(float).tiny)


def gl_inputs(r, preps):
    """``(data, graph, ps)`` for a ``gl`` record: the data after runmodel's
    preprocessing, the graph and the untied ``ps`` with ``ps.runps.structname``."""
    name = str(r["data"])
    if name not in preps:
        preps[name] = prep(name)
    data, ps = preps[name]
    ps = ps.replace(fixedall=0, fixedinternal=0, fixedexternal=0, prodtied=0)
    ps.runps.structname = str(r["structure"])
    return data, graph_from_mat(r["graph"]), ps


def dp_inputs(data, g, ps):
    """``dataprobwsig``'s inputs in fast mode (``graph_like_conn.m:6-16``,
    ``graph_like.m:7-10``): ``(Xinit, d, gL, ps)`` with the log-weight graph ``gL``."""
    gL = g.copy()
    Wsym = np.array(np.atleast_2d(gL.Wsym), dtype=float)
    mask = np.atleast_2d(np.asarray(gL.adjsym)) > 0
    Wsym[mask] = np.log(Wsym[mask])
    gL.Wsym = Wsym
    gL.sigma = np.log(float(gL.sigma))
    pf = ps.replace(fast=1)
    Xinit = np.concatenate([[gL.sigma], mat2vec(gL.Wsym, gL, pf)])
    d = np.asarray(data)[np.asarray(g.z).ravel() >= 0, :]
    return Xinit, d, gL, pf


def bench_gl(fx):
    """Time and check every ``gl`` record. Returns one row dict per graph."""
    rows, preps = [], {}
    for r in fx["gl"]:
        data, g, ps = gl_inputs(r, preps)
        row = {"graph": f"{r['structure']} x {r['data']}", "group": str(r["group"]),
               "nodes": int(_num(r["nnodes"])), "fail": []}
        pf = ps.replace(fast=1)
        t, n, v = timeit(lambda: likelihood.graph_like(data, g, pf)[0], 0.5, 3)
        row.update(oct_fast=_num(r["t_fast"]), py_fast=t, n_fast=n)
        if _rel(v, _num(r["fast"])) > FAST_RTOL:
            row["fail"].append(f"fast score rel {_rel(v, _num(r['fast'])):.1e}")
        if str(r["type"]) != "rel":
            ps0 = ps.replace(fast=0)
            t, n, v = timeit(lambda: likelihood.graph_like(data, g, ps0)[0], 1.0, 2)
            row.update(oct_slow=_num(r["t_slow"]), py_slow=t, n_slow=n,
                       slow_rel=_rel(v, _num(r["slow"])))
            if row["slow_rel"] > SLOW_RTOL:
                row["fail"].append(f"slow score rel {row['slow_rel']:.1e}")
            Xinit, d, gL, pf = dp_inputs(data, g, ps)
            if not np.allclose(Xinit, np.ravel(r["Xinit"]), rtol=FAST_RTOL, atol=0):
                row["fail"].append("Xinit")
            t, n, (ll, grad) = timeit(
                lambda: likelihood_feat.dataprobwsig(Xinit, d, gL, pf, nargout=2), 0.5, 3)
            row.update(oct_dp=_num(r["t_dp"]), py_dp=t, n_dp=n)
            if _rel(ll, _num(r["dp_ll"])) > FAST_RTOL:
                row["fail"].append("dataprobwsig value")
            og = np.ravel(r["dp_g"])
            if not np.allclose(grad, og, rtol=FAST_RTOL, atol=FAST_RTOL * np.abs(og).max()):
                row["fail"].append("dataprobwsig gradient")
        rows.append(row)
    return rows


def spied_runmodel(sind, dind, speed, kind="feat"):
    """``fx_perf.m``'s spied run in Python: ``runmodel(ps, sind, dind, 1)`` (0-based
    indices) with identity permutations, the headless ``ps`` of ``run_baseline.m`` at
    ``ps.speed = speed`` (relational: ``reloutsideinit = 'overd'``), and spies on
    ``search.structurefit``, ``search.choose_node_split`` and ``likelihood.graph_like``
    logging the fixture's events. Returns a dict with ``ll``, ``total`` (s), ``ev``
    (``n x 7``: kind, structurefit call, t, nfast, tfast, nslow, tslow) and ``lls`` (each
    structurefit call's ``bestgraphlls``)."""
    ps = run.masterrun_ps() if kind == "rel" else run.Params.default()
    for f in SHOW_FLAGS:
        setattr(ps, f, 0)
    ps.speed = speed
    st = {"nsf": 0, "nfast": 0, "tfast": 0.0, "nslow": 0, "tslow": 0.0, "last": None}
    ev, lls = [], []
    t0 = time.perf_counter()

    def event(k, i):
        ev.append([k, i, time.perf_counter() - t0, st["nfast"], st["tfast"], st["nslow"],
                   st["tslow"]])

    real_sf, real_cns, real_gl = (search.structurefit, search.choose_node_split,
                                  likelihood.graph_like)

    def sf_spy(data, ps, graph=None, savefile=None, **kw):
        st["nsf"] += 1
        k = st["nsf"]
        st["last"] = None
        event(EV_START, k)
        out = real_sf(data, ps, graph, savefile, **kw)
        event(EV_END, k)
        lls.append(np.asarray(out[2], dtype=float))
        return out

    def cns_spy(graph, *a, **kw):
        if st["last"] is not graph:
            event(EV_DEPTH, st["nsf"])
            st["last"] = graph
        return real_cns(graph, *a, **kw)

    def gl_spy(data, graph, ps):
        t1 = time.perf_counter()
        out = real_gl(data, graph, ps)
        dt = time.perf_counter() - t1
        if getattr(ps, "fast", None) == 1:
            st["nfast"] += 1
            st["tfast"] += dt
        else:
            st["nslow"] += 1
            st["tslow"] += dt
        return out

    search.structurefit, search.choose_node_split, likelihood.graph_like = (
        sf_spy, cns_spy, gl_spy)
    try:
        ll = run.runmodel(ps, sind, dind, 1, rng=IdentityPermutations())[0]
    finally:
        search.structurefit, search.choose_node_split, likelihood.graph_like = (
            real_sf, real_cns, real_gl)
    return {"ll": float(ll), "total": time.perf_counter() - t0,
            "ev": np.asarray(ev, dtype=float).reshape(-1, 7), "lls": lls}


def depth_rows(ev):
    """Per-depth rows from an event log: ``(sfcall, depth, secs, nfast, tfast, nslow,
    tslow)`` for each depth (from its start event to the next event), and one row with
    ``depth = 0`` per structurefit call for the time before its first depth (scoring the
    start graph)."""
    ev = np.atleast_2d(np.asarray(ev, dtype=float))
    rows, depth = [], 0
    for a, b in zip(ev[:-1], ev[1:]):
        if a[0] == EV_START:
            depth = 0
        elif a[0] == EV_DEPTH:
            depth += 1
        else:
            continue
        rows.append((int(a[1]), depth, b[2] - a[2], *(b[3:] - a[3:])))
    return rows


def _sf_summary(ev, total):
    rows = depth_rows(ev)
    deep = [r for r in rows if r[1] > 0]
    ev = np.atleast_2d(ev)
    return {"total": total, "nsf": int(np.sum(ev[:, 0] == EV_START)), "depths": len(deep),
            "per_depth": float(np.mean([r[2] for r in deep])) if deep else float("nan"),
            "max_depth": float(np.max([r[2] for r in deep])) if deep else float("nan"),
            "nfast": int(ev[-1, 3]), "tfast": float(ev[-1, 4]), "nslow": int(ev[-1, 5]),
            "tslow": float(ev[-1, 6])}


def _cells(c):
    """A MATLAB cell of vectors (``loadmat(simplify_cells=True)``) -> list of lists."""
    if not isinstance(c, (list, tuple)) and not (isinstance(c, np.ndarray)
                                                 and c.dtype == object):
        c = [c]  # a one-element cell
    return [np.ravel(np.asarray(x, dtype=float)).tolist() for x in c]


def bench_sf(fx):
    """Run every ``sf`` record in Python. Returns one row dict per run."""
    rows = []
    for r in fx["sf"]:
        py = spied_runmodel(int(_num(r["sind"])) - 1, int(_num(r["dind"])) - 1,
                            int(_num(r["speed"])), str(r["kind"]))
        oct_ev = np.atleast_2d(np.asarray(r["ev"], dtype=float))
        row = {"run": f"{r['structure']} x {r['data']}", "speed": int(_num(r["speed"])),
               "oct": _sf_summary(oct_ev, _num(r["total"])),
               "py": _sf_summary(py["ev"], py["total"]),
               "oct_ll": _num(r["ll"]), "py_ll": py["ll"],
               "oct_depths": depth_rows(oct_ev), "py_depths": depth_rows(py["ev"]),
               "oct_lls": _cells(r["lls"]),
               "py_lls": [x.tolist() for x in py["lls"]]}
        rows.append(row)
    return rows


def _ms(x):
    return "-" if x is None else f"{1e3 * x:.3g}"


def _ratio(py, oc):
    return "-" if py is None or oc is None else f"{py / oc:.2f}"


def gl_table(rows):
    out = ["| graph | nodes | fast Oct / Py (ms) | ratio | slow Oct / Py (ms) | ratio | "
           "dataprobwsig Oct / Py (ms) | ratio | check |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| {r['graph']} | {r['nodes']} | {_ms(r['oct_fast'])} / {_ms(r['py_fast'])} | "
            f"{_ratio(r['py_fast'], r['oct_fast'])} | {_ms(r.get('oct_slow'))} / "
            f"{_ms(r.get('py_slow'))} | {_ratio(r.get('py_slow'), r.get('oct_slow'))} | "
            f"{_ms(r.get('oct_dp'))} / {_ms(r.get('py_dp'))} | "
            f"{_ratio(r.get('py_dp'), r.get('oct_dp'))} | "
            f"{'ok' if not r['fail'] else '; '.join(r['fail'])} |")
    return "\n".join(out)


def sf_table(rows):
    out = ["| run | speed | total Oct / Py (s) | ratio | depths Oct / Py | s per depth "
           "Oct / Py | graph_like fast calls Oct / Py (s in them) | slow calls Oct / Py "
           "(s in them) | final score Oct / Py |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o, p = r["oct"], r["py"]
        out.append(
            f"| {r['run']} | {r['speed']} | {o['total']:.2f} / {p['total']:.2f} | "
            f"{p['total'] / o['total']:.2f} | {o['depths']} / {p['depths']} | "
            f"{o['per_depth']:.3f} / {p['per_depth']:.3f} | "
            f"{o['nfast']} ({o['tfast']:.2f}) / {p['nfast']} ({p['tfast']:.2f}) | "
            f"{o['nslow']} ({o['tslow']:.2f}) / {p['nslow']} ({p['tslow']:.2f}) | "
            f"{r['oct_ll']:.4f} / {r['py_ll']:.4f} |")
    return "\n".join(out)


def depth_table(row):
    """Per-depth comparison for one ``sf`` row (depths matched by position)."""
    out = [f"{row['run']} (speed {row['speed']}), per structurefit call and depth:", "",
           "| call | depth | Oct s | Py s | Oct fast/slow calls | Py fast/slow calls |",
           "|---|---|---|---|---|---|"]
    od = {(r[0], r[1]): r for r in row["oct_depths"]}
    pd = {(r[0], r[1]): r for r in row["py_depths"]}
    for k in sorted(set(od) | set(pd)):
        o, p = od.get(k), pd.get(k)
        out.append(f"| {k[0]} | {k[1] or 'start'} | {'-' if o is None else f'{o[2]:.3f}'} | "
                   f"{'-' if p is None else f'{p[2]:.3f}'} | "
                   f"{'-' if o is None else f'{int(o[3])}/{int(o[5])}'} | "
                   f"{'-' if p is None else f'{int(p[3])}/{int(p[5])}'} |")
    return "\n".join(out)


def profile_dataprob(fx, reps=200):
    """cProfile of ``dataprobwsig`` (two outputs) on the feature ``gl`` graphs, ``reps``
    calls each. Returns the stats text (top 25 by internal time)."""
    preps, calls = {}, []
    for r in fx["gl"]:
        if str(r["type"]) == "rel":
            continue
        data, g, ps = gl_inputs(r, preps)
        calls.append(dp_inputs(data, g, ps))
    pr = cProfile.Profile()
    pr.enable()
    for Xinit, d, gL, pf in calls:
        for _ in range(reps):
            likelihood_feat.dataprobwsig(Xinit, d, gL, pf, nargout=2)
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(25)
    return s.getvalue()


def _live_fixture(sections):
    from tests.conftest import OCTAVE_TESTS_DIR, _configure_octave_env, find_octave
    from tools.gen_fixtures import run_one
    exe = find_octave()
    if exe is None:
        raise SystemExit("--live needs Octave")
    _configure_octave_env(exe)
    tmp = Path(tempfile.mkdtemp())
    script = OCTAVE_TESTS_DIR / "fx_perf.m"
    # gen_fixtures.run_one runs fx_perf(outfile) (all sections)
    run_one(exe, "perf", script, tmp)
    return load_fixture("perf", fixtures_dir=tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sections", default="gl,sf")
    ap.add_argument("--live", action="store_true", help="regenerate the Octave side first")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--blas-threads", type=int, default=1,
                    help="BLAS threads for the gl section and the profile (default 1, as "
                         "runmodel uses; 0 = the library's setting). runmodel and "
                         "structurefit set formdiscovery.threads.BLAS_THREADS themselves")
    args = ap.parse_args(argv)
    from formdiscovery import threads
    threads.BLAS_THREADS = args.blas_threads or None
    with blas_threads(args.blas_threads or None):
        return _main(args)


def _main(args):
    sections = args.sections.split(",")
    fx = _live_fixture(sections) if args.live else load_fixture("perf")
    print(f"Octave {fx['octave_version']}, fixture nproc {int(_num(fx['nproc']))}; "
          f"numpy {np.__version__}; BLAS threads {args.blas_threads or 'default'}")
    res, ok = {}, True
    if "gl" in sections:
        res["gl"] = bench_gl(fx)
        print("\n" + gl_table(res["gl"]))
        ok &= not any(r["fail"] for r in res["gl"])
    if "sf" in sections:
        res["sf"] = bench_sf(fx)
        print("\n" + sf_table(res["sf"]))
        for r in res["sf"]:
            print("\n" + depth_table(r))
    if args.profile:
        print("\n" + profile_dataprob(fx))
    if args.json:
        args.json.write_text(json.dumps(
            res, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
