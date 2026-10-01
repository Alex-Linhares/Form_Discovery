"""Item 34 (PLAN §6 phase B): the optional interactive backends (``viz/plotly_backend.py``,
``viz/pyvis_backend.py``, ``viz/interactive.py``), ``draw_dot(..., backend='plotly' |
'pyvis')``, ``draw_graph``, the ``draw`` CLI and the demo notebook
(``examples/formdiscovery_demo.ipynb``).

Fixtures:

- ``tests/fixtures/viz_draw.mat`` (``legacy/tests_octave/fx_viz_draw.m``, regenerated in this
  iteration): the real ``draw_dot`` on 83 graphs, with the positions ``X``/``Y`` it gives
  ``graph_draw``, the labels, font size, node colours and every arrow in drawing order.
  Both backends are fed Octave's positions and must draw Octave's nodes (position,
  label, fill) and arrows (same order, same direction).
- ``tests/fixtures/viz_networkx.mat`` (item 33): the 63 final baseline graphs with ``z``
  and names, for the hover text (object → cluster, cluster → members).
- ``tests/fixtures/masterrun.mat`` (item 29): the Octave ``masterrun`` demo, the target
  of the notebook.
- Live (``octave``): the real ``draw_dot`` on the nine final graphs of the Octave
  ``masterrun`` demo; with pygraphviz, ``draw_graph(..., backend='plotly'|'pyvis')``
  places every node where draw_dot does.
"""
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from formdiscovery import cli, run
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.viz import interactive as vi
from formdiscovery.viz import networkx_backend as nxb
from formdiscovery.viz import pygraphviz_backend as pgb
from formdiscovery.viz.draw import (BACKENDS, INTERACTIVE, ProgressFigures, draw_dot,
                                    draw_graph, draw_results, order_positions)
from formdiscovery.viz.graph_draw import edge_segments
from tests.conftest import OCTAVE_TESTS_DIR

go = pytest.importorskip("plotly.graph_objects")
pytest.importorskip("pyvis.network")

from formdiscovery.viz.plotly_backend import draw_plotly, rgb  # noqa: E402
from formdiscovery.viz.pyvis_backend import SCALE, draw_pyvis  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO / "examples" / "formdiscovery_demo.ipynb"
FX = load_fixture("viz_draw")
NX = load_fixture("viz_networkx")
ND = len(FX["dd_run"])
NG = len(NX["nx_run"])

needs_pgv = pytest.mark.skipif(not pgb.have_pygraphviz(), reason="needs pygraphviz")


def _v(a):
    return np.ravel(np.asarray(a, dtype=float))


def _labels(v):
    if isinstance(v, str):
        return [v]
    return [a if isinstance(a, str) else "" for a in np.atleast_1d(v)]


def _adj(k):
    return (np.atleast_2d(np.asarray(FX["dd_adj"][k], dtype=float)) > 0).astype(float)


def _octave_arrows(k):
    return np.asarray(FX["dd_arrows"][k], dtype=float).reshape(-1, 4)


def _octave_pairs(k):
    """The ``(i, j)`` of Octave's arrows, in drawing order: :func:`edge_segments` with
    Octave's half-widths reproduces Octave's arrow end points (checked here again)."""
    segs = edge_segments(_adj(k), FX["dd_x"][k], FX["dd_y"][k], FX["dd_wd"][k])
    got = np.array([[*s[2], *s[3]] for s in segs]).reshape(-1, 4)
    np.testing.assert_allclose(got, _octave_arrows(k), rtol=0, atol=1e-14)
    return [(s[0], s[1]) for s in segs]


