"""networkx backend and exports (item 33, PLAN.md §6 phase B).

Conversion:

- :func:`to_networkx` turns a :class:`formdiscovery.graph.Graph` (or a MATLAB-style
  ``graph`` dict, or a bare adjacency matrix) into a ``networkx.DiGraph``/``Graph``. Nodes
  are the 0-based indices of ``graph.adj`` (objects ``0..objcount-1``, then the cluster
  nodes, CONVENTIONS.md), with attributes ``kind`` (``'object'``/``'cluster'``),
  ``label`` (the object name, ``''`` for clusters) and ``cluster_id`` (``z`` of an
  object, ``-1`` if missing; ``node - objcount`` of a cluster node, the value ``z``
  takes for its objects). Edges carry ``W`` (the model's edge weight,
  ``inv_covariance.m``: the Laplacian of ``W``) and ``weight = 1/W`` (the branch
  length, the distance networkx layouts read). Graph attributes: ``type``,
  ``objcount``, and ``sigma`` when set.
- :func:`from_networkx` inverts it: ``(adj, W, labels, kind, cluster_id)``.
- :func:`to_graphml`/:func:`from_graphml` and :func:`to_dot`/:func:`from_dot` write and
  read these attributes (Gephi, Cytoscape, Graphviz). The DOT text is written without
  pygraphviz; it carries ``len = 1/W`` (Graphviz's preferred edge length) instead of
  ``weight``, which Graphviz reads as an integer edge strength. Reading DOT needs
  pygraphviz.

Drawing (``draw_dot(..., backend='networkx')``, :mod:`.draw`):

- :func:`nx_layout` lays the binarised ``adj`` out as draw_dot does. With pygraphviz,
  ``nx.nx_agraph.graphviz_layout(prog='neato')`` on the graph ``graph_to_dot`` writes
  (nodes ``'1'..'n'``, its edge order, ``center``/``size``) with draw_dot's neato
  attributes (:func:`.pygraphviz_backend.neato_args`): the points equal those in the
  neato text Octave parses, so the positions equal draw_dot's exactly
  (``tests/test_viz_networkx.py``). Without it, ``nx.kamada_kawai_layout`` (the stress
  model closest to neato's), scaled to a mean edge length of 72 points as neato's.
  Either way the points are normalised as
  ``dot_to_graph.m:103-110`` (KI-34) and ordered as ``draw_dot.m:52-72`` (singletons at
  0.05, :func:`.draw.order_positions`).
- :func:`draw_networkx` draws with ``nx.draw_networkx_*`` on the unit square: grey fill
  for self-loop nodes (``graph_draw.m:47-48``), no self-loop edges, arrows for directed
  graphs; symmetric pairs as two arrows (``undirected='arrows'``, KI-37) or one line.
"""

import math
from pathlib import Path

import numpy as np

from .dot import adj_is_directed, normalise_xy

__all__ = ["LAYOUTS", "to_networkx", "from_networkx", "to_graphml", "from_graphml",
           "to_dot", "from_dot", "have_graphviz_layout", "nx_layout", "draw_networkx"]

LAYOUTS = ("auto", "neato", "kamada_kawai")
NEATO_EDGE_PT = 72.0  # neato's default edge length (len = 1 inch)


# --- conversion -------------------------------------------------------------------------

def _get(graph, field):
    if isinstance(graph, dict):
        return graph.get(field)
    return getattr(graph, field, None)


def _py(v):
    """numpy scalars as Python scalars (GraphML writes Python types only)."""
    return v.item() if isinstance(v, np.generic) else v


