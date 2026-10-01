"""Parity of ``search.spr`` (with ``makerp``, ``makers``) and ``search.collapsedims``
(with ``getocc``, ``get_occnodescomp``, ``zassign``) with Octave (item 25, L4-b2), with
replayed permutations.

The fixture ``tests/fixtures/spr.mat`` comes from ``legacy/tests_octave/fx_spr.m`` (regenerate
with ``python legacy/tools/gen_fixtures.py spr``). It re-runs 11 runs with ``spr`` and
``collapsedims`` replaced by a spy (``legacy/tests_octave/l4b2_spy.m``):

- ``calls``: ``bl`` records are real calls from ``gibbs_clean``; ``pt`` records run the
  same call on a perturbed graph (random object moves and, for ``spr``, a random regraft)
  so that changes are accepted; ``cr`` records are crafted ``collapsedims`` calls on 2 x n
  and 3 x m chain/ring products (the real product graphs almost never have room to
  collapse). Each record holds the ``randperm`` draws made inside the call, replayed here
  and used up exactly. Near-miss graphs already in the input list are the strings
  ``'in1'``, ``'in2'``, ...
- ``sub``: the subfunctions on the input graph of the first kept call per mode and run.

``spr`` covers tree (cluster and object pruning) and the hierarchy family (hierarchy,
dirhierarchy, dirhierarchynoself, undirhierarchy, undirhierarchynoself); ``collapsedims``
covers grid and cylinder on the feature demos and on synthgrid. Scores are fast mode and
match to rtol 1e-10. Fixture indices are 1-based; the port is 0-based.
"""

import dataclasses

import numpy as np
import pytest

from formdiscovery import FormDiscoveryError, likelihood
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.params import graph_prior
from formdiscovery.rng import ReplayPermutations, parse_queue
from formdiscovery.search import (collapsedims, get_occnodescomp, getocc, makerp, makers,
                                  spr, zassign)
from tests.helpers import graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tests.test_swap import _list, _placeholders, _prep, _text, check_nearmisses

FX = load_fixture("spr")
CALLS = list(FX["calls"])
SUB = list(FX["sub"])
RUNS = [str(x) for x in np.ravel(FX["runs"])]

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


def _ns(r):
    v = r["nearmscores"]
    return np.atleast_1d(np.asarray(v, dtype=float)) if np.size(v) else np.empty(0)


def _call(r, rng, graph=None, debug=0, ns=None, ng=None):
    data, ps, _ = _inputs(r)
    ns = _ns(r) if ns is None else ns
    ng = _placeholders(ns.size) if ng is None else ng
    g = graph_from_mat(r["graph"]) if graph is None else graph
    if str(r["fn"]) == "spr":
        return spr(g, data, ps, int(r["comp"]) - 1, float(r["epsilon"]),
                   float(r["currscore"]), int(r["overallchange"]), debug, ns, ng, rng=rng)
    return collapsedims(g, data, ps, float(r["epsilon"]), float(r["currscore"]),
                        int(r["overallchange"]), int(r["loopmax"]), ns, ng, debug=debug,
                        rng=rng)


def _changed(r):
    return float(r["out_currscore"]) != float(r["currscore"])


def check_record(r, msg):
    data, ps, _ = _inputs(r)
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    g, cs, oc, ns, ng = _call(r, rng)
    rng.assert_exhausted()
    ocs = float(r["out_currscore"])
    assert cs == ocs or np.isclose(cs, ocs, rtol=1e-10, atol=0), (msg, cs, ocs)
    assert oc == int(r["out_overallchange"]), msg
    d = graph_diff(g, r["out_graph"])
    assert d is None, f"{msg}: {d}"
    check_nearmisses(ns, ng, r, msg, data, ps)
    return g, cs


def _msg(i, r):
    return (f"call {i} {str(r['fn'])} {str(r['kind'])} {RUNS[int(r['run']) - 1]} "
            f"n={int(r['n'])} comp={int(r['comp'])}")


# --- contents ------------------------------------------------------------------------------

