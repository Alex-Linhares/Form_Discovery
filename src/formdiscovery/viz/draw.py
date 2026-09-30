"""``draw_dot.m`` facade and progress figures (item 32, PLAN.md §6 phase A; the
networkx backend is item 33, the interactive plotly and pyvis backends item 34).

:func:`draw_dot` is ``draw_dot(adj, labels, 'pos', ..., 'nodemult', ..., 'fontsz', ...)``:
lay the graph out with neato (:mod:`.pygraphviz_backend`), read the positions back
(:func:`dot_positions`, ``draw_dot.m:52-72``) and draw with :func:`.graph_draw.graph_draw`
on matplotlib axes. The temporary ``_GtDout.dot``/``_LAYout.dot`` files are not written.

:class:`ProgressFigures` is a ``show`` callback for :func:`formdiscovery.run.runmodel`,
:func:`formdiscovery.search.structurefit` and :func:`formdiscovery.search.best_split`: it
reproduces MATLAB's figures 1 (true graph / pre-clean), 2 (post-clean) and 3 (best split /
inferred graph), live and/or as numbered image files.

:func:`draw_graph` draws a model graph (a :class:`formdiscovery.graph.Graph` with its
object names) through the facade, with per-node hover text for the interactive
backends (:func:`.interactive.hover_text`).
"""

import warnings
from pathlib import Path

import numpy as np

from .dot import dot_to_graph
from .graph_draw import graph_draw

__all__ = ["BACKENDS", "INTERACTIVE", "FIGURE", "default_fontsize", "dot_positions", "order_positions",
           "draw_dot",
           "draw_graph", "pad_names", "ProgressFigures", "draw_results"]

BACKENDS = ("pygraphviz", "networkx", "plotly", "pyvis")
# backends that draw into a plotly figure / pyvis network instead of matplotlib axes
INTERACTIVE = ("plotly", "pyvis")
# MATLAB figure number of each show event (runmodel.m:41,183, structurefit.m:86,199,
# best_split.m:153)
FIGURE = {"truegraph": 1, "preclean": 1, "postclean": 2, "bestsplit": 3,
          "inferredgraph": 3}


def default_fontsize(n):
    """``draw_dot.m:76-78``: 7 for ``n > 40``, 12 for ``n < 12``, else 9."""
    return 7 if n > 40 else (12 if n < 12 else 9)


def pad_names(names, n, fill=""):
    """``runmodel.m:42-44``/``structurefit.m:89-91``: ``names`` extended to ``n`` entries
    with ``fill`` (``''``, or ``' '`` in structurefit's figures)."""
    names = [] if names is None else ["" if s is None else str(s) for s in names]
    return names + [fill] * (n - len(names))


def dot_positions(lay, n, pos=None):
    """``draw_dot.m:52-72``: node positions from neato's layout text ``lay`` for an
    ``n``-node graph. Returns ``(xret, yret, x, y, names)``:

    - ``xret``/``yret``: :func:`.dot.dot_to_graph`'s positions, in order of first
      appearance in an edge, with the nodes that are in no edge (singletons) appended
      at ``0.05`` in increasing order (``mysetdiff``); draw_dot's first outputs;
    - ``x``/``y``: the same sorted by node number (node ``i`` at index ``i - 1``), what
      graph_draw gets, unless ``pos`` (``2 x n``, draw_dot's ``'pos'``) replaces them;
    - ``names``: node-number labels in sorted order (draw_dot's labels when none given).
    """
    _, names, x, y = dot_to_graph(lay)
    return order_positions(names, x, y, n, pos)


def order_positions(names, x, y, n, pos=None):
    """:func:`dot_positions` after the parse (``draw_dot.m:55-72``): ``names`` are the
    node numbers (strings, ``'1'..'n'``) of the laid-out nodes, ``x``/``y`` their
    normalised positions, in the same order."""
    num = [int(float(s)) for s in names]  # str2num(char(names))
    x = list(np.asarray(x, dtype=float).ravel())
    y = list(np.asarray(y, dtype=float).ravel())
    names = list(names)
    if len(names) < n:  # singletons without coordinates, lower left
        seen = set(num)
        rest = [k for k in range(1, n + 1) if k not in seen]
        num += rest[: n - len(names)]
        x += [0.05] * (n - len(names))
        y += [0.05] * (n - len(names))
        names += [str(k) for k in num[len(names):]]
    lbl = np.argsort(np.asarray(num), kind="stable")
    xret, yret = np.array(x), np.array(y)
    xs, ys = xret[lbl], yret[lbl]
    if pos is not None:
        pos = np.asarray(pos, dtype=float)
        xs, ys = pos[0].copy(), pos[1].copy()
    return xret, yret, xs, ys, [names[i] for i in lbl]


