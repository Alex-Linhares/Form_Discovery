"""loop0003 item 05: several forms, the ranked results table and the frame history,
offscreen (pytest-qt).

:class:`formdiscovery.gui.runs.RunQueue` runs chain, ring and tree x demo_chain_feat one
at a time or side by side, each on its own thread; every score is masterrun's for that
pair either way. The window ranks them by ll (winner highlighted), shows a clicked row's
final graph and statistics, and scrubs back through a form's frames, keeping at most
``frame_cap`` of them.
"""

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from formdiscovery.gui.app import screenshot  # noqa: E402
from formdiscovery.gui.main_window import MainWindow  # noqa: E402
from formdiscovery.gui.results import COLUMNS, WINNER_BG, ResultsTable  # noqa: E402
from formdiscovery.gui.runs import FrameHistory, RunQueue, ranked  # noqa: E402
from formdiscovery.io import DATA_DIR  # noqa: E402
from formdiscovery.run import MASTERRUN_STRUCT, masterrun, masterrun_ps  # noqa: E402

DEMO = DATA_DIR / "demo_chain_feat.mat"
TIMEOUT = 60000
FORMS = {"chain": 1, "ring": 3, "tree": 5}  # form -> sind (masterrun's thisstruct)


@pytest.fixture(scope="module")
def master():
    """masterrun's chain, ring and tree x demo_chain_feat (seed 1, repeat 1): ll by form."""
    assert tuple(FORMS.values()) == MASTERRUN_STRUCT
    res = masterrun(masterrun_ps(), thisstruct=list(FORMS.values()), thisdata=[0])
    return {f: float(res.modellike[s, 0, 0]) for f, s in FORMS.items()}


class Ended(QObject):
    """Relays a queue's ``all_done`` (for ``qtbot.waitSignal``) and records its
    ``form_ended`` order."""

    done = Signal(str)

    def __init__(self, q):
        super().__init__()
        self.order = []
        q.form_ended.connect(self.on_form)
        q.all_done.connect(self.done)

    def on_form(self, form, outcome):
        self.order.append((form, outcome))


def run_queue(qtbot, q):
    rec = Ended(q)
    try:
        with qtbot.waitSignal(rec.done, timeout=TIMEOUT) as sig:
            q.start()
    finally:  # never leave a run going into later tests (ANOMALIES.md A24)
        if q.is_running():
            q.cancel()
            q.wait(TIMEOUT)
    return sig.args[0], rec.order


@pytest.mark.parametrize("parallel", [1, 3])
def test_queue_matches_masterrun(qtbot, master, parallel):
    q = RunQueue(DEMO, list(FORMS), parallel=parallel)
    outcome, order = run_queue(qtbot, q)
    assert outcome == "finished" and not q.is_running() and not q.active()
    assert sorted(order) == sorted((f, "finished") for f in FORMS)
    if parallel == 1:  # one at a time, in the order given
        assert [f for f, _ in order] == list(FORMS)
    assert q.max_active == parallel
    for r in q.runs:  # bit for bit, whatever ran next to it
        assert r.ll() == master[r.form]
        assert len(r.history) == r.history.received == r.result["frames"]
        assert r.history.last().event == "inferredgraph"
        assert np.array_equal(r.history.last().adj, r.result["graph"].adj)
        assert len(r.depths) >= 1
    best = max(master, key=master.get)
    assert q.winner().form == best
    assert [r.form for r in q.finished_runs()] == sorted(master, key=master.get,
                                                         reverse=True)


def test_queue_cancel_skips_pending(qtbot):
    q = RunQueue(DEMO, list(FORMS), parallel=1)

    class StopOnFrame(QObject):
        def on_frame(self, form, f):
            q.cancel()

    stopper = StopOnFrame()
    q.frame.connect(stopper.on_frame)
    outcome, order = run_queue(qtbot, q)
    assert outcome == "cancelled"
    assert [r.status for r in q.runs] == ["cancelled"] * 3
    assert q.runs[0].history.received >= 1
    assert all(r.history.received == 0 and r.result is None for r in q.runs[1:])
    assert q.max_active == 1 and q.winner() is None


def test_queue_rejects_bad_forms(qapp):
    with pytest.raises(ValueError):
        RunQueue(DEMO, [])
    with pytest.raises(ValueError):
        RunQueue(DEMO, ["chain", "chain"])


