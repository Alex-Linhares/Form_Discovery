"""The main window: data picker, forms and run settings (loop0003 item 01).

Layout: an "Open data file…" button with the chosen path, the dataset info panel
(:meth:`formdiscovery.gui.dataset.DatasetInfo.summary`), the form list (the 24
``ps.structures`` of ``setps.m``, multi-select, chain/ring/tree preselected as in
``masterrun.m``'s ``thisstruct``), seed and speed spin boxes (speed defaults to
``defaultps.m``'s 54 and steps through :data:`SPEEDS` only: ``ps.speed`` is a mode code,
not a count; 1 and 2 crash in ``best_split`` (``KNOWN_ISSUES.md`` KI-1) and 23 is
runmodel's "Unknown speed value") and Run/Stop buttons. Run emits
:attr:`MainWindow.run_requested` with :meth:`MainWindow.run_settings`; the worker that consumes it is item 02, so Stop
stays disabled for now.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..io import DATA_DIR
from ..params import STRUCTURES
from ..run import MASTERRUN_STRUCT
from .dataset import dataset_info

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

    def __init__(self, path=None, data_dir=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("formdiscovery")
        self.data_dir = Path(data_dir or DATA_DIR)
        self.info = None

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
        settings = QGroupBox("Settings")
        sform = QFormLayout(settings)
        sform.addRow("Seed", self.seed_spin)
        sform.addRow("Speed", self.speed_spin)

        self.run_button = QPushButton("Run")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._on_run)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.stop_button)

        left = QVBoxLayout()
        left.addWidget(info_box, 1)
        left.addWidget(settings)
        middle = QHBoxLayout()
        middle.addLayout(left, 1)
        middle.addWidget(form_box, 1)
        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(middle, 1)
        root.addLayout(buttons)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.resize(760, 520)

        self.form_list.itemSelectionChanged.connect(self._update_run_enabled)
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
                "speed": self.speed_spin.value()}

    def _update_run_enabled(self):
        self.run_button.setEnabled(self.info is not None and bool(self.selected_forms()))

    def _on_run(self):
        if self.run_button.isEnabled():
            self.run_requested.emit(self.run_settings())
