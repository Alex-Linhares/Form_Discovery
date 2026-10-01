"""The main window: data picker, forms and run settings (loop0003 item 01).

Layout: an "Open data file…" button with the chosen path, the dataset info panel
(:meth:`formdiscovery.gui.dataset.DatasetInfo.summary`), the form list (the 24
``ps.structures`` of ``setps.m``, multi-select, chain/ring/tree preselected as in
``masterrun.m``'s ``thisstruct``), seed and speed spin boxes (speed defaults to
``defaultps.m``'s 54 and steps through :data:`SPEEDS` only: ``ps.speed`` is a mode code,
not a count; 1 and 2 crash in ``best_split`` (``KNOWN_ISSUES.md`` KI-1) and 23 is
runmodel's "Unknown speed value") and Run/Stop buttons. Run emits
:attr:`MainWindow.run_requested` with :meth:`MainWindow.run_settings`.

Item 02: :meth:`MainWindow.start_run` (connected to ``run_requested``) runs the first
selected form in a :class:`formdiscovery.gui.worker.RunWorker` on its own thread (the
queue of several forms is item 05) and emits :attr:`MainWindow.run_started` with the
worker; Stop calls :meth:`RunWorker.cancel`. Run is disabled while a run goes; a status
line shows the frames received and the outcome. Closing the window cancels the run and
waits for its thread.

Item 03: the right half is a :class:`formdiscovery.gui.canvas.GraphCanvas` fed by the
worker's ``frame`` signal (coalesced, stable positions); the settings add the drawing
backend (pygraphviz/networkx) and "Draw best splits" (the worker's ``bestsplit`` frames).
A stopped or failed run says so in the canvas status line.

Item 04: a "Statistics" column (:class:`formdiscovery.gui.stats.StatsPanel`) draws the
per-depth scores live from the worker's ``depth_done`` and, on ``finished``, shows the
final ll and its prior/likelihood parts, the clusters and their members, the score
history chart, wall time and frames, with "Export results…" (``.npz`` + ``.json``, as
``formdiscovery run`` writes) and "Save figure…" (the graph canvas, PNG/SVG).

Item 05: Run queues every selected form (:class:`formdiscovery.gui.runs.RunQueue`, one
worker thread per form, "Parallel runs" at a time). The "Results" table under the graph
(:class:`formdiscovery.gui.results.ResultsTable`) ranks them by ll with the winner
highlighted; clicking a row shows that form's final graph (or its latest frame while it
runs) and statistics. The canvas and the statistics follow the first running form, then
the next, and show the winner at the end, until a row is clicked. Every frame a form sends
is kept (:class:`formdiscovery.gui.runs.FrameHistory`, at most :attr:`MainWindow.
frame_cap` per form, oldest dropped); the slider under the canvas scrubs back through the
shown form's frames. At its right end the canvas is live; moved back, it stays on the
chosen frame while the run goes on.
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton, QSlider, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

from ..io import DATA_DIR
from ..params import STRUCTURES
from ..run import MASTERRUN_STRUCT
from .canvas import CANVAS_BACKENDS, GraphCanvas
from .dataset import dataset_info
from .results import ResultsTable
from .runs import FRAME_CAP, RunQueue
from .stats import StatsPanel

__all__ = ["MainWindow", "SpeedSpinBox", "SPEEDS", "DEFAULT_FORMS", "DEFAULT_SEED",
           "DEFAULT_SPEED", "FILE_FILTER"]

DEFAULT_FORMS = tuple(STRUCTURES[i] for i in MASTERRUN_STRUCT)  # chain, ring, tree
DEFAULT_SEED = 1      # cli.py's --seed default
DEFAULT_SPEED = 54    # defaultps.m
FILE_FILTER = "MATLAB data (*.mat);;All files (*)"
# defaultps.m's speed codes that run (1, 2: KI-1; 23: runmodel's "Unknown speed value")
SPEEDS = (3, 4, 5, 54)


class SpeedSpinBox(QSpinBox):
    """A spin box over :data:`SPEEDS` (arrows step to the next valid code)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(min(SPEEDS), max(SPEEDS))
        self.setValue(DEFAULT_SPEED)

    def stepBy(self, steps):
        vals = sorted(SPEEDS)
        cur = self.value()
        i = vals.index(cur) if cur in vals else 0
        self.setValue(vals[max(0, min(len(vals) - 1, i + steps))])

    def validate(self, text, pos):
        res = super().validate(text, pos)  # PySide6: (state, text, pos)
        if res[0] == QValidator.Acceptable and self.valueFromText(res[1]) not in SPEEDS:
            return (QValidator.Intermediate, res[1], res[2])
        return res


