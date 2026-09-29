"""Item 32 (PLAN §6 phase A): the neato layout (``viz/pygraphviz_backend.py``), the
``draw_dot`` facade and progress figures (``viz/draw.py``), ``graph_draw.m`` with
matplotlib (``viz/graph_draw.py``) and ``formdiscovery draw``.

Fixtures:

- ``tests/octave/fx_viz_draw.m`` → ``tests/fixtures/viz_draw.mat``: the real
  ``draw_dot`` on 83 graphs (the 74 of ``viz_dot.mat`` labelled as runmodel labels them,
  plus crafted cases) and 5 direct ``graph_draw`` calls, through a temporary copy of
  ``graph_draw.m`` with three recorded edits (it cannot run in Octave as released,
  ANOMALIES.md). Recorded: the DOT texts, draw_dot's outputs, what graph_draw gets
  (positions, labels, font size, ``nodemult``), its colours and half-widths ``wd`` and
  every arrow's end points.
- ``tests/octave/fx_viz_progress.m`` → ``tests/fixtures/viz_progress.mat``: two whole
  ``runmodel`` runs with every ``ps.show*`` flag set and ``figure``/``clf``/``title``/
  ``drawnow``/``draw_dot`` shadowed by recorders, with the draws logged for replay.

The positions, colours and arrow end points (given Octave's ``wd``) must match exactly.
Text extents are font dependent, so the drawing itself is checked by smoke tests and an
image regression against this port's own baselines (``tests/viz_images.py``).
"""
import json
import subprocess
import warnings
from collections import Counter

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.testing.compare import compare_images

from formdiscovery import FormDiscoveryError, cli, run, search
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.params import Params
from formdiscovery.search import num2str, show_graph, sprintf_g
from formdiscovery.viz import pygraphviz_backend as pgb
from formdiscovery.viz.dot import adj_is_directed, graph_to_dot
from formdiscovery.viz.draw import (FIGURE, ProgressFigures, default_fontsize,
                                    dot_positions, draw_dot, draw_results, pad_names)
from formdiscovery.viz.graph_draw import (GREY, arrow_head, box_halfwidths, edge_segments,
                                          graph_draw, node_colors, node_halfwidths,
                                          oval_halfwidths, text_extents)
from tests.conftest import find_octave
from tests.viz_images import BASELINE_DIR, IMAGE_CASES, VERSION_FILE, render_case

FX = load_fixture("viz_draw")
PX = load_fixture("viz_progress")
VD = load_fixture("viz_dot")
ND = len(FX["dd_run"])
NG = len(FX["gd_run"])
GV_VERSION = "14.1.2"


def _labels(v):
    if isinstance(v, str):
        return [v]
    return [a if isinstance(a, str) else "" for a in np.atleast_1d(v)]


def _adj(k, pre="dd"):
    return np.atleast_2d(np.asarray(FX[f"{pre}_adj"][k], dtype=float))


def _args(k, pre="dd"):
    a = FX[f"{pre}_args"][k]
    a = list(a) if isinstance(a, (list, np.ndarray)) else []
    return {str(a[i]): a[i + 1] for i in range(0, len(a), 2)}


def _arrows(k, pre="dd"):
    return np.asarray(FX[f"{pre}_arrows"][k], dtype=float).reshape(-1, 4)


def _segs(adj, x, y, wd):
    return np.array([[*s[2], *s[3]] for s in edge_segments(adj, x, y, wd)]).reshape(-1, 4)


# --- neato executables ------------------------------------------------------------------

def _fd_neato():
    """``neato`` of the fd env: next to Octave (the base interpreter's Graphviz has no
    neato plugin, matlab/PATCHES.md)."""
    from pathlib import Path
    exe = find_octave()
    if exe:
        p = Path(exe).parent / "neato"
        if p.is_file() and pgb._probe(str(p)):
            return str(p)
    return None


NEATO = pgb.find_neato() or _fd_neato()


def _gv_version(exe):
    r = subprocess.run([exe, "-V"], capture_output=True, text=True)
    return (r.stderr + r.stdout).split("version")[-1].split()[0]


needs_cli = pytest.mark.skipif(NEATO is None or _gv_version(NEATO) != GV_VERSION,
                               reason=f"needs a working neato {GV_VERSION}")
needs_pgv = pytest.mark.skipif(not pgb.have_pygraphviz(),
                               reason="pygraphviz not installed (use the fd env)")
needs_layout = pytest.mark.skipif(not pgb.have_pygraphviz() and NEATO is None,
                                  reason="no Graphviz layout (pygraphviz or neato)")


@pytest.fixture
def cli_neato(monkeypatch):
    monkeypatch.setenv("FORMDISCOVERY_NEATO", NEATO)
    return NEATO