def test_frame_history_cap():
    h = FrameHistory(cap=3)
    for k in range(5):
        h.append("postclean" if k % 2 else "preclean", np.eye(2) * k, ["a"], f"t {k}", k,
                 0.1 * k)
    assert len(h) == 3 and h.received == 5 and h.dropped == 2
    assert [f.number for f in h] == [3, 4, 5]
    assert h.last().title == "t 4" and h.last("postclean").title == "t 3"
    assert h.last("inferredgraph") is None
    assert h[0].canvas_args()[-2:] == (pytest.approx(0.2), 3)
    unbounded = FrameHistory(cap=None)
    for k in range(5):
        unbounded.append("preclean", np.eye(2), [], "", 0, 0.0)
    assert len(unbounded) == 5 and unbounded.dropped == 0


class _Run:
    def __init__(self, form, status, ll=None):
        self.form, self.status, self._ll = form, status, ll

    def ll(self):
        return self._ll


def test_ranked_order():
    runs = [_Run("a", "failed"), _Run("b", "finished", -10.0), _Run("c", "pending"),
            _Run("d", "finished", -5.0), _Run("e", "running"), _Run("f", "cancelled"),
            _Run("g", "finished", -5.0)]
    assert [r.form for r in ranked(runs)] == ["d", "g", "b", "e", "c", "f", "a"]


# --- the window ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def done_win(qapp):
    """A window that ran chain, ring and tree x demo_chain_feat, two at a time."""
    w = MainWindow(path=DEMO)
    w.set_forms(list(FORMS))
    w.parallel_spin.setValue(2)
    w.show()
    s = w.run_settings()
    assert s["parallel"] == 2 and s["forms"] == list(FORMS)
    ended = []
    w.run_ended.connect(ended.append)
    w.run_requested.emit(s)
    assert w.wait_run(TIMEOUT)
    qapp.processEvents()
    assert ended == ["finished"]
    yield w
    w.close()


def test_window_ranks_forms(done_win, master):
    w = done_win
    t = w.results
    best = max(master, key=master.get)
    assert t.order == sorted(master, key=master.get, reverse=True)
    assert t.winner == best and w.queue.max_active == 2
    for i, form in enumerate(t.order):
        assert t.cell(form, "#") == str(i + 1)
        assert t.cell(form, "ll") == f"{master[form]:.4f}"
        r = w.queue.run(form).result
        assert t.cell(form, "prior") == f"{r['prior']:.4f}"
        assert t.cell(form, "frames") == str(r["frames"])
        assert t.cell(form, "status") == ("winner" if form == best else "finished")
    row = t.order.index(best)
    for j in range(len(COLUMNS)):
        assert t.item(row, j).font().bold()
        assert t.item(row, j).background().color() == QColor(WINNER_BG)
    other = t.order.index(t.order[-1])
    assert not t.item(other, 0).font().bold()
    # the display ends on the winner
    assert w.last_result["form"] == best and w.last_result["ll"] == master[best]
    assert w.shown == best and t.selected_form() == best
    final = w.queue.run(best).history.last("inferredgraph")
    assert w.canvas.last_title == final.title
    assert w.stats.stats["form"] == best and w.stats.stats["ll"] == master[best]
    assert w.status_label.text() == (f"3 forms in {w.queue.wall:.1f} s; winner {best}: "
                                     f"ll = {master[best]:.4f}")
    assert w.run_button.isEnabled() and not w.stop_button.isEnabled()


def test_window_click_row_shows_form(done_win, qtbot, master):
    w = done_win
    t = w.results
    for form in [f for f in t.order if f != t.winner] + [t.winner]:
        row = t.order.index(form)
        rect = t.visualItemRect(t.item(row, 1))
        qtbot.mouseClick(t.viewport(), Qt.LeftButton, pos=rect.center())
        assert w.shown == form and t.selected_form() == form and not w._follow
        h = w.queue.run(form).history
        assert w.canvas.last_title == h.last("inferredgraph").title
        assert w.canvas.last_event == "inferredgraph"
        assert w.stats.stats["form"] == form and w.stats.stats["ll"] == master[form]
        assert w.history_slider.maximum() == len(h) - 1 == w.history_slider.value()
        assert w.history_label.text().startswith(f"{h.received} / {h.received} · ")


