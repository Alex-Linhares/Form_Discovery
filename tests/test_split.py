"""Parity of ``graph.split_node``, ``graph.empty_graph`` and ``graph.add_element`` (item 12,
L2-a2) with Octave.

The fixture ``tests/fixtures/split.mat`` comes from ``tests/octave/fx_split.m`` (regenerate
with ``python tools/gen_fixtures.py split``). It has two parts:

- ``sq_*``: seeded split sequences from ``makeemptygraph`` for the 26 single-component names
  and grid/cylinder (``prodtied`` 0/1). Every step uses random component weights, a random
  production, node and partition, then ``empty_graph``/``add_element`` as in
  ``best_split.m``, plus the ``compind = -1`` variants.
- ``bl_*``: calls captured by spies while re-running the baseline runs chain/ring/tree ×
  ``demo_chain_feat`` and the 18 relational structures × ``demo_ring_rel_bin``.

Fixture values are 1-based; the port is 0-based (``CONVENTIONS.md``). ``pind`` is a
production number in both.
"""

from collections import Counter

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.graph import (Component, Graph, add_element, empty_graph, makeemptygraph,
                                 split_node, split_production)
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, load_fixture
from formdiscovery.params import Params
from tests.helpers import assert_graph_equal, graph_equal

FX = load_fixture("split")
PS = Params.default()
ALL_PRODUCTIONS = {"partition", "connected", "chain", "ring", "hierarchy", "rootchain",
                   "domtreeflat", "tree", "treever2", None}


def _ps(prodtied=0, name=None, nobj=None):
    ps = PS.replace(prodtied=int(prodtied))
    ps.runps.structname = name
    ps.runps.nobjects = nobj
    ps.runps.type = "feat"
    return ps


def _idx(v):
    return np.atleast_1d(np.asarray(v, dtype=np.int64)) - 1


def _comp(v):
    """MATLAB compind -> port: 1-based -> 0-based, -1 (high level) stays negative."""
    v = int(v)
    return v - 1 if v > 0 else v


def check_split(r, msg):
    g = graph_from_mat(r["graph"])
    ci, c, pind = _comp(r["compind"]), int(r["c"]) - 1, int(r["pind"])
    out, c1, c2 = split_node(g, ci, c, pind, _idx(r["part1"]), _idx(r["part2"]),
                             _ps(r["prodtied"]))
    prod = split_production(g, ci, c, pind)
    if r["isinf"]:
        assert out is None and c1 is None and c2 is None, msg
        assert prod is None, msg
    else:
        assert prod is not None, msg
        assert (c1, c2) == (int(r["c1"]) - 1, int(r["c2"]) - 1), msg
        assert_graph_equal(out, r["out"], msg=f"{msg} ({g.components[ci].type}, {prod})")
    return prod


def check_empty(r, msg):
    out = empty_graph(graph_from_mat(r["graph"]), _comp(r["compind"]), int(r["c1"]) - 1,
                      int(r["c2"]) - 1)
    assert_graph_equal(out, r["out"], msg=msg)
    assert out.adj.dtype == bool


def check_add(r, msg):
    out = add_element(graph_from_mat(r["graph"]), _comp(r["compind"]), int(r["c"]) - 1,
                      int(r["element"]) - 1, _ps(r["prodtied"]))
    assert_graph_equal(out, r["out"], msg=msg)


# --- seeded sequences --------------------------------------------------------------------

def test_sequence_names():
    names = list(FX["sq_name"])
    assert len(names) == 26 + 4
    assert {"grid:prodtied0", "grid:prodtied1", "cylinder:prodtied0",
            "cylinder:prodtied1", "tree:prodtied0", "undirdomtree:prodtied0"} <= set(names)


@pytest.mark.parametrize("seq", range(30))
def test_split_node_sequences(seq):
    recs = [r for r in FX["sq_sp"] if int(r["seq"]) == seq + 1]
    assert recs
    for k, r in enumerate(recs):
        check_split(r, f"{FX['sq_name'][seq]} step {int(r['step'])}")


def test_empty_graph_sequences():
    assert len(FX["sq_eg"]) > 300
    assert any(int(r["compind"]) == -1 for r in FX["sq_eg"])
    for k, r in enumerate(FX["sq_eg"]):
        check_empty(r, f"sq_eg {k} ({FX['sq_name'][int(r['seq']) - 1]})")


def test_add_element_sequences():
    assert len(FX["sq_ae"]) > 500
    assert any(int(r["compind"]) == -1 for r in FX["sq_ae"])
    for k, r in enumerate(FX["sq_ae"]):
        check_add(r, f"sq_ae {k} ({FX['sq_name'][int(r['seq']) - 1]})")


