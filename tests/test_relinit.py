"""Parity of ``graph.relgraphinit`` (+ ``_chooseinithead``/``_growgraph``/``_finishgraph``),
``graph.makelcfreq``, ``graph.filloutrelgraph`` and ``graph.reordermissing`` (item 14, L2-b1)
with Octave.

The fixture ``tests/fixtures/relinit.mat`` comes from ``tests/octave/fx_relinit.m``
(regenerate with ``python tools/gen_fixtures.py relinit``):

- ``ri``: ``relgraphinit`` for the 24 ``ps.structures`` names and the 4 domtree names on the
  7 relational data sets and on seeded random relations, with ``z = 1:n``, one cluster and
  two seeded partitions (output graph or Octave's error message);
- ``lc``: ``makelcfreq`` on the data sets and on non-contiguous labels;
- ``fo``: ``filloutrelgraph`` on order/domtree/connected graphs (``ri`` outputs, seeded
  ``split_node`` sequences, calls spied from baseline runs);
- ``rm``: ``reordermissing`` on the 38 judges chunks for graphs over judges' objects.

Fixture values are 1-based; the port is 0-based (``CONVENTIONS.md``).
"""

from collections import Counter

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.graph import filloutrelgraph, makelcfreq, relgraphinit, reordermissing
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, load_dataset, load_fixture
from formdiscovery.params import DATASETS, Params, setrunps
from formdiscovery.preprocess import scaledata
from tests.helpers import assert_graph_equal, graph_equal

FX = load_fixture("relinit")
PS = Params.default()
NAMES = [str(n) for n in FX["names"]]
RELSETS = ["demo_ring_rel_bin", "demo_hierarchy_rel_bin", "demo_order_rel_freq",
           "mangabeys", "bushcabinet", "kularing", "prisoners"]
_R = {d: load_dataset(d)["R"] for d in RELSETS}


def _rel(r):
    return _R[str(r["dname"])] if np.size(r["dname"]) else np.atleast_2d(r["R"])


def _z0(r):
    return np.asarray(r["z"], dtype=np.int64).ravel() - 1


def _ps_rel(name, n):
    ps = PS.copy()
    ps.runps.structname = name
    ps.runps.nobjects = n
    ps.runps.type = "rel"
    return ps


def _err(r):
    return str(r["err"]) if np.size(r["err"]) else ""


# --- relgraphinit ------------------------------------------------------------------------

def check_ri(r):
    R = _rel(r)
    ps = _ps_rel(str(r["name"]), R.shape[0])
    src = str(r["dname"]) if np.size(r["dname"]) else f"input {int(r['input'])}"
    msg = f"{src} {r['name']} z{int(r['zkind'])}"
    if _err(r):
        with pytest.raises(FormDiscoveryError, match=_err(r)):
            relgraphinit(R, _z0(r), ps)
        return None
    out = relgraphinit(R, _z0(r), ps)
    assert_graph_equal(out, r["out"], msg=msg)
    return out


@pytest.mark.parametrize("name", NAMES)
def test_relgraphinit(name):
    recs = [r for r in FX["ri"] if str(r["name"]) == name]
    assert len(recs) == 20 * 4
    for r in recs:
        check_ri(r)


def test_relgraphinit_coverage():
    assert len(NAMES) == 28 and len(FX["ri"]) == 28 * 20 * 4
    errs = Counter((str(r["name"]), _err(r)) for r in FX["ri"] if _err(r))
    # growgraph errors whenever there are two or more clusters (60 of the 80 inputs)
    for name in ["connected", "connectednoself", "chain", "tree", "grid"]:
        assert errs[(name, "unexpected structure type")] == 60, name
    for name in ["domtree", "dirdomtreenoself", "undirdomtree", "undirdomtreenoself"]:
        assert errs[(name, "init not implemented for domtree")] == 60, name
    ok = [r for r in FX["ri"] if not _err(r)]
    assert {str(r["name"]) for r in ok} == set(NAMES)   # every name works with one cluster
    # every relational name the 'overd' init uses gives a non-empty graph on every data set
    overd = ["dirchain", "dirchainnoself", "dirring", "dirringnoself", "dirhierarchy",
             "dirhierarchynoself", "undirchain", "undirchainnoself", "undirring",
             "undirringnoself", "undirhierarchy", "undirhierarchynoself"]
    for r in ok:
        if str(r["name"]) in overd and int(r["zkind"]) == 1 and np.size(r["dname"]):
            n = _rel(r).shape[0]
            assert np.sum(np.asarray(r["out"]["adjcluster"]) != 0) >= n - 1