def draw_dot(adj, labels=None, backend="pygraphviz", *, pos=None, nodemult=0.5,
             fontsz=None, ax=None, flags="matlab", engine="auto", undirected="arrows",
             wd=None, layout="auto", node_size=None, hover=None, return_figure=False):
    """``draw_dot.m:1-86``: lay out and draw the graph with adjacency matrix ``adj``;
    returns ``(xret, yret, labels)`` as MATLAB does.

    - ``labels``: one string per node (``None``: the node numbers, as ``nargin == 1``).
      Fewer labels than nodes fail in graph_draw, and raise here.
    - ``pos``, ``nodemult`` (0.5), ``fontsz`` (:func:`default_fontsize`): draw_dot's
      options.
    - ``ax``: matplotlib axes (``None``: pyplot's current axes).
    - ``backend='pygraphviz'``: neato via :func:`.pygraphviz_backend.layout_text`
      (``flags``, ``engine``) and matplotlib drawing (``undirected``, ``wd``: see
      :func:`.graph_draw.graph_draw`).
    - ``backend='networkx'`` (item 33): the layout of
      :func:`.networkx_backend.nx_layout` (``layout='auto'|'neato'|'kamada_kawai'``,
      ``flags``; neato gives draw_dot's positions exactly) and
      :func:`.networkx_backend.draw_networkx` (``undirected``, ``node_size``).
      ``engine`` and ``wd`` do not apply.
    - ``backend='plotly'`` / ``'pyvis'`` (item 34, optional extras): the same layout as
      ``'networkx'`` (``layout``, ``flags``), drawn by :func:`.plotly_backend.draw_plotly`
      or :func:`.pyvis_backend.draw_pyvis` (``undirected``, ``hover``: one string per
      node; ``node_size`` for plotly). ``ax`` is then a plotly figure / directed pyvis
      network to draw into (``None``: a new one).
    - ``return_figure=True`` returns ``(xret, yret, labels, fig)``: the matplotlib
      figure of the axes, the plotly figure or the pyvis network.

    A graph without edges raises (:func:`.dot.dot_to_graph`), as in MATLAB. A non-square
    ``adj`` warns (l.34).
    """
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}, not {backend!r}")
    adj = np.asarray(adj, dtype=float)
    n, m = adj.shape
    if n != m:
        warnings.warn("not a square adjacency matrix!")
    if backend in INTERACTIVE and ax is not None and hasattr(ax, "add_patch"):
        raise ValueError(f"backend {backend!r} draws into a plotly figure / pyvis "
                         "network, not matplotlib axes")
    if backend == "networkx" or backend in INTERACTIVE:
        from .networkx_backend import nx_layout

        xret, yret, x, y, names = order_positions(*nx_layout(adj, layout, flags), n, pos)
    else:
        from .pygraphviz_backend import layout_text

        _, lay, _ = layout_text(adj, flags=flags, engine=engine)
        xret, yret, x, y, names = dot_positions(lay, n, pos)
    if labels is None:
        labels = names
    labels = ["" if s is None else str(s) for s in labels]
    if len(labels) < n:
        raise ValueError(f"draw_dot: {len(labels)} labels for {n} nodes")
    if fontsz is None:
        fontsz = default_fontsize(n)
    b = (adj > 0).astype(float)
    if backend == "plotly":
        from .plotly_backend import draw_plotly

        fig = draw_plotly(b, labels[:n], x, y, fig=ax, fontsize=fontsz, nodemult=nodemult,
                          undirected=undirected, node_size=node_size, hover=hover)
    elif backend == "pyvis":
        from .pyvis_backend import draw_pyvis

        fig = draw_pyvis(b, labels[:n], x, y, net=ax, fontsize=fontsz,
                         undirected=undirected, hover=hover)
    else:
        if ax is None:
            import matplotlib.pyplot as plt
            ax = plt.gca()
        if backend == "networkx":
            from .networkx_backend import draw_networkx

            draw_networkx(b, labels[:n], x, y, ax=ax, fontsize=fontsz, nodemult=nodemult,
                          undirected=undirected, node_size=node_size)
        else:
            graph_draw(b, node_labels=labels[:n], x=x, y=y, fontsize=fontsz,
                       node_shapes=np.zeros(len(x)), nodemult=nodemult, ax=ax,
                       undirected=undirected, wd=wd)
        fig = ax.figure
    if return_figure:
        return xret, yret, labels, fig
    return xret, yret, labels


