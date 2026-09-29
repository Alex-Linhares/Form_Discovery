"""Item 31 (PLAN §6 phase A): ``viz/dot.py`` against Octave's ``graph_to_dot.m`` and
``dot_to_graph.m``.

Fixture ``tests/octave/fx_viz_dot.m`` → ``tests/fixtures/viz_dot.mat``:

- ``bl_*``: the unmodified ``draw_dot(graph.adj, names)`` on every final baseline graph
  (9 feature + 54 relational runs), with the ``graph_draw`` shim recording the
  ``_GtDout.dot`` text and neato's ``_LAYout.dot`` layout, and Octave's ``dot_to_graph``
  of that layout. The DOT text must match byte for byte; the parse of the same layout
  text must match exactly.
- ``go_*``: ``graph_to_dot`` option variants, including the KI-31 error.
- ``cr_*``: ``dot_to_graph`` on crafted texts (errors and warnings included).

``tests/fixtures/dot_to_graph.mat`` (item 03, ``fx_dot_to_graph.m``) adds four neato
layouts and two pre-2.30 layouts.
"""
import re
import warnings

import numpy as np
import pytest

from formdiscovery.io import load_fixture
from formdiscovery.viz.dot import (
    _octave_d,
    _sscanf_pos,
    adj_is_directed,
    dot_to_graph,
    dot_to_graph_file,
    graph_to_dot,
)
from tests.conftest import FIXTURES_DIR

FX = load_fixture("viz_dot")
NBL = len(FX["bl_gt"])
NGO = len(FX["go_text"])
NCR = len(FX["cr_text"])


def _s(v):
    """A MATLAB char value from ``simplify_cells`` (empty char/double → ``''``)."""
    return v if isinstance(v, str) else ""


def _labels(v):
    if isinstance(v, str):
        return [v]
    return [_s(a) for a in np.atleast_1d(v)]


def _cell_value(v):
    """``go_args`` values: cell of strings → list, cell matrix → nested lists with
    ``None`` for MATLAB's ``[]``."""
    if isinstance(v, np.ndarray) and v.dtype == object:
        if v.ndim == 1:
            return [_s(a) for a in v]
        return [[a if isinstance(a, str) else (None if a.dtype.kind == "f" else "")
                 for a in row] for row in v]
    if isinstance(v, np.ndarray) and v.size == 1:
        return v.item()
    return v


def _go_kwargs(k):
    args = FX["go_args"][k]
    if isinstance(args, np.ndarray) and args.size == 0:
        return {}
    args = list(args)
    return {args[i]: _cell_value(args[i + 1]) for i in range(0, len(args), 2)}


def _mat(v, n):
    return np.asarray(v, dtype=float).reshape(n, n) if n else np.zeros((0, 0))


def _check_parse(text, A, labels, x, y):
    got = dot_to_graph(text)
    labels = _labels(labels)
    n = len(labels)
    assert got[1] == labels
    np.testing.assert_array_equal(got[0], _mat(A, n))
    np.testing.assert_array_equal(got[2], np.atleast_1d(np.asarray(x, dtype=float)))
    np.testing.assert_array_equal(got[3], np.atleast_1d(np.asarray(y, dtype=float)))
    return got


# --- graph_to_dot ---------------------------------------------------------------------

@pytest.mark.parametrize("k", range(NBL))
def test_graph_to_dot_baseline_matches_octave(k):
    """draw_dot.m:35-38 then graph_to_dot: byte parity with Octave's _GtDout.dot."""
    adj = np.atleast_2d(FX["bl_adj"][k])
    text = graph_to_dot((adj > 0).astype(float), directed=adj_is_directed(adj))
    assert text == FX["bl_gt"][k]


def test_baseline_covers_both_edge_kinds():
    kinds = {t.split(" ", 1)[0] for t in FX["bl_gt"]}
    assert kinds == {"digraph", "graph"}
    assert NBL == 74
    assert sum(r.startswith("true ") for r in FX["bl_run"]) == 11


@pytest.mark.parametrize("k", range(NGO))
def test_graph_to_dot_options_match_octave(k, tmp_path):
    adj = np.atleast_2d(np.asarray(FX["go_adj"][k], dtype=float))
    kw = _go_kwargs(k)
    err = _s(FX["go_err"][k])
    path = tmp_path / "go.dot"
    if err:
        assert "labeltxt" in err
        with pytest.raises(NameError, match="labeltxt"):
            graph_to_dot(adj, filename=path, **kw)
    else:
        assert graph_to_dot(adj, filename=path, **kw) == FX["go_text"][k]
    assert path.read_text() == _s(FX["go_text"][k])


def test_graph_to_dot_ki31_undirected_arc_label():
    """KI-31: graph_to_dot.m:50 assigns 'labeltext'; l.66 reads 'labeltxt'."""
    with pytest.raises(NameError):
        graph_to_dot(np.ones((2, 2)), directed=0, arc_label=[["a", "b"], ["c", "d"]])
    # an empty arc_label is 'isempty' and takes the no-label branch
    assert "[dir=none]" in graph_to_dot(np.ones((2, 2)), directed=0, arc_label=[])