@pytest.fixture
def engine(monkeypatch):
    """The layout engine for end-to-end tests: pygraphviz, else the fd env's neato."""
    if pgb.have_pygraphviz():
        return "pygraphviz"
    if NEATO is None:
        pytest.skip("no Graphviz layout")
    monkeypatch.setenv("FORMDISCOVERY_NEATO", NEATO)
    return "cli"


def _ax(w=5.6, h=4.2):
    fig = Figure(figsize=(w, h), dpi=100)
    return fig.add_subplot()


# --- fixture ------------------------------------------------------------------------------

def test_fixture_contents():
    assert ND == 83 and NG == 5
    assert GV_VERSION in FX["neato_version"]
    runs = list(FX["dd_run"])
    assert runs[:74] == list(VD["bl_run"])
    assert runs[74:] == ["nolabels", "singletons", "selfloops", "pos", "nodemult",
                         "fontsz", "undirected", "spacepad", "chain105"]
    # the three recorded edits of the temporary graph_draw.m copy
    t = FX["graph_draw_edits"]
    assert t.count("'VerticalAlignment'") == 4 and "'VerticalAlign'," not in t
    assert t.count("gd_arrow_rec([x(node)+dx1") == 2
    assert t.count("global GD_REC") == 1
    assert len(PX["runs"]) == 2


# --- draw_dot.m l.33-84: DOT text, positions, labels, font size ---------------------------

@pytest.mark.parametrize("k", range(ND))
def test_draw_dot_matches_octave(k):
    """graph_to_dot of ``adj > 0`` with draw_dot's ``directed``, then the positions,
    labels, font size and ``nodemult`` graph_draw gets, and draw_dot's outputs."""
    adj = _adj(k)
    n = adj.shape[0]
    a = _args(k)
    gt = graph_to_dot((adj > 0).astype(float), directed=int(adj_is_directed(adj)))
    assert gt == FX["dd_gt"][k]
    xret, yret, x, y, names = dot_positions(FX["dd_lay"][k], n, a.get("pos"))
    np.testing.assert_array_equal(xret, np.ravel(FX["dd_xret"][k]))
    np.testing.assert_array_equal(yret, np.ravel(FX["dd_yret"][k]))
    np.testing.assert_array_equal(x, np.ravel(FX["dd_x"][k]))
    np.testing.assert_array_equal(y, np.ravel(FX["dd_y"][k]))
    lab_in = FX["dd_labels_in"][k]
    given = not (isinstance(lab_in, np.ndarray) and lab_in.dtype != object and lab_in.size == 0)
    want = _labels(lab_in) if given else names
    assert want == _labels(FX["dd_labels_out"][k])
    assert want[:n] == _labels(FX["dd_labels"][k])
    assert float(a.get("fontsz", default_fontsize(n))) == FX["dd_fontsize"][k]
    assert float(a.get("nodemult", 0.5)) == FX["dd_nodemult"][k]


def test_draw_dot_positions_match_viz_dot():
    """The 74 graphs of item 31's fixture: same xret/yret/X/Y from their layouts."""
    for k in range(len(VD["bl_run"])):
        n = np.atleast_2d(VD["bl_adj"][k]).shape[0]
        xret, yret, x, y, _ = dot_positions(VD["bl_lay"][k], n)
        np.testing.assert_array_equal(xret, np.ravel(VD["bl_xret"][k]))
        np.testing.assert_array_equal(yret, np.ravel(VD["bl_yret"][k]))
        np.testing.assert_array_equal(x, np.ravel(VD["bl_X"][k]))
        np.testing.assert_array_equal(y, np.ravel(VD["bl_Y"][k]))


def test_singletons_and_nolabels():
    """Nodes 2 and 5 are in no edge: appended at 0.05 in increasing order (mysetdiff),
    named by number; ``nargin == 1`` labels are the sorted node numbers."""
    k = list(FX["dd_run"]).index("nolabels")
    xret, yret, x, y, names = dot_positions(FX["dd_lay"][k], 6)
    assert names == ["1", "2", "3", "4", "5", "6"]
    assert list(xret[-2:]) == [0.05, 0.05] and list(yret[-2:]) == [0.05, 0.05]
    assert x[1] == x[4] == 0.05


def test_default_fontsize():
    assert [default_fontsize(n) for n in (1, 11, 12, 40, 41, 105)] == [12, 12, 9, 9, 7, 7]


def test_pad_names():
    assert pad_names(["a", None], 4) == ["a", "", "", ""]
    assert pad_names(None, 2, " ") == [" ", " "]
    assert pad_names(["a", "b"], 1) == ["a", "b"]