def test_contents():
    assert RUNS == ["tree:demo_tree_feat", "hierarchy:demo_tree_feat", "tree:demo_chain_feat",
                    "dirhierarchy:demo_hierarchy_rel_bin",
                    "dirhierarchynoself:demo_hierarchy_rel_bin",
                    "undirhierarchy:demo_hierarchy_rel_bin",
                    "undirhierarchynoself:demo_hierarchy_rel_bin",
                    "cylinder:demo_ring_feat", "grid:demo_ring_feat",
                    "cylinder:demo_chain_feat", "grid:synthgrid"]
    kinds = {}
    for r in CALLS:
        kinds.setdefault((str(r["fn"]), str(r["kind"])), []).append(r)
    assert {k: len(v) for k, v in kinds.items()} == {
        ("spr", "bl"): 16, ("spr", "pt"): 16, ("collapsedims", "bl"): 11,
        ("collapsedims", "pt"): 11, ("collapsedims", "cr"): 16}
    # spr: every type, accepted changes, object pruning (two draws or more) on trees
    sprs = [r for r in CALLS if str(r["fn"]) == "spr"]
    types = {graph_from_mat(r["graph"]).components[int(r["comp"]) - 1].type for r in sprs}
    assert types == {"tree", "hierarchy", "dirhierarchy", "dirhierarchynoself",
                     "undirhierarchy", "undirhierarchynoself"}
    assert {(t, c) for t in ("bl", "pt") for c in (True, False)} - {
        (str(r["kind"]), _changed(r)) for r in sprs} == {("pt", False)}
    # collapsedims: accepted changes (crafted), draws, near-miss lists, loopmax 1-3
    cds = [r for r in CALLS if str(r["fn"]) == "collapsedims"]
    assert all(_changed(r) for r in cds if str(r["kind"]) == "cr")
    assert sum(len(parse_queue(_text(r["logtext"]))) for r in cds) > 100
    assert {int(r["loopmax"]) for r in cds} == {1, 2, 3}
    assert any(np.isfinite(np.ravel(r["out_nearmscores"])).any() for r in cds
               if np.size(r["out_nearmscores"]))
    assert {graph_from_mat(r["graph"]).type for r in cds} == {"grid", "cylinder"}


def test_spied_runs_match_baseline():
    """The spy and the pass-through shim do not change the runs."""
    n = 0
    for run, ll in zip(RUNS, np.ravel(FX["run_ll"])):
        s, d = run.split(":")
        expected = FEAT_LL.get((s, d), REL_LL.get((s, d)))
        if expected is None:  # hierarchy, grid, cylinder are not in the baselines
            assert np.isfinite(ll)
            continue
        assert ll == pytest.approx(expected, rel=1e-12), run
        n += 1
    assert n == 6


# --- spr / collapsedims --------------------------------------------------------------------

@pytest.mark.parametrize("i", range(len(CALLS)))
def test_call(i):
    check_record(CALLS[i], _msg(i, CALLS[i]))


def test_spr_redraws_after_accept():
    """spr.m:37: an accepted change draws a new ``makerp`` permutation, so an accepting
    call makes more draws than it has ``objflag`` passes."""
    n = 0
    for r in CALLS:
        if str(r["fn"]) != "spr":
            continue
        draws = parse_queue(_text(r["logtext"]))
        typ = graph_from_mat(r["graph"]).components[int(r["comp"]) - 1].type
        passes = 2 if typ == "tree" else 1
        if not _changed(r):
            assert len(draws) == passes
        else:
            assert len(draws) > passes
            n += 1
    assert n > 10


def test_collapsedims_draws_only_when_room():
    """collapsedims.m:33-35: one draw per slice that fits in the vacant clusters."""
    for r in CALLS:
        if str(r["fn"]) != "collapsedims" or _changed(r) or int(r["loopmax"]) != 1:
            continue
        g = graph_from_mat(r["graph"])
        expected = []
        for i in range(int(g.ncomp)):
            for j in get_occnodescomp(g, i):
                occ, unocc = getocc(g, i, int(j))
                zj = occ[np.asarray(g.compinds)[occ, i] == j]
                if zj.size <= unocc.size:
                    expected.append(zj.size)
        assert [len(p) for p in parse_queue(_text(r["logtext"]))] == expected


def test_accepted_graph_is_scored_candidate():
    for r in CALLS:
        if not _changed(r):
            continue
        data, ps, _ = _inputs(r)
        g, cs, *_ = _call(r, ReplayPermutations(parse_queue(_text(r["logtext"]))))
        logI, _ = likelihood.graph_like(data, g, ps)
        assert np.isclose(logI + graph_prior(g, ps), cs, rtol=1e-12, atol=0)


def test_inputs_not_mutated():
    for fn in ("spr", "collapsedims"):
        r = next(r for r in CALLS if str(r["fn"]) == fn and _changed(r) and np.size(
            r["nearmscores"]))
        g = graph_from_mat(r["graph"])
        ns = _ns(r)
        ns0, ng = ns.copy(), _placeholders(ns.size)
        _call(r, ReplayPermutations(parse_queue(_text(r["logtext"]))), graph=g, ns=ns, ng=ng)
        assert graph_diff(g, r["graph"], rtol=0, atol=0) is None
        assert np.array_equal(ns, ns0) and ng == _placeholders(ns.size)


@pytest.mark.parametrize("fn", ["spr", "collapsedims"])
def test_debug_raises(fn):
    """``debug`` stops at the first accepted change (MATLAB's keyboard, patched)."""
    r = next(r for r in CALLS if str(r["fn"]) == fn and _changed(r))
    with pytest.raises(FormDiscoveryError, match="debug stop"):
        _call(r, ReplayPermutations(parse_queue(_text(r["logtext"]))), debug=1)