def test_graph_to_dot_dict_arc_labels_and_no_file(tmp_path):
    adj = np.array([[0, 1], [0, 0]])
    assert graph_to_dot(adj, arc_label={(0, 1): "e"}).splitlines()[-2] == '1 -> 2 [label="e"];'
    assert list(tmp_path.iterdir()) == []


def test_graph_to_dot_rejects_non_square():
    with pytest.raises(ValueError):
        graph_to_dot(np.zeros((2, 3)))


def test_octave_d_format():
    """Octave's %d (fixture case 9 shows 10.5 and 1/3); MATLAB would print %e."""
    assert _octave_d(1234567) == "1234567"         # Octave: printf("%d", 1234567)
    assert [_octave_d(v) for v in (10, 10.5, 1 / 3, -2.5, 1e10 + 0.5, np.inf, np.nan)] == [
        "10", "10.5", "0.333333", "-2.5", "1e+10", "Inf", "NaN"]


def test_adj_is_directed():
    assert not adj_is_directed(np.array([[1, 2], [2, 0]]))
    assert adj_is_directed(np.array([[0, 1], [0, 0]]))
    assert adj_is_directed(np.array([[0, np.nan], [np.nan, 0]]))
    for k in range(NBL):
        adj = np.atleast_2d(FX["bl_adj"][k])
        assert adj_is_directed(adj) == FX["bl_gt"][k].startswith("digraph")


# --- dot_to_graph ---------------------------------------------------------------------

@pytest.mark.parametrize("k", range(NBL))
def test_dot_to_graph_baseline_layout_matches_octave(k):
    """Octave's parse of neato's layout of every baseline graph (same text, so exact)."""
    got = _check_parse(FX["bl_lay"][k], FX["bl_A"][k], FX["bl_labels"][k],
                       FX["bl_x"][k], FX["bl_y"][k])
    # draw_dot's xret/yret are dot_to_graph's x/y (plus singletons at 0.05, item 32)
    n = len(got[1])
    np.testing.assert_array_equal(np.atleast_1d(FX["bl_xret"][k])[:n], got[2])
    np.testing.assert_array_equal(np.atleast_1d(FX["bl_yret"][k])[:n], got[3])


def test_baseline_layouts_use_the_fd_neato():
    assert FX["neato_version"].startswith("neato - graphviz version 14.")
    for lay in FX["bl_lay"]:
        assert "pos=" in lay


def test_baseline_neato_attributes_ki32():
    """KI-32: draw_dot.m:46-47 glue '-Gregular' and '-Gminlen=5' into one attribute."""
    for lay in FX["bl_lay"]:
        assert '"regular-Gminlen"=5' in lay
        assert "minlen=5" not in lay.replace('"regular-Gminlen"=5', "")
        assert "maxiter=25000" in lay and "overlap=false" in lay


D2G = load_fixture("dot_to_graph")
D2G_FILES = list(D2G["files"])


@pytest.mark.parametrize("k", range(len(D2G_FILES)))
def test_dot_to_graph_matches_octave(k):
    """KI-7 pin: multi-line Graphviz 14 attributes are read by carry-over (lay1-4), and
    the old one-line format still parses (old1-2)."""
    path = FIXTURES_DIR / "dot_to_graph" / D2G_FILES[k]
    labels = [s.strip() for s in _labels(D2G[f"labels{k + 1}"])]
    got = dot_to_graph_file(path)
    assert got[1] == labels
    np.testing.assert_array_equal(got[0], np.asarray(D2G[f"A{k + 1}"], dtype=float))
    np.testing.assert_array_equal(got[2], D2G[f"x{k + 1}"])
    np.testing.assert_array_equal(got[3], D2G[f"y{k + 1}"])


def test_ki7_positions_come_from_the_next_line():
    lay1 = (FIXTURES_DIR / "dot_to_graph" / "lay1.dot").read_text()
    node_lines = [ln for ln in lay1.splitlines() if re.match(r"\s*\d+\s*\[height", ln)]
    assert node_lines and all("pos" not in ln for ln in node_lines)
    assert np.all(dot_to_graph(lay1)[2] > 0)


def _whole_name_positions(text):
    """Positions by whole node name (what a real DOT parser gives)."""
    pos = {}
    for m in re.finditer(r'^\s*(\S+)\s*\[[^\]]*?pos="([-\d.e+]+),([-\d.e+]+)"', text,
                         flags=re.M | re.S):
        pos.setdefault(m.group(1), (float(m.group(2)), float(m.group(3))))
    return pos