# --- graph_draw.m: colours and arrows ------------------------------------------------------

@pytest.mark.parametrize("k", range(ND))
def test_graph_draw_geometry_matches_octave(k):
    """Grey fill for self-loop nodes and every arrow's end points (in drawing order),
    given Octave's half-widths."""
    adj = (_adj(k) > 0).astype(float)
    np.testing.assert_array_equal(node_colors(adj), FX["dd_color"][k])
    got = _segs(adj, FX["dd_x"][k], FX["dd_y"][k], FX["dd_wd"][k])
    want = _arrows(k)
    assert got.shape == want.shape
    np.testing.assert_allclose(got, want, rtol=0, atol=1e-14)


@pytest.mark.parametrize("k", range(NG))
def test_graph_draw_direct_calls(k):
    """Direct graph_draw calls: default labels, boxes, weights other than 1 (not drawn),
    vertical edges (alpha = ±pi/2) and coincident nodes."""
    adj = _adj(k, "gd")
    a = _args(k, "gd")
    np.testing.assert_array_equal(node_colors(adj), FX["gd_color"][k])
    got = _segs(adj, a["X"], a["Y"], FX["gd_wd"][k])
    np.testing.assert_allclose(got, _arrows(k, "gd"), rtol=0, atol=1e-14)
    if FX["gd_run"][k] == "default":
        assert _labels(FX["gd_labels"][k]) == ["1", "2", "3", "4"]
    if FX["gd_run"][k] == "weighted":
        assert got.shape[0] == 4 == np.sum(adj == 1)  # the 2 in adj[0, 1] is not drawn
    if FX["gd_run"][k] == "shapes":
        np.testing.assert_array_equal(FX["gd_node_t"][k], [0, 1, 0, 1])


def test_undirected_edges_get_two_arrows():
    """KI-37: the one-line branch is disabled, so each symmetric pair is two arrows."""
    k = list(FX["dd_run"]).index("undirected")
    adj = _adj(k)
    assert np.array_equal(adj, adj.T)
    assert _arrows(k).shape[0] == int(adj.sum()) == 10
    segs = edge_segments(adj, FX["dd_x"][k], FX["dd_y"][k], FX["dd_wd"][k])
    assert {(i, j) for i, j, _, _ in segs} == {(i, j) for i, j in zip(*np.nonzero(adj))}


def test_halfwidths():
    e = np.array([[0.06, 0.02], [0.01, 0.03], [0.0, 0.0]])
    np.testing.assert_allclose(oval_halfwidths(e, 0.5),
                               [[0.02, 0.01], [0.015, 0.015], [0, 0]])
    np.testing.assert_allclose(box_halfwidths(e), [[0.04, 0.02 * 2 / 3], [0.02, 0.02],
                                                   [0, 0]])
    wd = node_halfwidths(e, [0, 1, 0], 0.5)
    np.testing.assert_allclose(wd, [[0.02, 0.01], [0.02, 0.02], [0, 0]])
    # Octave's radii obey wx = max(2/3 w, h) * nodemult >= wy
    for k in range(ND):
        wd = np.asarray(FX["dd_wd"][k]).reshape(-1, 2)
        assert np.all(wd[:, 0] >= wd[:, 1])


def test_empty_label_zero_extent():
    """Octave: an empty label has a zero extent, so its node is a point."""
    k = 0
    labels = _labels(FX["dd_labels"][k])
    wd = np.asarray(FX["dd_wd"][k])
    assert all((wd[i] == 0).all() == (labels[i] == "") for i in range(len(labels)))
    ex = text_extents(_ax(), ["", "12"], 9)
    assert (ex[0] == 0).all() and (ex[1] > 0).all()


def test_arrow_head():
    head = arrow_head((0, 0), (10, 0), lambda p: np.asarray(p, float))
    np.testing.assert_allclose(head[0], [10, 0])
    np.testing.assert_allclose(head[1:, 0], [5, 5])
    half = 5 * np.tan(np.radians(12))
    np.testing.assert_allclose(sorted(head[1:, 1]), [-half, half])
    assert arrow_head((1, 1), (1, 1), lambda p: np.asarray(p, float)) is None


# --- rendering ------------------------------------------------------------------------------

