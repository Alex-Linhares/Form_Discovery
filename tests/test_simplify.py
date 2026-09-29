"""Parity of ``graph.simplify_graph`` (+ ``redundantinds``) and ``graph.subtreeattach``
(item 13, L2-a3) with Octave.

The fixture ``tests/fixtures/simplify.mat`` comes from ``tests/octave/fx_simplify.m``
(regenerate with ``python tools/gen_fixtures.py simplify``). It has three parts:

- ``gh``: every ``bestgraph`` of the baseline growth histories simplified with
  ``cleanstrong`` 0 and 1.
- ``sq``/``st``: seeded split sequences for the 26 single-component names and grid/cylinder;
  "dirty" variants (members of a node moved away, two nodes emptied) simplified under
  cs0/feat, cs1/feat, cs0/rel and, for trees, cs0/fixedall and cs0/fixedinternal; tree and
  hierarchy regrafts (``subtreeattach`` with ``objflag`` 0 and 1, the parentless no-op),
  each followed by ``simplify_graph`` with ``cleanstrong`` 0 and 1.
- ``bl_*``: calls captured by spies while re-running baseline runs (chain, ring, two tree
  runs, four relational hierarchy runs).

Fixture values are 1-based; the port is 0-based (``CONVENTIONS.md``).
"""

from collections import Counter

import numpy as np
import pytest
from scipy.io import loadmat

import formdiscovery.graph as fg
from formdiscovery import FormDiscoveryError
from formdiscovery.graph import (Component, Graph, makeemptygraph, simplify_graph, split_node,
                                 subtreeattach)
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, load_fixture
from formdiscovery.params import Params
from tests.helpers import assert_graph_equal, graph_equal

FX = load_fixture("simplify")
PS = Params.default()


def _ps(r):
    ps = PS.replace(cleanstrong=int(r["cleanstrong"]), prodtied=int(r["prodtied"]),
                    fixedall=int(r["fixedall"]), fixedinternal=int(r["fixedinternal"]),
                    fixedexternal=int(r["fixedexternal"]))
    ps.runps.type = str(r["rtype"])
    return ps


def _ps_attach(r, cs=0):
    ps = PS.replace(cleanstrong=cs, prodtied=int(r["prodtied"]))
    ps.runps.type = "feat"
    return ps


def check_simplify(r, msg):
    g = graph_from_mat(r["graph"])
    out = simplify_graph(g, _ps(r))
    assert_graph_equal(out, r["out"], msg=f"{msg} ({g.type})")
    return g, out


def check_attach(r, msg):
    """Compare one subtreeattach call; returns the output, or ``None`` when Octave raised
    (then the port must raise the same error)."""
    g = graph_from_mat(r["graph"])
    ci = int(r["comp"]) - 1
    j, ep, ec = int(r["j"]) - 1, int(r["edgep"]) - 1, int(r["edgec"]) - 1
    if np.size(r["err"]):
        with pytest.raises(FormDiscoveryError, match=str(r["err"])):
            subtreeattach(g, j, ep, ec, ci, _ps_attach(r), objflag=int(r["objflag"]))
        return None
    out = subtreeattach(g, j, ep, ec, ci, _ps_attach(r), objflag=int(r["objflag"]))
    assert_graph_equal(out, r["out"], msg=f"{msg} ({g.components[ci].type})")
    return out


class CaseCounter:
    """Wrap ``graph.redundantinds`` and count the cases that removed nodes."""

    def __init__(self, monkeypatch):
        self.hits = Counter()
        orig = fg.redundantinds

        def spy(caseind, graph, i, adj, W, z, occ, ps):
            res = orig(caseind, graph, i, adj, W, z, occ, ps)
            if len(res[3]) < adj.shape[0]:
                ctype = graph.components[i].type
                fam = "tree" if ctype == "tree" else "other"
                self.hits[(caseind, fam, bool(ps.cleanstrong))] += 1
            return res
        monkeypatch.setattr(fg, "redundantinds", spy)


# --- growth histories --------------------------------------------------------------------

def test_growth_history_graphs():
    assert len(FX["gh_file"]) == 73
    assert len(FX["gh"]) >= 200
    changed = 0
    for k, r in enumerate(FX["gh"]):
        g, out = check_simplify(r, f"gh {k} ({FX['gh_file'][int(r['file']) - 1]})")
        changed += not graph_equal(g, out)
    assert changed >= 5   # e.g. tree roots removed with cleanstrong 1


