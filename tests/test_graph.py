"""Parity of ``formdiscovery.graph`` (item 11, L2-a1) with Octave.

The fixture ``tests/fixtures/graph.mat`` comes from ``legacy/tests_octave/fx_graph.m`` (regenerate
with ``python legacy/tools/gen_fixtures.py graph``). It holds ``makeemptygraph`` for the 24
``ps.structures`` names (grid and cylinder included) plus the four extra domtree names, with
1 and 5 objects; ``combinegraphs`` with ``zonly`` 0/1 on every graph of the baseline growth
histories; grid/cylinder products built from baseline chain/ring components (``zonly`` and
``prodtied`` 0/1, and a missing-object variant); and every ``combinegraphs`` call made
while growing grid/cylinder/chain/ring/tree graphs by seeded ``split_node`` sequences
(captured by a spy, so the ``origgraph``/``compind``/``imap`` inputs are the real ones),
with ``prodtied`` 0 and 1. Graphs are compared with ``tests.helpers.graph_diff``.
"""

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.graph import GRAPH_FIELDS, Graph, combinegraphs, makeemptygraph
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, graph_to_mat, load_fixture
from formdiscovery.params import STRUCTURES, Params
from tests.helpers import assert_graph_equal, graph_diff, graph_equal

FX = load_fixture("graph")
PS = Params.default()
EXTRA_NAMES = ("domtree", "dirdomtreenoself", "undirdomtree", "undirdomtreenoself")


def _ps(name=None, nobj=None, prodtied=0):
    ps = PS.replace(prodtied=prodtied)
    ps.runps.structname = name
    ps.runps.nobjects = nobj
    ps.runps.type = "feat"
    return ps


def _captured_calls(fx):
    """Yield ``(i, graph, ps, kwargs, expected)`` for each spied combinegraphs call."""
    for i, (gi, want) in enumerate(zip(fx["cg_in"], fx["cg_out"])):
        kw = dict(zonly=int(fx["cg_zonly"][i]))
        if fx["cg_hasorig"][i]:
            kw.update(origgraph=graph_from_mat(fx["cg_orig"][i]),
                      compind=int(fx["cg_compind"][i]) - 1,
                      imap=np.asarray(fx["cg_imap"][i], dtype=float) - 1)
        yield i, graph_from_mat(gi), _ps(prodtied=int(fx["cg_prodtied"][i])), kw, want


# --- makeemptygraph ----------------------------------------------------------------------

def test_makeemptygraph_names():
    assert list(FX["me_names"]) == list(STRUCTURES) + list(EXTRA_NAMES)
    assert len(STRUCTURES) == 24 and {"grid", "cylinder"} <= set(STRUCTURES)


@pytest.mark.parametrize("k", range(2))
@pytest.mark.parametrize("t", range(len(STRUCTURES) + len(EXTRA_NAMES)))
def test_makeemptygraph(k, t):
    name, nobj = FX["me_names"][t], int(FX["me_nobj"][k])
    g = makeemptygraph(_ps(name, nobj))
    assert_graph_equal(g, FX["me_graphs"][k][t], msg=f"{name} n={nobj}")
    assert g.adj.dtype == bool and g.adjsym.dtype == bool
    assert g.ncomp == (2 if name in ("grid", "cylinder") else 1)
    want_pc = 2 if name == "tree" else 3 if "hierarchy" in name or "domtree" in name else 1
    assert [c.prodcount for c in g.components] == [want_pc] * g.ncomp


def test_makeemptygraph_unknown_raises():
    assert FX["me_bogus_err"] == 1
    with pytest.raises(FormDiscoveryError, match="unknown structure"):
        makeemptygraph(_ps("bogus", 3))


# --- combinegraphs -----------------------------------------------------------------------

@pytest.mark.parametrize("zonly", [0, 1])
def test_combinegraphs_baseline_growth_histories(zonly):
    want = FX["bl_out1"] if zonly else FX["bl_out0"]
    assert len(FX["bl_in"]) == 126
    for i, gi in enumerate(FX["bl_in"]):
        g = combinegraphs(graph_from_mat(gi), PS, zonly=zonly)
        assert_graph_equal(g, want[i], msg=f"{FX['bl_file'][i]} step {FX['bl_step'][i]}")


def test_combinegraphs_baseline_products():
    for i, gi in enumerate(FX["pr_in"]):
        ps = _ps(prodtied=int(FX["pr_prodtied"][i]))
        g = combinegraphs(graph_from_mat(gi), ps, zonly=int(FX["pr_zonly"][i]))
        assert_graph_equal(g, FX["pr_out"][i], msg=f"{FX['pr_name'][i]} case {i}")
        assert g.globinds.shape == tuple(g.compsizes)
    # the missing-object variant: z = -1 kept, W over the observed objects only
    miss = [i for i, n in enumerate(FX["pr_name"]) if n.endswith("missing")]
    assert miss
    g = combinegraphs(graph_from_mat(FX["pr_in"][miss[0]]), PS)
    assert (g.z == -1).sum() == 2 and g.W.shape[0] == g.objcount - 2 + g.adjcluster.shape[0]