def _same_direction(arrow, tail, head):
    """Octave's arrow (start, stop) goes from ``tail`` towards ``head``: it starts nearer
    the tail and stops nearer the head. (It is not exactly parallel to the centre line:
    graph_draw offsets the ends by ``wd_x cos``/``wd_y sin`` of the edge angle.) Coincident
    nodes (KI-8 in synthgrid) give a zero-length arrow."""
    start, stop = np.asarray(arrow[:2]), np.asarray(arrow[2:])
    if not np.any(np.subtract(head, tail)):
        return np.array_equal(start, stop)
    near = lambda p, q, r: np.linalg.norm(p - q) < np.linalg.norm(p - r)  # noqa: E731
    return near(start, tail, head) and near(stop, head, tail)


def _plotly_case(k, **kw):
    return draw_plotly(_adj(k), _labels(FX["dd_labels"][k]), _v(FX["dd_x"][k]),
                       _v(FX["dd_y"][k]), fontsize=float(FX["dd_fontsize"][k]),
                       nodemult=float(FX["dd_nodemult"][k]), **kw)


def _pyvis_case(k, **kw):
    return draw_pyvis(_adj(k), _labels(FX["dd_labels"][k]), _v(FX["dd_x"][k]),
                      _v(FX["dd_y"][k]), fontsize=float(FX["dd_fontsize"][k]), **kw)


def _trace(fig, name):
    return [t for t in fig.data if t.name == name]


# --- shared pieces --------------------------------------------------------------------------

def test_backends_registered():
    assert BACKENDS == ("pygraphviz", "networkx", "plotly", "pyvis")
    assert INTERACTIVE == ("plotly", "pyvis")
    assert vi.have_plotly() and vi.have_pyvis()


def test_edge_sets():
    adj = np.array([[1, 1, 0, 0], [1, 0, 1, 0], [0, 0, 0, 1], [0, 0, 1, 0]], float)
    assert vi.edge_sets(adj) == ([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)], [])
    assert vi.edge_sets(adj, "lines") == ([(1, 2)], [(0, 1), (2, 3)])
    assert vi.edge_sets(np.zeros((3, 3))) == ([], [])
    with pytest.raises(ValueError, match="undirected"):
        vi.edge_sets(adj, "both")


@pytest.mark.parametrize("k", range(ND))
def test_edge_sets_are_graph_draws_arrows(k):
    """``edge_sets`` lists the arrows graph_draw.m draws, in Octave's drawing order."""
    assert vi.edge_sets(_adj(k))[0] == _octave_pairs(k)


def test_default_hover():
    assert vi.default_hover(["a", "", " "]) == ["a<br>node 0", "node 1", "node 2"]
    assert vi.default_hover(["a"], sep="\n") == ["a\nnode 0"]


@pytest.mark.parametrize("k", range(NG))
def test_hover_text_matches_octave_clusters(k):
    """Object hover names Octave's cluster ``z``; a cluster node lists exactly the objects
    Octave assigns to it, and each hangs off it in Octave's ``graph.adj``."""
    z = _v(NX["nx_z"][k]).astype(int)
    oc = int(NX["nx_objcount"][k])
    adj = np.atleast_2d(NX["nx_adj"][k]) != 0
    names = _labels(NX["nx_names"][k])
    g = {"type": str(NX["nx_type"][k]), "objcount": oc, "z": np.where(z > 0, z - 1, -1),
         "adj": adj, "W": np.atleast_2d(NX["nx_W"][k])}
    h = vi.hover_text(g, names)
    assert len(h) == adj.shape[0]
    for i in range(oc):
        name = names[i] if i < len(names) and names[i] else f"object {i}"
        assert h[i] == f"{name}<br>object {i}, cluster {z[i] - 1}"
        assert adj[oc + z[i] - 1, i] or adj[i, oc + z[i] - 1]
    for c in range(adj.shape[0] - oc):
        members = [names[i] if i < len(names) and names[i] else f"object {i}"
                   for i in range(oc) if z[i] - 1 == c]
        assert h[oc + c] == f"cluster {c}<br>members: " + \
            (", ".join(members) if members else "(none)")