def to_networkx(graph, names=None, directed=None):
    """``graph`` (:class:`~formdiscovery.graph.Graph`, a dict with the same fields, or an
    ``n x n`` adjacency matrix) as a networkx graph; see the module docstring.

    - ``names``: the object names (``names[i]`` labels object ``i``; missing or ``None``
      entries give ``''``). For a bare matrix every node is an object.
    - ``directed``: ``None`` (default) decides as ``draw_dot.m:35`` (``adj`` not
      symmetric → ``DiGraph``; the stored ``graph.adj`` of every form is one-directional,
      so this gives a ``DiGraph``). ``False`` gives a ``Graph`` over ``adj | adj'``, each
      pair once with the ``W`` of the first direction found in row-major order
      (``adjsym``/``Wsym`` hold both).

    Edges are the nonzero ``adj`` entries off and on the diagonal, in row-major order;
    ``W`` comes from ``graph.W`` (``adj`` itself for a matrix), ``weight = 1/W``
    (``inf`` where ``W == 0``).
    """
    import networkx as nx

    if isinstance(graph, np.ndarray) or isinstance(graph, (list, tuple)):
        adj = np.atleast_2d(np.asarray(graph, dtype=float))
        W = adj.copy()
        objcount, z, attrs = adj.shape[0], None, {}
    else:
        adj = np.atleast_2d(np.asarray(_get(graph, "adj"), dtype=float))
        Wg = _get(graph, "W")
        W = (adj != 0).astype(float) if Wg is None else \
            np.atleast_2d(np.asarray(Wg, dtype=float))
        objcount = int(_get(graph, "objcount"))
        z = _get(graph, "z")
        attrs = {"type": str(_get(graph, "type") or ""), "objcount": objcount}
        if _get(graph, "sigma") is not None:
            attrs["sigma"] = float(_get(graph, "sigma"))
    n = adj.shape[0]
    if adj.ndim != 2 or adj.shape[1] != n or W.shape != adj.shape:
        raise ValueError("to_networkx: adj and W must be square and of the same size")
    if directed is None:
        directed = adj_is_directed(adj)
    G = nx.DiGraph(**attrs) if directed else nx.Graph(**attrs)
    names = [] if names is None else list(names)
    zs = None if z is None else np.asarray(z, dtype=int).ravel()
    for i in range(n):
        if i < objcount:
            lab = names[i] if i < len(names) and names[i] is not None else ""
            cid = int(zs[i]) if zs is not None and i < len(zs) else -1
            G.add_node(i, kind="object", label=str(lab), cluster_id=cid)
        else:
            G.add_node(i, kind="cluster", label="", cluster_id=i - objcount)
    for i, j in zip(*np.nonzero(adj)):
        i, j = int(i), int(j)
        if not directed and G.has_edge(i, j):
            continue
        w = float(W[i, j])
        G.add_edge(i, j, W=w, weight=math.inf if w == 0 else 1.0 / w)
    return G


def _node_index(G):
    """The nodes of ``G`` as ``{node: 0-based index}``: the integer value of each node
    (GraphML/DOT readers give strings) when they are ``0..n-1``, else ``G``'s order."""
    nodes = list(G.nodes)
    try:
        ints = [int(v) for v in nodes]
    except (TypeError, ValueError):
        ints = None
    if ints is not None and sorted(ints) == list(range(len(nodes))):
        return dict(zip(nodes, ints))
    return {v: k for k, v in enumerate(nodes)}


def from_networkx(G):
    """The inverse of :func:`to_networkx`: a dict with ``adj`` (bool ``n x n``), ``W``,
    ``labels``, ``kind`` and ``cluster_id`` (lists in node order), ``directed``, and
    the graph attributes (``type``, ``objcount``, ``sigma``) when present.

    ``W`` is read from the ``W`` edge attribute, else as ``1/weight``, else 1. An
    undirected graph gives symmetric ``adj``/``W``. Nodes are ordered by
    :func:`_node_index` (their integer value, so a GraphML or DOT file read back keeps
    the numbering)."""
    idx = _node_index(G)
    n = len(idx)
    adj = np.zeros((n, n), dtype=bool)
    W = np.zeros((n, n))
    for u, v, d in G.edges(data=True):
        i, j = idx[u], idx[v]
        if "W" in d:
            w = float(d["W"])
        elif "weight" in d:
            w = 1.0 / float(d["weight"]) if float(d["weight"]) != 0 else math.inf
        else:
            w = 1.0
        adj[i, j] = True
        W[i, j] = w
        if not G.is_directed():
            adj[j, i] = True
            W[j, i] = w
    order = sorted(idx, key=idx.get)
    nd = G.nodes
    out = {"adj": adj, "W": W, "directed": G.is_directed(),
           "labels": [str(nd[v].get("label", "")) for v in order],
           "kind": [str(nd[v].get("kind", "object")) for v in order],
           "cluster_id": [int(nd[v].get("cluster_id", -1)) for v in order]}
    for k in ("type", "objcount", "sigma"):
        if k in G.graph:
            out[k] = G.graph[k]
    if "objcount" in out:
        out["objcount"] = int(out["objcount"])
    if "sigma" in out:
        out["sigma"] = float(out["sigma"])
    return out


def to_graphml(graph, path, names=None, directed=None):
    """Write :func:`to_networkx` of ``graph`` as GraphML to ``path``; returns the
    networkx graph."""
    import networkx as nx

    G = graph if _is_nx(graph) else to_networkx(graph, names, directed)
    H = G.copy()
    H.graph = {k: _py(v) for k, v in H.graph.items()}
    nx.write_graphml(H, str(path))
    return G


