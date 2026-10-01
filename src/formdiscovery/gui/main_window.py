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
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton, QSpinBox, QVBoxLayout,
    QWidget,
)

from ..io import DATA_DIR
from ..params import STRUCTURES
from ..run import MASTERRUN_STRUCT
from .canvas import CANVAS_BACKENDS, GraphCanvas
from .dataset import dataset_info
from .stats import StatsPanel
from .worker import RunWorker, start_worker

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
        self.worker = self.thread = None
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
        settings = QGroupBox("Settings")
        sform = QFormLayout(settings)
        sform.addRow("Seed", self.seed_spin)
        sform.addRow("Speed", self.speed_spin)
        sform.addRow("Drawing", self.backend_combo)
        sform.addRow("", self.bestsplit_check)

        self.canvas = GraphCanvas()
        self.canvas.setMinimumSize(420, 360)
        self.backend_combo.currentTextChanged.connect(self.canvas.set_backend)
        graph_box = QGroupBox("Graph")
        QVBoxLayout(graph_box).addWidget(self.canvas)
        self.stats = StatsPanel(figure_source=self.canvas)
        self.stats.setMinimumWidth(340)
        stats_box = QGroupBox("Statistics")
        QVBoxLayout(stats_box).addWidget(self.stats)

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
        middle.addWidget(graph_box, 3)
        middle.addWidget(stats_box, 2)
        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(middle, 1)
        root.addLayout(buttons)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.resize(1440, 800)

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
                "bestsplit": self.bestsplit_check.isChecked()}

    def _update_run_enabled(self):
        self.run_button.setEnabled(self.info is not None and bool(self.selected_forms())
                                   and not self.running())

    def _on_run(self):
        if self.run_button.isEnabled():
            self.run_requested.emit(self.run_settings())

    # --- runs (item 02) --------------------------------------------------------------
    def running(self):
        return self.thread is not None

    def start_run(self, settings):
        """Run the first form of ``settings`` (:meth:`run_settings`) in a worker thread;
        returns the :class:`RunWorker` (None if a run is already going)."""
        if self.running() or settings["path"] is None or not settings["forms"]:
            return None
        form = settings["forms"][0]
        w = RunWorker(settings["path"], form, seed=settings["seed"],
                      speed=settings["speed"], bestsplit=settings.get("bestsplit", False))
        self.canvas.begin_run(f"Running {form}…")
        self.stats.begin_run(f"Running {form} on {Path(settings['path']).stem}…")
        w.frame.connect(self.canvas.push_frame)
        w.depth_done.connect(self.stats.push_depth)
        w.finished.connect(self.stats.show_result)
        w.frame.connect(self._on_frame)
        w.finished.connect(self._on_finished)
        w.failed.connect(self._on_failed)
        w.cancelled.connect(self._on_cancelled)
        self.worker, self.last_result, self.last_error = w, None, None
        self.status_label.setText(f"Running {form} on {Path(settings['path']).stem}…")
        self.run_started.emit(w)
        self.thread = start_worker(w, start=False)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()
        self.stop_button.setEnabled(True)
        self._update_run_enabled()
        return w

    def stop_run(self):
        """Ask the current run to stop (it ends with ``cancelled``)."""
        if self.worker is not None:
            self.worker.cancel()
            self.stop_button.setEnabled(False)
            self.status_label.setText("Stopping…")

    def wait_run(self, ms=60000):
        """Block until the run's thread ends (tests, close); True if it ended."""
        if self.thread is None:
            return True
        ok = self.thread.wait(ms)
        if ok:
            self._on_thread_finished()
        return ok

    def _on_frame(self, event, adj, names, title, depth):
        w = self.worker
        if w is not None and not w.is_cancelled():
            self.status_label.setText(f"{w.form}: {event}, depth {depth}, "
                                      f"frame {w.frames}")

    def _on_finished(self, result):
        self.last_result = result
        self.status_label.setText(f"{result['form']}: ll = {result['ll']:.4f} "
                                  f"({result['frames']} frames, {result['wall']:.1f} s)")
        self.run_ended.emit("finished")

    def _on_failed(self, tb):
        self.last_error = tb
        self.status_label.setText("Run failed: " + tb.strip().splitlines()[-1])
        self.canvas.flush()
        self.canvas.set_status("Run failed.")
        self.run_ended.emit("failed")

    def _on_cancelled(self):
        self.status_label.setText("Run stopped.")
        self.canvas.flush()
        last = self.canvas.status
        self.canvas.set_status("stopped" + (f" · last: {last}" if self.canvas.drawn else ""))
        self.run_ended.emit("cancelled")

    def _on_thread_finished(self):
        if self.thread is None or self.thread.isRunning():
            return
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = self.worker = None
        self.stop_button.setEnabled(False)
        self._update_run_enabled()

    def closeEvent(self, event):
        """Cancel a running search and wait for its thread before closing."""
        if self.worker is not None:
            self.worker.cancel()
            self.wait_run()
        super().closeEvent(event)