def draw_graph(graph, names=None, backend="plotly", *, title=None, **kw):
    """Draw a model graph (:class:`~formdiscovery.graph.Graph` or a results-file dict
    with ``adj``, ``W``, ``z``, ``objcount``, ``type``) with :func:`draw_dot`, the
    object names padded with ``''`` as ``runmodel.m:184-186``. The interactive backends
    get :func:`.interactive.hover_text` (object → cluster, cluster → members) unless
    ``hover`` is given. Returns the figure (matplotlib figure, plotly figure or pyvis
    network); ``title`` titles it (plotly layout title, matplotlib axes title, pyvis
    ``heading``)."""
    from .interactive import hover_text

    get = graph.get if isinstance(graph, dict) else (lambda f: getattr(graph, f))
    adj = np.asarray(get("adj"), dtype=float)
    labels = pad_names(names, adj.shape[0], "")
    if backend in INTERACTIVE and kw.get("hover") is None:
        kw["hover"] = hover_text(graph, names, sep="\n" if backend == "pyvis" else "<br>")
    *_, fig = draw_dot(adj, labels, backend, return_figure=True, **kw)
    if title is not None:
        if backend == "plotly":
            fig.update_layout(title=title)
        elif backend == "pyvis":
            fig.heading = title
        else:
            (kw.get("ax") or fig.axes[-1]).set_title(title)
    return fig


class ProgressFigures:
    """A ``show(event, adj, names, title)`` callback reproducing MATLAB's figures.

    The model code calls ``show`` where MATLAB draws, when the ``ps.show*`` flag is set
    (see :meth:`enable`), with the names already padded and the title formatted as in
    MATLAB. Each event goes to its MATLAB figure (:data:`FIGURE`): the figure is
    cleared, the graph drawn with :func:`draw_dot` and titled.

    - ``outdir``: each drawing is also saved as ``<outdir>/<k>_fig<f>_<event>.<fmt>``
      (``k`` counts from 1, 4 digits).
    - ``live``: use pyplot figures 1-3 and pause briefly (``drawnow``); otherwise
      off-screen figures.
    - ``strict=False``: a drawing that fails (e.g. a graph with no edges) warns instead
      of stopping the run.
    - ``draw_kw``: passed to :func:`draw_dot`.

    ``calls`` records ``(event, figure, title, file)`` for every call.
    """

    def __init__(self, outdir=None, live=False, fmt="png", figsize=(5.6, 4.2), dpi=100,
                 strict=False, **draw_kw):
        if draw_kw.get("backend") in INTERACTIVE:
            raise ValueError("ProgressFigures draws matplotlib figures: use the "
                             "pygraphviz or networkx backend")
        self.outdir = None if outdir is None else Path(outdir)
        self.live, self.fmt, self.figsize, self.dpi = live, fmt, figsize, dpi
        self.strict, self.draw_kw = strict, draw_kw
        self.figures, self.calls = {}, []

    @staticmethod
    def enable(ps, events=("preclean", "postclean", "bestsplit", "inferredgraph",
                           "truegraph")):
        """A copy of ``ps`` with the ``show<event>`` flags of ``events`` set to 1."""
        ps = ps.copy()
        for e in events:
            if e not in FIGURE:
                raise ValueError(f"unknown show event {e!r}")
            setattr(ps, f"show{e}", 1)
        return ps

    def _figure(self, num):
        if self.live:
            import matplotlib.pyplot as plt
            return plt.figure(num, figsize=self.figsize, dpi=self.dpi)
        if num not in self.figures:
            from matplotlib.figure import Figure
            self.figures[num] = Figure(figsize=self.figsize, dpi=self.dpi)
        return self.figures[num]

    def __call__(self, event, adj, names, title):
        num = FIGURE[event]
        fig = self._figure(num)
        fig.clf()
        ax = fig.add_subplot()
        path = None
        try:
            draw_dot(adj, names, ax=ax, **self.draw_kw)
        except Exception as e:  # noqa: BLE001 - display must not stop a run
            if self.strict:
                raise
            warnings.warn(f"ProgressFigures: {event} not drawn: {e}")
        ax.set_title(title)
        if self.outdir is not None:
            self.outdir.mkdir(parents=True, exist_ok=True)
            path = self.outdir / f"{len(self.calls) + 1:04d}_fig{num}_{event}.{self.fmt}"
            fig.savefig(path)
        if self.live:
            import matplotlib.pyplot as plt
            plt.pause(0.001)
        self.calls.append((event, num, title, path))


def _g(x):
    x = float(x)
    if np.isnan(x):
        return "NaN"
    if np.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    return "%g" % x