def test_graph_draw_renders():
    k = list(FX["dd_run"]).index("selfloops")
    adj = (_adj(k) > 0).astype(float)
    ax = _ax()
    x, y, h = graph_draw(adj, _labels(FX["dd_labels"][k]), FX["dd_x"][k], FX["dd_y"][k],
                         fontsize=12, ax=ax)
    n = adj.shape[0]
    assert len(h["nodes"]) == n and len(h["labels"]) == n
    assert [t.get_text() for t in h["labels"]] == _labels(FX["dd_labels"][k])
    fills = [tuple(p.get_facecolor()[:3]) for p in h["nodes"]]
    assert [f == GREY for f in fills] == [True, False, False, True, False]
    off = int(adj.sum() - np.trace(adj))
    assert len(h["edges"]) == len(h["heads"]) == off == 3
    assert ax.get_xlim() == (0, 1) and ax.get_ylim() == (0, 1)
    assert not ax.get_xticks().size
    # a node's ellipse has 61 vertices around its centre
    v = h["nodes"][0].get_xy()
    assert len(v) >= 61
    np.testing.assert_allclose(v[:61].mean(axis=0), [x[0], y[0]], atol=1e-3)
    # the drawn arrow lines are edge_segments of the measured half-widths
    segs = _segs(adj, x, y, h["wd"])
    lines = np.array([[*ln.get_xydata()[0], *ln.get_xydata()[1]] for ln in h["edges"]])
    np.testing.assert_allclose(lines, segs, rtol=0, atol=1e-15)


def test_graph_draw_octave_wd_and_lines_mode():
    k = list(FX["dd_run"]).index("undirected")
    adj = _adj(k)
    _, _, h = graph_draw(adj, _labels(FX["dd_labels"][k]), FX["dd_x"][k], FX["dd_y"][k],
                         ax=_ax(), wd=FX["dd_wd"][k])
    lines = np.array([[*ln.get_xydata()[0], *ln.get_xydata()[1]] for ln in h["edges"]])
    np.testing.assert_allclose(lines, _arrows(k), rtol=0, atol=1e-14)
    assert len(h["heads"]) == 10
    _, _, h = graph_draw(adj, _labels(FX["dd_labels"][k]), FX["dd_x"][k], FX["dd_y"][k],
                         ax=_ax(), undirected="lines")
    assert len(h["edges"]) == 5 and len(h["heads"]) == 0


def test_graph_draw_mixed_shapes_colour_quirk():
    """textoval/textbox index the full colour list locally: with node_shapes [1 0], the
    oval (node 2) gets node 1's colour and the box node 2's (graph_draw.m:60-66)."""
    adj = np.array([[1.0, 1.0], [0.0, 0.0]])  # node 1 grey
    _, _, h = graph_draw(adj, ["a", "b"], [0.2, 0.8], [0.5, 0.5], node_shapes=[1, 0],
                         ax=_ax())
    assert tuple(h["nodes"][1].get_facecolor()[:3]) == GREY  # the oval
    assert tuple(h["nodes"][0].get_facecolor()[:3]) == GREY  # the box: color(1,:) too
    _, _, h = graph_draw(adj, ["a", "b"], [0.2, 0.8], [0.5, 0.5], ax=_ax())
    assert tuple(h["nodes"][1].get_facecolor()[:3]) == (1, 1, 1)


def test_graph_draw_errors():
    with pytest.raises(ValueError, match="make_layout"):
        graph_draw(np.zeros((2, 2)), ax=_ax())
    with pytest.raises(ValueError, match="undirected"):
        graph_draw(np.zeros((2, 2)), x=[0, 1], y=[0, 1], ax=_ax(), undirected="x")


@pytest.mark.parametrize("name", list(IMAGE_CASES))
def test_image_regression(name, tmp_path):
    """Geometry (labels hidden) at RMS tolerance 2 on any matplotlib; the full image at
    2 on the baselines' matplotlib version and 15 otherwise (text anti-aliasing changed
    between 3.10 and 3.11)."""
    same = VERSION_FILE.read_text().strip() == matplotlib.__version__
    for suffix, text, tol in (("_notext", False, 2), ("", True, 2 if same else 15)):
        out = tmp_path / f"{name}{suffix}.png"
        render_case(FX, name, out, text=text)
        err = compare_images(str(BASELINE_DIR / f"{name}{suffix}.png"), str(out), tol=tol,
                             in_decorator=True)
        assert err is None, err


# --- neato layout (live Graphviz) -----------------------------------------------------------

def test_neato_args():
    assert pgb.neato_args(12) == ["-Tdot", "-Gmaxiter=25000", "-Gregular-Gminlen=5",
                                  "-Goverlap=false"]
    # KI-35: strcat glues -x onto the overlap value
    assert pgb.neato_args(101) == ["-Tdot", "-Gmaxiter=25000", "-Gregular-Gminlen=5",
                                   "-Goverlap=false-x"]
    assert pgb.neato_args(100)[-1] == "-Goverlap=false"
    assert pgb.neato_args(12, "intended") == ["-Tdot", "-Gmaxiter=25000", "-Gregular",
                                              "-Gminlen=5", "-Goverlap=false"]
    assert pgb.neato_args(101, "intended")[-1] == "-x"
    with pytest.raises(ValueError):
        pgb.neato_attrs(3, "other")


