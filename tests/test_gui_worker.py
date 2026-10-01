"""loop0003 item 02: the worker thread and the cancel hook, offscreen (pytest-qt).

:class:`formdiscovery.gui.worker.RunWorker` runs ``demo_chain_feat x chain`` on its own
``QThread``; its frames, per-depth scores and result reach the GUI thread through signals,
and the result is masterrun's for that pair. :func:`formdiscovery.search.run_hooks`
cancels a run at the next ``show_graph`` call or ``structurefit`` depth; without it
nothing changes. The window's Run/Stop buttons drive the worker.
"""

import shutil
import threading

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject, QThread, Signal  # noqa: E402

from formdiscovery import search  # noqa: E402
from formdiscovery.gui.main_window import MainWindow  # noqa: E402
from formdiscovery.gui.worker import EVENTS, RunWorker, run_ps, start_worker  # noqa: E402
from formdiscovery.io import DATA_DIR  # noqa: E402
from formdiscovery.run import masterrun, masterrun_ps  # noqa: E402

DEMO = DATA_DIR / "demo_chain_feat.mat"
TIMEOUT = 60000  # ms; the demo run takes about 1-2 s


@pytest.fixture(scope="module")
def master_ll():
    """masterrun's score for chain x demo_chain_feat (seed 1, repeat 1)."""
    res = masterrun(masterrun_ps(), thisstruct=[1], thisdata=[0])
    return float(res.modellike[1, 0, 0])


class Recorder(QObject):
    """Collects a worker's signals in the GUI thread (a QObject living there, so the
    connections are queued), noting the thread each slot ran in. ``ended`` relays the
    outcome from the GUI thread, for ``qtbot.waitSignal``. ``on_first_frame`` (optional)
    is called, in the GUI thread, with the first frame."""

    ended = Signal(str)

    def __init__(self, worker, on_first_frame=None):
        super().__init__()
        self.frames, self.depths, self.results, self.errors = [], [], [], []
        self.cancelled = 0
        self.slot_threads = set()
        self.on_first_frame = on_first_frame
        worker.frame.connect(self.on_frame)
        worker.depth_done.connect(self.on_depth)
        worker.finished.connect(self.on_finished)
        worker.failed.connect(self.on_failed)
        worker.cancelled.connect(self.on_cancelled)

    def on_frame(self, *args):
        self.slot_threads.add(threading.get_ident())
        self.frames.append(args)
        if len(self.frames) == 1 and self.on_first_frame is not None:
            self.on_first_frame(args)

    def on_depth(self, lls):
        self.slot_threads.add(threading.get_ident())
        self.depths.append(lls)

    def on_finished(self, res):
        self.results.append(res)
        self.ended.emit("finished")

    def on_failed(self, tb):
        self.errors.append(tb)
        self.ended.emit("failed")

    def on_cancelled(self):
        self.cancelled += 1
        self.ended.emit("cancelled")


def run_worker(qtbot, worker, outcome="finished", on_first_frame=None):
    rec = Recorder(worker, on_first_frame)
    thread = start_worker(worker, start=False)
    try:
        with qtbot.waitSignal(rec.ended, timeout=TIMEOUT) as sig:
            thread.start()
    finally:  # never leave the run going into later tests (ANOMALIES.md A24)
        if not thread.wait(0):
            worker.cancel()
            thread.wait(TIMEOUT)
    assert sig.args == [outcome]
    assert thread.wait(TIMEOUT)
    qtbot.wait(10)  # deliver anything still queued
    return rec, thread


def test_run_ps_shipped_and_user_file(tmp_path):
    ps, sind, dind = run_ps(DEMO, "chain")
    assert (ps.structures[sind], ps.data[dind], dind) == ("chain", "demo_chain_feat", 0)
    assert ps.speed == 54 and ps.reloutsideinit == "overd"
    user = tmp_path / "mydata.mat"
    shutil.copy(DEMO, user)
    ps2, sind2, dind2 = run_ps(user, "ring", speed=5)
    n = len(masterrun_ps().data)
    assert (sind2, dind2, ps2.speed) == (3, n, 5)
    assert ps2.data[-1] == "mydata" and ps2.dlocs[-1] == str(tmp_path / "mydata")
    assert len(ps2.simdim) == n + 1
    with pytest.raises(ValueError):
        run_ps(DEMO, "nosuchform")