# --- spied baseline runs -----------------------------------------------------------------

def test_spied_runs_match_baseline():
    """The spies do not change the runs: final scores equal the committed baselines."""
    feat = loadmat(FIXTURES_DIR / "baseline" / "feat" / "resultsdemo.mat")["modellike"]
    rel = loadmat(FIXTURES_DIR / "baseline" / "rel" / "resultsdemo.mat")["modellike"]
    sinds = [2, 4, 6] + [1, 9, 10, 11, 12, 13, 3] + list(range(14, 25))
    assert len(FX["bl_run"]) == len(sinds) == 21
    for r, s in enumerate(sinds):
        want = feat[s - 1, 0] if r < 3 else rel[s - 1, 3]   # rind 1: 2-D
        np.testing.assert_allclose(FX["bl_ll"][r], want, rtol=1e-10, err_msg=FX["bl_run"][r])


def test_split_node_baseline_calls():
    prods = Counter()
    for k, r in enumerate(FX["bl_sp"]):
        prods[check_split(r, f"bl_sp {k} ({FX['bl_run'][int(r['run']) - 1]})")] += 1
    assert set(prods) == ALL_PRODUCTIONS, prods


def test_empty_graph_baseline_calls():
    assert len(FX["bl_eg"]) >= 40
    for k, r in enumerate(FX["bl_eg"]):
        check_empty(r, f"bl_eg {k} ({FX['bl_run'][int(r['run']) - 1]})")


def test_add_element_baseline_calls():
    assert len(FX["bl_ae"]) >= 100
    for k, r in enumerate(FX["bl_ae"]):
        check_add(r, f"bl_ae {k} ({FX['bl_run'][int(r['run']) - 1]})")


# --- coverage and quirks -----------------------------------------------------------------

def _productions(recs):
    out = Counter()
    for r in recs:
        g = graph_from_mat(r["graph"])
        ci = _comp(r["compind"])
        out[(g.components[ci].type, int(r["pind"]),
             split_production(g, ci, int(r["c"]) - 1, int(r["pind"])))] += 1
    return out


def test_every_production_covered():
    """PLAN §5: every (family, pind) production, including the -inf returns."""
    seen = _productions(FX["sq_sp"]) + _productions(FX["bl_sp"])
    prods = {p for (_, _, p) in seen}
    assert prods == ALL_PRODUCTIONS
    fam = {(t, pind, p) for (t, pind, p) in seen}
    # hierarchy family: pind 1-3 incl. rootchain, domtreeflat and both -inf cases
    hier = {(pind, p) for (t, pind, p) in fam if "hierarchy" in t or "domtree" in t}
    assert {(1, "hierarchy"), (2, "chain"), (2, "rootchain"), (2, None), (3, "domtreeflat"),
            (3, None)} <= hier
    assert {(1, "tree"), (2, "treever2"), (2, None)} <= {(pind, p) for (t, pind, p) in fam
                                                        if t == "tree"}
    # 'ordernoself' is in the pind-2 list (split_node.m:31) but has prodcount 1
    # (makeemptygraph.m), so only pind 1 is ever used for it
    assert ("order", 1, "chain") in fam and ("ordernoself", 1, "chain") in fam
    assert {t for (t, _, p) in fam if p == "ring"} >= {"ring", "dirring", "undirringnoself"}
    assert {t for (t, _, p) in fam if p == "partition"} == {"partition", "partitionnoself"}
    assert {t for (t, _, p) in fam if p == "connected"} == {"connected", "connectednoself"}


def test_ring_first_split_two_cycle():
    """A one-node ring splits into the 2-cycle c -> c+1 -> c (split_node.m:103-106)."""
    ps = _ps(name="ring", nobj=4)
    g, c1, c2 = split_node(makeemptygraph(ps), 0, 0, 1, [0, 1], [2, 3], ps)
    np.testing.assert_array_equal(g.components[0].adj, [[0, 1], [1, 0]])
    np.testing.assert_array_equal(g.components[0].z, [0, 0, 1, 1])
    assert (c1, c2) == (0, 1) and g.components[0].edgecountsym == 1
    ps = _ps(name="chain", nobj=4)
    g, _, _ = split_node(makeemptygraph(ps), 0, 0, 1, [0, 1], [2, 3], ps)
    np.testing.assert_array_equal(g.components[0].adj, [[0, 1], [0, 0]])
    ones = [r for r in FX["sq_sp"] if not r["isinf"]
            and graph_from_mat(r["graph"]).components[_comp(r["compind"])].type == "ring"
            and graph_from_mat(r["graph"]).components[_comp(r["compind"])].nodecount == 1]
    assert ones  # the Octave sequences include first ring splits (grid/cylinder too)