class MainWindow(QMainWindow):
    """The form discovery window. ``path`` (optional) is loaded at start; ``data_dir`` is
    where the file dialog opens (default :data:`formdiscovery.io.DATA_DIR`)."""

    run_requested = Signal(dict)
    dataset_changed = Signal(object)  # DatasetInfo
    run_started = Signal(object)      # RunWorker (connect before its thread runs on)
    run_ended = Signal(str)           # 'finished' / 'failed' / 'cancelled'

    def __init__(self, path=None, data_dir=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("formdiscovery")
        self.data_dir = Path(data_dir or DATA_DIR)
        self.info = None
        self.queue = None         # RunQueue of the last Run
        self.shown = None         # form shown in the canvas and statistics
        self._follow = True       # the display follows the runs (until a row is clicked)
        self._live = True         # the canvas draws the shown form's frames as they come
        self.frame_cap = FRAME_CAP
        self.last_result = self.last_error = None

        self.open_button = QPushButton("Open data file…")
        self.open_button.clicked.connect(self.open_dialog)
        self.path_label = QLabel("No file loaded")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top = QHBoxLayout()
        top.addWidget(self.open_button)
        top.addWidget(self.path_label, 1)

        self.info_label = QLabel("Open a .mat data file to begin.")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_box = QGroupBox("Data set")
        QVBoxLayout(info_box).addWidget(self.info_label)

        self.form_list = QListWidget()
        self.form_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.form_list.addItems(list(STRUCTURES))
        self.set_forms(DEFAULT_FORMS)
        form_box = QGroupBox("Forms")
        QVBoxLayout(form_box).addWidget(self.form_list)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(DEFAULT_SEED)
        self.speed_spin = SpeedSpinBox()
        self.speed_spin.setToolTip("ps.speed (defaultps.m): when branch lengths are "
                                   "optimised; 3 per split, 4 per depth, 5 approximate, "
                                   "54 = 5 then 4. Relational data always uses 5.")
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(list(CANVAS_BACKENDS))
        self.bestsplit_check = QCheckBox("Draw best splits")
        self.bestsplit_check.setToolTip("Also show each depth's best split (ps.showbestsplit)")
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.parallel_spin.setValue(1)
        self.parallel_spin.setToolTip("Forms run at the same time, each on its own thread")
        settings = QGroupBox("Settings")
        sform = QFormLayout(settings)
        sform.addRow("Seed", self.seed_spin)
        sform.addRow("Speed", self.speed_spin)
        sform.addRow("Drawing", self.backend_combo)
        sform.addRow("", self.bestsplit_check)
        sform.addRow("Parallel runs", self.parallel_spin)

        self.canvas = GraphCanvas()
        self.canvas.setMinimumSize(420, 360)
        self.backend_combo.currentTextChanged.connect(self.canvas.set_backend)
        self.history_slider = QSlider(Qt.Horizontal)
        self.history_slider.setEnabled(False)
        self.history_slider.setToolTip("Scrub back through the frames of the shown form "
                                       "(right end: live)")
        self.history_slider.valueChanged.connect(self._on_slider)
        self.history_label = QLabel("no frames")
        history = QHBoxLayout()
        history.addWidget(QLabel("Frames"))
        history.addWidget(self.history_slider, 1)
        history.addWidget(self.history_label)
        graph_box = QGroupBox("Graph")
        glay = QVBoxLayout(graph_box)
        glay.addWidget(self.canvas, 1)
        glay.addLayout(history)
        self.results = ResultsTable()
        self.results.form_selected.connect(self.select_form)
        results_box = QGroupBox("Results (ranked by ll)")
        QVBoxLayout(results_box).addWidget(self.results)
        self.stats = StatsPanel(figure_source=self.canvas)
        self.stats.setMinimumWidth(340)
        stats_box = QGroupBox("Statistics")
        QVBoxLayout(stats_box).addWidget(self.stats)
        center = QSplitter(Qt.Vertical)
        center.addWidget(graph_box)
        center.addWidget(results_box)
        center.setStretchFactor(0, 4)
        center.setStretchFactor(1, 1)
        center.setChildrenCollapsible(False)

        self.run_button = QPushButton("Run")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._on_run)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_run)
        self.status_label = QLabel("")
        buttons = QHBoxLayout()
        buttons.addWidget(self.status_label, 1)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.stop_button)

        left = QVBoxLayout()
        left.addWidget(info_box, 1)
        left.addWidget(settings)
        left.addWidget(form_box, 1)
        middle = QHBoxLayout()
        middle.addLayout(left, 2)
        middle.addWidget(center, 3)
        middle.addWidget(stats_box, 2)
        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(middle, 1)
        root.addLayout(buttons)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.resize(1440, 900)

        self.form_list.itemSelectionChanged.connect(self._update_run_enabled)
        self.run_requested.connect(self.start_run)
        if path is not None:
            self.load_file(path)

    # --- data file -------------------------------------------------------------------
    def open_dialog(self):
        """Ask for a ``.mat`` file (starting in :attr:`data_dir`) and load it."""
        path, _ = QFileDialog.getOpenFileName(self, "Open data file", str(self.data_dir),
                                              FILE_FILTER)
        if path:
            self.load_file(path)
        return path or None

    def load_file(self, path):
        """Load ``path`` and show its description; on failure show the error, clear the
        data set and return None."""
        path = Path(path)
        try:
            info = dataset_info(path)
        except Exception as e:  # any unreadable or unsuitable user file
            self.info = None
            self.path_label.setText(str(path))
            self.info_label.setText(f"Could not load {path.name}:\n{type(e).__name__}: {e}")
            self._update_run_enabled()
            return None
        self.info = info
        self.data_dir = path.parent
        self.path_label.setText(str(path))
        self.info_label.setText(info.summary())
        self.setWindowTitle(f"formdiscovery — {path.name}")
        self._update_run_enabled()
        self.dataset_changed.emit(info)
        return info

    # --- forms and settings ----------------------------------------------------------
    def selected_forms(self):
        """Selected form names, in ``ps.structures`` order."""
        return [self.form_list.item(i).text() for i in range(self.form_list.count())
                if self.form_list.item(i).isSelected()]

    def set_forms(self, names):
        """Select exactly ``names`` (unknown names raise ``ValueError``)."""
        names = set(names)
        unknown = names - set(STRUCTURES)
        if unknown:
            raise ValueError(f"unknown forms: {sorted(unknown)}")
        for i in range(self.form_list.count()):
            item = self.form_list.item(i)
            item.setSelected(item.text() in names)

    def run_settings(self):
        """What a run needs: the file, its description, the forms, seed and speed."""
        return {"path": None if self.info is None else self.info.path,
                "info": self.info,
                "forms": self.selected_forms(),
                "seed": self.seed_spin.value(),
                "speed": self.speed_spin.value(),
                "backend": self.backend_combo.currentText(),
                "bestsplit": self.bestsplit_check.isChecked(),
                "parallel": self.parallel_spin.value()}

    def _update_run_enabled(self):
        self.run_button.setEnabled(self.info is not None and bool(self.selected_forms())
                                   and not self.running())

    def _on_run(self):
        if self.run_button.isEnabled():
            self.run_requested.emit(self.run_settings())

    # --- runs (items 02, 05) ---------------------------------------------------------
    def running(self):
        return self.queue is not None and self.queue.is_running()

    def _current_run(self):
        """The shown form's run if its thread is alive, else the first live one."""
        if self.queue is None:
            return None
        act = self.queue.active()
        return next((r for r in act if r.form == self.shown), act[0] if act else None)

    @property
    def worker(self):
        """The :class:`RunWorker` of the shown (else the first) running form, or None."""
        r = self._current_run()
        return None if r is None else r.worker

    @property
    def thread(self):
        """That worker's ``QThread``, or None."""
        r = self._current_run()
        return None if r is None else r.thread

    def start_run(self, settings):
        """Queue the forms of ``settings`` (:meth:`run_settings`), ``parallel`` at a time,
        each in its own worker thread; returns the first form's :class:`RunWorker` (None
        if a run is already going)."""
        if self.running() or settings["path"] is None or not settings["forms"]:
            return None
        forms = list(settings["forms"])
        q = RunQueue(settings["path"], forms, seed=settings["seed"],
                     speed=settings["speed"], bestsplit=settings.get("bestsplit", False),
                     parallel=settings.get("parallel", 1), cap=self.frame_cap, parent=self)
        q.run_started.connect(self._on_run_started)
        q.frame.connect(self._on_frame)
        q.depth_done.connect(self._on_depth)
        q.form_ended.connect(self._on_form_ended)
        q.all_done.connect(self._on_all_done)
        if self.queue is not None:
            self.queue.deleteLater()
        self.queue, self.last_result, self.last_error = q, None, None
        self.shown, self._follow, self._live = None, True, True
        self.results.update_runs(q.runs)
        self.status_label.setText(f"Running {', '.join(forms)} on "
                                  f"{Path(settings['path']).stem}…")
        q.start()
        self.stop_button.setEnabled(True)
        self._update_run_enabled()
        return q.runs[0].worker

    def stop_run(self):
        """Ask the queue to stop (running forms end ``cancelled``, pending ones never
        start)."""
        if self.running():
            self.queue.cancel()
            self.stop_button.setEnabled(False)
            self.status_label.setText("Stopping…")

    def wait_run(self, ms=60000):
        """Run the event loop until the queue is done (tests, close); True if it is."""
        if not self.running():
            return True
        return self.queue.wait(ms)

    # --- what is shown ---------------------------------------------------------------
    def select_form(self, form):
        """Show ``form`` (a results table click): its final graph, or its latest frame
        while it runs, its frames on the slider and its statistics. The display then
        stops following the runs."""
        self._follow = False
        self.show_form(form)

    def show_form(self, form):
        """Show ``form`` of the current queue in the canvas, slider and statistics."""
        r = self.queue.run(form)
        self.shown, self._live = form, True
        self.results.select_form(form)
        data = Path(self.queue.path).stem
        msg = {"pending": f"{form}: waiting to start", "running": f"Running {form}…",
               "cancelled": f"{form}: stopped", "failed": f"{form}: run failed"}
        self.canvas.begin_run(msg.get(r.status, ""))
        self._sync_slider()
        last = r.history.last()
        if r.status == "finished":
            final = r.history.last("inferredgraph") or last
            if final is not None:
                self.canvas.draw_frame(*final.canvas_args())
            self.stats.show_result(r.result)
        else:
            if last is not None:
                self.canvas.draw_frame(*last.canvas_args())
            if r.status in ("cancelled", "failed"):
                self.canvas.set_status(msg[r.status] + (f" · last: {self.canvas.status}"
                                                        if last is not None else ""))
            self.stats.begin_run(f"{msg[r.status]} on {data}")
            for lls in r.depths:
                self.stats.push_depth(lls)

    def _sync_slider(self, keep=None):
        """Slider range = the shown form's frames; at the end when live, else ``keep``."""
        r = None if self.shown is None else self.queue.run(self.shown)
        n = 0 if r is None else len(r.history)
        sl = self.history_slider
        sl.blockSignals(True)
        try:
            sl.setRange(0, max(0, n - 1))
            sl.setEnabled(n > 1)
            if self._live or keep is None:
                sl.setValue(max(0, n - 1))
            else:
                sl.setValue(max(0, min(keep, n - 1)))
        finally:
            sl.blockSignals(False)
        self._update_history_label()

    def _update_history_label(self):
        r = None if self.shown is None else self.queue.run(self.shown)
        if r is None or not len(r.history):
            self.history_label.setText("no frames")
            return
        h = r.history
        f = h[self.history_slider.value()]
        text = f"{f.number} / {h.received} · {f.event}"
        if h.dropped:
            text += f" ({h.dropped} oldest dropped)"
        self.history_label.setText(text + ("" if self._live else " · paused"))

    def _on_slider(self, value):
        """The user moved the slider: draw that frame; the right end is live again."""
        r = None if self.shown is None else self.queue.run(self.shown)
        if r is None or not len(r.history):
            return
        self._live = value >= len(r.history) - 1
        self.canvas.pending = None
        self.canvas.draw_frame(*r.history[value].canvas_args())
        self._update_history_label()

    # --- queue signals ---------------------------------------------------------------
    def _on_run_started(self, r):
        self.results.update_runs(self.queue.runs)
        if self.shown is None or (self._follow
                                  and self.queue.run(self.shown).status != "running"):
            self.show_form(r.form)
        self.run_started.emit(r.worker)

    def _on_frame(self, form, f):
        r = self.queue.run(form)
        if r.worker is not None and not r.worker.is_cancelled():
            self.status_label.setText(f"{form}: {f.event}, depth {f.depth}, "
                                      f"frame {f.number}")
        if form != self.shown:
            return
        if self._live:
            self._sync_slider()
            self.canvas.push_entry(*f.canvas_args())
        else:  # keep the chosen frame while older ones are dropped
            keep = self.history_slider.value()
            if r.history.dropped and len(r.history) == r.history.cap:
                keep -= 1
            self._sync_slider(max(0, keep))

    def _on_depth(self, form, lls):
        if form == self.shown:
            self.stats.push_depth(lls)

    def _on_form_ended(self, form, outcome):
        r = self.queue.run(form)
        if outcome == "failed":
            self.last_error = r.error
        self.results.update_runs(self.queue.runs)
        if form == self.shown:
            if outcome == "finished":
                self.stats.show_result(r.result)
            else:
                self.canvas.flush()
                if outcome == "failed":
                    self.canvas.set_status("Run failed.")
                else:
                    last = self.canvas.status
                    self.canvas.set_status(
                        "stopped" + (f" · last: {last}" if self.canvas.drawn else ""))
                self.stats.begin_run(f"{form}: " + ("run failed" if outcome == "failed"
                                                    else "stopped"))
            nxt = next((x for x in self.queue.runs if x.status == "running"), None)
            if self._follow and nxt is not None and not self.queue.stopped:
                self.show_form(nxt.form)

    def _on_all_done(self, outcome):
        q = self.queue
        win = q.winner()
        self.last_result = None if win is None else win.result
        self.results.update_runs(q.runs)
        if outcome == "finished" and win is not None and self._follow \
                and win.form != self.shown:
            self.show_form(win.form)
        if self.shown is not None:
            self.results.select_form(self.shown)
        if outcome == "cancelled":
            self.status_label.setText("Run stopped.")
        elif outcome == "failed":
            lines = (self.last_error or "").strip().splitlines()
            self.status_label.setText("Run failed: " + lines[-1] if lines else "Run failed.")
        elif len(q.runs) == 1:
            res = win.result
            self.status_label.setText(f"{res['form']}: ll = {res['ll']:.4f} "
                                      f"({res['frames']} frames, {res['wall']:.1f} s)")
        else:
            self.status_label.setText(f"{len(q.runs)} forms in {q.wall:.1f} s; winner "
                                      f"{win.form}: ll = {win.ll():.4f}")
        self.stop_button.setEnabled(False)
        self._update_run_enabled()
        self.run_ended.emit(outcome)

    def closeEvent(self, event):
        """Cancel a running search and wait for its thread before closing."""
        if self.running():
            self.queue.cancel()
            self.wait_run()
        super().closeEvent(event)