def test_worker_run_matches_masterrun(qtbot, master_ll):
    worker = RunWorker(DEMO, "chain", seed=1)
    rec, thread = run_worker(qtbot, worker)
    assert not rec.errors and rec.cancelled == 0 and len(rec.results) == 1
    res = rec.results[0]
    assert res["ll"] == master_ll  # the hooks and the signals change nothing
    assert (res["form"], res["sind"], res["dind"], res["seed"]) == ("chain", 1, 0, 1)
    assert res["frames"] == len(rec.frames) and res["wall"] > 0
    assert thread.isFinished()
    # slots ran in the GUI (test) thread, not the worker's
    assert rec.slot_threads == {threading.get_ident()}

    events = [f[0] for f in rec.frames]
    assert set(events) <= set(EVENTS) and "bestsplit" not in events
    assert events[-1] == "inferredgraph" and events.count("inferredgraph") == 1
    ndepths = sum(len(lls) for lls in res["bestglls"].ravel() if lls is not None
                  and np.size(lls))
    assert events.count("postclean") == ndepths >= 1
    assert len(rec.frames) >= ndepths
    for event, adj, names, title, depth in rec.frames:
        assert isinstance(adj, np.ndarray) and adj.ndim == 2 and adj.shape[0] == len(names)
        assert all(isinstance(n, str) for n in names)
        assert isinstance(title, str) and depth >= 1
    assert rec.frames[-1][3].startswith("chain: estimated structure:")
    np.testing.assert_array_equal(rec.frames[-1][1], res["graph"].adj)

    # depth_done: one per postclean, each stage's history grows by one score
    assert len(rec.depths) == ndepths
    for prev, cur in zip(rec.depths, rec.depths[1:]):
        assert len(cur) == len(prev) + 1 or len(cur) == 1
        if len(cur) > 1:
            np.testing.assert_array_equal(cur[:-1], prev)
            assert cur[-1] > cur[-2]
    post = [f for f in rec.frames if f[0] == "postclean"]
    assert [f[4] for f in post] == [len(lls) for lls in rec.depths]


def test_worker_bestsplit_frames(qtbot):
    worker = RunWorker(DEMO, "chain", speed=5, bestsplit=True)
    rec, _ = run_worker(qtbot, worker)
    assert len(rec.results) == 1
    events = [f[0] for f in rec.frames]
    assert events.count("bestsplit") > events.count("preclean") >= 1


def test_cancel_after_first_frame(qtbot):
    worker = RunWorker(DEMO, "chain")
    first = []

    def on_first(frame):
        first.append(frame)
        worker.cancel()
    rec, thread = run_worker(qtbot, worker, "cancelled", on_first)
    assert thread.isFinished() and not thread.isRunning()
    assert rec.cancelled == 1 and not rec.results and not rec.errors
    assert first and first[0][0] == "preclean"
    assert "inferredgraph" not in [f[0] for f in rec.frames]
    assert worker.is_cancelled()


def test_cancel_before_start(qtbot):
    worker = RunWorker(DEMO, "chain")
    worker.cancel()
    rec, thread = run_worker(qtbot, worker, "cancelled")
    assert rec.cancelled == 1 and rec.frames == [] and not rec.results


def test_failure_reports_traceback(qtbot, tmp_path):
    bad = tmp_path / "bad.mat"
    bad.write_bytes(b"not a mat file")
    worker = RunWorker(bad, "chain")
    rec, thread = run_worker(qtbot, worker, "failed")
    assert len(rec.errors) == 1 and "Traceback" in rec.errors[0]
    assert not rec.results and rec.cancelled == 0 and thread.isFinished()