@pytest.mark.parametrize("fn", ["spr", "collapsedims"])
def test_default_rng_runs(fn):
    """rng=None / an int seed use numpy permutations; the score never gets worse."""
    r = next(r for r in CALLS if str(r["fn"]) == fn and str(r["kind"]) != "bl")
    for rng in (None, 5):
        g, cs, oc, ns, ng = _call(r, rng)
        assert cs >= float(r["currscore"])


def test_makerp_sizes():
    r = next(r for r in CALLS if str(r["fn"]) == "spr")
    g = graph_from_mat(r["graph"])
    i = int(r["comp"]) - 1
    assert sorted(makerp(g, i, 0, 3)) == list(range(int(g.components[i].nodecount)))
    assert sorted(makerp(g, i, 1, 3)) == list(range(int(g.objcount)))


# --- subfunctions --------------------------------------------------------------------------

def _vec0(v):
    return np.atleast_1d(np.asarray(v, dtype=float)).astype(np.int64).ravel() - 1 \
        if np.size(v) else np.empty(0, dtype=np.int64)


def _items(v):
    return [v] if isinstance(v, dict) else list(v)


def test_makers():
    seen = set()
    for k, s in enumerate(SUB):
        if str(s["fn"]) != "spr":
            continue
        g = graph_from_mat(s["graph"])
        i = int(s["comp"]) - 1
        typ = g.components[i].type
        for t in _items(s["mk"]):
            j, of = int(t["j"]) - 1, int(t["objflag"])
            msg = f"sub {k} {typ} j={j} objflag={of}"
            assert not _text(t["err"]), msg
            rs, cs = makers(g, j, i, of)
            np.testing.assert_array_equal(rs, _vec0(t["rs"]), err_msg=msg)
            np.testing.assert_array_equal(cs, _vec0(t["cs"]), err_msg=msg)
            seen.add((typ == "tree", of, rs.size > 0))
    # objects always have somewhere to go; parentless nodes (the root) have nowhere
    assert seen == {(True, 0, True), (True, 0, False), (True, 1, True),
                    (False, 0, True), (False, 0, False), (False, 1, True)}


def test_getocc_get_occnodescomp_zassign():
    n = 0
    for k, s in enumerate(SUB):
        if str(s["fn"]) != "collapsedims":
            continue
        g = graph_from_mat(s["graph"])
        occn = [s["occn"]] if int(g.ncomp) == 1 else list(s["occn"])
        for i in range(int(g.ncomp)):
            np.testing.assert_array_equal(get_occnodescomp(g, i), _vec0(occn[i]))
        for t in _items(s["go"]):
            occ, unocc = getocc(g, int(t["i"]) - 1, int(t["j"]) - 1)
            np.testing.assert_array_equal(occ, _vec0(t["occ"]), err_msg=f"sub {k}")
            np.testing.assert_array_equal(unocc, _vec0(t["unocc"]), err_msg=f"sub {k}")
        h = zassign(int(s["za_from"]) - 1, int(s["za_to"]) - 1, g, 0, 0)
        d = graph_diff(h, s["za"], rtol=0, atol=0)
        assert d is None, f"sub {k}: {d}"
        n += 1
    assert n >= 4


def test_ki27_makers_unknown_type():
    """KNOWN_ISSUES.md KI-27 pin: ``domtreenoself`` reaches spr (gibbs_clean.m:88-90) but
    makers has no case for it (spr.m:72-98); the port raises."""
    r = next(r for r in CALLS if str(r["fn"]) == "spr" and graph_from_mat(
        r["graph"]).components[int(r["comp"]) - 1].type == "hierarchy")
    g = graph_from_mat(r["graph"])
    i = int(r["comp"]) - 1
    g.components[i].type = "domtreenoself"
    j = next(j for j in range(int(g.components[i].nodecount))
             if np.asarray(g.components[i].adj)[:, j].any())
    with pytest.raises(FormDiscoveryError, match="KI-27"):
        makers(g, j, i, 0)
    with pytest.raises(FormDiscoveryError, match="KI-27"):
        makers(g, 0, i, 1)


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "spr.mat"
    octave.eval(f"fx_spr('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    assert len(fx["calls"]) == len(CALLS)
    for x, y in zip(fx["calls"], CALLS):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["out_currscore"]) == float(y["out_currscore"])
        assert graph_diff(x["out_graph"], y["out_graph"], rtol=0, atol=0) is None
    np.testing.assert_array_equal(fx["run_ll"], FX["run_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "spr7919.mat"
    octave.eval(f"fx_spr('{out}', 7918);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    calls = list(fx["calls"])
    assert [str(x) for x in np.ravel(fx["runs"])] == RUNS and len(calls) > 50
    assert any(_changed(r) for r in calls)
    for i, r in enumerate(calls):
        check_record(r, f"fresh {_msg(i, r)}")