def test_octave_layouts_carry_the_glued_flags():
    """KI-32/KI-35 in Octave's own neato output."""
    for k in range(ND):
        lay = FX["dd_lay"][k]
        assert '"regular-Gminlen"=5' in lay and "minlen=5" not in lay.replace(
            '"regular-Gminlen"=5', "")
        n = _adj(k).shape[0]
        assert ('overlap="false-x"' in lay) == (n > 100)
    assert _adj(ND - 1).shape[0] == 105


def _layout_cases():
    return [(FX["dd_adj"][k], FX["dd_gt"][k], FX["dd_lay"][k]) for k in range(ND)]


@needs_pgv
def test_pygraphviz_layout_is_octaves():
    """pygraphviz (same Graphviz) reproduces Octave's neato layout byte for byte on all
    83 draw_dot graphs and the 74 of viz_dot.mat."""
    cases = _layout_cases() + [(a, g, l) for a, g, l in
                               zip(VD["bl_adj"], VD["bl_gt"], VD["bl_lay"])]
    for adj, gt, lay in cases:
        g2, l2, _ = pgb.layout_text(np.atleast_2d(adj), engine="pygraphviz")
        assert g2 == gt
        assert l2 == lay


@needs_cli
def test_cli_layout_is_octaves(cli_neato):
    for adj, gt, lay in _layout_cases():
        g2, l2, _ = pgb.layout_text(np.atleast_2d(adj), engine="cli")
        assert (g2, l2) == (gt, lay)


@needs_cli
def test_intended_flags_same_positions(cli_neato):
    """``regular`` and ``minlen`` are not neato layout attributes: the intended flags
    give the same positions (n <= 100). With -x (n > 100) the text differs."""
    for k in list(range(0, 74, 7)) + [74, 76, 80]:
        adj = _adj(k)
        _, lay, _ = pgb.layout_text(adj, flags="intended", engine="cli")
        n = adj.shape[0]
        a = dot_positions(lay, n)
        b = dot_positions(FX["dd_lay"][k], n)
        for p, q in zip(a[:4], b[:4]):
            np.testing.assert_array_equal(p, q)
    _, lay, _ = pgb.layout_text(_adj(ND - 1), flags="intended", engine="cli")
    assert 'overlap="false-x"' not in lay


@needs_pgv
def test_pygraphviz_rejects_reduce():
    with pytest.raises(ValueError, match="-x"):
        pgb.neato_layout(FX["dd_gt"][ND - 1], 105, flags="intended", engine="pygraphviz")


def test_engine_errors(monkeypatch):
    with pytest.raises(ValueError):
        pgb.neato_layout("graph {}", 1, engine="nope")
    monkeypatch.setattr(pgb, "have_pygraphviz", lambda: False)
    monkeypatch.setattr(pgb, "find_neato", lambda: None)
    with pytest.raises(RuntimeError, match="no Graphviz"):
        pgb.neato_layout("graph {}", 1)


def test_find_neato_probes(monkeypatch, tmp_path):
    """A neato that cannot lay out (like /usr/bin/neato here) is skipped."""
    fake = tmp_path / "neato"
    fake.write_text("#!/bin/sh\necho 'There is no layout engine support for \"neato\"' >&2\n"
                    "exit 1\n")
    fake.chmod(0o755)
    assert not pgb._probe(str(fake))
    monkeypatch.setenv("FORMDISCOVERY_NEATO", str(fake))
    monkeypatch.setenv("PATH", str(tmp_path))
    got = pgb.find_neato()
    assert got != str(fake)
    if NEATO:
        monkeypatch.setenv("FORMDISCOVERY_NEATO", NEATO)
        assert pgb.find_neato() == NEATO


# --- draw_dot facade end to end ---------------------------------------------------------------

@pytest.mark.parametrize("k", [0, 11, 20, 60] + list(range(74, 83)))
def test_draw_dot_end_to_end(k, engine):
    """Layout, positions and drawing: xret/yret and labels as Octave's draw_dot; with
    Octave's ``wd`` the drawn arrows are Octave's."""
    adj = _adj(k)
    a = _args(k)
    lab_in = FX["dd_labels_in"][k]
    given = not (isinstance(lab_in, np.ndarray) and lab_in.dtype != object and lab_in.size == 0)
    kw = {kk: v for kk, v in a.items() if kk in ("pos", "nodemult", "fontsz")}
    ax = _ax()
    xret, yret, labels = draw_dot(adj, _labels(lab_in) if given else None, ax=ax,
                                  engine=engine, wd=FX["dd_wd"][k], **kw)
    np.testing.assert_array_equal(xret, np.ravel(FX["dd_xret"][k]))
    np.testing.assert_array_equal(yret, np.ravel(FX["dd_yret"][k]))
    assert labels == _labels(FX["dd_labels_out"][k])
    lines = np.array([[*ln.get_xydata()[0], *ln.get_xydata()[1]] for ln in ax.lines])
    np.testing.assert_allclose(lines.reshape(-1, 4), _arrows(k), rtol=0, atol=1e-14)
    assert len(ax.texts) == adj.shape[0]