def test_dot_to_graph_ring12_substring_labels():
    """KI-8 pin. ring12 (lay2) has labels 1, 10, 11, 12: the lines of 10-12 also match
    '1'. The fixture's result is replicated; on the crafted cases 4, 5 and 9 the
    substring match gives a position to the wrong node."""
    path = FIXTURES_DIR / "dot_to_graph" / "lay2.dot"
    _, labels, x, y = dot_to_graph_file(path)
    assert {"1", "10", "11", "12"} <= set(labels)
    np.testing.assert_array_equal(x, D2G["x2"])
    # crafted case 5: labels ['1', '10;', '11', '1;']. The line '10 [pos="2,3"]' comes
    # first and matches the label '1', so node 1 takes node 10's position.
    k = 5
    got = dot_to_graph(FX["cr_text"][k])
    assert got[1] == ["1", "10;", "11", "1;"]
    whole = _whole_name_positions(FX["cr_text"][k])
    assert whole["1"] == (1.0, 1.0) and whole["10"] == (2.0, 3.0)

    def norm(raw):
        raw = np.array(raw, dtype=float)
        return 0.9 * (raw - raw.min()) / ((raw.max() - raw.min()) + 1) + 0.05

    np.testing.assert_array_equal(got[2], norm([whole["10"][0], 0, whole["11"][0], 0]))
    assert not np.array_equal(got[2], norm([whole["1"][0], 0, whole["11"][0], 0]))
    np.testing.assert_array_equal(got[2], FX["cr_x"][k])


@pytest.mark.parametrize("k", range(NCR))
def test_dot_to_graph_crafted_matches_octave(k):
    text = FX["cr_text"][k]
    err = _s(FX["cr_err"][k])
    warn = _s(FX["cr_warn"][k])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        if err:
            exc = {"valid DOT": ValueError, "'Adj' undefined": ValueError,
                   "out of bound": IndexError}
            (etype,) = [t for key, t in exc.items() if key in err]
            with pytest.raises(etype):
                dot_to_graph(text)
        else:
            _check_parse(text, FX["cr_A"][k], FX["cr_labels"][k], FX["cr_x"][k],
                         FX["cr_y"][k])
    warned = any("does not contain node coordinates" in str(m.message) for m in w)
    assert warned == ("does not contain node coordinates" in warn)


def test_ki33_right_node_keeps_semicolon_unless_longest_line():
    """KI-33: dot_to_graph.m:57 cuts the last character of the padded line."""
    with pytest.warns(UserWarning, match="node coordinates"):
        got = dot_to_graph(FX["cr_text"][0])     # 'a -- b -- c;' (longest), 'c -- a;'
    assert got[1] == ["a", "b", "c", "a;"]
    with pytest.warns(UserWarning, match="node coordinates"):
        got = dot_to_graph("graph G {\n1 -- 2;\n}")    # '1 -- 2;' is not the longest line
    assert got[1] == ["1", "2;"]
    with pytest.warns(UserWarning, match="node coordinates"):
        got = dot_to_graph("graph {\n1 -- 2;\n}")      # now it is
    assert got[1] == ["1", "2"]


def test_ki34_x_divided_by_range_plus_one():
    """KI-34: dot_to_graph.m:108 divides x by range+1, y by range."""
    _, _, x, y = dot_to_graph('graph G {\n1 -- 2 [x];\n1 [pos="0,0"];\n2 [pos="2,1"];\n}')
    np.testing.assert_array_equal(x, [0.05, 0.9 * 2 / 3 + 0.05])
    np.testing.assert_array_equal(y, [0.05, 0.9 * 1 / 1 + 0.05])
    _, _, x, y = dot_to_graph('graph G {\n1 -- 2 [x];\n1 [pos="4,3"];\n2 [pos="5,3"];\n}')
    np.testing.assert_array_equal(y, [0.5, 0.5])


def test_sscanf_pos():
    assert _sscanf_pos('pos="1.5,-2e1"];') == [1.5, -20.0]
    assert _sscanf_pos('pos = " 3 , 4"') == [3.0]            # ',' must follow %f directly
    assert _sscanf_pos('pos="7"') == [7.0]
    assert _sscanf_pos('position="1,2"') == []
    assert _sscanf_pos("pos") == []


def test_roundtrip_through_graph_to_dot():
    """graph_to_dot text parses back to the same adjacency (no positions: warns)."""
    adj = np.array([[0, 1, 1, 0], [0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 1, 0]])
    text = graph_to_dot(adj).replace(" ;", " [x];")      # keep ';' out of the names
    with pytest.warns(UserWarning, match="node coordinates"):
        A, labels, x, y = dot_to_graph(text)
    order = [int(s) - 1 for s in labels]
    np.testing.assert_array_equal((A > 0).astype(int), adj[np.ix_(order, order)])


def test_empty_text_raises():
    with pytest.raises(ValueError):
        dot_to_graph("\n  \n")


# --- live -----------------------------------------------------------------------------

@pytest.mark.octave
def test_viz_dot_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "viz_dot.mat"
    octave.feval("fx_viz_dot", str(out), nout=0)
    new = load_fixture(out.name, fixtures_dir=tmp_path)
    for key in ("bl_run", "bl_gt", "bl_lay", "go_text", "go_err", "cr_err", "neato_version"):
        assert [_s(v) for v in np.atleast_1d(new[key])] == \
            [_s(v) for v in np.atleast_1d(FX[key])], key
    for key in ("bl_A", "bl_x", "bl_y", "cr_A", "cr_x", "cr_y"):
        for a, b in zip(new[key], FX[key]):
            np.testing.assert_array_equal(a, b)