def test_hover_text_bare_matrix_and_sep():
    adj = np.array([[0, 1], [0, 0]], float)
    assert vi.hover_text(adj, ["a", "b"], sep="\n") == ["a\nobject 0", "b\nobject 1"]


# --- plotly ---------------------------------------------------------------------------------

@pytest.mark.parametrize("k", range(ND))
def test_plotly_draws_octaves_nodes_and_arrows(k):
    """Every draw_dot case: nodes at Octave's X/Y with Octave's labels and fills, one arrow
    per Octave arrow in drawing order, pointing the same way, from centre to centre."""
    fig = _plotly_case(k)
    nodes, = _trace(fig, "nodes")
    x, y = _v(FX["dd_x"][k]), _v(FX["dd_y"][k])
    np.testing.assert_array_equal(nodes.x, x)
    np.testing.assert_array_equal(nodes.y, y)
    assert list(nodes.text) == _labels(FX["dd_labels"][k])[:len(x)]
    assert list(nodes.marker.color) == [rgb(c) for c in np.atleast_2d(FX["dd_color"][k])]
    assert nodes.textfont.size == pytest.approx(float(FX["dd_fontsize"][k]) * 4 / 3)
    ann = fig.layout.annotations
    pairs = _octave_pairs(k)
    assert len(ann) == len(pairs)
    for a, (i, j), arr in zip(ann, pairs, _octave_arrows(k)):
        assert (a.ax, a.ay, a.x, a.y) == (x[i], y[i], x[j], y[j])
        assert (a.axref, a.ayref) == ("x", "y") and a.showarrow
        assert _same_direction(arr, (x[i], y[i]), (x[j], y[j]))
    lines, = _trace(fig, "lines")
    assert len(lines.x) == 0
    assert list(fig.layout.xaxis.range) == [0, 1] == list(fig.layout.yaxis.range)


def test_plotly_undirected_lines_and_hover():
    k = list(FX["dd_run"]).index("undirected")
    fig = _plotly_case(k)
    assert len(fig.layout.annotations) == int(_adj(k).sum()) == 10  # KI-37: two per pair
    fig = _plotly_case(k, undirected="lines", hover=[f"h{i}" for i in range(5)],
                       node_size=12)
    lines, = _trace(fig, "lines")
    assert len(fig.layout.annotations) == 0 and len(lines.x) == 15  # 5 pairs + None
    nodes, = _trace(fig, "nodes")
    assert list(nodes.hovertext) == [f"h{i}" for i in range(5)]
    assert nodes.marker.size == 12


def test_plotly_selfloops_grey_and_not_edges():
    k = list(FX["dd_run"]).index("selfloops")
    adj = _adj(k)
    fig = _plotly_case(k)
    nodes, = _trace(fig, "nodes")
    grey = [c == "rgb(204,204,204)" for c in nodes.marker.color]
    assert grey == list(np.diag(adj) > 0) and any(grey)
    assert len(fig.layout.annotations) == int(adj.sum() - np.trace(adj))


def test_plotly_subplots_and_errors():
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2)
    adj = np.array([[0, 1], [0, 0]], float)
    draw_plotly(adj, ["a", "b"], [0.1, 0.9], [0.2, 0.8], fig=fig, row=1, col=2)
    a = fig.layout.annotations[-1]
    assert (a.xref, a.yref, a.axref, a.ayref) == ("x2", "y2", "x2", "y2")
    assert fig.data[-1].xaxis == "x2"
    with pytest.raises(ValueError, match="2 nodes"):
        draw_plotly(adj, ["a"], [0.1, 0.9], [0.2, 0.8])
    html = draw_plotly(adj, ["alpha", "beta"], [0.1, 0.9], [0.2, 0.8]).to_html(
        include_plotlyjs=False)
    assert "alpha" in html and "beta" in html


# --- pyvis ----------------------------------------------------------------------------------