def test_layout_binarises_weights(engine):
    """draw_dot.m:36: ``adj > 0`` goes to graph_to_dot (weights and signs dropped);
    ``directed`` is taken before that (l.35)."""
    k = list(FX["dd_run"]).index("feat 2 1")
    adj = _adj(k)
    w = adj * np.arange(1, adj.size + 1).reshape(adj.shape)
    gt, lay, directed = pgb.layout_text(w, engine=engine)
    assert (gt, lay, directed) == (FX["dd_gt"][k], FX["dd_lay"][k], 1)
    sym = np.array([[0, 2.0], [1.0, 0]])  # binarised symmetric, but directed as given
    gt, _, directed = pgb.layout_text(sym, engine=engine)
    assert directed == 1 and "1 -> 2" in gt and "2 -> 1" in gt


def test_draw_dot_errors(engine):
    with pytest.raises(ValueError, match="backend"):
        draw_dot(np.eye(2), backend="plotly")
    with pytest.raises(ValueError, match="labels"):
        draw_dot(np.array([[0, 1.0], [0, 0]]), ["a"], ax=_ax(), engine=engine)
    with pytest.raises(ValueError):  # no edges: dot_to_graph fails, as in MATLAB
        draw_dot(np.zeros((3, 3)), ax=_ax(), engine=engine)


@needs_pgv
def test_render_graphviz(tmp_path):
    k = list(FX["dd_run"]).index("selfloops")
    out = tmp_path / "g.svg"
    pgb.render(_adj(k), _labels(FX["dd_labels"][k]), out)
    svg = out.read_text()
    assert svg.count('class="node"') == 5 and "L4" in svg and "#cccccc" in svg
    png = pgb.render(_adj(k), None, format="png")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# --- progress figures (show callbacks) ------------------------------------------------------

def _octave_events(r):
    """(event figure, title, adj, labels) of every draw_dot call in an Octave display log:
    the title is the one set in the same figure block (before or after draw_dot)."""
    out, cur = [], None
    for e in r["ev"]:
        kind = e["kind"]
        if kind == "figure":
            cur = {"fig": int(e["value"]), "title": None, "adj": None}
            out.append(cur)
        elif kind == "title":
            cur["title"] = str(e["value"])
        elif kind == "draw_dot":
            assert cur["adj"] is None
            cur["adj"] = np.atleast_2d(np.asarray(e["adj"], dtype=float))
            cur["labels"] = _labels(e["labels"])
    return out


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, event, adj, names, title):
        self.events.append({"event": event, "fig": FIGURE[event], "title": title,
                            "adj": np.asarray(adj), "labels": list(names)})


@pytest.mark.parametrize("i", range(2))
def test_progress_events_match_octave(i, monkeypatch, tmp_path):
    """Replay the two runs with every ps.show* flag: the same sequence of figures,
    titles (``%g``/``num2str``), graphs and padded names as MATLAB's display code, and
    runmodel's names padded (KI-38)."""
    from tests.test_runmodel import replay

    r = PX["runs"][i]
    rec = Recorder()
    flags = dict(showtruegraph=1, showinferredgraph=1, showbestsplit=1, showpreclean=1,
                 showpostclean=1)
    (ll, graph, names, _, _), ties = replay(r, f"progress {i}", monkeypatch, tmp_path,
                                            show=rec, **flags)
    np.testing.assert_allclose(ll, r["out_ll"], rtol=1e-10)
    want = _octave_events(r)
    assert len(rec.events) == len(want)
    counts = Counter(e["event"] for e in rec.events)
    assert counts["truegraph"] == counts["inferredgraph"] == 1
    assert counts["preclean"] >= 1 and counts["postclean"] >= 1
    if i == 0:
        assert counts["bestsplit"] > 0
    mirrored = 0
    for j, (g, w) in enumerate(zip(rec.events, want)):
        msg = f"run {i} event {j} {g['event']}"
        assert g["fig"] == w["fig"], msg
        assert g["title"] == w["title"], (msg, g["title"], w["title"])
        assert g["labels"] == w["labels"], msg
        if g["event"] == "bestsplit" and not np.array_equal(g["adj"], w["adj"]):
            # a tied split: best_split shows its own choice; the replay's SplitOracle
            # then substitutes Octave's tied (mirror image) candidate
            assert g["adj"].shape == w["adj"].shape and g["adj"].sum() == w["adj"].sum()
            assert sorted(g["adj"].sum(0)) == sorted(w["adj"].sum(0)), msg
            mirrored += 1
            continue
        np.testing.assert_array_equal(g["adj"], w["adj"], err_msg=msg)
    print(f"run {i}: {len(want)} display calls, {mirrored} mirrored, {ties} ties")
    assert mirrored <= ties
    assert list(names) == _labels(r["out_names"])


