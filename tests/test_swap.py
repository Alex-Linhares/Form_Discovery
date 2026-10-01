"""Parity of ``search.swapobjclust`` and its subfunctions ``chooseswaps``, ``doswap``,
``sourceobjs``, ``sourcecls`` and ``cltypes`` (item 24, L4-b1) with Octave, with replayed
permutations.

The fixture ``tests/fixtures/swap.mat`` comes from ``legacy/tests_octave/fx_swap.m``
(regenerate with ``python legacy/tools/gen_fixtures.py swap``). It re-runs 11 baseline runs with
``swapobjclust`` replaced by a spy (``legacy/tests_octave/swap_spy.m``):

- ``sw``: kept calls. ``bl`` records are real calls from ``gibbs_clean``; ``pt`` records
  run the same mode on a perturbed graph so that changes are accepted. Each record holds
  the ``randperm`` draws made inside the call, which are replayed here with
  :class:`formdiscovery.rng.ReplayPermutations` and must be used up exactly. Near-miss
  graphs that were already in the input list are the strings ``'in1'``, ``'in2'``, ...;
  the Python call gets the same strings.
- ``sub``: the subfunctions on the input graph of the first kept call per mode and run.

All five kinds of change are covered: object moves, cluster moves and swaps within a
component, and cluster moves and swaps across the whole (product) graph, each in full
and fast (``dijkstra`` neighbourhood) mode, on single graphs and on grid/cylinder
products. Fixture indices are 1-based; the port is 0-based (``CONVENTIONS.md``). Scores
are fast mode (``gibbs_clean`` sets ``ps.fast = 1``) and match to rtol 1e-10.
"""

import dataclasses

import numpy as np
import pytest

from formdiscovery import FormDiscoveryError, likelihood
from formdiscovery.io import graph_from_mat, load_dataset, load_fixture
from formdiscovery.params import DATASETS, Params, graph_prior, setrunps, structcounts
from formdiscovery.preprocess import scaledata
from formdiscovery.rng import ReplayPermutations, parse_queue
from formdiscovery.search import (chooseswaps, cltypes, doswap, sourcecls, sourceobjs,
                                  swapobjclust)
from formdiscovery.graph import simplify_graph
from tests.helpers import graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL

FX = load_fixture("swap")
SW = list(FX["sw"])
SUB = list(FX["sub"])
RUNS = [str(x) for x in np.ravel(FX["runs"])]
TIE_RTOL = 1e-10


def _text(x):
    return str(x) if np.size(x) else ""


def _prep(name):
    """fx_swap.m's prep (runmodel.m:27-95 without the graph initialisation)."""
    data = load_dataset(name)
    nobj, ps = setrunps(data, DATASETS.index(name), Params.default())
    data, ps = scaledata(data, ps)
    ps = ps.replace(overrideSS=0 if ps.overrideSS is None else ps.overrideSS, cleanstrong=0)
    return data, structcounts(nobj, ps)


PREP = {}
for _d in FX["ds"]:
    _data, _ps = _prep(str(_d["name"]))
    if "data" in _d:  # exact Octave data (Python scaledata agrees to ~1 ulp)
        _data = np.asarray(_d["data"], dtype=float)
    PREP[str(_d["name"])] = (_data, _ps)


def _inputs(r):
    """Data and ps of a record: the run's data set and the recorded ps fields."""
    run = RUNS[int(r["run"]) - 1]
    data, ps = PREP[run.split(":")[1]]
    q = r["ps"]
    ps = ps.replace(speed=int(q["speed"]), fast=int(q["fast"]), fixedall=int(q["fixedall"]),
                    fixedinternal=int(q["fixedinternal"]),
                    fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]),
                    cleanstrong=int(q["cleanstrong"]))
    ps.runps = dataclasses.replace(ps.runps, structname=str(q["structname"]))
    return data, ps, run


def _comp(r):
    c = int(r["comp"])
    return None if c == 0 else c - 1


def _list(v):
    return [] if np.size(v) == 0 else list(np.ravel(np.asarray(v, dtype=object)))


def _placeholders(n):
    return [f"in{k + 1}" for k in range(n)]


def _mode(r):
    return ("whole" if _comp(r) is None else "comp", int(r["objflag"]), int(r["fastflag"]),
            np.size(r["nearmscores"]) > 0)