@pytest.mark.parametrize("k", range(ND))
def test_pyvis_draws_octaves_nodes_and_arrows(k):
    net = _pyvis_case(k)
    x, y = _v(FX["dd_x"][k]), _v(FX["dd_y"][k])
    assert [nd["id"] for nd in net.nodes] == list(range(len(x)))
    np.testing.assert_array_equal([nd["x"] for nd in net.nodes], SCALE * x)
    np.testing.assert_array_equal([nd["y"] for nd in net.nodes], -SCALE * y)
    assert [nd["label"] for nd in net.nodes] == \
        [s or " " for s in _labels(FX["dd_labels"][k])[:len(x)]]
    assert [nd["color"]["background"] for nd in net.nodes] == \
        [rgb(c) for c in np.atleast_2d(FX["dd_color"][k])]
    assert all(nd["physics"] is False for nd in net.nodes)
    assert [(e["from"], e["to"]) for e in net.edges] == _octave_pairs(k)
    assert all(e["arrows"] == "to" for e in net.edges)


def test_pyvis_undirected_lines_selfloops_errors(tmp_path):
    from pyvis.network import Network

    k = list(FX["dd_run"]).index("undirected")
    net = _pyvis_case(k)
    assert len(net.edges) == 10  # both arrows of each pair survive (directed network)
    net = _pyvis_case(k, undirected="lines", hover=[f"h{i}" for i in range(5)])
    assert len(net.edges) == 5 and all(e["arrows"] == {"to": {"enabled": False}}
                                       for e in net.edges)
    assert [nd["title"] for nd in net.nodes] == [f"h{i}" for i in range(5)]
    k = list(FX["dd_run"]).index("selfloops")
    net = _pyvis_case(k)
    grey = [nd["color"]["background"] == "rgb(204,204,204)" for nd in net.nodes]
    assert grey == list(np.diag(_adj(k)) > 0)
    assert all(e["from"] != e["to"] for e in net.edges)
    with pytest.raises(ValueError, match="directed"):
        draw_pyvis(_adj(k), ["a"] * 10, np.zeros(10), np.zeros(10), net=Network())
    path = tmp_path / "g.html"
    net.write_html(str(path))
    text = path.read_text()
    assert "vis-network" in text and '"physics": false' in text


# --- facade ---------------------------------------------------------------------------------

@pytest.mark.parametrize("backend", INTERACTIVE)
def test_draw_dot_interactive_kamada_kawai(backend):
    """The facade returns MATLAB's ``(xret, yret, labels)`` from the networkx layout and
    draws the nodes at the ordered positions (singletons at 0.05)."""
    k = list(FX["dd_run"]).index("singletons")
    adj = np.atleast_2d(np.asarray(FX["dd_adj"][k], dtype=float))
    labels = _labels(FX["dd_labels_in"][k])
    xr, yr, lab, fig = draw_dot(adj, labels, backend, layout="kamada_kawai",
                                return_figure=True)
    exp = order_positions(*nxb.nx_layout(adj, "kamada_kawai"), adj.shape[0])
    np.testing.assert_array_equal(xr, exp[0])
    np.testing.assert_array_equal(yr, exp[1])
    if backend == "plotly":
        nodes, = _trace(fig, "nodes")
        np.testing.assert_array_equal(nodes.x, exp[2])
        np.testing.assert_array_equal(nodes.y, exp[3])
    else:
        np.testing.assert_array_equal([nd["x"] for nd in fig.nodes], SCALE * exp[2])
    assert np.sum(xr == 0.05) >= 1


@needs_pgv
@pytest.mark.parametrize("backend", INTERACTIVE)
@pytest.mark.parametrize("run_", ["true demo_chain_feat", "feat 6 3", "rel 10 4",
                                  "nolabels", "singletons", "selfloops", "pos",
                                  "nodemult", "fontsz", "spacepad"])