def test_relgraphinit_structure():
    """Chains have n-1 edges, rings n, hierarchies are trees with one root, order is a
    chain; the all-zero relation ties everywhere and still grows a full graph."""
    for r in FX["ri"]:
        if _err(r) or int(r["zkind"]) != 1:
            continue
        name = str(r["name"])
        A = np.asarray(r["out"]["adjcluster"]) != 0
        n = A.shape[0]
        if "chain" in name or name in ("order", "ordernoself") or "hierarchy" in name:
            assert A.sum() == n - 1, name
        elif "ring" in name:
            assert A.sum() == n, name
        elif "partition" in name:
            assert A.sum() == 0
    zero = [r for r in FX["ri"] if not np.size(r["dname"]) and np.size(r["R"])
            and not np.any(r["R"]) and str(r["name"]) == "dirchain" and int(r["zkind"]) == 1]
    assert len(zero) == 1
    np.testing.assert_array_equal(np.asarray(zero[0]["out"]["adjcluster"]),
                                  np.eye(6, k=1))  # ties: tail side, first unused node


def test_relgraphinit_no_mutation():
    R = _R["demo_ring_rel_bin"].copy()
    R0 = R.copy()
    z = np.arange(8)
    ps = _ps_rel("undirring", 8)
    ps0 = ps.copy()
    relgraphinit(R, z, ps)
    np.testing.assert_array_equal(R, R0)
    np.testing.assert_array_equal(z, np.arange(8))
    assert repr(ps) == repr(ps0)


# --- makelcfreq --------------------------------------------------------------------------

def test_makelcfreq():
    assert len(FX["lc"]) == 7 * 4 + 6
    nerr = 0
    for k, r in enumerate(FX["lc"]):
        R = _rel(r)
        if int(r["sym"]):
            R = R + R.T
        if _err(r):
            nerr += 1
            with pytest.raises(FormDiscoveryError, match="out of bound"):
                makelcfreq(R, _z0(r))
            continue
        np.testing.assert_array_equal(makelcfreq(R, _z0(r)), np.atleast_2d(r["out"]),
                                      err_msg=f"lc {k}")
    assert nerr == 3


# --- filloutrelgraph ---------------------------------------------------------------------

def test_filloutrelgraph():
    assert len(FX["fo"]) >= 200
    seen = Counter()
    for k, r in enumerate(FX["fo"]):
        g = graph_from_mat(r["graph"])
        out = filloutrelgraph(g)
        assert_graph_equal(out, r["out"], msg=f"fo {k} ({r['src']}, {g.type})")
        seen[(str(r["src"]), g.type, not graph_equal(g, out))] += 1
    for src in ("ri", "sq", "bl"):
        assert any(s == src and ch for (s, _, ch) in seen), src
    for t in ("order", "ordernoself", "domtree", "dirdomtreenoself", "undirdomtree",
              "undirdomtreenoself", "connected", "connectednoself"):
        assert seen[("sq", t, True)] >= 1, t
    for t in ("order", "ordernoself", "connected", "connectednoself"):
        assert seen[("bl", t, True)] >= 1, t


def test_spied_runs_match_baseline():
    """The spy does not change the runs: final scores equal the committed baselines."""
    rel = loadmat(FIXTURES_DIR / "baseline" / "rel" / "resultsdemo.mat")["modellike"]
    assert len(FX["bl_run"]) == 8
    for r in range(8):
        s, d = int(FX["bl_sind"][r]), int(FX["bl_dind"][r])
        np.testing.assert_allclose(FX["bl_ll"][r], rel[s - 1, d - 1], rtol=1e-10,
                                   err_msg=FX["bl_run"][r])


def test_filloutrelgraph_no_mutation():
    g = graph_from_mat(FX["fo"][0]["graph"])
    g0 = g.copy()
    filloutrelgraph(g)
    assert_graph_equal(g, g0)


# --- reordermissing ----------------------------------------------------------------------

def _judges_ps():
    data = load_dataset("judges")
    _, ps = setrunps(data, DATASETS.index("judges"), PS)
    _, ps = scaledata(data, ps)
    return ps