def run_record(r):
    data, ps, run = _inputs(r)
    ns = np.atleast_1d(np.asarray(r["nearmscores"], dtype=float)) if np.size(r["nearmscores"]) \
        else np.empty(0)
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    out = swapobjclust(graph_from_mat(r["graph"]), data, ps, _comp(r), float(r["epsilon"]),
                       float(r["currscore"]), int(r["overallchange"]), int(r["loopmax"]),
                       ns, _placeholders(ns.size), objflag=int(r["objflag"]),
                       fastflag=int(r["fastflag"]), rng=rng)
    rng.assert_exhausted()
    return out, data, ps, run


def check_nearmisses(scores, graphs, r, msg, data, ps):
    """Near-miss scores to rtol 1e-10. Each entry equals Octave's entry at the same
    position, or (if several stored scores are tied to TIE_RTOL, e.g. a move and the
    mirror-image move) an Octave entry with a tied score. If the tied group runs to the
    end of the list, more candidates may have tied than fit, and rounding decides which
    are kept (``testscore > nearmscores(end)``); then any Python graph that rescores to
    the tied value is accepted. The committed fixture never needs this last rule; the
    fresh-seed live run needs it once (six or more exact ties that differ from Octave's
    by 1e-13)."""
    oscores = np.atleast_1d(np.asarray(r["out_nearmscores"], dtype=float)) \
        if np.size(r["out_nearmscores"]) else np.empty(0)
    assert scores.shape == oscores.shape, msg
    fin = np.isfinite(oscores)
    assert np.array_equal(np.isfinite(scores), fin), msg
    np.testing.assert_allclose(scores[fin], oscores[fin], rtol=TIE_RTOL, atol=0, err_msg=msg)
    ographs = _list(r["out_nearmgraphs"])
    assert len(graphs) == len(ographs) == scores.size, msg

    def same(a, b):
        if isinstance(b, str) or isinstance(a, str) or a is None:
            return a == b
        return graph_diff(a, b) is None

    for k, g in enumerate(graphs):
        if same(g, ographs[k]):
            continue
        tied = [m for m in range(len(ographs)) if np.isfinite(oscores[k])
                and np.isclose(oscores[m], oscores[k], rtol=TIE_RTOL, atol=0)]
        if any(same(g, ographs[m]) for m in tied):
            continue
        assert tied and max(tied) == len(ographs) - 1 and not isinstance(g, str), \
            f"{msg}: near miss {k}"
        logI, _ = likelihood.graph_like(data, g, ps)
        assert np.isclose(logI + graph_prior(g, ps), oscores[k], rtol=TIE_RTOL, atol=0), \
            f"{msg}: near miss {k} rescored"


def check_record(r, msg):
    (g, cs, oc, ns, ng), data, ps, run = run_record(r)
    ocs = float(r["out_currscore"])
    assert cs == ocs or np.isclose(cs, ocs, rtol=1e-10, atol=0), (msg, cs, ocs)
    assert oc == int(r["out_overallchange"]), msg
    d = graph_diff(g, r["out_graph"])
    assert d is None, f"{msg}: {d}"
    check_nearmisses(ns, ng, r, msg, data, ps)
    return g, cs


# --- contents ------------------------------------------------------------------------------

def test_contents():
    assert RUNS == ["chain:demo_chain_feat", "ring:demo_ring_feat", "tree:demo_tree_feat",
                    "hierarchy:demo_tree_feat", "grid:demo_chain_feat",
                    "cylinder:demo_ring_feat", "dirring:demo_ring_rel_bin",
                    "undirchain:demo_order_rel_freq", "order:demo_order_rel_freq",
                    "dirhierarchy:demo_hierarchy_rel_bin",
                    "undirhierarchy:demo_hierarchy_rel_bin"]
    assert len(SW) == 238 and len(SUB) == 59
    kinds = [str(r["kind"]) for r in SW]
    assert kinds.count("bl") == 119 and kinds.count("pt") == 119
    # every mode, with a change accepted and without
    seen = {(_mode(r)[:3], float(r["out_currscore"]) != float(r["currscore"])) for r in SW}
    for mode in [("whole", 1, 0), ("whole", 1, 1), ("whole", 0, 0), ("whole", 0, 1),
                 ("comp", 0, 0), ("comp", 0, 1)]:
        assert (mode, True) in seen and (mode, False) in seen, mode
    # near-miss lists in every kind of call, and loopmax 1-3
    assert {m for m in map(_mode, SW) if m[3]} == {
        ("whole", 1, 0, True), ("whole", 1, 1, True), ("whole", 0, 0, True),
        ("comp", 0, 0, True), ("comp", 0, 1, True)}
    assert {int(r["loopmax"]) for r in SW} == {1, 2, 3}
    # product graphs and whole-graph swaps
    prod = [r for r in SW if int(graph_from_mat(r["graph"]).ncomp) > 1]
    assert {RUNS[int(r["run"]) - 1] for r in prod} == {"grid:demo_chain_feat",
                                                        "cylinder:demo_ring_feat"}