def test_show_flags_off_calls_nothing(monkeypatch, tmp_path):
    from tests.test_runmodel import replay

    r = PX["runs"][1]
    rec = Recorder()
    (_, _, names, _, _), _ = replay(r, "noshow", monkeypatch, tmp_path, show=rec)
    assert rec.events == []
    assert len(names) == 8  # not padded


def test_names_padded_without_callback(monkeypatch, tmp_path):
    """KI-38 follows the flags, not the callback."""
    from tests.test_runmodel import replay

    r = PX["runs"][1]
    (_, graph, names, _, _), _ = replay(r, "pad", monkeypatch, tmp_path,
                                        showinferredgraph=1)
    assert names == _labels(r["out_names"])[:len(names)]
    assert len(names) == np.shape(graph.adj)[0] and names[-1] == ""


def test_names_padded_to_true_graph(monkeypatch, tmp_path):
    """KI-38, showtruegraph: padded to the true graph's node count."""
    from tests.test_runmodel import replay

    (_, _, names, _, _), _ = replay(PX["runs"][1], "padtrue", monkeypatch, tmp_path,
                                    showtruegraph=1)
    true_adj = FX["dd_adj"][list(FX["dd_run"]).index("true demo_ring_rel_bin")]
    assert len(names) == np.shape(true_adj)[0] == 12 and names[8:] == [""] * 4


def test_truegraph_without_adj_raises(tmp_path):
    ps = Params.default()
    ps.showtruegraph = 1
    with pytest.raises(FormDiscoveryError, match="adj"):
        run.runmodel(ps, 1, ps.data.index("animals"), 1)


def test_show_graph_helper():
    got = []
    show_graph(lambda *a: got.append(a), 1, "preclean", np.zeros((3, 3)), ["a"], " ", "t")
    assert got[0][0] == "preclean" and got[0][2] == ["a", " ", " "] and got[0][3] == "t"
    show_graph(lambda *a: got.append(a), 0, "preclean", np.zeros((3, 3)), ["a"], " ", "t")
    show_graph(None, 1, "preclean", np.zeros((3, 3)), ["a"], " ", "t")
    assert len(got) == 1


def test_num2str_sprintf_g():
    assert num2str(-8874.759213) == "-8874.7592"
    assert num2str(-22.18723477) == "-22.1872"  # Octave 10.3 prints these seven
    assert num2str(0.001234567) == "0.0012346"
    assert num2str(3.0) == "3" and num2str(-np.inf) == "-Inf" and num2str(np.nan) == "NaN"
    assert num2str(123456789.123) == "123456789.123"
    assert sprintf_g(-8874.759213) == "-8874.76" and sprintf_g(1e-7) == "1e-07"
    assert sprintf_g(np.inf) == "Inf"


def test_progress_figures_files(tmp_path, engine):
    pf = ProgressFigures(outdir=tmp_path, engine=engine)
    k = list(FX["dd_run"]).index("selfloops")
    pf("preclean", _adj(k), _labels(FX["dd_labels"][k]), "pre-clean: x  -1")
    pf("postclean", _adj(k), _labels(FX["dd_labels"][k]), "post-clean: x  -1")
    pf("inferredgraph", _adj(k), _labels(FX["dd_labels"][k]), "final")
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["0001_fig1_preclean.png", "0002_fig2_postclean.png",
                     "0003_fig3_inferredgraph.png"]
    assert [c[1] for c in pf.calls] == [1, 2, 3]
    assert pf.figures[1].axes[0].get_title() == "pre-clean: x  -1"
    assert len(pf.figures[1].axes) == 1  # cleared (clf) before each drawing
    with pytest.warns(UserWarning, match="not drawn"):
        pf("bestsplit", np.zeros((3, 3)), ["a", "b", "c"], "-5")
    with pytest.raises(ValueError):
        ProgressFigures(strict=True, engine=engine)("bestsplit", np.zeros((3, 3)),
                                                    ["a", "b", "c"], "-5")


