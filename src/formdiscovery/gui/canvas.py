"""The live graph canvas (loop0003 item 03).

:class:`GraphCanvas` is a matplotlib ``FigureCanvasQTAgg`` that draws the worker's frames
(:attr:`formdiscovery.gui.worker.RunWorker.frame`: ``event, adj, names, title, depth``)
with :func:`formdiscovery.viz.draw.draw_dot` (``backend`` ``'pygraphviz'``, the default,
or ``'networkx'``), titled with the model's title (``show_graph``'s, e.g.
``post-clean: chain  -8538.11``), and a status line under the graph: event, depth, score
(the title's last word), seconds since :meth:`GraphCanvas.begin_run`, frame number.

Coalescing: :meth:`GraphCanvas.push_frame` only stores the frame; a single-shot timer
(``interval`` ms) draws the latest stored one, so a burst of frames costs one drawing and
the older ones are dropped. An ``inferredgraph`` frame (the run's last) is drawn at once
and never dropped. :meth:`GraphCanvas.flush` draws a pending frame now.

Stable positions (``stable=True``, default): neato (pygraphviz) lays each frame out
starting from the previous frame's points: every node ``k`` (``'1'..'n'``, as
``graph_to_dot`` names them) that was in the previous frame gets that frame's ``pos`` as
its initial position (neato's ``pos`` attribute, not pinned), the new ones start at
random; the result goes to ``draw_dot(..., pos=)`` normalised as draw_dot does
(:func:`formdiscovery.viz.draw.dot_positions`). The first frame of a run is draw_dot's own
layout. The model keeps the object nodes ``1..nobj`` first in every graph, so those are
matched exactly; cluster nodes are matched by index, which a split or clean may reassign
(they then start from another node's point and neato moves them). ``draw_dot`` still runs
its own layout when given ``pos`` (its ``xret``/``yret`` come from it), so each frame
costs two neato runs (milliseconds for the demo graphs). With ``stable=False``, or without
pygraphviz, every frame is draw_dot's fresh layout and nodes jump between frames.

A frame that cannot be drawn (e.g. a graph without edges, which draw_dot rejects as
MATLAB does) shows the error in the axes instead of stopping the run.
"""

import time

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer, Signal, Slot

from ..viz.draw import dot_positions, draw_dot

__all__ = ["GraphCanvas", "CANVAS_BACKENDS", "frame_score"]

CANVAS_BACKENDS = ("pygraphviz", "networkx")  # draw_dot's matplotlib backends
FINAL_EVENT = "inferredgraph"


def frame_score(title):
    """The score at the end of a show title (``'pre-clean: chain  -8875.93'``,
    ``'-Inf'``, ...), or None."""
    words = str(title).split()
    if not words:
        return None
    try:
        return float(words[-1])
    except ValueError:
        return None


def _have_pygraphviz():
    try:
        import pygraphviz  # noqa: F401
    except ImportError:
        return False
    return True