def test_run_hooks_unit():
    got = []
    show = lambda *a: got.append(a)  # noqa: E731
    adj = np.zeros((2, 2))
    search.show_graph(show, 1, "preclean", adj, [], "", "t")  # no hooks: no check
    assert search.current_depth() == 0
    flag = {"stop": False}
    with search.run_hooks(cancel=lambda: flag["stop"]):
        search.show_graph(show, 0, "preclean", adj, [], "", "t")
        flag["stop"] = True
        with pytest.raises(search.RunCancelled):
            search.show_graph(show, 0, "preclean", adj, [], "", "t")  # flag off: checked
        with search.run_hooks():  # nested: no cancel inside
            search.show_graph(show, 1, "preclean", adj, [], "", "t")
        with pytest.raises(search.RunCancelled):
            search.check_cancel()
    search.check_cancel()  # restored
    assert len(got) == 2
    assert not issubclass(search.RunCancelled, search.FormDiscoveryError)


def test_run_hooks_are_per_thread():
    """A cancel hook in one thread does not reach another (item 05 runs several)."""
    errors = []
    with search.run_hooks(cancel=lambda: True):
        t = threading.Thread(target=lambda: errors.append(_try_check()))
        t.start()
        t.join()
    assert errors == [None]


def _try_check():
    try:
        search.check_cancel()
    except search.RunCancelled as e:
        return e
    return None


def test_structurefit_hooks_cancel_and_depths():
    """The per-depth check stops ``structurefit`` with no ``show`` at all, and
    ``on_depth`` sees the same history ``callback`` does."""
    from formdiscovery.preprocess import scaledata
    from formdiscovery.io import load_dataset
    from formdiscovery.params import setrunps, structcounts

    ps = masterrun_ps()
    ps.runps.structname = "chain"
    ps.speed, ps.init = 5, "none"
    data = load_dataset("demo_chain_feat")
    nobj, ps = setrunps(data, 0, ps)
    data, ps = scaledata(data, ps)
    ps.overrideSS, ps.cleanstrong = 0, 0
    ps = structcounts(nobj, ps)
    seen, cb = [], []
    with search.run_hooks(on_depth=lambda lls, g: seen.append(lls)):
        ll, _, lls, _ = search.structurefit(data, ps, rng=1,
                                            callback=lambda l, g: cb.append(l))
    ll0, _, lls0, _ = search.structurefit(data, ps, rng=1)
    assert ll == ll0 and np.array_equal(lls, lls0) and len(seen) == len(lls) >= 1
    for a, b in zip(seen, cb):
        np.testing.assert_array_equal(a, b)
    calls = []

    def cancel():
        calls.append(search.current_depth())
        return search.current_depth() >= 2
    with search.run_hooks(cancel=cancel), pytest.raises(search.RunCancelled):
        search.structurefit(data, ps, rng=1)
    assert calls[-1] == 2


# --- the window ----------------------------------------------------------------------
@pytest.fixture
def win(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    yield w
    w.close()


def test_window_run_to_completion(win, qtbot, master_ll):
    win.set_forms(["chain"])
    started = []
    win.run_started.connect(started.append)
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        qtbot.mouseClick(win.run_button, _left())
        assert win.running() and win.stop_button.isEnabled()
        assert not win.run_button.isEnabled()
    assert sig.args == ["finished"]
    assert len(started) == 1 and isinstance(started[0], RunWorker)
    assert win.wait_run(TIMEOUT)
    assert not win.running() and win.run_button.isEnabled()
    assert not win.stop_button.isEnabled()
    assert win.last_result["ll"] == master_ll
    assert win.status_label.text().startswith("chain: ll = ")


def test_window_stop(win, qtbot):
    win.set_forms(["ring"])
    recs = []
    win.run_started.connect(lambda w: recs.append(Recorder(w, lambda f: win.stop_run())))
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        win.run_requested.emit(win.run_settings())
    assert len(recs) == 1 and recs[0].frames
    assert sig.args == ["cancelled"]
    assert win.wait_run(TIMEOUT)
    assert win.status_label.text() == "Run stopped."
    assert win.run_button.isEnabled() and not win.stop_button.isEnabled()
    assert win.last_result is None


def test_window_close_joins_running_thread(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.set_forms(["tree"])
    worker = w.start_run(w.run_settings())
    thread = w.thread
    assert isinstance(thread, QThread) and w.start_run(w.run_settings()) is None
    w.close()
    assert worker.is_cancelled() and thread.isFinished() and not w.running()


def _left():
    from PySide6.QtCore import Qt
    return Qt.LeftButton
