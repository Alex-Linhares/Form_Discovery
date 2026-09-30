"""Item 33 (PLAN §6 phase B): the networkx backend (``viz/networkx_backend.py``):
``to_networkx``/``from_networkx``, GraphML and DOT exports, the ``graphviz_layout`` /
``kamada_kawai_layout`` layouts and ``draw_dot(..., backend='networkx')``.

Fixtures:

- ``tests/octave/fx_viz_networkx.m`` → ``tests/fixtures/viz_networkx.mat``: the 63 final
  baseline graphs with Octave's ``find(graph.adj)`` edge list, ``W``, ``1./W``, the
  undirected pairs of ``adjsym``/``Wsym``, the degrees and ``inv_covariance``'s Laplacian.
- ``tests/fixtures/viz_draw.mat`` (item 32): the real ``draw_dot`` on 83 graphs, with
  Octave's neato layout texts and positions.

The neato layout through ``graphviz_layout`` must give draw_dot's positions exactly
(same Graphviz), except where draw_dot's own parser misplaces nodes (KI-8): the networkx
backend reads whole node names, so there it equals a whole-name parse of Octave's layout.
"""
import math
import re
import subprocess
import warnings

import matplotlib
import networkx as nx
import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.testing.compare import compare_images

import formdiscovery.viz.dot as vdot
from formdiscovery import cli, run
from formdiscovery.io import load_fixture
from formdiscovery.viz import networkx_backend as nxb
from formdiscovery.viz import pygraphviz_backend as pgb
from formdiscovery.viz.draw import (BACKENDS, ProgressFigures, dot_positions, draw_dot,
                                    draw_results, order_positions)
from formdiscovery.viz.graph_draw import GREY
from tests.viz_images import BACKEND_DIRS, IMAGE_CASES, VERSION_FILE, render_case

NX = load_fixture("viz_networkx")
FX = load_fixture("viz_draw")
NG = len(NX["nx_run"])
ND = len(FX["dd_run"])
# draw_dot cases whose Octave positions are wrong because of KI-8 (dot_to_graph's
# substring label matching): label -> number of nodes left without a position
KI8_CASES = {"true synthpartition": 1, "true synthchain": 1, "true synthring": 1,
             "true synthtree": 1, "true synthgrid": 6}

needs_pgv = pytest.mark.skipif(not pgb.have_pygraphviz(), reason="needs pygraphviz")


def _v(a):
    return np.ravel(np.asarray(a, dtype=float))


def _labels(v):
    if isinstance(v, str):
        return [v]
    return [a if isinstance(a, str) else "" for a in np.atleast_1d(v)]


def _graph(k):
    """Graph ``k`` of the fixture as a MATLAB-style dict (``z`` 0-based, -1 missing)."""
    z = _v(NX["nx_z"][k]).astype(int)
    return {"type": str(NX["nx_type"][k]), "objcount": int(NX["nx_objcount"][k]),
            "z": np.where(z > 0, z - 1, -1), "sigma": float(NX["nx_sigma"][k]),
            "adj": np.atleast_2d(NX["nx_adj"][k]) != 0, "W": np.atleast_2d(NX["nx_W"][k]),
            "Wsym": np.atleast_2d(NX["nx_Wsym"][k])}


def _names(k):
    return _labels(NX["nx_names"][k])


def _dd_adj(k):
    return np.atleast_2d(np.asarray(FX["dd_adj"][k], dtype=float))


def whole_name_positions(lay):
    """``{name: (x, y)}`` of the nodes of a neato ``-Tdot`` layout text, matching whole
    node names (a node statement is ``<name> [ ... pos="x,y" ... ]``; edge statements
    have ``--``/``->`` before the bracket)."""
    out = {}
    for m in re.finditer(r"^\s*(\w+)\s*\[(.*?)\];", lay, re.M | re.S):
        p = re.search(r'\bpos="([^"]+)"', m.group(2))
        if p and m.group(1) not in ("graph", "node", "edge"):
            out[m.group(1)] = tuple(float(t) for t in p.group(1).split(","))
    return out


