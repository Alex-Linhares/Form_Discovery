"""Statistics of a finished run (loop0003 item 04).

:func:`run_stats` turns the worker's ``finished`` result
(:attr:`formdiscovery.gui.worker.RunWorker.finished`) into plain numbers:

- ``ll``: runmodel's final score; ``prior`` and ``likelihood``: its two parts,
  :func:`formdiscovery.params.graph_prior` and :func:`formdiscovery.likelihood.graph_like`
  of the final graph (:func:`score_parts`). They are computed as ``runmodel.m:178-180``
  scores a speed-5 run, in slow mode (``ps.fast = 0``: MAP branch lengths, the weight
  prior integrated), with ``ps`` rebuilt as runmodel builds it (``setrunps``,
  ``scaledata``, ``structcounts``). The final speed-4 score of a speed-54 run is the same
  slow score, so ``prior + likelihood == ll`` for both (the fast score, ``ps.fast = 1``,
  is not: about 20 nats higher on the demo, it leaves the weight prior out). The worker
  computes the parts in its thread; :func:`run_stats` only fills them in when missing.
- ``clusters``: the object names grouped by ``graph.z`` (0-based cluster -> names, in
  cluster order; ``-1``, an unassigned object, listed last), ``nclusters`` and ``nnodes``
  as :func:`formdiscovery.run.graph_summary` counts them;
- ``history``: runmodel's ``bestglls`` cell (``bestgraphlls`` per ``structurefit``
  stage) in run order, as ``(label, lls)``: higher ``ps.speed`` columns first (speed 54
  runs 5 then 4), stages in order, empty stages kept (no depth accepted). A tree's last
  fit (root removed) overwrites its speed-4 cell, as in MATLAB. Speed-5 histories are
  approximate (fast-mode) scores, so the last one can lie above the final ll
  (``ANOMALIES.md`` A26: -8224.02 vs -8247.19 for chain x demo_chain_feat);
- ``wall``, ``frames``, ``form``, ``data``, ``seed``, ``speed``.

:class:`StatsPanel` shows them (:func:`stats_text`, a matplotlib chart of the history
with the final ll as a dashed line) when ``finished`` arrives, draws the current stage live
from ``depth_done``, and exports the run with :func:`export_results` (``.npz`` + ``.json``,
what ``formdiscovery run`` writes, :func:`formdiscovery.run.save_results`; read back
with :func:`formdiscovery.run.load_results`) and the final graph figure with
:func:`export_figure` (PNG or SVG).
"""

from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .. import likelihood
from ..io import load_dataset
from ..params import graph_prior, setrunps, structcounts
from ..preprocess import scaledata
from ..run import MasterResults, graph_summary, save_results
from ..threads import limit_blas_threads
from .worker import run_ps

__all__ = ["StatsPanel", "run_stats", "stats_text", "score_parts", "history_stages",
           "clusters", "export_results", "export_figure", "SERIES", "RESULTS_FILTER",
           "FIGURE_FILTER"]

# categorical slots in fixed order (one per structurefit stage), muted ink for the final ll
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7",
          "#e34948")
INK, MUTED = "#0b0b0b", "#52514e"
RESULTS_FILTER = "Results (*.npz *.json)"
FIGURE_FILTER = "PNG image (*.png);;SVG image (*.svg)"


@limit_blas_threads
def score_parts(path, form, graph, speed=None, data_dir=None):
    """``(prior, likelihood)`` of ``graph`` (form ``form`` fitted to the data file
    ``path``), scored in slow mode with ``ps`` rebuilt as ``runmodel.m:13-33`` does
    (module docstring); their sum is runmodel's final ll."""
    ps, sind, dind = run_ps(path, form, speed, data_dir)
    ps.runps.structname = ps.structures[sind]
    data = load_dataset(ps.dlocs[dind])
    nobjects, ps = setrunps(data, dind, ps)
    data, ps = scaledata(data, ps)
    ps = structcounts(nobjects, ps)
    prior = graph_prior(graph, ps)
    like, _ = likelihood.graph_like(data, graph, ps.replace(fast=0))
    return float(prior), float(like)


def history_stages(bestglls):
    """runmodel's ``bestglls`` cell as ``[(label, lls), ...]`` in run order (module
    docstring); ``lls`` a 1-D float array, possibly empty."""
    out = []
    if bestglls is None:
        return out
    cell = np.asarray(bestglls, dtype=object)
    if cell.ndim != 2:
        return out
    for j in range(cell.shape[1] - 1, -1, -1):  # speed j + 1
        for i in range(cell.shape[0]):
            v = cell[i, j]
            if v is not None:
                out.append((f"speed {j + 1}, stage {i + 1}",
                            np.asarray(v, dtype=float).ravel()))
    return out