def test_marker_weight_quirk():
    """KI-17: connected and domtreeflat splits leave raw marker values as weights."""
    hits = Counter()
    for r in list(FX["sq_sp"]) + list(FX["bl_sp"]):
        if r["isinf"]:
            continue
        g = graph_from_mat(r["graph"])
        ci = _comp(r["compind"])
        prod = split_production(g, ci, int(r["c"]) - 1, int(r["pind"]))
        oW = g.components[ci].W
        old = oW.ravel(order="F")[oW.ravel(order="F") > 0]
        if prod not in ("connected", "domtreeflat") or old.size == 0:
            continue
        nW = graph_from_mat(r["out"]).components[ci].W
        new = nW[nW > 0]
        stray = [v for v in new if not np.isclose(old, v).any()
                 and not np.isclose(v, np.median(old))]
        if stray:
            hits[prod] += 1
            assert all(v == round(v) and 1 <= v <= old.size for v in stray)
    assert hits["connected"] >= 5 and hits["domtreeflat"] >= 5, hits


def test_production_not_applicable_returns_none():
    ps = _ps(name="dirhierarchy", nobj=3)
    g = makeemptygraph(ps)
    assert split_node(g, 0, 0, 2, [0], [1, 2], ps) == (None, None, None)  # one node
    assert split_node(g, 0, 0, 3, [0], [1, 2], ps) == (None, None, None)  # no parents
    ps = _ps(name="tree", nobj=3)
    assert split_node(makeemptygraph(ps), 0, 0, 2, [0], [1, 2], ps) == (None, None, None)


def test_unknown_production_raises():
    ps = _ps(name="chain", nobj=3)
    g = makeemptygraph(ps)
    g.components[0].type = "bogus"
    with pytest.raises(FormDiscoveryError, match="Unknown structure"):
        split_node(g, 0, 0, 1, [0], [1, 2], ps)
    assert split_production(g, 0, 0, 2) == "bogus"


def test_inputs_not_mutated():
    r = next(r for r in FX["sq_sp"] if not r["isinf"] and int(r["step"]) > 3)
    g = graph_from_mat(r["graph"])
    before = g.copy()
    ps = _ps(r["prodtied"])
    out, c1, c2 = split_node(g, _comp(r["compind"]), int(r["c"]) - 1, int(r["pind"]),
                             _idx(r["part1"]), _idx(r["part2"]), ps)
    assert graph_equal(g, before)
    e = empty_graph(out, _comp(r["compind"]), c1, c2)
    assert graph_equal(graph_from_mat(r["out"]), out)
    before = e.copy()
    add_element(e, _comp(r["compind"]), c1, 0, ps)
    assert graph_equal(e, before)
    assert isinstance(out, Graph) and isinstance(out.components[0], Component)


# --- live Octave -------------------------------------------------------------------------

def _same(a, b, k):
    if a.dtype == object:
        assert a.shape == b.shape, k
        for x, y in zip(a.ravel(), b.ravel()):
            _same(np.asarray(x), np.asarray(y), k)
    elif a.dtype.names:
        assert a.dtype.names == b.dtype.names, k
        for f in a.dtype.names:
            _same(a[f], b[f], f"{k}.{f}")
    else:
        np.testing.assert_array_equal(a, b, err_msg=k)


@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "split.mat"
    octave.feval("fx_split", str(out), nout=0)
    old = loadmat(FIXTURES_DIR / "split.mat")
    new = loadmat(out)
    for k, v in old.items():
        if not k.startswith("__") and k != "octave_version":
            _same(v, new[k], k)


@pytest.mark.octave
def test_live_fresh_sequences(octave, tmp_path):
    out = tmp_path / "split_live.mat"
    octave.feval("fx_split", str(out), 7919.0, nout=0)
    fx = load_fixture("split_live", fixtures_dir=tmp_path)
    for k, r in enumerate(fx["sq_sp"]):
        check_split(r, f"live sq_sp {k}")
    for k, r in enumerate(fx["sq_eg"]):
        check_empty(r, f"live sq_eg {k}")
    for k, r in enumerate(fx["sq_ae"]):
        check_add(r, f"live sq_ae {k}")
    assert len(fx["sq_sp"]) == 240