# --- fixture ------------------------------------------------------------------------------

def test_fixture_contents():
    assert NG == 63
    assert list(NX["nx_run"][:3]) == ["feat 2 1", "feat 4 1", "feat 6 1"]
    assert sum(r.startswith("rel") for r in NX["nx_run"]) == 54
    assert "networkx" in BACKENDS


# --- to_networkx against Octave -----------------------------------------------------------

@pytest.mark.parametrize("k", range(NG))
def test_to_networkx_matches_octave(k):
    """Nodes, kinds, labels, cluster ids; edges, ``W`` and ``weight = 1/W`` equal
    Octave's ``find(graph.adj)``, ``W(find(adj))`` and ``1 ./ W`` exactly."""
    g, names = _graph(k), _names(k)
    G = nxb.to_networkx(g, names)
    n, nobj = g["adj"].shape[0], g["objcount"]
    assert G.is_directed()  # graph.adj is one-directional for every form
    assert list(G.nodes) == list(range(n))
    assert G.graph == {"type": g["type"], "objcount": nobj, "sigma": g["sigma"]}
    for i in range(n):
        d = G.nodes[i]
        if i < nobj:
            assert d == {"kind": "object", "label": names[i], "cluster_id": int(g["z"][i])}
        else:
            assert d == {"kind": "cluster", "label": "", "cluster_id": i - nobj}
    ei, ej = _v(NX["nx_ei"][k]).astype(int) - 1, _v(NX["nx_ej"][k]).astype(int) - 1
    oct_edges = {(a, b): (w, ln) for a, b, w, ln in
                 zip(ei, ej, _v(NX["nx_ew"][k]), _v(NX["nx_elen"][k]))}
    assert set(G.edges) == set(oct_edges)
    for (a, b), (w, ln) in oct_edges.items():
        assert G.edges[a, b]["W"] == w
        assert G.edges[a, b]["weight"] == ln
    # row-major edge order, as graph_to_dot writes them
    assert list(G.edges) == sorted(oct_edges)
    # every observed object hangs off its cluster node
    for i in range(nobj):
        if g["z"][i] >= 0:
            assert G.has_edge(nobj + int(g["z"][i]), i)


@pytest.mark.parametrize("k", range(NG))
def test_to_networkx_undirected_laplacian(k):
    """``directed=False``: one edge per ``adjsym`` pair with Octave's ``Wsym``; the
    networkx Laplacian over ``W`` is ``inv_covariance``'s ``L`` and the degrees are
    ``sum(adjsym, 2)``."""
    g = _graph(k)
    G = nxb.to_networkx(g, _names(k), directed=False)
    assert not G.is_directed()
    si, sj = _v(NX["nx_si"][k]).astype(int) - 1, _v(NX["nx_sj"][k]).astype(int) - 1
    pairs = {frozenset((a, b)): w for a, b, w in zip(si, sj, _v(NX["nx_sw"][k]))}
    assert {frozenset(e) for e in G.edges} == set(pairs)
    for e, w in pairs.items():
        assert G.edges[tuple(e)]["W"] == w
    L = nx.laplacian_matrix(G, nodelist=range(len(G)), weight="W").toarray()
    np.testing.assert_allclose(L, np.atleast_2d(NX["nx_L"][k]), rtol=1e-12, atol=1e-14)
    np.testing.assert_array_equal([G.degree(v) for v in range(len(G))],
                                  _v(NX["nx_deg"][k]))