# --- seeded sequences --------------------------------------------------------------------

@pytest.mark.parametrize("seq", range(30))
def test_simplify_sequences(seq):
    recs = [r for r in FX["sq"] if int(r["seq"]) == seq + 1]
    assert recs
    for r in recs:
        check_simplify(r, f"{FX['sq_name'][seq]} step {int(r['step'])} variant "
                          f"{int(r['variant'])} cs{int(r['cleanstrong'])}/{r['rtype']}")


def test_subtreeattach_sequences():
    assert len(FX["st"]) >= 80
    for k, r in enumerate(FX["st"]):
        msg = f"st {k} ({FX['sq_name'][int(r['seq']) - 1]}, objflag {int(r['objflag'])})"
        assert np.size(r["err"]) == 0, msg
        out = check_attach(r, msg)
        for cs in (0, 1):
            assert_graph_equal(simplify_graph(out, _ps_attach(r, cs)), r[f"simp{cs}"],
                               msg=f"{msg} simplify cs{cs}")


def test_subtreeattach_coverage():
    """Tree and hierarchy regrafts onto edges and nodes, objects and subtrees, no-ops."""
    seen = Counter()
    for r in list(FX["st"]) + list(FX["bl_st"]):
        g = graph_from_mat(r["graph"])
        t = g.components[int(r["comp"]) - 1].type
        noop = graph_equal(g, r["out"])
        seen[("tree" if t == "tree" else "hier", int(r["objflag"]), noop)] += 1
    for key in [("tree", 0, False), ("tree", 1, False), ("hier", 0, False),
                ("hier", 1, False), ("tree", 0, True), ("hier", 0, True)]:
        assert seen[key] >= 2, (key, seen)


# --- spied baseline runs -----------------------------------------------------------------

def test_spied_runs_match_baseline():
    """The spies do not change the runs: final scores equal the committed baselines."""
    feat = loadmat(FIXTURES_DIR / "baseline" / "feat" / "resultsdemo.mat")["modellike"]
    rel = loadmat(FIXTURES_DIR / "baseline" / "rel" / "resultsdemo.mat")["modellike"]
    assert len(FX["bl_run"]) == 8
    for r in range(8):
        s, d = int(FX["bl_sind"][r]), int(FX["bl_dind"][r])
        want = (feat if d <= 3 else rel)[s - 1, d - 1]
        np.testing.assert_allclose(FX["bl_ll"][r], want, rtol=1e-10, err_msg=FX["bl_run"][r])


def test_simplify_baseline_calls():
    assert len(FX["bl_sg"]) >= 100
    for k, r in enumerate(FX["bl_sg"]):
        g, out = check_simplify(r, f"bl_sg {k} ({FX['bl_run'][int(r['run']) - 1]})")
        assert graph_equal(g, out) != bool(r["changed"])
    assert {int(r["cleanstrong"]) for r in FX["bl_sg"] if r["changed"]} == {0, 1}


def test_subtreeattach_baseline_calls():
    assert {int(r["objflag"]) for r in FX["bl_st"]} == {0, 1}
    for k, r in enumerate(FX["bl_st"]):
        check_attach(r, f"bl_st {k} ({FX['bl_run'][int(r['run']) - 1]})")


# --- coverage and quirks -----------------------------------------------------------------

def test_every_case_covered(monkeypatch):
    """All three redundantinds cases fire, for trees and other types, cleanstrong 0/1."""
    cc = CaseCounter(monkeypatch)
    for r in list(FX["sq"]) + list(FX["gh"]) + list(FX["bl_sg"]):
        simplify_graph(graph_from_mat(r["graph"]), _ps(r))
    for case in (1, 2, 3):
        for fam in ("tree", "other"):
            assert cc.hits[(case, fam, False)] + cc.hits[(case, fam, True)] > 0, \
                (case, fam, cc.hits)
    assert cc.hits[(2, "tree", True)] > 0 and cc.hits[(2, "tree", False)] > 0


