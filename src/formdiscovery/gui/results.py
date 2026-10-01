"""The forms of a run ranked by score (loop0003 item 05).

:class:`ResultsTable` lists the forms of a :class:`formdiscovery.gui.runs.RunQueue`, one
row each: rank, form, ll (runmodel's final score, masterrun's ``modellike``), its prior and
likelihood parts, clusters, wall time, frames and status. Finished forms come first, best
ll first (:func:`formdiscovery.gui.runs.ranked`); the winner (highest ll) is bold on a
tinted row and its status reads ``winner`` (only when at least two forms finished). Clicking a row emits :attr:`form_selected`;
the window then shows that form's final graph, frames and statistics.
"""

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from ..run import graph_summary
from .runs import ranked

__all__ = ["ResultsTable", "COLUMNS", "WINNER_BG", "row_values"]

COLUMNS = ("#", "form", "ll", "prior", "likelihood", "clusters", "time (s)", "frames",
           "status")
WINNER_BG = "#dbe9fa"


def _num(x, fmt):
    return "" if x is None or not np.isfinite(x) else format(x, fmt)


def row_values(run, rank=None, winner=False):
    """The cells of ``run`` (a :class:`formdiscovery.gui.runs.FormRun`) as strings."""
    res = run.result
    frames = run.history.received
    if res is None:
        return ["" if rank is None else str(rank), run.form, "", "", "", "", "",
                str(frames) if frames else "", run.status]
    return [str(rank), run.form, _num(res["ll"], ".4f"), _num(res.get("prior"), ".4f"),
            _num(res.get("likelihood"), ".4f"), str(graph_summary(res["graph"])["nclusters"]),
            _num(res["wall"], ".2f"), str(res["frames"]),
            "winner" if winner else run.status]


class ResultsTable(QTableWidget):
    """Forms ranked by ll (module docstring)."""

    form_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(list(COLUMNS))
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)
        rowh = self.verticalHeader().defaultSectionSize()
        self.setMinimumHeight(hdr.sizeHint().height() + 4 * rowh + 2 * self.frameWidth())
        self.order = []      # forms, top to bottom
        self.winner = None
        self.cellClicked.connect(self._on_click)

    def update_runs(self, runs):
        """Refill from ``runs`` (FormRun list), keeping the selected form selected."""
        keep = self.selected_form()
        rows = ranked(list(runs))
        done = [r for r in rows if r.status == "finished"]
        self.winner = done[0].form if done else None
        self.order = [r.form for r in rows]
        self.setRowCount(len(rows))
        bold = QFont(self.font())
        bold.setBold(True)
        for i, r in enumerate(rows):
            win = r.form == self.winner and len(done) >= 2  # one form has nothing to beat
            rank = i + 1 if r.status == "finished" else None
            for j, text in enumerate(row_values(r, rank, win)):
                item = QTableWidgetItem(text)
                if j in (0, 2, 3, 4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if win:
                    item.setFont(bold)
                    item.setBackground(QBrush(QColor(WINNER_BG)))
                self.setItem(i, j, item)
        if keep in self.order:
            self.select_form(keep)

    def cell(self, form, column):
        """The text in ``form``'s row under ``column`` (a :data:`COLUMNS` name)."""
        return self.item(self.order.index(form), COLUMNS.index(column)).text()

    def selected_form(self):
        rows = {i.row() for i in self.selectedItems()}
        return self.order[min(rows)] if rows else None

    def select_form(self, form):
        """Select ``form``'s row without emitting :attr:`form_selected`."""
        self.blockSignals(True)
        try:
            self.selectRow(self.order.index(form))
        finally:
            self.blockSignals(False)

    def _on_click(self, row, column):
        if 0 <= row < len(self.order):
            self.form_selected.emit(self.order[row])
