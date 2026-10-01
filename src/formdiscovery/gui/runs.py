"""Several forms in a row or side by side, and the frames each one sent (loop0003 item 05).

:class:`RunQueue` runs the selected forms on one data file, each in its own
:class:`formdiscovery.gui.worker.RunWorker` on its own ``QThread``, at most ``parallel``
at a time, in the order given (``ps.structures`` order from the window); the next form
starts as soon as one ends. Each form's seed is the same (``NumpyPermutations(seed)``,
masterrun's repeat 1), so every result is masterrun's for that pair whatever ``parallel``
is. BLAS is pinned to one thread by the model drivers (:mod:`formdiscovery.threads`).
The search is Python code holding the GIL most of the time, so threads overlap only in the
numpy/scipy calls that release it (``ANOMALIES.md`` A27).

:class:`FormRun` is one form of the queue: its worker and thread, its outcome
(``pending``, ``running``, ``finished``, ``failed``, ``cancelled``), its result (the
worker's ``finished`` dict), its ``depth_done`` histories and a :class:`FrameHistory` of
the frames it sent. It is a ``QObject`` living in the GUI thread, so the worker's signals
reach its methods through queued connections (``ANOMALIES.md`` A23), and it re-emits them
with the form name.

:class:`FrameHistory` keeps the last ``cap`` frames (oldest dropped first, ``dropped``
counts them) as :class:`Frame` records with their run-wide number and the seconds since
the form started, for the window's history slider.

Stop (:meth:`RunQueue.cancel`) cancels the running forms (their workers stop at the next
hook check) and the pending ones never start (outcome ``cancelled``). :attr:`RunQueue.
all_done` is emitted once every form has an outcome and every thread has ended, with
``finished`` (all finished), ``cancelled`` (stopped) or ``failed`` (some failed).
"""

import collections
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, Signal, Slot

from .worker import RunWorker, start_worker

__all__ = ["RunQueue", "FormRun", "FrameHistory", "Frame", "FRAME_CAP", "OUTCOMES",
           "ranked"]

FRAME_CAP = 500   # frames kept per form (a demo run sends 11-33)
OUTCOMES = ("finished", "failed", "cancelled")


class Frame(NamedTuple):
    """One recorded frame: the worker's ``frame`` arguments, the frame's number in its
    run (1-based, counting dropped ones) and the seconds since the run started."""
    event: str
    adj: np.ndarray
    names: list
    title: str
    depth: int
    number: int
    elapsed: float

    def canvas_args(self):
        """Arguments of :meth:`formdiscovery.gui.canvas.GraphCanvas.push_entry`."""
        return (self.event, self.adj, self.names, self.title, self.depth, self.elapsed,
                self.number)


class FrameHistory:
    """The last ``cap`` frames of a run (``None``: no cap)."""

    def __init__(self, cap=FRAME_CAP):
        self.cap = cap
        self.frames = collections.deque(maxlen=cap)
        self.received = self.dropped = 0

    def __len__(self):
        return len(self.frames)

    def __getitem__(self, i):
        return self.frames[i]

    def append(self, event, adj, names, title, depth, elapsed):
        self.received += 1
        if self.cap is not None and len(self.frames) == self.cap:
            self.dropped += 1
        f = Frame(str(event), adj, list(names), str(title), int(depth), self.received,
                  float(elapsed))
        self.frames.append(f)
        return f

    def last(self, event=None):
        """The newest frame (of ``event`` if given), or None."""
        for f in reversed(self.frames):
            if event is None or f.event == event:
                return f
        return None


class FormRun(QObject):
    """One form of a :class:`RunQueue` (module docstring)."""

    frame = Signal(str, object)      # form, Frame
    depth_done = Signal(str, object)  # form, bestgraphlls
    ended = Signal(str, str)         # form, outcome

    def __init__(self, path, form, seed=1, speed=None, bestsplit=False, cap=FRAME_CAP,
                 data_dir=None, parent=None):
        super().__init__(parent)
        self.path, self.form, self.seed, self.speed = Path(path), form, seed, speed
        self.bestsplit, self.data_dir = bestsplit, data_dir
        self.history = FrameHistory(cap)
        self.depths = []          # depth_done histories, in order
        self.status = "pending"
        self.result = self.error = None
        self.worker = self.thread = None
        self.ended_worker = self.ended_thread = None  # after the thread ended
        self.t0 = None

    def ll(self):
        return None if self.result is None else self.result["ll"]

    def make_worker(self):
        """Create the worker and connect it to this object's methods."""
        w = RunWorker(self.path, self.form, seed=self.seed, speed=self.speed,
                      bestsplit=self.bestsplit, data_dir=self.data_dir)
        w.frame.connect(self.on_frame)
        w.depth_done.connect(self.on_depth)
        w.finished.connect(self.on_finished)
        w.failed.connect(self.on_failed)
        w.cancelled.connect(self.on_cancelled)
        self.worker = w
        return w

    @Slot(str, object, object, str, int)
    def on_frame(self, event, adj, names, title, depth):
        f = self.history.append(event, adj, names, title, depth,
                                time.perf_counter() - self.t0)
        self.frame.emit(self.form, f)

    @Slot(object)
    def on_depth(self, lls):
        self.depths.append(lls)
        self.depth_done.emit(self.form, lls)

    @Slot(object)
    def on_finished(self, result):
        self.result = result
        self._end("finished")

    @Slot(str)
    def on_failed(self, tb):
        self.error = tb
        self._end("failed")

    @Slot()
    def on_cancelled(self):
        self._end("cancelled")

    def _end(self, outcome):
        if self.status in OUTCOMES:
            return
        self.status = outcome
        self.ended.emit(self.form, outcome)