def test_spied_runs_match_baseline():
    """The spy and the pass-through shim do not change the runs."""
    n = 0
    for run, ll in zip(RUNS, np.ravel(FX["run_ll"])):
        s, d = run.split(":")
        expected = FEAT_LL.get((s, d), REL_LL.get((s, d)))
        if expected is None:  # hierarchy, grid and cylinder are not in the baselines
            assert np.isfinite(ll)
            continue
        assert ll == pytest.approx(expected, rel=1e-12), run
        n += 1
    assert n == 8


# --- swapobjclust --------------------------------------------------------------------------

@pytest.mark.parametrize("i", range(len(SW)))
def test_swapobjclust(i):
    r = SW[i]
    check_record(r, f"sw {i} {str(r['kind'])} {RUNS[int(r['run']) - 1]} call {int(r['n'])} "
                    f"{_mode(r)}")


def test_accepted_graph_is_simplified_candidate():
    """The returned graph is the simplified candidate that was scored (l.39-49): its
    score is currscore, and simplify_graph leaves it unchanged."""
    n = 0
    for r in SW:
        if float(r["out_currscore"]) == float(r["currscore"]):
            continue
        (g, cs, *_), data, ps, _ = run_record(r)
        logI, _ = likelihood.graph_like(data, g, ps)
        assert np.isclose(logI + graph_prior(g, ps), cs, rtol=1e-12, atol=0)
        assert graph_diff(simplify_graph(g, ps), g, rtol=0, atol=0) is None
        n += 1
        if n == 20:
            break
    assert n == 20


def test_stale_permutation_after_accept():
    """After an accepted change the candidates are listed again but the pass goes on with
    the old permutation (l.33-50): one draw per pass, sized for the first list. Some
    records accept a change whose new list has a different length."""
    n = 0
    for r in SW:
        draws = parse_queue(_text(r["logtext"]))
        assert 1 <= len(draws) <= int(r["loopmax"])
        if float(r["out_currscore"]) == float(r["currscore"]):
            continue
        g_in, g_out = graph_from_mat(r["graph"]), graph_from_mat(r["out_graph"])
        args = (_comp(r) is None, int(r["objflag"]), _comp(r), int(r["fastflag"]))
        if int(r["loopmax"]) == 1 and len(draws[0]) == chooseswaps(g_in, *args)[0].shape[0] \
                != chooseswaps(g_out, *args)[0].shape[0]:
            n += 1
    assert n > 0


def test_inputs_not_mutated():
    r = next(r for r in SW if float(r["out_currscore"]) != float(r["currscore"])
             and np.size(r["nearmscores"]))
    data, ps, _ = _inputs(r)
    g = graph_from_mat(r["graph"])
    ns = np.asarray(r["nearmscores"], dtype=float).ravel()
    ns0, ng = ns.copy(), _placeholders(ns.size)
    d0 = np.array(data, copy=True)
    swapobjclust(g, data, ps, _comp(r), 1e-4, float(r["currscore"]), 0, int(r["loopmax"]),
                 ns, ng, objflag=int(r["objflag"]), fastflag=int(r["fastflag"]),
                 rng=ReplayPermutations(parse_queue(_text(r["logtext"]))))
    assert graph_diff(g, r["graph"], rtol=0, atol=0) is None
    assert np.array_equal(ns, ns0) and ng == _placeholders(ns.size)
    assert np.array_equal(np.asarray(data), d0)


def test_debug_raises():
    """``debug`` stops at the first accepted change (MATLAB's keyboard, patched)."""
    r = next(r for r in SW if float(r["out_currscore"]) != float(r["currscore"]))
    data, ps, _ = _inputs(r)
    with pytest.raises(FormDiscoveryError, match="debug stop"):
        swapobjclust(graph_from_mat(r["graph"]), data, ps, _comp(r), 1e-4,
                     float(r["currscore"]), 0, int(r["loopmax"]), [], [],
                     objflag=int(r["objflag"]), fastflag=int(r["fastflag"]), debug=1,
                     rng=ReplayPermutations(parse_queue(_text(r["logtext"]))))


