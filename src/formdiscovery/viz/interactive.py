"""Shared pieces of the interactive backends (item 34, PLAN.md §6 phase B): plotly
(:mod:`.plotly_backend`) and pyvis (:mod:`.pyvis_backend`), both optional extras
(``pip install formdiscovery[interactive]``).

- :func:`edge_sets` splits the drawn edges as ``graph_draw.m:49, 72-94`` does: every
  nonzero ``adj[i, j]`` off the diagonal is an arrow ``i -> j``; with
  ``undirected='lines'`` a symmetric pair is one plain line instead (the branch the
  original disables, KI-37). Self-loops are not edges; they grey the node
  (``graph_draw.m:47-48``, :func:`.graph_draw.node_colors`).
- :func:`hover_text` builds the per-node hover text of a model graph from the node
  attributes of :func:`.networkx_backend.to_networkx` (``kind``, ``label``,
  ``cluster_id``): an object shows its name and cluster, a cluster node its members.
"""

import numpy as np

__all__ = ["UNDIRECTED", "have_plotly", "have_pyvis", "edge_sets", "default_hover",
           "hover_text"]

UNDIRECTED = ("arrows", "lines")


def have_plotly():
    """True when plotly can be imported."""
    try:
        import plotly.graph_objects  # noqa: F401
    except ImportError:
        return False
    return True


def have_pyvis():
    """True when pyvis can be imported."""
    try:
        import pyvis.network  # noqa: F401
    except ImportError:
        return False
    return True


def edge_sets(adj, undirected="arrows"):
    """``(arrows, lines)``: 0-based ``(i, j)`` pairs in row-major order. ``arrows`` are
    drawn ``i -> j`` (``graph_draw.m:72-94``); ``lines`` (only with
    ``undirected='lines'``) hold each symmetric pair once, ``i < j``, without a head."""
    if undirected not in UNDIRECTED:
        raise ValueError(f"undirected must be one of {UNDIRECTED}, not {undirected!r}")
    adj = np.asarray(adj, dtype=float)
    off = (adj != 0) & ~np.eye(adj.shape[0], dtype=bool)
    pairs = [(int(i), int(j)) for i, j in zip(*np.nonzero(off))]
    if undirected == "arrows":
        return pairs, []
    arrows = [(i, j) for i, j in pairs if not off[j, i]]
    lines = [(i, j) for i, j in pairs if off[j, i] and i < j]
    return arrows, lines


def default_hover(labels, sep="<br>"):
    """Hover text for a bare adjacency matrix: the label and the 0-based node index."""
    return [f"{s}{sep}node {k}" if s.strip() else f"node {k}"
            for k, s in enumerate(str(s) for s in labels)]


def hover_text(graph, names=None, sep="<br>"):
    """Per-node hover text of ``graph`` (a :class:`~formdiscovery.graph.Graph`, a
    MATLAB-style dict, or a matrix; see :func:`.networkx_backend.to_networkx`):

    - object ``i``: ``'<name><sep>object i, cluster c'`` (``c`` = ``cluster_id``, the
      0-based cluster node ``objcount + c``; omitted when unknown);
    - cluster node: ``'cluster c<sep>members: a, b, ...'`` (the objects with
      ``cluster_id == c``; ``'(none)'`` for an internal node).

    ``sep`` is ``'<br>'`` for plotly and ``'\\n'`` for pyvis (vis-network shows
    titles as plain text)."""
    from .networkx_backend import to_networkx

    G = to_networkx(graph, names)
    nodes = sorted(G.nodes)
    members = {}
    for v in nodes:
        a = G.nodes[v]
        if a["kind"] == "object" and a["cluster_id"] >= 0:
            members.setdefault(a["cluster_id"], []).append(a["label"] or f"object {v}")
    out = []
    for v in nodes:
        a = G.nodes[v]
        if a["kind"] == "object":
            head = a["label"] or f"object {v}"
            cl = f", cluster {a['cluster_id']}" if a["cluster_id"] >= 0 else ""
            out.append(f"{head}{sep}object {v}{cl}")
        else:
            m = members.get(a["cluster_id"])
            out.append(f"cluster {a['cluster_id']}{sep}members: "
                       + (", ".join(m) if m else "(none)"))
    return out