def ranked(runs):
    """``runs`` (FormRun-like: ``form``, ``status``, ``ll()``) in table order: the
    finished ones by ll, best first (ties keep the queue order), then running, pending,
    cancelled and failed in queue order."""
    order = {"finished": 0, "running": 1, "pending": 2, "cancelled": 3, "failed": 4}
    idx = {id(r): i for i, r in enumerate(runs)}
    return sorted(runs, key=lambda r: (order[r.status],
                                       -r.ll() if r.status == "finished" else 0,
                                       idx[id(r)]))


class RunQueue(QObject):
    """Runs ``forms`` on the data file ``path`` (module docstring)."""

    run_started = Signal(object)      # FormRun (its worker is connected, not started)
    frame = Signal(str, object)       # form, Frame
    depth_done = Signal(str, object)  # form, bestgraphlls
    form_ended = Signal(str, str)     # form, outcome
    all_done = Signal(str)            # finished / cancelled / failed

    def __init__(self, path, forms, seed=1, speed=None, bestsplit=False, parallel=1,
                 cap=FRAME_CAP, data_dir=None, parent=None):
        super().__init__(parent)
        if not forms:
            raise ValueError("no forms to run")
        if len(set(forms)) != len(forms):
            raise ValueError(f"forms repeat: {list(forms)}")
        self.path, self.parallel = Path(path), max(1, int(parallel))
        self.runs = [FormRun(path, f, seed, speed, bestsplit, cap, data_dir, parent=self)
                     for f in forms]
        for r in self.runs:
            r.frame.connect(self.frame)
            r.depth_done.connect(self.depth_done)
            r.ended.connect(self._on_ended)
        self.stopped = False
        self.outcome = None
        self.t0 = self.wall = None
        self.max_active = 0       # most threads running at once (tests)

    # --- queries ---------------------------------------------------------------------
    def run(self, form):
        return next(r for r in self.runs if r.form == form)

    @property
    def forms(self):
        return [r.form for r in self.runs]

    def active(self):
        """Forms whose thread has not ended yet."""
        return [r for r in self.runs if r.thread is not None]

    def is_running(self):
        return self.t0 is not None and self.outcome is None

    def finished_runs(self):
        return [r for r in ranked(self.runs) if r.status == "finished"]

    def winner(self):
        """The finished form with the highest ll (first in queue order on a tie)."""
        done = self.finished_runs()
        return done[0] if done else None

    # --- control ---------------------------------------------------------------------
    def start(self):
        """Start the first ``parallel`` forms."""
        if self.t0 is not None:
            raise RuntimeError("the queue has already started")
        self.t0 = time.perf_counter()
        self._fill()

    def cancel(self):
        """Stop: cancel the running forms, never start the pending ones."""
        self.stopped = True
        for r in self.runs:
            if r.status == "pending":
                r._end("cancelled")
            elif r.worker is not None and r.status == "running":
                r.worker.cancel()
        self._check_done()

    def wait(self, ms=60000):
        """Process events until the queue is done (tests, closing); True if it is."""
        deadline = time.perf_counter() + ms / 1000
        while self.is_running():
            if time.perf_counter() > deadline:
                return False
            QCoreApplication.processEvents(QEventLoop.AllEvents, 20)
            for r in self.active():
                if r.thread is not None and r.thread.wait(10):  # (reaped meanwhile)
                    QCoreApplication.processEvents()  # its queued signals first
                    self._reap(r)
        return True

    # --- internals -------------------------------------------------------------------
    def _fill(self):
        while not self.stopped and len(self.active()) < self.parallel:
            r = next((r for r in self.runs if r.status == "pending"), None)
            if r is None:
                break
            self._launch(r)

    def _launch(self, r):
        w = r.make_worker()
        r.status = "running"
        self.run_started.emit(r)
        r.thread = start_worker(w, start=False)
        r.thread.finished.connect(self._on_thread_finished)
        r.t0 = time.perf_counter()
        r.thread.start()
        self.max_active = max(self.max_active, len(self.active()))

    @Slot(str, str)
    def _on_ended(self, form, outcome):
        self.form_ended.emit(form, outcome)
        self._fill()
        self._check_done()

    @Slot()
    def _on_thread_finished(self):
        # a thread's ``finished`` is queued after its worker's outcome signal, so the
        # runs with an outcome are the ones ending; wait() covers the last instructions
        for r in self.active():
            if r.status in OUTCOMES and r.thread.wait(5000):
                self._reap(r)

    def _reap(self, r):
        if r.thread is None or not r.thread.isFinished():
            return
        # no deleteLater: wait() processes events, which would delete them under a
        # caller still holding them; the FormRun keeps them until it goes
        r.ended_thread, r.ended_worker = r.thread, r.worker
        r.thread = r.worker = None
        if r.status == "running":  # ended without a signal (should not happen)
            r._end("failed")
        self._fill()
        self._check_done()

    def _check_done(self):
        if self.outcome is not None or self.t0 is None or self.active():
            return
        if any(r.status not in OUTCOMES for r in self.runs):
            return
        statuses = {r.status for r in self.runs}
        self.outcome = ("cancelled" if self.stopped else
                        "failed" if "failed" in statuses else "finished")
        self.wall = time.perf_counter() - self.t0
        self.all_done.emit(self.outcome)