def test_to_networkx_matrix_and_options():
    adj = np.array([[0, 2.0, 0], [2.0, 0, 0.5], [0, 0.5, 1]])
    G = nxb.to_networkx(adj, ["a", None])
    assert not G.is_directed()  # symmetric: draw_dot.m:35
    assert G.graph == {}
    assert [G.nodes[i]["label"] for i in range(3)] == ["a", "", ""]
    assert all(G.nodes[i]["kind"] == "object" and G.nodes[i]["cluster_id"] == -1
               for i in range(3))
    assert set(G.edges) == {(0, 1), (1, 2), (2, 2)}
    assert G.edges[1, 2]["W"] == 0.5 and G.edges[1, 2]["weight"] == 2.0
    D = nxb.to_networkx(adj, directed=True)
    assert D.number_of_edges() == 5
    # undirected: each pair takes the W of its first entry in row-major order
    g = {"type": "ring", "objcount": 2, "z": np.array([0, 0]),
         "adj": np.array([[0, 1], [1, 0]], bool), "W": np.array([[0, 2.0], [3.0, 0]])}
    assert nxb.to_networkx(g, directed=False).edges[0, 1]["W"] == 2.0
    # W == 0 on an edge gives an infinite length; a missing W gives unit weights
    g = {"type": "chain", "objcount": 1, "z": np.array([0]),
         "adj": np.array([[0, 0], [1, 0]], bool), "W": np.zeros((2, 2))}
    assert nxb.to_networkx(g).edges[1, 0]["weight"] == math.inf
    g["W"] = None
    assert nxb.to_networkx(g).edges[1, 0]["W"] == 1.0
    with pytest.raises(ValueError):
        nxb.to_networkx({**g, "W": np.zeros((3, 3))})


def test_to_networkx_graph_dataclass():
    from formdiscovery.io import graph_from_mat
    fx = load_fixture("runmodel")
    rec = list(fx["runs"])[0]
    g = graph_from_mat(rec["out_graph"])
    G = nxb.to_networkx(g, _labels(rec["out_names"]))
    assert G.graph["type"] == g.type and G.graph["objcount"] == g.objcount
    np.testing.assert_array_equal(nx.to_numpy_array(G, nodelist=range(len(G)),
                                                    weight=None) != 0, g.adj)
    assert [G.nodes[i]["cluster_id"] for i in range(g.objcount)] == list(g.z)


# --- round trips --------------------------------------------------------------------------

def _check_roundtrip(r, g, names, directed=True):
    adj = g["adj"] if directed else (g["adj"] | g["adj"].T)
    np.testing.assert_array_equal(r["adj"], adj)
    W = np.where(g["adj"], g["W"], 0.0)
    if not directed:
        W = np.where(adj, np.maximum(W, W.T), 0.0)
    np.testing.assert_array_equal(r["W"], W)
    nobj = g["objcount"]
    n = adj.shape[0]
    assert r["labels"] == names[:nobj] + [""] * (n - nobj)
    assert r["kind"] == ["object"] * nobj + ["cluster"] * (n - nobj)
    assert r["cluster_id"] == [int(c) for c in g["z"]] + list(range(n - nobj))
    assert r["type"] == g["type"] and r["objcount"] == nobj and r["sigma"] == g["sigma"]
    assert r["directed"] == directed


@pytest.mark.parametrize("k", range(NG))
def test_roundtrip_networkx_graphml(k, tmp_path):
    g, names = _graph(k), _names(k)
    _check_roundtrip(nxb.from_networkx(nxb.to_networkx(g, names)), g, names)
    path = tmp_path / "g.graphml"
    nxb.to_graphml(g, path, names)
    _check_roundtrip(nxb.from_graphml(path), g, names)


def test_roundtrip_undirected(tmp_path):
    """``directed=False``: each pair once; the ``W`` of a one-directional ``adj`` is the
    one stored (the other direction is 0)."""
    for k in (0, 5, 20):
        g, names = _graph(k), _names(k)
        G = nxb.to_networkx(g, names, directed=False)
        _check_roundtrip(nxb.from_networkx(G), g, names, directed=False)
        nxb.to_graphml(G, tmp_path / "u.graphml")
        _check_roundtrip(nxb.from_graphml(tmp_path / "u.graphml"), g, names, directed=False)