def draw_results(res, runs=None, path=None, ncols=3, panel=(5.6, 4.2), dpi=100, **draw_kw):
    """Draw the final graphs of a :class:`formdiscovery.run.MasterResults` (``runs``:
    indices into ``res.runs``, default all), one panel each, titled as
    ``runmodel.m:187`` (``'<type>: estimated structure:  <ll>'``) under the data set
    name, with the object names padded with ``''`` (l.184-186). Returns the matplotlib
    figure; saves it to ``path`` when given.

    ``backend='plotly'`` returns a plotly ``make_subplots`` figure instead, with hover
    text (:func:`.interactive.hover_text`), saved as HTML to ``path``. ``'pyvis'``
    draws one graph per page: use :func:`draw_graph`."""
    sel = list(range(len(res.runs))) if runs is None else list(runs)
    if not sel:
        raise ValueError("no runs to draw")
    nc = min(ncols, len(sel))
    nr = -(-len(sel) // nc)
    backend = draw_kw.get("backend")
    if backend == "pyvis":
        raise ValueError("draw_results: pyvis draws one graph per page; use draw_graph")
    if backend == "plotly":
        return _draw_results_plotly(res, sel, path, nr, nc, panel, dpi, draw_kw)
    from matplotlib.figure import Figure

    fig = Figure(figsize=(panel[0] * nc, panel[1] * nr), dpi=dpi)
    for p, k in enumerate(sel):
        r = res.runs[k]
        idx = (int(r["sind"]), int(r["dind"]), int(r["rind"]) - 1)
        g = res.structure[idx]
        get = g.get if isinstance(g, dict) else (lambda f, g=g: getattr(g, f))
        adj = np.asarray(get("adj"), dtype=float)
        names = res.names[0, idx[1]]
        ax = fig.add_subplot(nr, nc, p + 1)
        draw_dot(adj, pad_names(names, adj.shape[0], ""), ax=ax, **draw_kw)
        ax.set_title(f"{r['data']}\n{get('type')}: estimated structure:  {_g(r['ll'])}",
                     fontsize=9)
    if path is not None:
        fig.savefig(path)
    return fig


def _run_panel(res, r):
    """The graph, padded names and panel title of results record ``r``."""
    idx = (int(r["sind"]), int(r["dind"]), int(r["rind"]) - 1)
    g = res.structure[idx]
    get = g.get if isinstance(g, dict) else (lambda f, g=g: getattr(g, f))
    names = res.names[0, idx[1]]
    title = f"{r['data']}<br>{get('type')}: estimated structure:  {_g(r['ll'])}"
    return g, names, title


def _draw_results_plotly(res, sel, path, nr, nc, panel, dpi, draw_kw):
    """:func:`draw_results` with ``backend='plotly'``: one subplot per run."""
    from plotly.subplots import make_subplots

    from .interactive import hover_text
    from .plotly_backend import draw_plotly

    panels = [_run_panel(res, res.runs[k]) for k in sel]
    fig = make_subplots(rows=nr, cols=nc, subplot_titles=[t for _, _, t in panels],
                        horizontal_spacing=0.03, vertical_spacing=0.08)
    kw = {k: v for k, v in draw_kw.items() if k != "backend"}
    for p, (g, names, _) in enumerate(panels):
        get = g.get if isinstance(g, dict) else (lambda f, g=g: getattr(g, f))
        adj = np.asarray(get("adj"), dtype=float)
        _, _, x, y, lbl = _layout(adj, pad_names(names, adj.shape[0], ""), kw)
        draw_plotly((adj > 0).astype(float), lbl, x, y, fig=fig,
                    fontsize=kw.get("fontsz") or default_fontsize(adj.shape[0]),
                    nodemult=kw.get("nodemult", 0.5),
                    undirected=kw.get("undirected", "arrows"),
                    node_size=kw.get("node_size"), hover=hover_text(g, names),
                    row=p // nc + 1, col=p % nc + 1)
    for a in fig.layout.annotations:
        if a.text:
            a.font.size = 11
    fig.update_layout(width=int(panel[0] * dpi * nc), height=int(panel[1] * dpi * nr))
    if path is not None:
        fig.write_html(str(path))
    return fig


def _layout(adj, labels, kw):
    """draw_dot's positions through :func:`.networkx_backend.nx_layout` (the interactive
    backends' layout): ``(xret, yret, x, y, labels)``."""
    from .networkx_backend import nx_layout

    n = adj.shape[0]
    xret, yret, x, y, _ = order_positions(
        *nx_layout(adj, kw.get("layout", "auto"), kw.get("flags", "matlab")), n,
        kw.get("pos"))
    return xret, yret, x, y, labels