class GraphCanvas(FigureCanvasQTAgg):
    """Draws the frames of a run (see the module docstring)."""

    frame_drawn = Signal(str, str)  # event, title (after each drawing)

    def __init__(self, backend="pygraphviz", stable=True, interval=100, parent=None,
                 figsize=(6.4, 4.8), dpi=100):
        super().__init__(Figure(figsize=figsize, dpi=dpi))
        if parent is not None:
            self.setParent(parent)
        self.set_backend(backend)
        self.stable = bool(stable)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(int(interval))
        self._timer.timeout.connect(self.flush)
        self.clear()

    # --- settings --------------------------------------------------------------------
    def set_backend(self, backend):
        if backend not in CANVAS_BACKENDS:
            raise ValueError(f"backend must be one of {CANVAS_BACKENDS}, not {backend!r}")
        self.backend = backend

    def stable_layout(self):
        """Whether frames are laid out from the previous positions (needs pygraphviz)."""
        return self.stable and _have_pygraphviz()

    # --- run state -------------------------------------------------------------------
    def clear(self, message=""):
        """Forget the frames and show an empty canvas with ``message``."""
        self._timer.stop()
        self.pending = None
        self.received = self.drawn = self.dropped = 0
        self.last_event = self.last_title = None
        self.status = message
        self.positions = None   # 2 x n normalised positions of the last stable drawing
        self._raw = None        # node name -> neato 'pos' of the last stable layout
        self._t0 = time.perf_counter()
        fig = self.figure
        fig.clf()
        ax = fig.add_subplot()
        ax.set_axis_off()
        if message:
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
        self.draw()

    def begin_run(self, message="Waiting for the first graph…"):
        """Reset for a new run; elapsed times count from now."""
        self.clear(message)

    def set_status(self, text):
        """Replace the status line (e.g. ``Run stopped.``) and redraw it."""
        self.status = str(text)
        if self.figure.texts:
            self.figure.texts[-1].set_text(self.status)
        else:
            self.figure.text(0.01, 0.01, self.status, fontsize=9, ha="left", va="bottom")
        self.draw()

    # --- frames ----------------------------------------------------------------------
    @Slot(str, object, object, str, int)
    def push_frame(self, event, adj, names, title, depth):
        """Store a frame (the worker's ``frame`` signal); it is drawn by the timer, at
        once for ``inferredgraph``."""
        self.received += 1
        if self.pending is not None:
            self.dropped += 1
        self.pending = (str(event), np.asarray(adj, dtype=float), list(names), str(title),
                        int(depth), time.perf_counter() - self._t0, self.received)
        if event == FINAL_EVENT:
            self.flush()
        elif not self._timer.isActive():
            self._timer.start()

    @Slot()
    def flush(self):
        """Draw the pending frame now (no-op without one)."""
        self._timer.stop()
        if self.pending is None:
            return
        frame, self.pending = self.pending, None
        self.draw_frame(*frame)

    def draw_frame(self, event, adj, names, title, depth, elapsed=None, number=None):
        """Draw one frame now."""
        adj = np.asarray(adj, dtype=float)
        fig = self.figure
        fig.clf()
        ax = fig.add_subplot()
        try:
            pos = self._stable_pos(adj) if self.stable_layout() else None
            draw_dot(adj, names, self.backend, pos=pos, ax=ax)
            self.positions = pos
        except Exception as e:  # noqa: BLE001 - display must not stop a run
            ax.cla()
            ax.set_axis_off()
            ax.text(0.5, 0.5, f"graph not drawn:\n{type(e).__name__}: {e}", ha="center",
                    va="center", transform=ax.transAxes, fontsize=9)
            self.positions = None
        ax.set_title(title, fontsize=10)
        parts = [event, f"depth {depth}"]
        if frame_score(title) is not None:
            parts.append(f"score {title.split()[-1]}")  # as the title prints it
        if elapsed is not None:
            parts.append(f"{elapsed:.1f} s")
        if number is not None:
            parts.append(f"frame {number}")
        self.status = " · ".join(parts)
        fig.text(0.01, 0.01, self.status, fontsize=9, ha="left", va="bottom")
        self.draw()
        self.drawn += 1
        self.last_event, self.last_title = event, title
        self.frame_drawn.emit(event, title)

    def _stable_pos(self, adj):
        """neato positions of ``adj`` started from the previous frame's (module
        docstring), as draw_dot's normalised ``2 x n`` ``pos``."""
        import pygraphviz

        from ..viz.dot import adj_is_directed, graph_to_dot
        from ..viz.pygraphviz_backend import neato_attrs

        n = adj.shape[0]
        b = (adj > 0).astype(float)
        g = pygraphviz.AGraph(string=graph_to_dot(b, directed=int(adj_is_directed(adj))))
        attrs, _ = neato_attrs(n)
        for k, v in attrs:
            g.graph_attr[k] = v
        if self._raw:
            for name, p in self._raw.items():
                if g.has_node(name):
                    g.get_node(name).attr["pos"] = p
        lay = g.draw(format="dot", prog="neato").decode()
        out = pygraphviz.AGraph(string=lay)
        self._raw = {nd.name: nd.attr["pos"] for nd in out.nodes() if nd.attr.get("pos")}
        _, _, x, y, _ = dot_positions(lay, n)
        return np.vstack([x, y])