def test_from_networkx_foreign_graph():
    """Nodes that are not ``0..n-1`` keep ``G``'s order; ``weight`` alone gives
    ``W = 1/weight``; no attributes give ``W = 1``."""
    G = nx.Graph()
    G.add_edge("b", "a", weight=4.0)
    G.add_edge("a", "c")
    r = nxb.from_networkx(G)
    assert r["labels"] == ["", "", ""] and r["kind"] == ["object"] * 3
    np.testing.assert_array_equal(r["W"], [[0, 0.25, 0], [0.25, 0, 1], [0, 1, 0]])
    assert "type" not in r


def test_to_dot_text():
    """The DOT export is plain text (no Graphviz needed): 0-based nodes with ``kind``,
    ``label``, ``cluster_id``; edges with ``W`` and ``len = 1/W``; floats with ``repr``."""
    k = 0
    g, names = _graph(k), _names(k)
    text = nxb.to_dot(g, names=names)
    assert text.startswith("digraph G {\n") and text.endswith("}\n")
    assert f'  type="{g["type"]}";\n' in text
    assert '  0 [kind="object", label="1", cluster_id=%d];\n' % g["z"][0] in text
    edges = re.findall(r"^  (\d+) -> (\d+) \[W=([^,]+), len=([^\]]+)\];$", text, re.M)
    ei, ej = _v(NX["nx_ei"][k]).astype(int) - 1, _v(NX["nx_ej"][k]).astype(int) - 1
    assert sorted((int(a), int(b)) for a, b, _, _ in edges) == sorted(zip(ei, ej))
    W = g["W"]
    for a, b, w, ln in edges:
        assert float(w) == W[int(a), int(b)] and float(ln) == 1.0 / W[int(a), int(b)]
    und = nxb.to_dot(g, directed=False)
    assert und.startswith("graph G {\n") and " -- " in und and " -> " not in und
    # strings are escaped; W == 0 has no len; infinite values are quoted
    G = nx.DiGraph(note='say "hi"\\now')
    G.add_node(0, label='a "b"', kind="object", cluster_id=-1)
    G.add_node(1, label="", kind="cluster", cluster_id=0)
    G.add_edge(1, 0, W=0.0, weight=math.inf)
    t = nxb.to_dot(G)
    assert r'note="say \"hi\"\\now";' in t and r'label="a \"b\""' in t
    assert "1 -> 0 [W=0.0];" in t
    assert nxb._dot_val(math.inf) == '"inf"' and nxb._dot_val(True) == '"true"'


def test_to_dot_writes_file(tmp_path):
    p = tmp_path / "g.dot"
    text = nxb.to_dot(_graph(3), p, _names(3))
    assert p.read_text() == text


@needs_pgv
@pytest.mark.parametrize("k", range(NG))
def test_roundtrip_dot(k, tmp_path):
    g, names = _graph(k), _names(k)
    _check_roundtrip(nxb.from_dot(nxb.to_dot(g, names=names)), g, names)


@needs_pgv
def test_to_dot_is_valid_graphviz():
    """Graphviz lays the export out, reading ``len``."""
    import pygraphviz
    A = pygraphviz.AGraph(string=nxb.to_dot(_graph(2), names=_names(2)))
    A.layout(prog="neato")
    assert all(n.attr["pos"] for n in A.nodes())


# --- layout -------------------------------------------------------------------------------

def test_whole_name_parser():
    """The test's whole-name parse of a layout text (checked against pygraphviz where
    installed) and ``dot_to_graph`` agree on the graphs KI-8 does not touch."""
    lay = FX["dd_lay"][0]
    pts = whole_name_positions(lay)
    _, names, _, _ = vdot.dot_to_graph(lay)
    assert set(pts) == set(names)
    if pgb.have_pygraphviz():
        import pygraphviz
        for k in range(ND):
            A = pygraphviz.AGraph(string=FX["dd_lay"][k])
            ref = {str(v): tuple(float(t) for t in v.attr["pos"].split(","))
                   for v in A.nodes() if v.attr.get("pos")}
            assert whole_name_positions(FX["dd_lay"][k]) == ref