def test_reordermissing():
    graphs = [graph_from_mat(g) for g in FX["rm_graphs"]]
    assert len(FX["rm"]) == len(graphs) * int(FX["rm_chunknum"]) * 2
    for k, r in enumerate(FX["rm"]):
        g = graphs[int(r["graph"]) - 1]
        ps = PS.replace(fixedexternal=int(r["fixedexternal"]))
        obs = np.asarray(r["obsind"], dtype=np.int64).ravel() - 1
        miss = np.asarray(r["missind"], dtype=np.int64).ravel() - 1
        ng, nW = reordermissing(g, r["Wvec"], obs, miss, ps)
        msg = f"rm {k} (graph {int(r['graph'])} {g.type}, chunk {int(r['chunk'])})"
        assert_graph_equal(ng, r["out"], msg=msg)
        np.testing.assert_allclose(nW, np.ravel(r["Wout"]), rtol=1e-10, atol=0, err_msg=msg)


def test_reordermissing_indices_follow_dataprobwsig():
    """obsind/missind in the fixture are what dataprobwsig.m:31-34 builds from the Python
    judges chunks, and the fixture covers graphs with unassigned objects."""
    ps = _judges_ps()
    assert ps.runps.chunknum == int(FX["rm_chunknum"]) == 38
    graphs = [graph_from_mat(g) for g in FX["rm_graphs"]]
    assert sum(np.any(g.z < 0) for g in graphs) >= 3
    for r in FX["rm"]:
        g = graphs[int(r["graph"]) - 1]
        c = int(r["chunk"]) - 1
        these = g.z >= 0
        inchunk = np.zeros(len(g.z), dtype=bool)
        inchunk[ps.runps.objind[c]] = True
        np.testing.assert_array_equal(np.flatnonzero(these & inchunk),
                                      np.asarray(r["obsind"]).ravel() - 1)
        np.testing.assert_array_equal(np.flatnonzero(these & ~inchunk),
                                      np.asarray(r["missind"]).ravel() - 1)
    # some chunks actually move objects
    moved = [r for r in FX["rm"] if np.size(r["missind"])
             and np.max(np.ravel(r["obsind"]), initial=0) > np.min(np.ravel(r["missind"]))]
    assert len(moved) >= 50


def test_reordermissing_errors_and_no_mutation():
    g = graph_from_mat(FX["rm_graphs"][0])
    g0 = g.copy()
    W = np.arange(1.0, g.objcount + 6)
    W0 = W.copy()
    obs = np.arange(0, g.objcount, 2)
    miss = np.arange(1, g.objcount, 2)
    ng, nW = reordermissing(g, W, obs, miss, PS)
    assert_graph_equal(g, g0)
    np.testing.assert_array_equal(W, W0)
    assert not graph_equal(ng, g)
    with pytest.raises(FormDiscoveryError):
        reordermissing(g, W, obs, miss[:-1], PS)


# --- live Octave -------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "relinit.mat"
    octave.eval(f"fx_relinit('{out}');", nout=0)
    new = load_fixture("relinit", fixtures_dir=tmp_path)
    for key in ("ri", "lc", "fo", "rm"):
        assert len(new[key]) == len(FX[key])
    for a, b in zip(new["ri"], FX["ri"]):
        assert _err(a) == _err(b)
        if not _err(a):
            assert_graph_equal(a["out"], b["out"])
    np.testing.assert_allclose(new["bl_ll"], FX["bl_ll"], rtol=1e-12)


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    """Fresh random relations, partitions, split sequences and judges graphs."""
    out = tmp_path / "relinit.mat"
    octave.eval(f"fx_relinit('{out}', 7919);", nout=0)
    new = load_fixture("relinit", fixtures_dir=tmp_path)
    for r in new["ri"]:
        check_ri(r)
    for r in new["lc"]:
        R = _rel(r)
        if int(r["sym"]):
            R = R + R.T
        if _err(r):
            with pytest.raises(FormDiscoveryError):
                makelcfreq(R, _z0(r))
        else:
            np.testing.assert_array_equal(makelcfreq(R, _z0(r)), np.atleast_2d(r["out"]))
    for r in new["fo"]:
        assert_graph_equal(filloutrelgraph(graph_from_mat(r["graph"])), r["out"])
    graphs = [graph_from_mat(g) for g in new["rm_graphs"]]
    for r in new["rm"]:
        ng, nW = reordermissing(graphs[int(r["graph"]) - 1], r["Wvec"],
                                np.ravel(r["obsind"]).astype(np.int64) - 1,
                                np.ravel(r["missind"]).astype(np.int64) - 1,
                                PS.replace(fixedexternal=int(r["fixedexternal"])))
        assert_graph_equal(ng, r["out"])
        np.testing.assert_allclose(nW, np.ravel(r["Wout"]), rtol=1e-10, atol=0)