def test_progress_enable():
    ps = Params.default()
    ps2 = ProgressFigures.enable(ps, ("preclean", "inferredgraph"))
    assert ps.showpreclean == 0 and ps2.showpreclean == 1 and ps2.showinferredgraph == 1
    assert ps2.showpostclean == 0
    with pytest.raises(ValueError):
        ProgressFigures.enable(ps, ("nope",))


# --- results drawing and the CLI ------------------------------------------------------------

def _results(tmp_path):
    """A results file holding two of the runmodel fixture's final graphs."""
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


def test_draw_results(tmp_path, engine):
    res = run.load_results(_results(tmp_path))
    fig = draw_results(res, engine=engine)
    assert len(fig.axes) == 2
    t = fig.axes[0].get_title()
    assert t.startswith("demo_chain_feat\nchain: estimated structure:  -")
    fig = draw_results(res, [1], tmp_path / "one.png", engine=engine)
    assert len(fig.axes) == 1 and (tmp_path / "one.png").stat().st_size > 1000
    with pytest.raises(ValueError):
        draw_results(res, [])


def test_cli_draw(tmp_path, engine, capsys):
    path = _results(tmp_path)
    out = tmp_path / "fig.png"
    assert cli.main(["draw", str(path.with_suffix(".npz")), "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"\x89PNG"
    assert "saved" in capsys.readouterr().out
    out2 = tmp_path / "fig2.pdf"
    assert cli.main(["draw", str(path) + ".json", "--out", str(out2), "--runs", "1",
                     "--undirected", "lines", "-q"]) == 0
    assert out2.read_bytes()[:4] == b"%PDF"
    with pytest.raises(SystemExit):
        cli.main(["draw", str(path) + ".json", "--out", str(out), "--runs", "5"])
    with pytest.raises(SystemExit):
        cli.main(["draw", str(path) + ".json", "--out", str(out), "--graphviz"])


@needs_pgv
def test_cli_draw_graphviz(tmp_path):
    path = _results(tmp_path)
    out = tmp_path / "g.svg"
    assert cli.main(["draw", str(path) + ".json", "--out", str(out), "--runs", "0",
                     "--graphviz", "-q"]) == 0
    assert out.read_text().count('class="node"') == 12


def test_cli_run_figures(tmp_path, engine, monkeypatch):
    """``run --figures`` turns on masterrun's two figures (post-clean, inferred graph)."""
    seen = []
    real = run.masterrun

    def fake(ps, *a, **k):
        seen.append((ps.showpostclean, ps.showinferredgraph, ps.showpreclean,
                     type(k["show"]).__name__))
        return run.MasterResults()

    monkeypatch.setattr(cli, "masterrun", fake)
    assert cli.main(["run", "--structures", "chain", "--datasets", "1", "--out",
                     str(tmp_path), "--figures", str(tmp_path / "figs"), "-q"]) == 0
    assert seen == [(1, 1, 0, "ProgressFigures")]
    assert real is run.masterrun


def test_cli_draw_help():
    r = subprocess.run(["python", "-m", "formdiscovery", "draw", "--help"],
                       capture_output=True, text=True,
                       env={**__import__("os").environ, "PYTHONPATH": "src"})
    assert r.returncode == 0 and "--graphviz" in r.stdout


# --- live Octave -------------------------------------------------------------------------------

@pytest.mark.octave
def test_viz_draw_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "viz_draw.mat"
    octave.feval("fx_viz_draw", str(out), nout=0)
    new = load_fixture(out.name, fixtures_dir=tmp_path)
    for key in ("dd_run", "dd_gt", "dd_lay", "gd_run", "neato_version", "graph_draw_edits"):
        assert json.dumps(np.atleast_1d(new[key]).tolist()) == \
            json.dumps(np.atleast_1d(FX[key]).tolist()), key
    for key in ("dd_xret", "dd_yret", "dd_x", "dd_y", "dd_color", "dd_wd", "dd_arrows",
                "gd_wd", "gd_arrows"):
        for a, b in zip(new[key], FX[key]):
            np.testing.assert_array_equal(a, b)


@pytest.mark.octave
def test_viz_progress_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "viz_progress.mat"
    octave.feval("fx_viz_progress", str(out), nout=0)
    new = load_fixture(out.name, fixtures_dir=tmp_path)
    for a, b in zip(new["runs"], PX["runs"]):
        assert a["logtext"] == b["logtext"]
        assert a["out_ll"] == b["out_ll"]
        ea, eb = _octave_events(a), _octave_events(b)
        assert [(e["fig"], e["title"]) for e in ea] == [(e["fig"], e["title"]) for e in eb]
        for x, y in zip(ea, eb):
            np.testing.assert_array_equal(x["adj"], y["adj"])