def _octave_raw_parse(lay, monkeypatch):
    """``dot_to_graph``'s raw (unnormalised) positions."""
    monkeypatch.setattr(vdot, "normalise_xy", lambda x, y: (x, y))
    _, names, x, y = vdot.dot_to_graph(lay)
    monkeypatch.undo()
    return dict(zip(names, zip(x, y)))


@pytest.mark.parametrize("k", range(ND))
def test_ki8_in_draw_dot_layouts(k, monkeypatch):
    """KI-8 measured on the real draw_dot layouts: Octave's parser misplaces nodes in
    exactly the 5 synthetic true graphs (46-89 nodes); in each, some nodes keep raw
    position ``(0, 0)`` (node ``41``'s line also matches ``4``), which moves the
    normalisation of every node. Elsewhere it equals the whole-name parse."""
    lay = FX["dd_lay"][k]
    raw, pts = _octave_raw_parse(lay, monkeypatch), whole_name_positions(lay)
    wrong = [s for s in raw if tuple(raw[s]) != pts[s]]  # nodes in some edge
    unset = [s for s in raw if raw[s][0] == 0]
    run_ = FX["dd_run"][k]
    if run_ in KI8_CASES:
        assert len(unset) == KI8_CASES[run_] and "41" in unset
        assert len(wrong) == 2 * len(unset)
    else:
        assert wrong == [] and unset == []


def _nx_expected(k, pos=None):
    """draw_dot's positions from a whole-name parse of Octave's layout."""
    adj = _dd_adj(k)
    edges, order = nxb._dot_order(adj > 0, vdot.adj_is_directed(adj))
    pts = whole_name_positions(FX["dd_lay"][k])
    names = [str(v + 1) for v in order]
    x, y = vdot.normalise_xy([pts[s][0] for s in names], [pts[s][1] for s in names])
    return order_positions(names, x, y, adj.shape[0], pos)


@pytest.mark.parametrize("k", range(ND))
def test_dot_order_is_dot_to_graphs(k):
    """``_dot_order`` lists the nodes in ``dot_to_graph``'s order (first appearance in
    graph_to_dot's edges)."""
    adj = _dd_adj(k)
    _, order = nxb._dot_order(adj > 0, vdot.adj_is_directed(adj))
    _, names, _, _ = vdot.dot_to_graph(FX["dd_lay"][k])
    assert [str(v + 1) for v in order] == names


@needs_pgv
@pytest.mark.parametrize("k", range(ND))
def test_neato_layout_parity(k):
    """``graphviz_layout(prog='neato')`` with draw_dot's attributes gives Octave's neato
    points exactly: draw_dot's ``xret/yret`` and graph_draw's ``X/Y`` on the 78 graphs
    KI-8 does not touch, the whole-name positions on the other 5."""
    adj = _dd_adj(k)
    n = adj.shape[0]
    args = {} if FX["dd_run"][k] != "pos" else \
        {"pos": np.vstack([_v(FX["dd_x"][k]), _v(FX["dd_y"][k])])}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        got = order_positions(*nxb.nx_layout(adj, "neato"), n, **args)
    exp = _nx_expected(k, **args)
    for a, b in zip(got[:4], exp[:4]):
        np.testing.assert_array_equal(a, b)
    assert got[4] == exp[4]
    if FX["dd_run"][k] not in KI8_CASES:
        np.testing.assert_array_equal(got[0], _v(FX["dd_xret"][k]))
        np.testing.assert_array_equal(got[1], _v(FX["dd_yret"][k]))
        np.testing.assert_array_equal(got[2], _v(FX["dd_x"][k]))
        np.testing.assert_array_equal(got[3], _v(FX["dd_y"][k]))
    else:
        assert not np.array_equal(got[0], _v(FX["dd_xret"][k]))


