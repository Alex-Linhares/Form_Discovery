"""``graph_draw.m`` with matplotlib (item 32, PLAN.md §6 phase A).

``draw_dot.m`` hands the node positions to ``graph_draw(adj, 'node_labels', labels,
'fontsize', fontsz, 'node_shapes', zeros, 'X', x, 'Y', y, 'nodemult', nodemult)``, which
draws, on axes limited to the unit square:

- one ellipse per node (``textoval``), sized from the label's text extent: half-widths
  ``wx = nodemult * max(2/3 * width, height)``, ``wy = nodemult * height`` (l.117-120).
  The fill is white, or grey ``[.8 .8 .8]`` for a node with a self-loop (l.47-48);
- the label centred on it;
- one arrow per nonzero ``adj[i, j] == 1`` off the diagonal, from ``i`` to ``j`` (l.72-94).
  The end points are moved off the node centres by ``wd * (cos, sin)`` of the edge angle
  (not the true ellipse boundary). The branch that would draw a symmetric pair as one plain
  line is disabled (``if 0 % ckemp``), so an undirected edge gets two opposite arrows, i.e.
  a head at both ends (KI-37). ``my_arrow`` draws a filled head 5 points long with a 12
  degree half-angle and a 90 degree base (l.176-186).

The geometry is split into pure functions (:func:`node_colors`, :func:`node_halfwidths`,
:func:`edge_segments`) that are pinned against the original running in Octave
(``tests/octave/fx_viz_draw.m``); the text extents come from the renderer (Octave's fltk
and matplotlib's Agg fonts differ), so the parity tests feed Octave's half-widths ``wd``
back in. :func:`graph_draw` does the drawing.
"""

import math

import numpy as np

__all__ = ["GREY", "node_colors", "oval_halfwidths", "box_halfwidths", "node_halfwidths",
           "edge_segments", "arrow_head", "text_extents", "graph_draw"]

GREY = (0.8, 0.8, 0.8)
ARROW_LEN = 5.0        # my_arrow deflen (points)
ARROW_TIPANGLE = 12.0  # my_arrow deftipangle (degrees)
_ELLIPSE_T = np.arange(0.0, 2 * np.pi + 1e-12, np.pi / 30)  # t = 0:pi/30:2*pi (61 points)


def node_colors(adj):
    """``graph_draw.m:30, 47-48``: ``N x 3`` fill colours, white except grey ``[.8 .8 .8]``
    for the nodes with a nonzero diagonal entry (self-loop)."""
    adj = np.asarray(adj, dtype=float)
    color = np.ones((adj.shape[0], 3))
    color[np.flatnonzero(np.diag(adj)), :] = GREY
    return color


def oval_halfwidths(extents, nodemult=0.5):
    """``textoval`` (``graph_draw.m:117-120``): ``[wx wy]`` per node from the text
    extents ``[width height]`` (data units): ``wy = h``, ``wx = max(2/3 w, h)``, both
    times ``nodemult``."""
    e = np.asarray(extents, dtype=float).reshape(-1, 2)
    wy = e[:, 1]
    wx = np.maximum(2.0 / 3.0 * e[:, 0], wy)
    return np.column_stack([nodemult * wx, nodemult * wy])


def box_halfwidths(extents):
    """``textbox`` (``graph_draw.m:160-161``): ``wy = 2/3 h``, ``wx = max(2/3 w, wy)``;
    ``nodemult`` is not applied."""
    e = np.asarray(extents, dtype=float).reshape(-1, 2)
    wy = 2.0 / 3.0 * e[:, 1]
    return np.column_stack([np.maximum(2.0 / 3.0 * e[:, 0], wy), wy])


def node_halfwidths(extents, node_shapes=None, nodemult=0.5):
    """``graph_draw.m:58-70``: ovals for ``node_shapes == 0``, boxes otherwise, assembled
    into one ``N x 2`` array ``wd``."""
    e = np.asarray(extents, dtype=float).reshape(-1, 2)
    t = np.zeros(len(e)) if node_shapes is None else np.asarray(node_shapes).ravel()
    wd = np.zeros((len(e), 2))
    idx1, idx2 = np.flatnonzero(t == 0), np.flatnonzero(t != 0)
    if idx1.size:
        wd[idx1] = oval_halfwidths(e[idx1], nodemult)
    if idx2.size:
        wd[idx2] = box_halfwidths(e[idx2])
    return wd


