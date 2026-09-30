"""pyvis backend (item 34, PLAN.md §6 phase B; optional extra ``interactive``).

:func:`draw_pyvis` builds a ``pyvis.network.Network`` (vis-network, for notebooks and
standalone HTML) with the nodes pinned at draw_dot's positions: node ``i`` at
``(scale * x[i], -scale * y[i])`` (screen ``y`` points down), physics off, so the
drawing is the neato layout of ``draw_dot.m`` and not vis-network's own. Nodes are
white ellipses with a black border, grey (``.8``) for self-loop nodes
(``graph_draw.m:47-48``), labelled, with a hover ``title``; edges are arrows ``i -> j``
(``graph_draw.m:72-94``: two opposite arrows for a symmetric pair, KI-37) or one
head-less line per symmetric pair with ``undirected='lines'``. Self-loops are not drawn.

The node ids are the 0-based node indices. Write the page with
``net.write_html(path)`` or embed ``net.generate_html()``.
"""

import numpy as np

from .graph_draw import node_colors
from .interactive import default_hover, edge_sets
from .plotly_backend import rgb

__all__ = ["SCALE", "draw_pyvis"]

SCALE = 600.0  # pixels per unit of the unit square


def draw_pyvis(adj, labels, x, y, net=None, fontsize=8, undirected="arrows",
               hover=None, scale=SCALE, width="700px", height="525px",
               cdn_resources="remote", notebook=False):
    """Draw ``adj`` (see the module docstring) and return the pyvis network.

    - ``net``: a directed ``Network`` to add to (``None``: a new one of ``width x
      height``, with ``cdn_resources`` and ``notebook`` passed on). pyvis keeps one edge
      per pair in an undirected network, so an undirected ``net`` raises.
    - ``hover``: one string per node (``None``: :func:`.interactive.default_hover` with
      newlines; vis-network shows titles as plain text).
    - ``fontsize``: label size in points (draw_dot's ``fontsz``), shown as pixels
      ``4/3`` larger.
    """
    from pyvis.network import Network

    adj = np.asarray(adj, dtype=float)
    n = adj.shape[0]
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    labels = ["" if s is None else str(s) for s in labels]
    if len(labels) < n or len(x) < n or len(y) < n:
        raise ValueError(f"draw_pyvis: {n} nodes need {n} labels and positions")
    arrows, lines = edge_sets(adj, undirected)
    if hover is None:
        hover = default_hover(labels[:n], sep="\n")
    if net is None:
        net = Network(height=height, width=width, directed=True, notebook=notebook,
                      cdn_resources=cdn_resources)
    elif not net.directed:
        raise ValueError("draw_pyvis: net must be directed (an undirected pyvis Network "
                         "drops the second arrow of a symmetric pair)")
    net.toggle_physics(False)
    colors = node_colors(adj)
    for k in range(n):
        # vis-network drops an empty label and shows the id: use a blank
        net.add_node(k, label=labels[k] or " ", title=str(hover[k]),
                     x=float(scale * x[k]), y=float(-scale * y[k]), physics=False,
                     shape="ellipse",
                     color={"background": rgb(colors[k]), "border": "black"},
                     font={"size": fontsize * 4 / 3, "color": "black"})
    for i, j in arrows:
        net.add_edge(i, j, arrows="to", color="black", width=1)
    for i, j in lines:
        net.add_edge(i, j, arrows={"to": {"enabled": False}}, color="black", width=1)
    return net