@needs_pgv
def test_neato_layout_equals_pygraphviz_backend():
    """Same positions as the pygraphviz backend wherever KI-8 does not apply."""
    for k in range(0, ND, 7):
        adj = _dd_adj(k)
        if FX["dd_run"][k] in KI8_CASES:
            continue
        a = order_positions(*nxb.nx_layout(adj, "neato"), adj.shape[0])
        _, lay, _ = pgb.layout_text(adj, engine="pygraphviz")
        b = dot_positions(lay, adj.shape[0])
        for u, v in zip(a[:4], b[:4]):
            np.testing.assert_array_equal(u, v)


@pytest.mark.parametrize("k", [0, 2, 13, 19, 23, ND - 1])
def test_kamada_kawai_layout(k):
    """Deterministic, in draw_dot's order, normalised to ``[0.05, 0.95]`` with the
    KI-34 x range; graph distance tracks drawn distance."""
    adj = _dd_adj(k)
    names, x, y = nxb.nx_layout(adj, "kamada_kawai")
    names2, x2, y2 = nxb.nx_layout(adj, "kamada_kawai")
    np.testing.assert_array_equal(x, x2)
    np.testing.assert_array_equal(y, y2)
    _, order = nxb._dot_order(adj > 0, vdot.adj_is_directed(adj))
    assert names == [str(v + 1) for v in order]
    assert x.min() == pytest.approx(0.05) and y.min() == pytest.approx(0.05)
    assert y.max() == pytest.approx(0.95) and x.max() < 0.95
    # Spearman correlation of hop distance and drawn distance
    G = nx.Graph()
    G.add_edges_from(zip(*np.nonzero(adj > 0)))
    idx = [int(s) - 1 for s in names]
    sp = dict(nx.all_pairs_shortest_path_length(G))
    hop, dst = [], []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if idx[b] in sp[idx[a]]:
                hop.append(sp[idx[a]][idx[b]])
                dst.append(math.hypot(x[a] - x[b], (y[a] - y[b])))
    from scipy.stats import spearmanr
    assert spearmanr(hop, dst).statistic > 0.8


def test_layout_errors_and_auto(monkeypatch):
    with pytest.raises(ValueError, match="no edges"):
        nxb.nx_layout(np.zeros((3, 3)))
    with pytest.raises(ValueError, match="layout"):
        nxb.nx_layout(np.ones((2, 2)), "spring")
    with pytest.raises(ValueError, match="-x"):
        nxb.nx_layout(_dd_adj(ND - 1), "neato", flags="intended")
    monkeypatch.setattr(nxb, "have_graphviz_layout", lambda: False)
    adj = _dd_adj(0)
    np.testing.assert_array_equal(nxb.nx_layout(adj)[1],
                                  nxb.nx_layout(adj, "kamada_kawai")[1])


# --- drawing ------------------------------------------------------------------------------

def _ax():
    return Figure(figsize=(5.6, 4.2)).add_subplot()