def test_draw_dot_interactive_is_octaves(backend, run_):
    """With the neato layout the facade returns Octave's draw_dot outputs and draws the
    nodes at the X/Y draw_dot passes to graph_draw."""
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
    labels = None if run_ == "nolabels" else _labels(FX["dd_labels_in"][k])
    adj = np.atleast_2d(np.asarray(FX["dd_adj"][k], dtype=float))
    xr, yr, lab, fig = draw_dot(adj, labels, backend, layout="neato", return_figure=True,
                                **kw)
    np.testing.assert_array_equal(xr, _v(FX["dd_xret"][k]))
    np.testing.assert_array_equal(yr, _v(FX["dd_yret"][k]))
    assert lab == _labels(FX["dd_labels_out"][k])
    x, y = _v(FX["dd_x"][k]), _v(FX["dd_y"][k])
    if backend == "plotly":
        nodes, = _trace(fig, "nodes")
        np.testing.assert_array_equal(nodes.x, x)
        np.testing.assert_array_equal(nodes.y, y)
        assert nodes.textfont.size == pytest.approx(float(FX["dd_fontsize"][k]) * 4 / 3)
    else:
        np.testing.assert_array_equal([nd["x"] for nd in fig.nodes], SCALE * x)
        np.testing.assert_array_equal([nd["y"] for nd in fig.nodes], -SCALE * y)


def test_draw_dot_return_figure_and_errors():
    from matplotlib.figure import Figure
    from pyvis.network import Network

    adj = np.array([[0, 1, 0], [0, 0, 1], [0, 0, 0]], float)
    ax = Figure().add_subplot()
    out = draw_dot(adj, None, "networkx", layout="kamada_kawai", ax=ax, return_figure=True)
    assert len(out) == 4 and out[3] is ax.figure
    assert len(draw_dot(adj, None, "networkx", layout="kamada_kawai", ax=ax)) == 3
    with pytest.raises(ValueError, match="matplotlib axes"):
        draw_dot(adj, None, "plotly", layout="kamada_kawai", ax=ax)
    fig = go.Figure()
    assert draw_dot(adj, None, "plotly", layout="kamada_kawai", ax=fig,
                    return_figure=True)[3] is fig
    net = Network(directed=True)
    assert draw_dot(adj, None, "pyvis", layout="kamada_kawai", ax=net,
                    return_figure=True)[3] is net
    with pytest.raises(ValueError, match="labels"):
        draw_dot(adj, ["a"], "plotly", layout="kamada_kawai")
    with pytest.raises(ValueError, match="no edges"):
        draw_dot(np.zeros((2, 2)), None, "pyvis", layout="kamada_kawai")


def _nx_graph(k):
    z = _v(NX["nx_z"][k]).astype(int)
    return {"type": str(NX["nx_type"][k]), "objcount": int(NX["nx_objcount"][k]),
            "z": np.where(z > 0, z - 1, -1), "adj": np.atleast_2d(NX["nx_adj"][k]) != 0,
            "W": np.atleast_2d(NX["nx_W"][k])}


@pytest.mark.parametrize("backend", ["plotly", "pyvis", "networkx"])
def test_draw_graph(backend):
    k = 8  # feat tree x demo_tree_feat
    g, names = _nx_graph(k), _labels(NX["nx_names"][k])
    kw = {}
    if backend == "networkx":  # no pyplot (the fd env's Qt backend needs a display)
        from matplotlib.figure import Figure
        kw["ax"] = Figure().add_subplot()
    fig = draw_graph(g, names, backend, layout="kamada_kawai", title="T", **kw)
    n = g["adj"].shape[0]
    if backend == "plotly":
        nodes, = _trace(fig, "nodes")
        assert list(nodes.hovertext) == vi.hover_text(g, names)
        assert list(nodes.text) == names + [""] * (n - len(names))
        assert fig.layout.title.text == "T"
    elif backend == "pyvis":
        assert [nd["title"] for nd in fig.nodes] == vi.hover_text(g, names, sep="\n")
        assert fig.heading == "T"
    else:
        assert kw["ax"].get_title() == "T" and fig is kw["ax"].figure
    fig = draw_graph(g, names, "plotly", layout="kamada_kawai", hover=["x"] * n)
    assert list(_trace(fig, "nodes")[0].hovertext) == ["x"] * n


