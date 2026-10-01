"""DOT text: ``graph_to_dot.m`` and ``dot_to_graph.m`` (item 31, PLAN.md §6 phase A).

``draw_dot.m`` writes the adjacency matrix as DOT text (``graph_to_dot``), runs
``neato -Tdot`` on it and reads the node positions back from the layout (``dot_to_graph``).
These are pure-text ports of the two files; running neato and drawing are item 32.

Both functions replicate the original byte for byte, quirks included:

- ``graph_to_dot`` raises for an undirected graph with arc labels (``labeltext`` typo,
  KI-31), and prints a non-integer ``width``/``height`` as Octave's ``%d`` does (``%g``;
  MATLAB would print ``%e``, ANOMALIES.md).
- ``dot_to_graph`` pads every line to the longest one (``char``), so the character cut off
  after the right-hand node is a pad space except on the longest line (KI-33). Positions
  are found by carrying the last node seen with a ``[`` over to the next line holding
  ``pos`` (KI-7), by substring label matching (KI-8), and ``x`` is divided by its range
  plus one (KI-34).

Pinned by ``legacy/tests_octave/fx_viz_dot.m`` → ``tests/fixtures/viz_dot.mat``
(``tests/test_viz_dot.py``).
"""

import re
import warnings
from pathlib import Path

import numpy as np

# Octave's isspace / strtrim whitespace (plus the NUL strtrim also drops).
_WS = " \t\n\v\f\r"
_FLOAT_RE = re.compile(r"[+-]?(?:(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|inf|nan)", re.I)


def adj_is_directed(adj):
    """``draw_dot.m:35``: undirected iff ``triu(adj,1) == tril(adj,-1)'`` (``isequal``).

    The diagonal (self-loops) is ignored; any NaN makes the graph directed.
    """
    adj = np.asarray(adj, dtype=float)
    return not np.array_equal(np.triu(adj, 1), np.tril(adj, -1).T)


def _octave_d(v):
    """Octave's ``sprintf('%d', v)``: an integer as ``%d``, anything else as ``%g``."""
    v = float(v)
    if np.isfinite(v) and v == int(v) and abs(v) < 2.0**63:
        return str(int(v))
    if np.isnan(v):
        return "NaN"
    if np.isinf(v):
        return "Inf" if v > 0 else "-Inf"
    return "%g" % v


def _arc(arc_label, i, j):
    """``arc_label{i,j}`` (0-based) as ``fprintf('%s')`` prints it (``[]`` → ``''``)."""
    try:
        s = arc_label[i, j] if isinstance(arc_label, dict) else arc_label[i][j]
    except (KeyError, IndexError):
        s = None
    return "" if s is None else str(s)