def test_draw_networkx_artists():
    """Grey self-loop nodes, no self-loop edges, one arrow per off-diagonal entry
    (KI-37) or one line per symmetric pair with ``undirected='lines'``."""
    k = list(FX["dd_run"]).index("selfloops")
    adj = (_dd_adj(k) > 0).astype(float)
    n = adj.shape[0]
    x, y = _v(FX["dd_x"][k]), _v(FX["dd_y"][k])
    G, h = nxb.draw_networkx(adj, _labels(FX["dd_labels"][k]), x, y, ax=_ax())
    fc = h["nodes"].get_facecolor()
    for i in range(n):
        assert (tuple(fc[i][:3]) == GREY) == bool(adj[i, i])
    off = int(np.sum(adj != 0) - np.trace(adj != 0))
    assert G.number_of_edges() == off == len(h["edges"])
    np.testing.assert_array_equal(h["nodes"].get_offsets(), np.column_stack([x, y]))
    assert [t.get_text() for t in h["labels"].values()] == _labels(FX["dd_labels"][k])
    k = list(FX["dd_run"]).index("undirected")
    adj = (_dd_adj(k) > 0).astype(float)
    G, h = nxb.draw_networkx(adj, _labels(FX["dd_labels"][k]), _v(FX["dd_x"][k]),
                             _v(FX["dd_y"][k]), ax=_ax(), undirected="lines")
    npair = int(np.sum(np.triu(adj, 1) * np.tril(adj, -1).T != 0))
    assert npair > 0 and len(h["lines"].get_segments()) == npair
    assert len(h["edges"]) == G.number_of_edges() - 2 * npair
    with pytest.raises(ValueError):
        nxb.draw_networkx(adj, [""] * len(adj), x, y, ax=_ax(), undirected="x")


def test_draw_dot_networkx_kamada_kawai():
    """The facade returns MATLAB's ``(xret, yret, labels)`` from the networkx layout."""
    k = list(FX["dd_run"]).index("singletons")
    adj = _dd_adj(k)
    labels = _labels(FX["dd_labels_in"][k]) if len(np.atleast_1d(FX["dd_labels_in"][k])) \
        else None
    ax = _ax()
    xr, yr, lab = draw_dot(adj, labels, backend="networkx", layout="kamada_kawai", ax=ax)
    exp = order_positions(*nxb.nx_layout(adj, "kamada_kawai"), adj.shape[0])
    np.testing.assert_array_equal(xr, exp[0])
    np.testing.assert_array_equal(yr, exp[1])
    assert np.sum(xr == 0.05) >= 1  # the singletons, lower left
    assert len(ax.collections[0].get_offsets()) == adj.shape[0]
    with pytest.raises(ValueError, match="backend"):
        draw_dot(adj, backend="bokeh")


@needs_pgv
@pytest.mark.parametrize("run_", ["true demo_chain_feat", "feat 6 3", "rel 10 4",
                                  "nolabels", "singletons", "selfloops", "pos",
                                  "nodemult", "fontsz", "spacepad"])
def test_draw_dot_networkx_is_octaves(run_):
    """``draw_dot(..., backend='networkx')`` returns Octave's draw_dot outputs."""
    k = list(FX["dd_run"]).index(run_)
    a = {str(x): v for x, v in zip(*[iter(np.atleast_1d(FX["dd_args"][k]))] * 2)} \
        if isinstance(FX["dd_args"][k], (list, np.ndarray)) else {}
    kw = {}
    if "pos" in a:
        kw["pos"] = np.asarray(a["pos"], dtype=float)
    if "nodemult" in a:
        kw["nodemult"] = float(a["nodemult"])
    if "fontsz" in a:
        kw["fontsz"] = float(a["fontsz"])
    lab_in = FX["dd_labels_in"][k]
    labels = None if run_ == "nolabels" else _labels(lab_in)
    ax = _ax()
    xr, yr, lab = draw_dot(_dd_adj(k), labels, backend="networkx", layout="neato", ax=ax,
                           **kw)
    np.testing.assert_array_equal(xr, _v(FX["dd_xret"][k]))
    np.testing.assert_array_equal(yr, _v(FX["dd_yret"][k]))
    assert lab == _labels(FX["dd_labels_out"][k])
    np.testing.assert_array_equal(ax.collections[0].get_offsets(),
                                  np.column_stack([_v(FX["dd_x"][k]), _v(FX["dd_y"][k])]))