# --- results, progress figures, CLI -----------------------------------------------------------

def _results(tmp_path):
    fx = load_fixture("runmodel")
    res = run.MasterResults()
    ps = run.masterrun_ps()
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


def test_draw_results_plotly(tmp_path):
    res = run.load_results(_results(tmp_path))
    fig = draw_results(res, path=tmp_path / "r.html", backend="plotly",
                       layout="kamada_kawai")
    nodes = _trace(fig, "nodes")
    assert len(nodes) == 2 and [t.xaxis for t in nodes] == ["x", "x2"]
    titles = [a.text for a in fig.layout.annotations if a.text]
    assert len(titles) == 2 and all("estimated structure" in t for t in titles)
    for t, r in zip(nodes, res.runs):
        g = res.structure[int(r["sind"]), int(r["dind"]), 0]
        assert list(t.hovertext) == vi.hover_text(g, res.names[0, int(r["dind"])])
    assert (tmp_path / "r.html").read_text().count("plotly") > 0
    with pytest.raises(ValueError, match="pyvis"):
        draw_results(res, backend="pyvis")


def test_progress_figures_reject_interactive():
    with pytest.raises(ValueError, match="matplotlib"):
        ProgressFigures(backend="plotly")


def test_cli_draw_interactive(tmp_path):
    path = _results(tmp_path)
    out = tmp_path / "fig.html"
    assert cli.main(["draw", str(path) + ".json", "--out", str(out), "--backend",
                     "plotly", "--layout", "kamada_kawai", "-q"]) == 0
    assert "plotly" in out.read_text()
    out2 = tmp_path / "net.html"
    assert cli.main(["draw", str(path) + ".json", "--out", str(out2), "--backend",
                     "pyvis", "--layout", "kamada_kawai", "--runs", "1", "-q"]) == 0
    assert "vis-network" in out2.read_text()
    with pytest.raises(SystemExit):
        cli.main(["draw", str(path) + ".json", "--out", str(out2), "--backend", "pyvis",
                  "--layout", "kamada_kawai", "-q"])
    r = subprocess.run(["python", "-m", "formdiscovery", "draw", "--help"],
                       capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": "src"})
    assert r.returncode == 0 and "plotly" in r.stdout and "pyvis" in r.stdout


# --- notebook -------------------------------------------------------------------------------

def _nb():
    nbformat = pytest.importorskip("nbformat")
    return nbformat, nbformat.read(NOTEBOOK, as_version=4)


def test_notebook_is_valid_and_current():
    """The committed notebook is valid, has the generator's cells (tools/
    gen_demo_notebook.py) and was executed without errors."""
    import importlib.util

    nbformat, nb = _nb()
    nbformat.validate(nb)
    spec = importlib.util.spec_from_file_location("gen_nb", REPO / "tools" /
                                                  "gen_demo_notebook.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert [(c.cell_type[:2].replace("ma", "md").replace("co", "code"), c.source)
            for c in nb.cells] == [(k, s) for k, s in gen.CELLS]
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert all(c.execution_count for c in code)
    assert not [o for c in code for o in c.outputs if o.output_type == "error"]
    for c in code:  # every cell compiles once the IPython magics are removed
        compile("\n".join(ln for ln in c.source.splitlines() if not ln.startswith("%")),
                "cell", "exec")


def test_notebook_reproduces_masterrun_demo():
    """The executed notebook shows the nine scores within 1e-3 rel of Octave's (PLAN §7.1)
    and each demo recovers its true form, as in Octave; it has the figures."""
    _, nb = _nb()
    text = "".join(o.get("text", "") for c in nb.cells if c.cell_type == "code"
                   for o in c.outputs if o.output_type == "stream")
    oc = np.asarray(load_fixture("masterrun")["modellike"], dtype=float)
    rows = [ln.split() for ln in text.splitlines() if ln.startswith("demo_") and
            len(ln.split()) == 5]
    assert len(rows) == 9
    ps = run.masterrun_ps()
    for d, form, py, octv, rel in rows:
        s, dd = ps.structures.index(form), ps.data.index(d)
        assert float(octv) == pytest.approx(oc[s, dd], abs=1e-4)
        assert abs(float(py) - oc[s, dd]) / abs(oc[s, dd]) < 1e-3
    for d in ("chain", "ring", "tree"):
        assert f"demo_{d}_feat: Python picks {d}, Octave picks {d}" in text
    kinds = [m for c in nb.cells if c.cell_type == "code" for o in c.outputs
             for m in o.get("data", {})]
    assert kinds.count("image/png") >= 3 and kinds.count("text/html") >= 2


@pytest.mark.slow
def test_notebook_executes(tmp_path):
    """Run the notebook from scratch (about 1 min)."""
    pytest.importorskip("nbclient")
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_nb", REPO / "tools" /
                                                  "gen_demo_notebook.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    nb = gen.execute(gen.build())
    assert not [o for c in nb.cells if c.cell_type == "code" for o in c.outputs
                if o.output_type == "error"]


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_live_masterrun_demo_positions(octave, tmp_path):
    """The real draw_dot on the nine final graphs of Octave's masterrun demo
    (``tests/fixtures/masterrun.mat``); with pygraphviz, both interactive backends place
    every node where draw_dot does."""
    octave.eval("warning('off', 'all');", nout=0)
    octave.addpath(str(OCTAVE_TESTS_DIR / "drawdot_shim"))
    octave.eval("setenv('PATH', [fullfile(OCTAVE_HOME(), 'bin') pathsep getenv('PATH')]);",
                nout=0)
    old = octave.pwd()
    octave.cd(str(tmp_path))
    try:
        fx = str(REPO / "tests" / "fixtures" / "masterrun.mat")
        octave.eval(f"global DRAWDOT_REC; S = load('{fx}');", nout=0)
        ps = run.masterrun_ps()
        compared = 0
        for s, d in [(1, 0), (3, 0), (5, 0), (1, 1), (3, 1), (5, 1), (1, 2), (3, 2), (5, 2)]:
            octave.eval(f"g = S.structure{{{s + 1}, {d + 1}}}; nm = S.names{{{d + 1}}}; "
                        "nm(end+1:size(g.adj, 1)) = {''}; draw_dot(g.adj, nm); "
                        "X = DRAWDOT_REC.X; Y = DRAWDOT_REC.Y; A = full(g.adj); "
                        "W = full(g.W); z = g.z; oc = g.objcount;", nout=0)
            X, Y = _v(octave.pull("X")), _v(octave.pull("Y"))
            g = {"adj": np.atleast_2d(octave.pull("A")), "W": np.atleast_2d(octave.pull("W")),
                 "z": _v(octave.pull("z")).astype(int) - 1,
                 "objcount": int(octave.pull("oc")), "type": ps.structures[s]}
            names = _labels(octave.pull("nm"))
            assert len(X) == g["adj"].shape[0]
            if not pgb.have_pygraphviz():
                continue
            fig = draw_graph(g, names[:g["objcount"]], "plotly", layout="neato")
            nodes, = _trace(fig, "nodes")
            np.testing.assert_array_equal(nodes.x, X)
            np.testing.assert_array_equal(nodes.y, Y)
            net = draw_graph(g, names[:g["objcount"]], "pyvis", layout="neato")
            np.testing.assert_array_equal([nd["x"] for nd in net.nodes], SCALE * X)
            compared += 1
        assert compared == (9 if pgb.have_pygraphviz() else 0)
    finally:
        octave.cd(old)
        octave.rmpath(str(OCTAVE_TESTS_DIR / "drawdot_shim"))