def graph_to_dot(adj, node_label=None, arc_label=None, width=10, height=10, leftright=0,
                 directed=1, filename=None):
    """``graph_to_dot.m:1-85``: DOT text for the graph with adjacency matrix ``adj``.

    Nodes are written as ``1..n`` (MATLAB's 1-based numbers). ``node_label`` is a sequence
    of ``n`` strings; ``arc_label`` a 2-D sequence (``arc_label[i][j]``, 0-based, ``None``
    = MATLAB's empty cell) or a dict keyed by ``(i, j)``. Directed graphs get an edge for
    every nonzero ``adj[i, j]`` (row-major, l.69); undirected graphs one per nonzero entry
    of the strict upper triangle (l.71). Label strings are written unescaped, as in the
    original. The text has no final newline (``fprintf(fid, '}')``).

    ``filename`` (MATLAB default ``'tmp.dot'``) is optional here: the text is returned, and
    also written to ``filename`` when given.

    Raises ``NameError`` for ``directed=0`` with a non-empty ``arc_label``: l.50 assigns
    ``labeltext`` and l.66 reads the undefined ``labeltxt`` (KI-31). As in Octave, the
    header and node lines are written to ``filename`` before the error.
    """
    adj = np.asarray(adj)
    if adj.ndim != 2 or adj.shape[0] != adj.shape[1]:
        raise ValueError("graph_to_dot: adj must be a square matrix")
    has_arc = arc_label is not None and len(arc_label) > 0
    has_node = node_label is not None and len(node_label) > 0
    out = []
    if directed:
        out.append("digraph G {\n")
        arctxt = "->"
        labeltxt = '[label="%s"]' if has_arc else ""
    else:
        out.append("graph G {\n")
        arctxt = "--"
        labeltxt = None if has_arc else "[dir=none]"   # KI-31: 'labeltext' typo
    out.append("center = 1;\n")
    out.append('size="%s,%s";\n' % (_octave_d(width), _octave_d(height)))
    if leftright:
        out.append("rankdir=LR;\n")
    n = adj.shape[0]
    for node in range(n):
        if has_node:
            out.append('%d [ label = "%s" ];\n' % (node + 1, node_label[node]))
        else:
            out.append("%d;\n" % (node + 1))
    if labeltxt is None:
        if filename is not None:
            Path(filename).write_text("".join(out))
        raise NameError("'labeltxt' undefined (graph_to_dot.m:66; l.50 sets 'labeltext', KI-31)")
    # edgeformat (l.64) is '%d -> %d ;\n', '%d -- %d [dir=none];\n' or with [label="%s"]
    for node1 in range(n):
        if directed:
            arcs = np.flatnonzero(adj[node1, :])
        else:
            arcs = np.flatnonzero(adj[node1, node1 + 1:]) + node1 + 1
        for node2 in arcs:
            lab = labeltxt % _arc(arc_label, node1, node2) if has_arc else labeltxt
            out.append("%d %s %d %s;\n" % (node1 + 1, arctxt, node2 + 1, lab))
    out.append("}")
    text = "".join(out)
    if filename is not None:
        Path(filename).write_text(text)
    return text


def _strfind(s, pat):
    """Octave ``strfind``: 1-based start positions of every (overlapping) match."""
    if not pat:
        return []
    out, i = [], s.find(pat)
    while i >= 0:
        out.append(i + 1)
        i = s.find(pat, i + 1)
    return out


def _sub(s, a, b):
    """MATLAB ``s(a:b)`` with 1-based inclusive bounds (empty when ``b < a``)."""
    return s[a - 1:b] if b >= a else ""


def _sscanf_pos(s):
    """``sscanf(s, ' pos  = "%f,%f"')`` (``dot_to_graph.m:97``): the numbers read.

    Blanks in the format match any run of whitespace (or none), other characters match
    literally, ``%f`` skips leading whitespace. Stops at the first mismatch, so fewer than
    two numbers may come back.
    """
    vals, i = [], 0
    for tok in (" ", "p", "o", "s", " ", "=", " ", '"', "%f", ",", "%f"):
        if tok == " ":
            while i < len(s) and s[i] in _WS:
                i += 1
        elif tok == "%f":
            while i < len(s) and s[i] in _WS:
                i += 1
            m = _FLOAT_RE.match(s, i)
            if not m:
                break
            vals.append(float(m.group(0)))
            i = m.end()
        elif i < len(s) and s[i] == tok:
            i += 1
        else:
            break
    return vals