def edge_segments(adj, x, y, wd):
    """``graph_draw.m:49, 72-94``: the arrows, in drawing order, as a list of
    ``(i, j, start, stop)`` (0-based nodes, ``start``/``stop`` = ``(x, y)``).

    The diagonal is removed first; then for each row ``i`` every ``j`` with
    ``adj[i, j] == 1`` (weights other than 1 are not drawn). With ``alpha`` the edge angle
    (``atan`` of the slope, ``±pi/2`` for a vertical edge) and ``sign = -1`` when
    ``x[j] <= x[i]`` (non-vertical), ``start = (x_i + s wd_i,x cos a, y_i + s wd_i,y sin
    a)`` and ``stop = (x_j - s wd_j,x cos a, y_j - s wd_j,y sin a)``. Both directions of
    a symmetric pair are listed (the one-line branch is disabled, KI-37).
    """
    adj = np.asarray(adj, dtype=float)
    adj = adj - np.diag(np.diag(adj))
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    wd = np.asarray(wd, dtype=float).reshape(-1, 2)
    out = []
    for node in range(adj.shape[0]):
        for node2 in np.flatnonzero(adj[node, :] == 1):
            sign = 1.0
            if (x[node2] - x[node]) == 0:
                alpha = -math.pi / 2 if y[node] > y[node2] else math.pi / 2
            else:
                alpha = math.atan((y[node2] - y[node]) / (x[node2] - x[node]))
                if x[node2] <= x[node]:
                    sign = -1.0
            dy1 = sign * wd[node, 1] * math.sin(alpha)
            dx1 = sign * wd[node, 0] * math.cos(alpha)
            dy2 = sign * wd[node2, 1] * math.sin(alpha)
            dx2 = sign * wd[node2, 0] * math.cos(alpha)
            out.append((node, int(node2), (x[node] + dx1, y[node] + dy1),
                        (x[node2] - dx2, y[node2] - dy2)))
    return out


def arrow_head(start, stop, to_display, length=ARROW_LEN, tipangle=ARROW_TIPANGLE):
    """The filled head of ``my_arrow`` (``graph_draw.m:176-186, 315-316, 357-521``) in display
    units: the tip at ``stop``, the base ``length`` points back along the arrow, half as
    wide as ``length * tan(tipangle)`` on each side (base angle 90 degrees, width 0).

    ``to_display`` maps data ``(x, y)`` to points. Returns the three corners (tip, base
    left, base right) in points, or ``None`` when ``start == stop``."""
    p0 = np.asarray(to_display(start), dtype=float)
    p1 = np.asarray(to_display(stop), dtype=float)
    d = p1 - p0
    n = math.hypot(*d)
    if n == 0:
        return None
    u = d / n
    perp = np.array([-u[1], u[0]])
    half = length * math.tan(math.radians(tipangle))
    base = p1 - length * u
    return np.array([p1, base + half * perp, base - half * perp])