def clusters(graph, names):
    """``[(cluster, [names]), ...]``: the objects grouped by ``graph.z`` (0-based
    clusters in order, then ``-1`` for unassigned objects)."""
    z = np.asarray(graph.z).ravel().astype(int)
    names = list(names)[:z.size]
    names += [str(k + 1) for k in range(len(names), z.size)]
    keys = sorted(set(z.tolist()), key=lambda c: (c < 0, c))
    return [(int(c), [names[k] for k in np.flatnonzero(z == c)]) for c in keys]


def run_stats(result):
    """The statistics of a worker ``finished`` result (module docstring)."""
    if "prior" not in result or "likelihood" not in result:
        result = dict(result)
        result["prior"], result["likelihood"] = score_parts(
            result["path"], result["form"], result["graph"], result.get("speed"))
    summ = graph_summary(result["graph"])
    return {"form": result["form"], "data": Path(result["path"]).stem,
            "path": str(result["path"]), "seed": result["seed"], "speed": result["speed"],
            "ll": float(result["ll"]), "prior": float(result["prior"]),
            "likelihood": float(result["likelihood"]),
            "nobjects": summ["nobjects"], "nclusters": summ["nclusters"],
            "nnodes": summ["nnodes"],
            "clusters": clusters(result["graph"], result["names"]),
            "history": history_stages(result.get("bestglls")),
            "wall": float(result["wall"]), "frames": int(result["frames"])}


def _num(x):
    return f"{x:.4f}" if np.isfinite(x) else str(x)


def stats_text(st):
    """The panel's text for :func:`run_stats` output ``st``."""
    lines = [f"{st['form']} on {st['data']}  (seed {st['seed']}, speed {st['speed']})",
             "",
             f"log score (ll)    {_num(st['ll'])}",
             f"  log prior       {_num(st['prior'])}   graph_prior",
             f"  log likelihood  {_num(st['likelihood'])}   graph_like"]
    gap = st["prior"] + st["likelihood"] - st["ll"]
    if not np.isclose(gap, 0.0, rtol=0, atol=1e-6):
        lines.append(f"  (prior + likelihood - ll = {gap:.6g})")
    lines += ["",
              f"objects {st['nobjects']}, clusters {st['nclusters']}, "
              f"cluster nodes {st['nnodes']}"]
    for c, members in st["clusters"]:
        label = "unassigned" if c < 0 else f"cluster {c + 1}"
        lines.append(f"  {label:<11s} ({len(members)}): {', '.join(members)}")
    lines += ["", "score per depth (bestgraphlls)"]
    for label, lls in st["history"]:
        vals = ", ".join(f"{v:.2f}" for v in lls) if lls.size else "no depth accepted"
        lines.append(f"  {label}: {vals}")
    if not st["history"]:
        lines.append("  (none)")
    elif any(label.startswith("speed 5,") for label, _ in st["history"]):
        lines.append("  (speed 5 scores are approximate, fast mode; ll is the slow score)")
    lines += ["", f"wall time {st['wall']:.2f} s, frames {st['frames']}"]
    return "\n".join(lines)


def _results_stem(path):
    path = Path(path)
    return path.with_suffix("") if path.suffix in (".npz", ".json") else path


def export_results(result, path):
    """Save the run as ``formdiscovery run`` would (``masterrun`` repeat 1, seed
    ``result['seed']``): ``<stem>.npz`` and ``<stem>.json`` with
    :func:`formdiscovery.run.save_results` (``path`` with or without the suffix).
    Returns ``(npz, json)`` paths."""
    stem = _results_stem(path)
    ps, sind, dind = run_ps(result["path"], result["form"], result["speed"])
    ps.speed = int(result["speed"])
    run = {"structure": ps.structures[sind], "data": ps.data[dind], "sind": sind,
           "dind": dind, "rind": 1, "seed": int(result["seed"]), "ll": float(result["ll"]),
           "seconds": float(result["wall"]), **graph_summary(result["graph"])}
    res = MasterResults()
    res.store(sind, dind, 1, ps.copy(), float(result["ll"]), result["graph"],
              list(result["names"]), result.get("bestglls"), run)
    save_results(res, stem, ps)
    return stem.with_suffix(".npz"), stem.with_suffix(".json")


def export_figure(figure, path):
    """Save the matplotlib ``figure`` to ``path`` (PNG or SVG from the suffix; no suffix:
    ``.png``). Returns the path."""
    path = Path(path)
    if path.suffix.lower() not in (".png", ".svg"):
        if path.suffix:
            raise ValueError(f"{path.name}: save the figure as .png or .svg")
        path = path.with_suffix(".png")
    figure.savefig(path, format=path.suffix[1:].lower(), bbox_inches="tight")
    return path