def test_window_slider_scrubs(done_win):
    w = done_win
    w.select_form("ring")
    h = w.queue.run("ring").history
    sl = w.history_slider
    assert sl.isEnabled() and sl.maximum() == len(h) - 1
    for k in (0, len(h) // 2):
        sl.setValue(k)
        assert w.canvas.last_title == h[k].title and w.canvas.last_event == h[k].event
        assert not w._live
        assert w.history_label.text() == f"{h[k].number} / {h.received} · {h[k].event} · paused"
        assert w.canvas.status.endswith(f"frame {h[k].number}")
    sl.setValue(sl.maximum())
    assert w._live and w.canvas.last_event == "inferredgraph"
    assert not w.history_label.text().endswith("paused")


def test_window_paused_during_run(qtbot):
    """Moving the slider back during a run keeps that frame on the canvas while the run
    goes on; the slider's range grows with the frames."""
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.set_forms(["chain"])
    w.bestsplit_check.setChecked(True)
    paused = []

    class Pause(QObject):
        def __init__(self, worker):
            super().__init__()
            worker.frame.connect(self.on_frame)

        def on_frame(self, *args):  # runs after the window recorded the frame
            if not paused and w.history_slider.maximum() >= 1:
                w.history_slider.setValue(0)
                paused.append(w.canvas.last_title)

    recs = []
    w.run_started.connect(lambda wk: recs.append(Pause(wk)))
    try:
        with qtbot.waitSignal(w.run_ended, timeout=TIMEOUT) as sig:
            w.run_requested.emit(w.run_settings())
    finally:
        w.stop_run()
        w.wait_run(TIMEOUT)
    assert sig.args == ["finished"] and paused
    h = w.queue.run("chain").history
    assert paused[0] == h[0].title
    assert w.canvas.last_title == h[0].title and w.canvas.last_event != "inferredgraph"
    assert w.history_slider.value() == 0 and w.history_slider.maximum() == len(h) - 1
    assert h.last().event == "inferredgraph" and w.stats.stats["form"] == "chain"
    w.history_slider.setValue(w.history_slider.maximum())
    assert w.canvas.last_event == "inferredgraph"


def test_window_frame_cap(qtbot, master):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.frame_cap = 4
    w.set_forms(["chain", "ring"])
    with qtbot.waitSignal(w.run_ended, timeout=TIMEOUT) as sig:
        w.run_requested.emit(w.run_settings())
    assert w.wait_run(TIMEOUT)
    assert sig.args == ["finished"]
    for r in w.queue.runs:
        h = r.history
        assert len(h) == 4 and h.dropped == h.received - 4 == r.result["frames"] - 4
        assert [f.number for f in h] == list(range(h.received - 3, h.received + 1))
        assert h.last().event == "inferredgraph"  # the newest is never the one dropped
        assert r.ll() == master[r.form]
    w.select_form("ring")
    h = w.queue.run("ring").history
    assert w.history_slider.maximum() == 3
    assert f"({h.dropped} oldest dropped)" in w.history_label.text()
    w.history_slider.setValue(0)
    assert w.canvas.status.endswith(f"frame {h[0].number}")


def test_window_follows_running_form(qtbot):
    """One at a time: the display shows each form while it runs, then the winner."""
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.set_forms(["chain", "ring"])
    shown = []
    w.run_started.connect(lambda wk: shown.append(w.shown))
    with qtbot.waitSignal(w.run_ended, timeout=TIMEOUT):
        w.run_requested.emit(w.run_settings())
    assert w.wait_run(TIMEOUT)
    assert shown == ["chain", "ring"]
    assert w.shown == w.results.winner


def test_window_stop_several_forms(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.set_forms(list(FORMS))

    class StopOnFrame(QObject):
        def __init__(self, worker):
            super().__init__()
            worker.frame.connect(self.on_frame)

        def on_frame(self, *args):
            w.stop_run()

    recs = []
    w.run_started.connect(lambda wk: recs.append(StopOnFrame(wk)))
    with qtbot.waitSignal(w.run_ended, timeout=TIMEOUT) as sig:
        w.run_requested.emit(w.run_settings())
    assert w.wait_run(TIMEOUT)
    assert sig.args == ["cancelled"] and len(recs) == 1
    assert [w.results.cell(f, "status") for f in w.results.order] == ["cancelled"] * 3
    assert w.status_label.text() == "Run stopped." and w.last_result is None
    assert w.canvas.status.startswith("stopped")
    assert w.run_button.isEnabled() and not w.stop_button.isEnabled()
    w.select_form("tree")  # never started
    assert w.canvas.status == "tree: stopped" and not w.history_slider.isEnabled()
    assert w.history_label.text() == "no frames"


def test_window_close_joins_queue(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.set_forms(list(FORMS))
    w.parallel_spin.setValue(3)
    first = w.start_run(w.run_settings())
    q = w.queue
    assert first is q.runs[0].worker and len(q.active()) == 3
    assert w.start_run(w.run_settings()) is None  # one run at a time
    threads = [r.thread for r in q.active()]
    w.close()
    assert not w.running() and not q.active()
    assert all(t.isFinished() for t in threads)
    assert {r.status for r in q.runs} <= {"cancelled", "finished"}


def test_results_table_unit(qapp):
    t = ResultsTable()
    assert t.columnCount() == len(COLUMNS) and t.rowCount() == 0
    assert t.selected_form() is None


def test_screenshot(done_win, tmp_path):
    done_win.select_form(done_win.results.winner)
    assert screenshot(done_win, tmp_path / "forms.png").stat().st_size > 0
