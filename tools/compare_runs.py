#!/usr/bin/env python
"""Compare Python scores with Octave's (M3 checkpoint, item 21).

``--score-true-graphs``: for each demo data set, build the true graph stored in its
``.mat`` file, score it with ``graph_like`` in fast mode (``ps.fast = 1``: the stored
weights) and slow mode (``ps.fast = 0``: optimiser + Laplace) in Python, and compare with
Octave's scores in ``tests/fixtures/truegraphs.mat`` (``tests/octave/fx_truegraphs.m``).
The graphs are built the way ``fx_truegraphs.m`` builds them (:func:`true_feat_graph`,
:func:`true_rel_graph`). Prints a Markdown table and exits 1 if any check fails.

Checks per row:

- the Python graph equals Octave's input graph (``tests/helpers.py::graph_diff``);
- fast ``logI`` and ``graph_prior``: rtol ``FAST_RTOL`` (1e-10);
- slow ``logI``, feature data: rel ``SLOW_RTOL`` (2e-4, ``tests/test_glslow.py``'s
  ``LOGI_RTOL``). The optimum is also checked: the fast score at Python's optimised
  weights must be at least the fast score at Octave's, minus ``OPT_TOL`` (1e-6);
- slow ``logI``, relational data: ``graph_like_rel`` has no optimiser, so slow equals
  fast and is compared to rtol ``FAST_RTOL``.

Usage::

    python tools/compare_runs.py --score-true-graphs            # committed fixture
    python tools/compare_runs.py --score-true-graphs --live     # rerun Octave first
    python tools/compare_runs.py --score-true-graphs --method L-BFGS-B
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import loadmat

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from formdiscovery import likelihood_feat  # noqa: E402
from formdiscovery.graph import combinegraphs, makeemptygraph  # noqa: E402
from formdiscovery.io import DATA_DIR, graph_from_mat, load_dataset, load_fixture  # noqa: E402
from formdiscovery.likelihood import graph_like  # noqa: E402
from formdiscovery.params import DATASETS, Params, graph_prior, setrunps, structcounts  # noqa: E402
from formdiscovery.preprocess import scaledata  # noqa: E402

FAST_RTOL = 1e-10
SLOW_RTOL = 2e-4
OPT_TOL = 1e-6
MODES = {"none": (0, 0, 0, 0), "exttie": (0, 0, 1, 0), "alltie": (0, 1, 1, 0)}
FEAT_DEMOS = ("demo_chain_feat", "demo_ring_feat", "demo_tree_feat")
REL_FORMS = {
    "demo_ring_rel_bin": ("dirring", "dirringnoself", "undirring", "undirringnoself"),
    "demo_hierarchy_rel_bin": ("dirhierarchy", "dirhierarchynoself", "undirhierarchy",
                               "undirhierarchynoself"),
    "demo_order_rel_freq": ("order", "ordernoself"),
}


def prep(name):
    """``fx_truegraphs.m``'s ``prep``: runmodel.m:27-95 without the graph initialisation."""
    data = load_dataset(name)
    nobj, ps = setrunps(data, DATASETS.index(name), Params.default())
    data, ps = scaledata(data, ps)
    ps = ps.replace(overrideSS=0 if ps.overrideSS is None else ps.overrideSS, cleanstrong=0)
    return data, structcounts(nobj, ps)


def setmode(ps, mode):
    fa, fi, fe, pt = MODES[mode]
    return ps.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt)