def test_default_rng_runs():
    """rng=None / an int seed use numpy permutations; the score never gets worse."""
    r = next(r for r in SW if str(r["kind"]) == "pt" and _comp(r) is not None)
    data, ps, _ = _inputs(r)
    g, cs, oc, ns, ng = swapobjclust(graph_from_mat(r["graph"]), data, ps, _comp(r), 1e-4,
                                     float(r["currscore"]), 0, 2, [], [], rng=5)
    assert cs >= float(r["currscore"]) and ns.size == 0 and ng == []


# --- subfunctions --------------------------------------------------------------------------

def _cell(v, n):
    """A MATLAB cell of length n as a list (load_fixture squeezes a 1 x 1 cell)."""
    return [v] if n == 1 else list(v)


def _vec0(v):
    return np.atleast_1d(np.asarray(v, dtype=float)).astype(np.int64) - 1 if np.size(v) \
        else np.empty(0, dtype=np.int64)


def _sw0(v, ncol):
    """A fixture sw1/sw2 matrix, 0-based (NaN stays NaN)."""
    a = np.asarray(v, dtype=float).reshape(-1, ncol) if np.size(v) else np.empty((0, ncol))
    return a - 1


def _sub_cases():
    for k, s in enumerate(SUB):
        g = graph_from_mat(s["graph"])
        yield k, s, g


def test_sub_contents():
    types = {graph_from_mat(s["graph"]).type for s in SUB}
    assert types == {"chain", "ring", "tree", "hierarchy", "grid", "cylinder", "dirring",
                     "undirchain", "order", "dirhierarchy", "undirhierarchy"}
    # KI-26: whole-graph mode on one-cluster graphs (never called by gibbs_clean)
    errs = {(int(t["fastflag"]), str(t["err"]).split(":")[0].split(" (")[0])
            for s in SUB for t in s["cs"] if _text(t["err"])}
    assert errs == {(0, "nchoosek"), (1, "vertical dimensions mismatch")}


def test_sourceobjs_sourcecls_cltypes():
    kinds = set()
    for k, s, g in _sub_cases():
        so = sourceobjs(g)
        np.testing.assert_array_equal(so, _vec0(s["sourceobjs"]), err_msg=f"sub {k}")
        np.testing.assert_array_equal(sourcecls(g), _vec0(s["sourcecls"]), err_msg=f"sub {k}")
        n = int(g.ncomp)
        for i, (sc, ext, int_) in enumerate(zip(_cell(s["sourcecls_i"], n), _cell(s["ext"], n),
                                                _cell(s["int"], n))):
            np.testing.assert_array_equal(sourcecls(g, i), _vec0(sc), err_msg=f"sub {k} {i}")
            e, it = cltypes(g, i)
            np.testing.assert_array_equal(e, _vec0(ext), err_msg=f"sub {k} {i}")
            np.testing.assert_array_equal(it, _vec0(int_), err_msg=f"sub {k} {i}")
        if so.size < int(g.objcount):
            kinds.add("objs-restricted")
        if sourcecls(g).size < np.unique(g.z).size:
            kinds.add("cls-restricted")
    assert kinds == {"objs-restricted", "cls-restricted"}