def test_tree_root_kept_unless_cleanstrong():
    """Case 2 on a tree removes the two-child root only with ps.cleanstrong."""
    ps = PS.replace()
    ps.runps.structname, ps.runps.nobjects, ps.runps.type = "tree", 4, "feat"
    g, _, _ = split_node(makeemptygraph(ps), 0, 0, 1, [0, 1], [2, 3], ps)
    assert g.components[0].nodecount == 3
    assert graph_equal(simplify_graph(g, ps.replace(cleanstrong=0)), g)
    out = simplify_graph(g, ps.replace(cleanstrong=1))
    assert out.components[0].nodecount == 2
    np.testing.assert_array_equal(out.components[0].adj, [[0, 1], [0, 0]])


def test_rel_and_fixed_disable_case3(monkeypatch):
    cc = CaseCounter(monkeypatch)
    for r in FX["sq"]:
        if str(r["rtype"]) == "rel" or int(r["fixedall"]) or int(r["fixedinternal"]):
            g = graph_from_mat(r["graph"])
            if g.components[0].type == "tree" and str(r["rtype"]) == "rel":
                continue   # the tree case 3 ignores runps.type
            simplify_graph(g, _ps(r))
    assert not any(case == 3 for (case, _, _) in cc.hits), cc.hits


def test_unexpected_structure_raises():
    r = next(r for r in FX["st"] if int(r["objflag"]) == 1
             and graph_from_mat(r["graph"]).components[0].type != "tree")
    g = graph_from_mat(r["graph"])
    g.components[0].type = "dirdomtreenoself"   # not in subtreeattach.m's list
    with pytest.raises(FormDiscoveryError, match="unexpected structure"):
        subtreeattach(g, int(r["j"]) - 1, int(r["edgep"]) - 1, int(r["edgec"]) - 1, 0,
                      _ps_attach(r), objflag=1)


def test_inputs_not_mutated():
    r = next(r for r in FX["st"] if int(r["objflag"]) == 1
             and graph_from_mat(r["graph"]).components[0].type == "tree")
    g = graph_from_mat(r["graph"])
    before = g.copy()
    out = subtreeattach(g, int(r["j"]) - 1, int(r["edgep"]) - 1, int(r["edgec"]) - 1, 0,
                        _ps_attach(r), objflag=1)
    assert graph_equal(g, before)
    before = out.copy()
    s = simplify_graph(out, _ps_attach(r, 1))
    assert graph_equal(out, before)
    assert isinstance(s, Graph) and isinstance(s.components[0], Component)


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
    out = tmp_path / "simplify.mat"
    octave.feval("fx_simplify", str(out), nout=0)
    old = loadmat(FIXTURES_DIR / "simplify.mat")
    new = loadmat(out)
    for k, v in old.items():
        if not k.startswith("__") and k != "octave_version":
            _same(v, new[k], k)


@pytest.mark.octave
def test_live_fresh_sequences(octave, tmp_path):
    out = tmp_path / "simplify_live.mat"
    octave.feval("fx_simplify", str(out), 7919.0, nout=0)
    fx = load_fixture("simplify_live", fixtures_dir=tmp_path)
    for k, r in enumerate(fx["sq"]):
        check_simplify(r, f"live sq {k}")
    for k, r in enumerate(fx["st"]):
        if check_attach(r, f"live st {k}") is None:
            continue
        for cs in (0, 1):
            assert_graph_equal(simplify_graph(graph_from_mat(r["out"]), _ps_attach(r, cs)),
                               r[f"simp{cs}"], msg=f"live st {k} simplify cs{cs}")


@pytest.mark.octave
def test_live_unexpected_structure_errors_in_octave(octave):
    """Octave errors on the same subtreeattach input the port rejects."""
    octave.eval("ps = defaultps(setps()); ps.runps.structname = 'dirdomtreenoself';"
                "ps.runps.nobjects = 3; ps.runps.type = 'feat'; g = makeemptygraph(ps);",
                nout=0)
    with pytest.raises(Exception, match="unexpected structure"):
        octave.eval("subtreeattach(g, 1, 1, 1, 1, ps, 'objflag', 1);", nout=0)
    ps = PS.replace()
    ps.runps.structname, ps.runps.nobjects, ps.runps.type = "dirdomtreenoself", 3, "feat"
    with pytest.raises(FormDiscoveryError, match="unexpected structure"):
        subtreeattach(makeemptygraph(ps), 0, 0, 0, 0, ps, objflag=1)