def from_graphml(path):
    """:func:`from_networkx` of the GraphML file ``path`` (as :func:`to_graphml` writes
    it)."""
    import networkx as nx

    return from_networkx(nx.read_graphml(str(path)))


def _is_nx(g):
    try:
        import networkx as nx
    except ImportError:
        return False
    return isinstance(g, nx.Graph)


def _dot_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _dot_val(v):
    if isinstance(v, (bool, np.bool_)):
        return _dot_str(str(bool(v)).lower())
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v)) if math.isfinite(v) else _dot_str(repr(float(v)))
    return _dot_str(v)


def to_dot(graph, path=None, names=None, directed=None):
    """DOT text of :func:`to_networkx` of ``graph`` (or of a networkx graph), written to
    ``path`` when given. Nodes are the 0-based indices with ``kind``, ``label`` and
    ``cluster_id``; edges carry ``W`` and ``len = 1/W`` (omitted where ``W == 0``).
    Floats are written with ``repr``, so they read back exactly. This is an export
    format; draw_dot's own DOT text is :func:`.dot.graph_to_dot`."""
    G = graph if _is_nx(graph) else to_networkx(graph, names, directed)
    op = "->" if G.is_directed() else "--"
    out = [("digraph" if G.is_directed() else "graph") + " G {\n"]
    for k, v in G.graph.items():
        out.append(f"  {k}={_dot_val(v)};\n")
    for v, d in G.nodes(data=True):
        a = ", ".join(f"{k}={_dot_val(x)}" for k, x in d.items())
        out.append(f"  {v} [{a}];\n" if a else f"  {v};\n")
    for u, v, d in G.edges(data=True):
        d = dict(d)
        w = d.pop("weight", None)
        if "W" in d and d["W"] != 0:
            d["len"] = 1.0 / float(d["W"])
        elif w is not None and math.isfinite(w):
            d["len"] = float(w)
        a = ", ".join(f"{k}={_dot_val(x)}" for k, x in d.items())
        out.append(f"  {u} {op} {v} [{a}];\n" if a else f"  {u} {op} {v};\n")
    out.append("}\n")
    text = "".join(out)
    if path is not None:
        Path(path).write_text(text)
    return text


def from_dot(text):
    """:func:`from_networkx` of DOT ``text`` (as :func:`to_dot` writes it), parsed by
    pygraphviz. Attribute values are strings in DOT, so ``W``, ``cluster_id``,
    ``objcount`` and ``sigma`` are converted back; ``len`` is ignored when ``W`` is
    present."""
    import networkx as nx
    import pygraphviz

    A = pygraphviz.AGraph(string=text)
    G = nx.nx_agraph.from_agraph(A)
    for _, _, d in G.edges(data=True):
        if "W" in d:
            d["W"] = float(d["W"])
        elif "len" in d:
            d["W"] = 1.0 / float(d["len"])
    g = {k: v for k, v in A.graph_attr.items() if k in ("type", "objcount", "sigma")}
    G.graph = g
    return from_networkx(G)


# --- layout and drawing -----------------------------------------------------------------

def have_graphviz_layout():
    """``nx.nx_agraph.graphviz_layout`` needs pygraphviz."""
    from .pygraphviz_backend import have_pygraphviz

    return have_pygraphviz()


def _dot_order(adj, directed):
    """The edges ``graph_to_dot`` writes (``graph_to_dot.m:69-71``: row-major, the upper
    triangle when undirected) and the nodes in order of first appearance in them (the
    order ``dot_to_graph`` returns), 0-based."""
    n = adj.shape[0]
    edges, order, seen = [], [], set()
    for i in range(n):
        js = np.flatnonzero(adj[i]) if directed else np.flatnonzero(adj[i, i + 1:]) + i + 1
        for j in js:
            edges.append((i, int(j)))
            for v in (i, int(j)):
                if v not in seen:
                    seen.add(v)
                    order.append(v)
    return edges, order