def test_chooseswaps_and_doswap():
    seen = set()
    for k, s, g in _sub_cases():
        data, ps, _ = _inputs(s)
        ncol = 2 + int(g.ncomp)
        for t in ([s["cs"]] if isinstance(s["cs"], dict) else list(s["cs"])):
            whole, oflag, fast = int(t["whole"]), int(t["oflag"]), int(t["fastflag"])
            comp = int(t["comp"]) - 1 if int(t["comp"]) else None
            msg = f"sub {k} {g.type} whole={whole} oflag={oflag} comp={comp} fast={fast}"
            if _text(t["err"]):
                # KI-26: whole-graph mode with one source cluster. Full mode fails in
                # nchoosek (raises here); fast mode fails in Octave's concatenation of
                # empty blocks and gives an empty list here.
                assert whole and g.adjcluster.shape[0] == 1, msg
                if fast:
                    assert "vertical dimensions mismatch" in str(t["err"]), msg
                    sw1, sw2 = chooseswaps(g, whole, oflag, comp, fast, 3)
                    assert sw1.shape == sw2.shape == (0, ncol), msg
                else:
                    assert "nchoosek" in str(t["err"]), msg
                    with pytest.raises(FormDiscoveryError, match="KI-26"):
                        chooseswaps(g, whole, oflag, comp, fast, 3)
                seen.add(("KI-26", fast))
                continue
            sw1, sw2 = chooseswaps(g, whole, oflag, comp, fast, 3)
            np.testing.assert_array_equal(sw1, _sw0(t["sw1"], ncol), err_msg=msg)
            np.testing.assert_array_equal(sw2, _sw0(t["sw2"], ncol), err_msg=msg)
            kind = "obj" if oflag else "whole" if whole else "comp"
            seen.add((kind, fast, "move" if np.isnan(sw2).all(axis=1).any() else "-"))
            if (~np.isnan(sw2).all(axis=1)).any():
                seen.add((kind, fast, "swap"))
            row = int(t["row"])
            if row:
                h = doswap(g, sw1[row - 1], sw2[row - 1], oflag, ps)
                d = graph_diff(h, t["swapped"], rtol=0, atol=0)
                assert d is None, f"{msg} row {row}: {d}"
                seen.add("doswap-" + kind)
            else:
                assert sw1.shape[0] == 0, msg
    for kind in ("whole", "comp"):
        for fast in (0, 1):
            assert (kind, fast, "move") in seen and (kind, fast, "swap") in seen, (kind, fast)
    assert ("obj", 0, "move") in seen and ("obj", 1, "move") in seen
    assert {"doswap-obj", "doswap-whole", "doswap-comp", ("KI-26", 0), ("KI-26", 1)} <= seen


def test_one_occupied_node_swaps_node_zero():
    """chooseswaps.m:186-189: with one occupied node the full-mode swap list is [1 1]
    (node 0 with itself in the port), whatever that node is."""
    for k, s, g in _sub_cases():
        for i, c in enumerate(g.components):
            occ = np.unique(np.asarray(c.z))
            if occ.size == 1 and int(c.nodecount) > 1:
                sw1, sw2 = chooseswaps(g, 0, 0, i, 0, 3)
                assert list(sw1[-1, :2]) == [i, 0] and sw1[-1, 2 + i] == 0
                assert list(sw2[-1, :2]) == [i, 0] and sw2[-1, 2 + i] == 0
                return
    g = graph_from_mat(SUB[0]["graph"])
    c = g.components[0]
    c.z = np.full_like(np.asarray(c.z), int(c.nodecount) - 1)
    sw1, sw2 = chooseswaps(g, 0, 0, 0, 0, 3)
    assert list(sw1[-1]) == [0, 0, 0] and list(sw2[-1]) == [0, 0, 0]


def test_ki26_single_source_cluster():
    """KNOWN_ISSUES.md KI-26 pin: whole-graph full mode with one source cluster raises."""
    s = next(s for s in SUB if int(graph_from_mat(s["graph"]).ncomp) > 1)
    g = graph_from_mat(s["graph"])
    for c in g.components:
        c.z = np.zeros_like(np.asarray(c.z))
    g.z = np.zeros_like(np.asarray(g.z))
    with pytest.raises(FormDiscoveryError, match="KI-26"):
        chooseswaps(g, 1, 0, None, 0, 3)
    sw1, sw2 = chooseswaps(g, 1, 0, None, 1, 3)   # fast mode has no nchoosek
    assert sw1.shape[1] == 2 + int(g.ncomp)


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "swap.mat"
    octave.eval(f"fx_swap('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    assert len(fx["sw"]) == len(SW)
    for x, y in zip(fx["sw"], SW):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["out_currscore"]) == float(y["out_currscore"])
        assert graph_diff(x["out_graph"], y["out_graph"], rtol=0, atol=0) is None
    np.testing.assert_array_equal(fx["run_ll"], FX["run_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "swap7919.mat"
    octave.eval(f"fx_swap('{out}', 7918);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    sw = list(fx["sw"])
    runs = [str(x) for x in np.ravel(fx["runs"])]
    assert runs == RUNS and len(sw) > 100
    assert any(float(r["out_currscore"]) != float(r["currscore"]) for r in sw)
    for i, r in enumerate(sw):
        check_record(r, f"fresh sw {i}")
