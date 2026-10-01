"""Run the model off the GUI thread (loop0003 item 02).

:class:`RunWorker` is a ``QObject`` that :func:`start_worker` moves to its own ``QThread``.
:meth:`RunWorker.run` calls :func:`formdiscovery.run.runmodel` for one (form, data file)
pair with ``ps`` from :meth:`formdiscovery.viz.draw.ProgressFigures.enable` (``preclean``,
``postclean``, ``inferredgraph``; ``bestsplit`` on request) and the seed masterrun gives
repeat 1 (``NumpyPermutations(seed)``), so the result is masterrun's for that pair.

The model's ``show(event, adj, names, title)`` callback and the run hooks
(:func:`formdiscovery.search.run_hooks`) run in the worker thread; the worker turns them
into Qt signals carrying copies (plain numpy/Python data), delivered to the GUI thread
by queued connections:

- ``frame(event, adj, names, title, depth)``: every shown graph; ``depth`` is
  :func:`formdiscovery.search.current_depth` (the ``structurefit`` depth being tried, or
  just accepted for ``postclean``; the last one for ``inferredgraph``);
- ``depth_done(lls)``: the current ``structurefit`` stage's ``bestgraphlls`` after each
  accepted depth (each stage, e.g. speed 5 then 4 at speed 54, starts again at 1);
- ``finished(result)``: a dict (``ll``, ``graph``, ``names``, ``bestglls``,
  ``bestgraph``, ``form``, ``sind``, ``dind``, ``path``, ``seed``, ``speed``, ``frames``,
  ``wall`` (the run's seconds), and, item 04, ``prior`` and ``likelihood``, the parts of
  ``ll`` from :func:`formdiscovery.gui.stats.score_parts`, NaN if that fails);
- ``failed(traceback)``: the formatted traceback of any other exception;
- ``cancelled()``: :meth:`RunWorker.cancel` was called (from any thread); the ``cancel``
  hook raises :class:`formdiscovery.search.RunCancelled` at the next ``show_graph`` call or
  ``structurefit`` depth and the run unwinds.

Exactly one of ``finished``/``failed``/``cancelled`` is emitted, then ``done``.

Connect these signals to methods of ``QObject`` s living in the GUI thread: PySide6 calls
a plain function or lambda (no receiver object) directly in the emitting thread, i.e. in
the worker thread, where it must not touch widgets (``ANOMALIES.md`` A23).
"""

import threading
import time
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from .. import search
from ..io import DATA_DIR
from ..rng import NumpyPermutations
from ..run import masterrun_ps, runmodel
from ..viz.draw import ProgressFigures

__all__ = ["RunWorker", "start_worker", "run_ps", "EVENTS"]

EVENTS = ("preclean", "postclean", "inferredgraph")  # bestsplit: optional


def run_ps(path, form, speed=None, data_dir=None):
    """``(ps, sind, dind)`` for running ``form`` on the data file ``path``:
    :func:`formdiscovery.run.masterrun_ps` (with ``speed`` if given). A shipped data set
    (``path`` in ``data_dir``, default :data:`formdiscovery.io.DATA_DIR`) keeps its
    ``ps.data`` index; any other file is appended to ``ps.data``/``ps.dlocs``/``ps.simdim``
    (``simdim`` 1000, as ``setps.m`` gives every set)."""
    path = Path(path).resolve()
    ps = masterrun_ps(data_dir)
    if speed is not None:
        ps.speed = int(speed)
    sind = list(ps.structures).index(form)
    stem = str(path.with_suffix(""))
    dlocs = [str(Path(d).resolve()) for d in ps.dlocs]
    if stem in dlocs:
        return ps, sind, dlocs.index(stem)
    ps.data = list(ps.data) + [path.stem]
    ps.dlocs = list(ps.dlocs) + [stem]
    ps.simdim = list(ps.simdim) + [1000]
    return ps, sind, len(ps.data) - 1


class RunWorker(QObject):
    """Runs ``form`` on the data file ``path`` (see the module docstring)."""

    frame = Signal(str, object, object, str, int)  # event, adj, names, title, depth
    depth_done = Signal(object)                    # bestgraphlls (1-D float array)
    finished = Signal(object)                      # result dict
    failed = Signal(str)                           # traceback
    cancelled = Signal()
    done = Signal()                                # after any of the three above

    def __init__(self, path, form, seed=1, speed=None, bestsplit=False, data_dir=None,
                 parent=None):
        super().__init__(parent)
        self.path, self.form, self.seed, self.speed = Path(path), form, int(seed), speed
        self.events = EVENTS + (("bestsplit",) if bestsplit else ())
        self.data_dir = DATA_DIR if data_dir is None else data_dir
        self.frames = 0
        self._cancel = threading.Event()

    def cancel(self):
        """Ask the run to stop (thread-safe); it stops at the next hook check."""
        self._cancel.set()

    def is_cancelled(self):
        return self._cancel.is_set()

    def _show(self, event, adj, names, title):
        self.frames += 1
        self.frame.emit(str(event), np.array(adj, dtype=float, copy=True),
                        [str(n) for n in names], str(title), search.current_depth())

    def _on_depth(self, lls, graphs):
        self.depth_done.emit(np.array(lls, dtype=float, copy=True))

    @Slot()
    def run(self):
        t0 = time.perf_counter()
        try:
            ps, sind, dind = run_ps(self.path, self.form, self.speed, self.data_dir)
            ps = ProgressFigures.enable(ps, self.events)
            with search.run_hooks(cancel=self._cancel.is_set, on_depth=self._on_depth):
                search.check_cancel()
                ll, graph, names, bestglls, bestgraph = runmodel(
                    ps, sind, dind, 1, rng=NumpyPermutations(self.seed), show=self._show)
        except search.RunCancelled:
            self.cancelled.emit()
        except Exception:  # noqa: BLE001 - reported to the GUI
            self.failed.emit(traceback.format_exc())
        else:
            wall = time.perf_counter() - t0
            from .stats import score_parts  # stats imports this module
            try:
                prior, like = score_parts(self.path, self.form, graph, self.speed,
                                          self.data_dir)
            except Exception:  # noqa: BLE001 - the run itself succeeded
                prior = like = float("nan")
            self.finished.emit({
                "ll": float(ll), "graph": graph, "names": list(names),
                "bestglls": bestglls, "bestgraph": bestgraph, "form": self.form,
                "sind": sind, "dind": dind, "path": self.path, "seed": self.seed,
                "speed": int(ps.speed), "frames": self.frames, "wall": wall,
                "prior": prior, "likelihood": like})
        self.done.emit()


def start_worker(worker, parent=None, start=True):
    """Move ``worker`` to a new ``QThread`` (child of ``parent``), start it unless
    ``start=False`` (connect to the thread first, then ``thread.start()``), and return the
    thread. The thread quits when the worker emits ``done``; the caller keeps references
    to both until then (``thread.wait()`` joins it)."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit, Qt.DirectConnection)  # quit() is thread-safe
    if start:
        thread.start()
    return thread