def nx_layout(adj, layout="auto", flags="matlab"):
    """draw_dot's layout of ``adj`` with networkx: ``(names, x, y)`` for the nodes in some
    edge, in order of first appearance (``names`` are ``'1'..'n'``), normalised as
    ``dot_to_graph.m:103-110``; pass them to :func:`.draw.order_positions`.

    ``layout='neato'``: ``graphviz_layout(prog='neato')`` with draw_dot's attributes
    (``flags``, :func:`.pygraphviz_backend.neato_args`), exactly draw_dot's positions;
    ``'kamada_kawai'``: ``nx.kamada_kawai_layout`` of the same graph, undirected
    (deterministic; scaled to a mean edge length of 72 points, neato's 1 inch, so that
    KI-34's ``range + 1`` stays negligible; the ``flags`` do not apply); ``'auto'``: neato when pygraphviz is installed. A graph with
    no edges raises ``ValueError``, as ``dot_to_graph`` does."""
    import networkx as nx

    from .pygraphviz_backend import neato_attrs, neato_args

    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, not {layout!r}")
    adj = np.asarray(adj, dtype=float)
    directed = adj_is_directed(adj)
    b = adj > 0
    n = b.shape[0]
    edges, order = _dot_order(b, directed)
    if not edges:
        raise ValueError("nx_layout: no edges ('Adj' undefined, dot_to_graph.m:111)")
    if layout == "auto":
        layout = "neato" if have_graphviz_layout() else "kamada_kawai"
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(str(i + 1) for i in range(n))
    G.add_edges_from((str(i + 1), str(j + 1)) for i, j in edges)
    if layout == "neato":
        _, reduce = neato_attrs(n, flags)
        if reduce:
            raise ValueError("neato's -x (flags='intended', n > 100) is not available "
                             "through graphviz_layout")
        G.graph["graph"] = {"center": "1", "size": "10,10"}  # graph_to_dot.m:36-37
        pos = nx.nx_agraph.graphviz_layout(G, prog="neato",
                                           args=" ".join(neato_args(n, flags)[1:]))
    else:
        H = G.to_undirected().subgraph(str(v + 1) for v in order)
        pos = nx.kamada_kawai_layout(H, weight=None)
        # in points, mean edge length neato's default 1 inch: KI-34's range + 1 is then
        # as negligible as it is on neato's output (on [-1, 1] it squeezes x threefold)
        el = np.mean([math.dist(pos[u], pos[v]) for u, v in H.edges if u != v] or [1.0])
        pos = {v: (NEATO_EDGE_PT * p[0] / el, NEATO_EDGE_PT * p[1] / el)
               for v, p in pos.items()}
    names = [str(v + 1) for v in order]
    x = np.array([pos[s][0] for s in names], dtype=float)
    y = np.array([pos[s][1] for s in names], dtype=float)
    if np.any(x != 0):
        x, y = normalise_xy(x, y)
    return names, x, y


def draw_networkx(adj, labels, x, y, ax=None, fontsize=8, nodemult=0.5,
                  undirected="arrows", node_size=None):
    """Draw ``adj`` with ``nx.draw_networkx_nodes/edges/labels`` on ``ax`` (``None``: the
    current pyplot axes), node ``i`` at ``(x[i], y[i])`` in the unit square, labelled
    ``labels[i]``. Nodes are white circles with a black edge, grey (``.8``) for self-loop
    nodes; self-loops are not drawn as edges (``graph_draw.m:47-49``). ``node_size``
    (points²) defaults to ``nodemult`` times 1200 (500 for 60 nodes or more).
    Returns the networkx graph drawn (nodes ``0..n-1``) and a dict of the artists."""
    import networkx as nx

    from .graph_draw import node_colors

    if ax is None:
        import matplotlib.pyplot as plt
        ax = plt.gca()
    if undirected not in ("arrows", "lines"):
        raise ValueError("undirected must be 'arrows' or 'lines'")
    adj = np.asarray(adj, dtype=float)
    n = adj.shape[0]
    off = (adj != 0) & ~np.eye(n, dtype=bool)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    G.add_edges_from((int(i), int(j)) for i, j in zip(*np.nonzero(off)))
    pos = {i: (float(x[i]), float(y[i])) for i in range(n)}
    if node_size is None:
        node_size = nodemult * (500 if n >= 60 else 1200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    h = {"nodes": nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_size,
                                         node_color=[tuple(c) for c in node_colors(adj)],
                                         edgecolors="black", linewidths=0.5)}
    if undirected == "lines":
        sym = [(i, j) for i, j in G.edges if G.has_edge(j, i)]
        one = [(i, j) for i, j in G.edges if not G.has_edge(j, i)]
        h["lines"] = nx.draw_networkx_edges(G, pos, edgelist=[(i, j) for i, j in sym
                                                              if i < j],
                                            ax=ax, arrows=False, width=0.5)
    else:
        one = list(G.edges)
    h["edges"] = nx.draw_networkx_edges(G, pos, edgelist=one, ax=ax, arrows=True,
                                        arrowstyle="-|>", arrowsize=8, width=0.5,
                                        node_size=node_size)
    h["labels"] = nx.draw_networkx_labels(G, pos, {i: str(labels[i]) for i in range(n)},
                                          ax=ax, font_size=fontsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_on()
    return G, h