def normalise_xy(x, y):
    """``dot_to_graph.m:106-110``: ``x = .9*(x-min)/(range+1)+.05`` (KI-34),
    ``y = .9*(y-min)/range+.05`` (``0.5`` when the range is 0). The caller checks that
    some ``x`` is nonzero (l.103)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = 0.9 * (x - x.min()) / ((x.max() - x.min()) + 1) + 0.05
    if (y.max() - y.min()) == 0:
        y = 0.5 * np.ones(y.shape)
    else:
        y = 0.9 * (y - y.min()) / (y.max() - y.min()) + 0.05
    return x, y


def dot_to_graph(text):
    """``dot_to_graph.m:1-114`` (Octave-patched copy, PATCHES.md 10-15) on DOT ``text``.

    Returns ``(adj, labels, x, y)``: ``adj`` is ``N x N`` (float) with the edges numbered
    ``1, 2, ...`` in file order (both entries for ``--``); ``labels`` the node names in order
    of first appearance in an edge; ``x``, ``y`` the positions normalised to ``[0.05, 0.95]``.
    Nodes without edges are ignored, as in the original.

    - Lines (l.35-38): C comments removed, split on ``\\n``, trimmed, empty lines dropped,
      then padded with blanks to the longest line (``char``).
    - Edges (l.46-74): each ``' -- '``, then each ``' -> '`` of a line. The left node is
      every token between the previous edge and the operator, concatenated
      (``sscanf('%s')``); the right node is the first token after it, in the line minus its
      last character (KI-33).
    - Positions (l.79-101): KI-7 carry-over and KI-8 substring matching; the first
      ``pos`` of the line is read with ``' pos  = "%f,%f"'``.
    - Normalisation (l.103-110): with no nonzero ``x``, warns ``'File does not contain node
      coordinates.'`` and leaves ``x``, ``y`` unnormalised; otherwise
      ``x = .9*(x-min)/(range+1)+.05`` (KI-34) and ``y = .9*(y-min)/range+.05``
      (``0.5`` when the range is 0).

    Raises ``ValueError`` when the first line lacks ``'graph '`` (l.41), ``IndexError`` when
    a ``pos`` holds fewer than two numbers (l.98), and ``ValueError`` when there are no edges
    (``Adj`` undefined, l.111).
    """
    txt = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = [ln.strip(_WS + "\0") for ln in txt.split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("dot_to_graph: empty file")
    width = max(len(ln) for ln in lines)
    lines = [ln.ljust(width) for ln in lines]
    if "graph " not in lines[0]:
        raise ValueError("* * * File does not appear to be in valid DOT format. * * *")

    labels = []
    edges = {}
    unread = []
    edge_id = 1

    def index(name):
        if name not in labels:
            labels.append(name)
        return labels.index(name)

    for line in lines:
        ddash = [p + 1 for p in _strfind(line, " -- ")]
        arrow = [p + 1 for p in _strfind(line, " -> ")]
        left_bound = 1
        read = False
        for k, dash_pos in enumerate(ddash + arrow):
            lnode = "".join(_sub(line, left_bound, dash_pos - 2).split())
            rtoks = _sub(line, dash_pos + 3, len(line) - 1).split()
            rnode = rtoks[0] if rtoks else ""
            li = index(lnode)
            ri = index(rnode)
            edges[(li, ri)] = edge_id
            if k < len(ddash):
                edges[(ri, li)] = edge_id
            edge_id += 1
            left_bound = dash_pos + 3
            read = True
        if not read:
            unread.append(line)

    nvrt = len(labels)
    x = np.zeros(nvrt)
    y = np.zeros(nvrt)
    lst_node = -1
    for line in unread:
        bra_pos = _strfind(line, "[")
        pos_pos = _strfind(line, "pos")
        for node in range(nvrt):
            lbl_pos = _strfind(line, labels[node])
            if lbl_pos and bra_pos and x[node] == 0:
                if lbl_pos[0] < bra_pos[0]:
                    lst_node = node
        if pos_pos and lst_node >= 0:
            node_pos = _sscanf_pos(line[pos_pos[0] - 1:])
            if len(node_pos) < 2:
                raise IndexError("dot_to_graph: node_pos(%d) out of bound %d"
                                 % (len(node_pos) + 1, len(node_pos)))
            x[lst_node] = node_pos[0]
            y[lst_node] = node_pos[1]
            lst_node = -1

    if not np.any(x != 0):
        warnings.warn("File does not contain node coordinates.", stacklevel=2)
    else:
        x, y = normalise_xy(x, y)
    if not edges:
        raise ValueError("dot_to_graph: no edges ('Adj' undefined, dot_to_graph.m:111)")
    adj = np.zeros((nvrt, nvrt))
    for (i, j), e in edges.items():
        adj[i, j] = e
    return adj, labels, x, y


def dot_to_graph_file(path):
    """:func:`dot_to_graph` on the text of the file ``path`` (``fileread``)."""
    return dot_to_graph(Path(path).read_text())