def true_feat_graph(mat, ps):
    """The true graph of a feature demo file (``fx_truegraphs.m``'s ``truefeatgraph``).

    ``mat`` holds ``adj``/``W`` over ``objcount`` objects then the cluster nodes, and
    ``sigma``. Object ``i`` hangs from cluster ``z[i]``; the component gets the upper
    triangle of the cluster block as ``adj`` (only ``adjsym``/``Wsym`` reach the feature
    likelihood), ``illegal`` = the clusters holding no object, and the graph
    ``leaflengths`` = the object weights and ``extlen``/``intlen`` = the unique leaf /
    cluster weight. ``ps.runps.structname`` must be the file's structure. Built with
    ``makeemptygraph`` + ``combinegraphs``, as in Octave.
    """
    n = int(np.asarray(mat["objcount"]).ravel()[0])
    A = np.asarray(mat["adj"], dtype=float)
    W = np.asarray(mat["W"], dtype=float)
    k = A.shape[0] - n
    z = np.empty(n, dtype=np.int64)
    lw = np.empty(n)
    for i in range(n):
        c = np.flatnonzero(A[i, n:])
        if len(c) != 1:
            raise ValueError(f"object {i} is not a leaf")
        z[i] = c[0]
        lw[i] = W[n + c[0], i]
    Ac = np.triu(A[n:, n:])
    Wc = W[n:, n:] * Ac
    g = makeemptygraph(ps)
    g.sigma = float(np.asarray(mat["sigma"]).ravel()[0])
    g.z = z.copy()
    g.leaflengths = lw
    ext, int_ = np.unique(lw), np.unique(Wc[Ac > 0])
    if len(ext) != 1 or len(int_) != 1:
        raise ValueError("weights are not tied")
    g.extlen, g.intlen = float(ext[0]), float(int_[0])
    c = g.components[0]
    c.adj, c.W = Ac, Wc
    c.adjsym = ((Ac != 0) | (Ac.T != 0)).astype(float)
    c.Wsym = Wc + Wc.T
    c.nodecount = k
    c.edgecount = c.edgecountsym = int(np.count_nonzero(Ac))
    c.z = z.copy()
    c.illegal = np.setdiff1d(np.arange(k), z).astype(np.int64)
    return combinegraphs(g, ps)


def true_rel_graph(mat, form):
    """The true graph of a relational demo file: its ``graph`` struct (``adjcluster``,
    ``adj``, ``objcount``, ``z``) with ``type = form``."""
    d = dict(mat["graph"])  # loadmat(simplify_cells=True) struct
    d["type"] = form
    return graph_from_mat(d)


def _num(v):
    return float(np.asarray(v).ravel()[0])


def _rel(a, b):
    return abs(a - b) / max(abs(b), np.finfo(float).tiny)


def score_true_graphs(fx=None, method=None):
    """Score every true graph in Python and compare with Octave's record in ``fx``
    (the ``truegraphs`` fixture, default: the committed one). Returns a list of row dicts;
    ``row['ok']`` is False, and ``row['fail']`` says why, when a check fails."""
    from tests.helpers import graph_diff
    fx = load_fixture("truegraphs") if fx is None else fx
    rows = []
    preps = {}
    for part in ("fe", "re"):
        for r in fx[part]:
            name, form = str(r["name"]), str(r["structure"])
            if name not in preps:
                preps[name] = prep(name)
            data, ps = preps[name]
            ps = ps.copy()
            ps.runps.structname = form
            mat = loadmat(DATA_DIR / f"{name}.mat", mat_dtype=True, simplify_cells=True)
            if part == "fe":
                mode = list(MODES)[int(r["mode"]) - 1]
                ps = setmode(ps, mode)
                g = true_feat_graph(mat, ps)
            else:
                mode = "-"
                g = true_rel_graph(mat, form)
            row = {"data": name, "form": form, "mode": mode, "kind": part, "fail": []}
            err = r["err"]
            if np.size(err):
                row["fail"].append(f"Octave error: {err}")
                row["ok"] = False
                rows.append(row)
                continue
            d = graph_diff(g, r["graph"])
            if d:
                row["fail"].append(f"graph: {d}")
            fast, gfast = graph_like(data, g, ps.replace(fast=1))
            if part == "fe":
                slow, gslow = likelihood_feat.graph_like_conn(
                    data, g, ps.replace(fast=0), method=method)
            else:
                slow, gslow = graph_like(data, g, ps.replace(fast=0))
            prior = graph_prior(g, ps)
            row.update(oct_fast=_num(r["fast"]), py_fast=fast, oct_slow=_num(r["slow"]),
                       py_slow=slow, prior=prior)
            row["fast_rel"] = _rel(fast, row["oct_fast"])
            row["slow_rel"] = _rel(slow, row["oct_slow"])
            if row["fast_rel"] > FAST_RTOL:
                row["fail"].append(f"fast rel diff {row['fast_rel']:.2e}")
            if _rel(prior, _num(r["prior"])) > FAST_RTOL:
                row["fail"].append("graph_prior")
            if part == "fe":
                if row["slow_rel"] > SLOW_RTOL:
                    row["fail"].append(f"slow rel diff {row['slow_rel']:.2e}")
                # the fast score at optimised weights is -(objective at the optimum)
                fps = ps.replace(fast=1)
                opt_py = graph_like(data, gslow, fps)[0]
                opt_oct = graph_like(data, graph_from_mat(r["slowgraph"]), fps)[0]
                row["opt_gain"] = opt_py - opt_oct
                if opt_py < opt_oct - OPT_TOL:
                    row["fail"].append(f"Python optimum worse by {-row['opt_gain']:.2e}")
            else:
                if row["slow_rel"] > FAST_RTOL or slow != fast:
                    row["fail"].append("rel slow != fast")
                d = graph_diff(gslow, r["slowgraph"])
                if d:
                    row["fail"].append(f"returned graph: {d}")
            if part == "fe":
                d = graph_diff(gfast, r["fastgraph"])
                if d:
                    row["fail"].append(f"fast graph: {d}")
            row["ok"] = not row["fail"]
            rows.append(row)
    return rows


