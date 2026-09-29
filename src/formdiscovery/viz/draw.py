"""``draw_dot.m`` facade and progress figures (item 32, PLAN.md §6 phase A).

:func:`draw_dot` is ``draw_dot(adj, labels, 'pos', ..., 'nodemult', ..., 'fontsz', ...)``:
lay the graph out with neato (:mod:`.pygraphviz_backend`), read the positions back
(:func:`dot_positions`, ``draw_dot.m:52-72``) and draw with :func:`.graph_draw.graph_draw`
on matplotlib axes. The temporary ``_GtDout.dot``/``_LAYout.dot`` files are not written.

:class:`ProgressFigures` is a ``show`` callback for :func:`formdiscovery.run.runmodel`,
:func:`formdiscovery.search.structurefit` and :func:`formdiscovery.search.best_split`: it
reproduces MATLAB's figures 1 (true graph / pre-clean), 2 (post-clean) and 3 (best split /
inferred graph), live and/or as numbered image files.
"""

import warnings
from pathlib import Path

import numpy as np

from .dot import dot_to_graph
from .graph_draw import graph_draw

__all__ = ["BACKENDS", "FIGURE", "default_fontsize", "dot_positions", "draw_dot",
           "pad_names", "ProgressFigures", "draw_results"]

BACKENDS = ("pygraphviz",)
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
             wd=None):
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

    A graph without edges raises (:func:`.dot.dot_to_graph`), as in MATLAB. A non-square
    ``adj`` warns (l.34).
    """
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}, not {backend!r}")
    from .pygraphviz_backend import layout_text

    adj = np.asarray(adj, dtype=float)
    n, m = adj.shape
    if n != m:
        warnings.warn("not a square adjacency matrix!")
    _, lay, _ = layout_text(adj, flags=flags, engine=engine)
    xret, yret, x, y, names = dot_positions(lay, n, pos)
    if labels is None:
        labels = names
    labels = ["" if s is None else str(s) for s in labels]
    if len(labels) < n:
        raise ValueError(f"draw_dot: {len(labels)} labels for {n} nodes")
    if fontsz is None:
        fontsz = default_fontsize(n)
    graph_draw((adj > 0).astype(float), node_labels=labels[:n], x=x, y=y, fontsize=fontsz,
               node_shapes=np.zeros(len(x)), nodemult=nodemult, ax=ax,
               undirected=undirected, wd=wd)
    return xret, yret, labels


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
    figure; saves it to ``path`` when given."""
    from matplotlib.figure import Figure

    sel = list(range(len(res.runs))) if runs is None else list(runs)
    if not sel:
        raise ValueError("no runs to draw")
    nc = min(ncols, len(sel))
    nr = -(-len(sel) // nc)
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