def text_extents(ax, labels, fontsize):
    """MATLAB ``get(text(...), 'Extent')`` ``[width height]`` of each label in data
    units of ``ax``, measured by the figure's renderer. An empty label measures
    ``[0 0]``, as in Octave."""
    fig = ax.figure
    if not hasattr(fig.canvas, "get_renderer"):  # a bare Figure: attach an Agg canvas
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(fig)
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = np.zeros((len(labels), 2))
    for i, s in enumerate(labels):
        if s == "":
            continue
        t = ax.text(0.5, 0.5, s, ha="center", va="center", fontsize=fontsize)
        bb = t.get_window_extent(renderer)
        t.remove()
        (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        out[i] = (abs(x1 - x0), abs(y1 - y0))
    return out


def graph_draw(adj, node_labels=None, x=None, y=None, fontsize=8, node_shapes=None,
               nodemult=0.5, linestyle="-", linewidth=0.5, linecolor="black", ax=None,
               undirected="arrows", wd=None):
    """``graph_draw.m:1-101``: draw the graph on matplotlib axes ``ax`` (``None``: the
    current pyplot axes) with node ``i`` at ``(x[i], y[i])`` in the unit square.

    Returns ``(x, y, h)``: the positions and a dict of artists (``nodes``, ``labels``,
    ``edges``, ``heads``) plus ``wd``, the node half-widths used.

    - ``node_labels`` defaults to ``'1'..'N'`` (``int2str``); ``node_shapes`` to ovals.
      As in MATLAB, the fill colour of the ``k``-th oval (and box) is ``color[k]`` of the
      whole list, so a mixed ``node_shapes`` shifts the colours (``textoval(..., color,
      ...)`` indexes ``c(i,:)`` locally); draw_dot always passes ovals only.
    - ``undirected='arrows'`` (default, the original): every edge an arrow, a symmetric
      pair two. ``'lines'`` draws a symmetric pair as one plain line (the disabled
      branch, l.88-92), so arrows mark directed edges only.
    - ``wd`` overrides the measured half-widths (tests feed Octave's).
    - ``linestyle``/``linewidth``/``linecolor`` are used by the line branch only, as in
      MATLAB; arrows are always black, 0.5 wide.

    ``x``/``y`` are required (MATLAB's fallback ``make_layout`` is not in the release).
    """
    from matplotlib.patches import Polygon

    if ax is None:
        import matplotlib.pyplot as plt
        ax = plt.gca()
    adj = np.asarray(adj, dtype=float)
    n = adj.shape[0]
    if x is None or y is None:
        raise ValueError("graph_draw: X and Y are required (make_layout is not in the "
                         "release)")
    if undirected not in ("arrows", "lines"):
        raise ValueError("undirected must be 'arrows' or 'lines'")
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    labels = [str(i + 1) for i in range(n)] if node_labels is None else \
        ["" if s is None else str(s) for s in node_labels]
    shapes = np.zeros(n) if node_shapes is None else np.asarray(node_shapes).ravel()
    color = node_colors(adj)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True)

    if wd is None:
        wd = node_halfwidths(text_extents(ax, labels, fontsize), shapes, nodemult)
    wd = np.asarray(wd, dtype=float).reshape(-1, 2)

    h = {"nodes": [None] * n, "labels": [None] * n, "edges": [], "heads": [], "wd": wd}
    for group in (np.flatnonzero(shapes == 0), np.flatnonzero(shapes != 0)):
        for k, i in enumerate(group):  # c(k,:): local index into the full colour list
            rx, ry = wd[i]
            if shapes[i] == 0:
                pts = np.column_stack([rx * np.cos(_ELLIPSE_T) + x[i],
                                       ry * np.sin(_ELLIPSE_T) + y[i]])
            else:
                pts = np.array([[x[i] - rx, y[i] + ry], [x[i] + rx, y[i] + ry],
                                [x[i] + rx, y[i] - ry], [x[i] - rx, y[i] - ry]])
            p = Polygon(pts, closed=True, facecolor=tuple(color[k]), edgecolor="black",
                        linewidth=0.5, zorder=1)
            ax.add_patch(p)
            h["nodes"][i] = p
            fs = fontsize if shapes[i] == 0 else None
            h["labels"][i] = ax.text(x[i], y[i], labels[i], ha="center", va="center",
                                     fontsize=fs, zorder=2)

    segs = edge_segments(adj, x, y, wd)
    sym = adj - np.diag(np.diag(adj))
    to_pts = _points_transform(ax)
    for i, j, start, stop in segs:
        if undirected == "lines" and sym[j, i] != 0:
            if i < j:
                h["edges"].append(ax.plot([start[0], stop[0]], [start[1], stop[1]],
                                          color=linecolor, linestyle=linestyle,
                                          linewidth=linewidth, zorder=3)[0])
            continue
        h["edges"].append(ax.plot([start[0], stop[0]], [start[1], stop[1]], color="black",
                                  linewidth=0.5, solid_capstyle="butt", zorder=3)[0])
        head = arrow_head(start, stop, to_pts)
        if head is not None:
            hp = Polygon(to_pts.inverse(head), closed=True, facecolor="black",
                         edgecolor="black", linewidth=0.5, zorder=3)
            ax.add_patch(hp)
            h["heads"].append(hp)
    return x, y, h


class _points_transform:
    """Data <-> points (1/72 inch) for ``ax`` at its current size."""

    def __init__(self, ax):
        self.data = ax.transData
        self.scale = 72.0 / ax.figure.dpi

    def __call__(self, p):
        return np.asarray(self.data.transform(p), dtype=float) * self.scale

    def inverse(self, pts):
        return self.data.inverted().transform(np.asarray(pts, dtype=float) / self.scale)