def format_table(rows):
    """Markdown table of :func:`score_true_graphs` rows."""
    out = ["| data | form | tying | Octave fast | Python fast | rel diff | Octave slow "
           "| Python slow | rel diff | opt gain | prior | ok |",
           "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        if "py_fast" not in r:
            out.append(f"| {r['data']} | {r['form']} | {r['mode']} | | | | | | | | | "
                       f"FAIL: {'; '.join(r['fail'])} |")
            continue
        gain = f"{r['opt_gain']:.1e}" if "opt_gain" in r else "-"
        slow_rel = f"{r['slow_rel']:.1e}" if r["kind"] == "fe" else "(= fast)"
        out.append(
            f"| {r['data']} | {r['form']} | {r['mode']} | {r['oct_fast']:.6f} "
            f"| {r['py_fast']:.6f} | {r['fast_rel']:.1e} | {r['oct_slow']:.6f} "
            f"| {r['py_slow']:.6f} | {slow_rel} | {gain} | {r['prior']:.6f} "
            f"| {'yes' if r['ok'] else 'FAIL: ' + '; '.join(r['fail'])} |")
    return "\n".join(out)


def live_fixture(outdir):
    """Run ``fx_truegraphs.m`` in Octave into ``outdir``; return the loaded records."""
    from tools.gen_fixtures import _configure_octave_env, find_octave, fixture_scripts, run_one
    exe = find_octave()
    if exe is None:
        raise RuntimeError("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
    _configure_octave_env(exe)
    if not run_one(exe, "truegraphs", fixture_scripts()["truegraphs"], outdir):
        raise RuntimeError("fx_truegraphs.m failed")
    return load_fixture("truegraphs", fixtures_dir=outdir)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--score-true-graphs", action="store_true",
                    help="score the demo data sets' true graphs in Octave and Python")
    ap.add_argument("--live", action="store_true",
                    help="rerun fx_truegraphs.m in Octave instead of reading the fixture")
    ap.add_argument("--method", default=None,
                    help=f"scipy method for slow mode (default {likelihood_feat.SLOW_METHOD})")
    args = ap.parse_args(argv)
    if not args.score_true_graphs:
        ap.error("nothing to do (use --score-true-graphs)")
    if args.live:
        with tempfile.TemporaryDirectory() as tmp:
            fx = live_fixture(tmp)
    else:
        fx = None
    rows = score_true_graphs(fx, method=args.method)
    print(format_table(rows))
    nbad = sum(not r["ok"] for r in rows)
    print(f"\n{len(rows) - nbad}/{len(rows)} rows pass "
          f"(fast rtol {FAST_RTOL:g}, slow rel {SLOW_RTOL:g}, optimum tol {OPT_TOL:g})")
    return 0 if nbad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