@pytest.mark.parametrize("name", list(IMAGE_CASES))
def test_image_regression_networkx(name, tmp_path):
    """The networkx drawing at Octave's positions against its own baselines
    (``tests/baseline_images/networkx/``), with the tolerances of item 32."""
    same = VERSION_FILE.read_text().strip() == matplotlib.__version__
    bdir = BACKEND_DIRS["networkx"]
    for suffix, text, tol in (("_notext", False, 2), ("", True, 2 if same else 15)):
        out = tmp_path / f"{name}{suffix}.png"
        render_case(FX, name, out, text=text, backend="networkx")
        err = compare_images(str(bdir / f"{name}{suffix}.png"), str(out), tol=tol,
                             in_decorator=True)
        assert err is None, err


def test_networkx_differs_from_graph_draw_render(tmp_path):
    """The two backends' baselines are distinct images (the per-backend sets are not
    copies)."""
    name = "feat_tree_demo_tree_feat"
    err = compare_images(str(BACKEND_DIRS["pygraphviz"] / f"{name}_notext.png"),
                         str(BACKEND_DIRS["networkx"] / f"{name}_notext.png"), tol=2,
                         in_decorator=True)
    assert err is not None


# --- progress figures, results, CLI -------------------------------------------------------

def _results(tmp_path):
    fx = load_fixture("runmodel")
    res = run.MasterResults()
    ps = run.masterrun_ps()
    from formdiscovery.io import graph_from_mat
    for rec in list(fx["runs"])[:2]:
        g = graph_from_mat(rec["out_graph"])
        s, d = int(rec["sind"]) - 1, int(rec["dind"]) - 1
        summ = {"structure": ps.structures[s], "data": ps.data[d], "sind": s, "dind": d,
                "rind": 1, "seed": None, "ll": float(rec["out_ll"]), "seconds": 0.0,
                **run.graph_summary(g)}
        res.store(s, d, 1, ps, float(rec["out_ll"]), g, _labels(rec["out_names"]),
                  np.empty((0, 0), dtype=object), summ)
    path = tmp_path / "res"
    run.save_results(res, path, ps)
    return path


def test_progress_figures_networkx(tmp_path):
    pf = ProgressFigures(outdir=tmp_path, backend="networkx", layout="kamada_kawai",
                         strict=True)
    pf("postclean", _dd_adj(0), [" "] * len(_dd_adj(0)), "chain")
    assert pf.calls[0][:3] == ("postclean", 2, "chain")
    assert pf.calls[0][3].stat().st_size > 1000


def test_draw_results_networkx(tmp_path):
    res = run.load_results(_results(tmp_path))
    fig = draw_results(res, path=tmp_path / "r.png", backend="networkx",
                       layout="kamada_kawai")
    assert len(fig.axes) == 2 and (tmp_path / "r.png").stat().st_size > 1000


def test_cli_draw_networkx(tmp_path):
    path = _results(tmp_path)
    out = tmp_path / "fig.png"
    assert cli.main(["draw", str(path) + ".json", "--out", str(out), "--backend",
                     "networkx", "--layout", "kamada_kawai", "-q"]) == 0
    assert out.read_bytes()[:4] == b"\x89PNG"
    r = subprocess.run(["python", "-m", "formdiscovery", "draw", "--help"],
                       capture_output=True, text=True,
                       env={**__import__("os").environ, "PYTHONPATH": "src"})
    assert r.returncode == 0 and "--backend" in r.stdout and "kamada_kawai" in r.stdout


# --- live Octave --------------------------------------------------------------------------

@pytest.mark.octave
def test_viz_networkx_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "viz_networkx.mat"
    octave.feval("fx_viz_networkx", str(out), nout=0)
    new = load_fixture(out.name, fixtures_dir=tmp_path)
    assert list(new["nx_run"]) == list(NX["nx_run"])
    for key in ("nx_adj", "nx_W", "nx_Wsym", "nx_ei", "nx_ej", "nx_ew", "nx_elen", "nx_si",
                "nx_sj", "nx_sw", "nx_L", "nx_deg", "nx_z"):
        for a, b in zip(new[key], NX[key]):
            np.testing.assert_array_equal(a, b)