def test_combinegraphs_split_sequences():
    n_copy = 0
    for i, g, ps, kw, want in _captured_calls(FX):
        out = combinegraphs(g, ps, **kw)
        assert_graph_equal(out, want, msg=f"call {i} ({FX['cg_seq'][int(FX['cg_seqid'][i]) - 1]})"
                           if FX["cg_seqid"][i] else f"call {i}")
        if "origgraph" in kw and not ps.prodtied and g.ncomp > 1:
            plain = combinegraphs(g, ps, zonly=kw["zonly"])
            n_copy += not np.array_equal(plain.Wcluster, out.Wcluster)
    # the origgraph copy path (l.99-117) changed Wcluster in many product-graph calls
    assert n_copy >= 30
    seqs = list(FX["cg_seq"])
    assert any("prodtied1" in s for s in seqs) and any("prodtied0" in s for s in seqs)


def test_combinegraphs_does_not_mutate_input():
    gi = graph_from_mat(FX["pr_in"][0])
    before = gi.copy()
    combinegraphs(gi, PS)
    assert graph_equal(gi, before)


def test_single_component_globinds_quirk():
    # zeros(compsizes) with a scalar compsizes is n x n; only the first column is used
    g = graph_from_mat(FX["bl_out0"][-1])
    n = int(g.compsizes[0])
    assert g.ncomp == 1 and g.globinds.shape == (n, n)
    np.testing.assert_array_equal(g.globinds[:, 0], np.arange(n))
    assert (g.globinds[:, 1:] == -1).all()


def test_combinegraphs_zonly_needs_matching_wcluster():
    gi = graph_from_mat(FX["pr_in"][0])  # components not combined yet: Wcluster is 1 comp
    assert FX["pr_zonly"][0] == 0
    with pytest.raises(FormDiscoveryError, match="nonconformant"):
        combinegraphs(gi, PS, zonly=1)


def test_combinegraphs_illegal_empty():
    """KI-2: every reachable product graph has empty component ``illegal`` lists."""
    for _, g, ps, kw, want in _captured_calls(FX):
        out = combinegraphs(g, ps, **kw)
        if g.ncomp > 1:
            assert out.illegal.size == 0 and np.size(want["illegal"]) == 0
    # single components keep their list (the tree sequences have internal nodes)
    trees = [graph_from_mat(w) for w in FX["cg_out"] if w["type"] == "tree"]
    assert any(t.illegal.size for t in trees)


def test_combinegraphs_nonempty_illegal_raises():
    """KI-2: Octave drops a first-component list silently and errors on the second."""
    assert FX["ki2_first_isempty"] == 1 and np.size(FX["ki2_first_illegal"]) == 0
    assert FX["ki2_second_err"] == 1 and "illind(0)" in FX["ki2_second_msg"]
    base = combinegraphs(graph_from_mat(FX["pr_in"][0]), PS)
    for i, ill in ((0, [0, 1]), (1, [0])):
        g = base.copy()
        g.components[i].illegal = np.array(ill)
        with pytest.raises(NotImplementedError, match="KI-2"):
            combinegraphs(g, PS)


# --- io and helpers ----------------------------------------------------------------------

def test_graph_mat_roundtrip():
    for d in (FX["cg_out"][50], FX["me_graphs"][0][0], FX["bl_out0"][3]):
        g = graph_from_mat(d)
        assert_graph_equal(graph_from_mat(graph_to_mat(g)), g, rtol=0, atol=0)
    assert set(graph_to_mat(g)) == set(GRAPH_FIELDS)


def test_graph_diff_reports_first_field():
    g = graph_from_mat(FX["cg_out"][50])
    assert graph_diff(g, g.copy()) is None
    h = g.copy()
    h.Wcluster = h.Wcluster * (1 + 1e-13)
    assert graph_equal(g, h)                 # within rtol
    h.z = h.z.copy()
    h.z[3] += 1
    h.components[1].nodemap = h.components[1].nodemap + 1
    d = graph_diff(g, h)
    assert d.startswith("z: 1 entries differ, first at (3,)")   # z comes before components
    h.z = g.z
    assert graph_diff(g, h).startswith("components[1].nodemap")
    assert "shape" in graph_diff(g, g.replace(adj=g.adj[:-1]))
    assert g.type == "cylinder"
    assert graph_diff(g, g.replace(type="grid")) == "type: 'cylinder' vs 'grid'"
    assert graph_diff(Graph(), Graph()) is None


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
    out = tmp_path / "graph.mat"
    octave.feval("fx_graph", str(out), nout=0)
    old = loadmat(FIXTURES_DIR / "graph.mat")
    new = loadmat(out)
    for k, v in old.items():
        if not k.startswith("__") and k != "octave_version":
            _same(v, new[k], k)


@pytest.mark.octave
def test_live_fresh_split_sequences(octave, tmp_path):
    out = tmp_path / "graph_live.mat"
    octave.feval("fx_graph", str(out), 7919.0, nout=0)
    fx = load_fixture("graph_live", fixtures_dir=tmp_path)
    n = 0
    for i, g, ps, kw, want in _captured_calls(fx):
        assert_graph_equal(combinegraphs(g, ps, **kw), want, msg=f"live call {i}")
        n += 1
    assert n > 100
