"""plotly backend (item 34, PLAN.md §6 phase B; optional extra ``interactive``).

:func:`draw_plotly` draws what ``graph_draw.m`` draws, as a ``plotly.graph_objects``
figure on the unit square: node ``i`` at ``(x[i], y[i])`` (draw_dot's positions, from
:func:`.networkx_backend.nx_layout` in the ``draw_dot(..., backend='plotly')`` facade),
white markers with a black outline, grey (``.8``) for self-loop nodes
(``graph_draw.m:47-48``), the label centred on the node, one arrow annotation per edge
``i -> j`` (``graph_draw.m:72-94``; two opposite arrows for a symmetric pair, KI-37, or
one line with ``undirected='lines'``), and hover text per node (:func:`.interactive
.hover_text` for a model graph).

The figure keeps the geometry in plain data: ``fig.data`` holds a ``'lines'`` trace
(the head-less edges, ``None``-separated) and a ``'nodes'`` trace (``x``, ``y``,
``text`` = labels, ``hovertext``, ``marker.color``); ``fig.layout.annotations`` holds
the arrows (``ax, ay`` → ``x, y`` in data coordinates). Subplots (``row``/``col`` of a
``make_subplots`` figure) are supported, for :func:`.draw.draw_results`.
"""

import numpy as np

from .graph_draw import node_colors
from .interactive import default_hover, edge_sets

__all__ = ["draw_plotly", "rgb"]


def rgb(c):
    """An RGB triple in [0, 1] as a plotly colour string."""
    return "rgb({},{},{})".format(*(int(round(255 * float(v))) for v in c))


def draw_plotly(adj, labels, x, y, fig=None, fontsize=8, nodemult=0.5,
                undirected="arrows", node_size=None, hover=None, row=None, col=None,
                title=None):
    """Draw ``adj`` (see the module docstring) and return the plotly figure.

    - ``fig``: a figure to draw into (``None``: a new ``go.Figure``); with ``row`` and
      ``col``, a subplot of a ``make_subplots`` figure.
    - ``node_size``: marker diameter in pixels, default ``nodemult`` times 60 (40 for 60
      nodes or more), as :func:`.networkx_backend.draw_networkx` scales it.
    - ``hover``: one string per node (``None``: :func:`.interactive.default_hover`).
    - ``fontsize``: label size in points (draw_dot's ``fontsz``).
    """
    import plotly.graph_objects as go

    adj = np.asarray(adj, dtype=float)
    n = adj.shape[0]
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    labels = ["" if s is None else str(s) for s in labels]
    if len(labels) < n or len(x) < n or len(y) < n:
        raise ValueError(f"draw_plotly: {n} nodes need {n} labels and positions")
    arrows, lines = edge_sets(adj, undirected)
    if hover is None:
        hover = default_hover(labels[:n])
    if node_size is None:
        node_size = nodemult * (40 if n >= 60 else 60)
    if fig is None:
        fig = go.Figure()
    sub = {} if row is None else {"row": row, "col": col}
    lx, ly = [], []
    for i, j in lines:
        lx += [x[i], x[j], None]
        ly += [y[i], y[j], None]
    fig.add_trace(go.Scatter(x=lx, y=ly, mode="lines", name="lines", hoverinfo="skip",
                             line={"color": "black", "width": 1}, showlegend=False),
                  **sub)
    for i, j in arrows:
        fig.add_annotation(x=x[j], y=y[j], ax=x[i], ay=y[i], showarrow=True,
                           arrowhead=2, arrowsize=1, arrowwidth=1, arrowcolor="black",
                           standoff=node_size / 2, startstandoff=node_size / 2, text="",
                           **sub)
        a = fig.layout.annotations[-1]
        a.axref, a.ayref = a.xref or "x", a.yref or "y"  # tail in data coordinates
    fig.add_trace(go.Scatter(x=x[:n], y=y[:n], mode="markers+text", name="nodes",
                             text=labels[:n], textposition="middle center",
                             textfont={"size": fontsize * 4 / 3, "color": "black"},
                             hovertext=list(hover[:n]), hoverinfo="text",
                             marker={"size": node_size,
                                     "color": [rgb(c) for c in node_colors(adj)],
                                     "line": {"color": "black", "width": 1}},
                             showlegend=False),
                  **sub)
    ax = {"range": [0, 1], "showticklabels": False, "showgrid": False, "zeroline": False,
          "mirror": True, "showline": True, "linecolor": "black"}
    fig.update_xaxes(**ax, **sub)
    fig.update_yaxes(**ax, **sub)
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      margin={"l": 20, "r": 20, "t": 40, "b": 20})
    if title is not None and row is None:
        fig.update_layout(title=title)
    return fig