class StatsPanel(QWidget):
    """The statistics of the last run: text, a per-depth score chart and export buttons.
    ``figure_source`` (optional) is the widget whose ``figure`` "Save figure…" saves
    (the window's :class:`formdiscovery.gui.canvas.GraphCanvas`)."""

    exported = Signal(str, object)  # 'results' / 'figure', path(s)

    def __init__(self, figure_source=None, parent=None):
        super().__init__(parent)
        self.figure_source = figure_source
        self.result = self.stats = None
        self.live = []          # stages of the running search (from depth_done)
        self.export_dir = Path.cwd()

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.chart = FigureCanvasQTAgg(Figure(figsize=(4.0, 2.6), dpi=100))
        self.chart.setMinimumHeight(220)
        self.results_button = QPushButton("Export results…")
        self.results_button.clicked.connect(self.export_results_dialog)
        self.figure_button = QPushButton("Save figure…")
        self.figure_button.clicked.connect(self.export_figure_dialog)
        buttons = QHBoxLayout()
        buttons.addWidget(self.results_button)
        buttons.addWidget(self.figure_button)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.text, 3)
        lay.addWidget(self.chart, 2)
        lay.addLayout(buttons)
        self.clear()

    # --- filling -------------------------------------------------------------------
    def clear(self, message="Run a form to see its statistics."):
        self.result = self.stats = None
        self.live = []
        self.text.setPlainText(message)
        self._plot([], None)
        self._update_buttons()

    def begin_run(self, message="Running…"):
        self.clear(message)

    @Slot(object)
    def push_depth(self, lls):
        """A ``depth_done`` history: a list no longer than the last one starts a new
        stage. The chart shows the stages so far."""
        lls = np.asarray(lls, dtype=float).ravel()
        if not self.live or lls.size <= self.live[-1][1].size:
            self.live.append((f"stage {len(self.live) + 1}", lls))
        else:
            self.live[-1] = (self.live[-1][0], lls)
        self._plot(self.live, None)

    @Slot(object)
    def show_result(self, result):
        """Fill the panel from a worker ``finished`` result."""
        self.result = result
        self.stats = run_stats(result)
        self.text.setPlainText(stats_text(self.stats))
        self._plot(self.stats["history"], self.stats["ll"])
        self._update_buttons()
        return self.stats

    def _plot(self, history, final):
        fig = self.chart.figure
        fig.clear()
        ax = fig.add_subplot(111)
        drawn = 0
        for k, (label, lls) in enumerate(history):
            if not lls.size:
                continue
            ax.plot(np.arange(1, lls.size + 1), lls, color=SERIES[drawn % len(SERIES)],
                    lw=2, marker="o", ms=6, mec="white", mew=1.5, label=label)
            drawn += 1
        if final is not None and np.isfinite(final):
            ax.axhline(final, color=MUTED, lw=1.5, ls="--", label=f"final ll {final:.2f}")
        ax.set_xlabel("depth", color=MUTED, fontsize=8)
        ax.set_ylabel("score", color=MUTED, fontsize=8)
        ax.set_title("Score per depth", color=INK, fontsize=9, loc="left")
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.xaxis.get_major_locator().set_params(integer=True)
        ax.grid(True, color="#e6e5e1", lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#c3c2b7")
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=7, frameon=False, loc="lower right", labelcolor=INK)
        else:
            ax.text(0.5, 0.5, "no depth yet", ha="center", va="center", color=MUTED,
                    fontsize=8, transform=ax.transAxes)
        fig.tight_layout()
        self.chart.draw_idle()

    def _update_buttons(self):
        self.results_button.setEnabled(self.result is not None)
        self.figure_button.setEnabled(self.result is not None
                                      and self.figure_source is not None)

    # --- export --------------------------------------------------------------------
    def export_results(self, path):
        npz, js = export_results(self.result, path)
        self.export_dir = npz.parent
        self.exported.emit("results", (npz, js))
        return npz, js

    def export_figure(self, path):
        out = export_figure(self.figure_source.figure, path)
        self.export_dir = out.parent
        self.exported.emit("figure", out)
        return out

    def export_results_dialog(self):
        if self.result is None:
            return None
        start = self.export_dir / f"results_{self.stats['form']}_{self.stats['data']}.npz"
        path, _ = QFileDialog.getSaveFileName(self, "Export results", str(start),
                                              RESULTS_FILTER)
        return self.export_results(path) if path else None

    def export_figure_dialog(self):
        if self.result is None or self.figure_source is None:
            return None
        start = self.export_dir / f"{self.stats['form']}_{self.stats['data']}.png"
        path, flt = QFileDialog.getSaveFileName(self, "Save figure", str(start),
                                                FIGURE_FILTER)
        if not path:
            return None
        if not Path(path).suffix:
            path += ".svg" if flt.startswith("SVG") else ".png"
        return self.export_figure(path)
