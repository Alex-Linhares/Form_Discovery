"""loop0003 item 03: the live graph canvas, offscreen (pytest-qt).

:class:`formdiscovery.gui.canvas.GraphCanvas` is fed the frames of a recorded
``demo_chain_feat x chain`` worker run (best splits included): it draws them with
``draw_dot`` (pygraphviz or networkx), coalesces bursts (latest wins) but always draws the
``inferredgraph``, writes a status line, and lays each frame out from the previous one's
positions. The window wires Run -> worker -> canvas, and Stop.
"""

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject  # noqa: E402

from formdiscovery.gui.canvas import CANVAS_BACKENDS, GraphCanvas, frame_score  # noqa: E402
from formdiscovery.gui.main_window import MainWindow  # noqa: E402
from formdiscovery.gui.worker import RunWorker  # noqa: E402
from formdiscovery.io import DATA_DIR  # noqa: E402
from formdiscovery.viz.draw import dot_positions  # noqa: E402
from formdiscovery.viz.pygraphviz_backend import layout_text  # noqa: E402

DEMO = DATA_DIR / "demo_chain_feat.mat"
TIMEOUT = 60000


class _Collect(QObject):
    def __init__(self, worker):
        super().__init__()
        self.frames, self.results = [], []
        worker.frame.connect(self.on_frame)
        worker.finished.connect(self.results.append)

    def on_frame(self, *args):
        self.frames.append(args)


@pytest.fixture(scope="module")
def recorded(qapp):
    """The frames (``event, adj, names, title, depth``) and result of a worker run of
    chain on demo_chain_feat with best splits (run synchronously: same thread, direct
    connections)."""
    w = RunWorker(DEMO, "chain", bestsplit=True)
    rec = _Collect(w)
    w.run()
    assert len(rec.results) == 1
    return rec.frames, rec.results[0]


@pytest.fixture
def canvas(qtbot):
    c = GraphCanvas()
    qtbot.addWidget(c)
    return c


def _title(c):
    return c.figure.axes[0].get_title()


def test_recorded_frames(recorded):
    frames, res = recorded
    events = [f[0] for f in frames]
    assert events[-1] == "inferredgraph" and events.count("inferredgraph") == 1
    assert {"bestsplit", "preclean", "postclean"} <= set(events)
    assert len(frames) == res["frames"]
    assert np.array_equal(frames[-1][1], res["graph"].adj)


def test_frame_score():
    assert frame_score("post-clean: chain  -8538.11") == -8538.11
    assert frame_score("chain: estimated structure:  -8247.19") == -8247.19
    assert frame_score("-Inf") == -np.inf
    assert frame_score("") is None and frame_score("no score") is None


def test_draw_one_frame(canvas, recorded):
    frames, _ = recorded
    ev, adj, names, title, depth = next(f for f in frames if f[0] == "postclean")
    drawn = []
    canvas.frame_drawn.connect(lambda e, t: drawn.append((e, t)))
    canvas.draw_frame(ev, adj, names, title, depth, elapsed=0.5, number=3)
    assert drawn == [(ev, title)] and canvas.drawn == 1
    assert _title(canvas) == title
    assert canvas.status == f"postclean · depth {depth} · score {title.split()[-1]} · 0.5 s · frame 3"
    assert canvas.figure.texts[-1].get_text() == canvas.status
    assert canvas.positions.shape == (2, adj.shape[0])
    # the first frame of a run is draw_dot's own layout
    _, lay, _ = layout_text(adj)
    _, _, x, y, _ = dot_positions(lay, adj.shape[0])
    np.testing.assert_allclose(canvas.positions, np.vstack([x, y]))


def test_burst_is_coalesced_and_inferredgraph_drawn(canvas, recorded):
    frames, _ = recorded
    canvas.begin_run()
    for f in frames:  # no event processing in between: one burst
        canvas.push_frame(*f)
    assert canvas.received == len(frames)
    assert canvas.drawn == 1 and canvas.dropped == len(frames) - 1
    assert canvas.last_event == "inferredgraph" and _title(canvas) == frames[-1][3]
    assert canvas.pending is None
    assert canvas.status.startswith("inferredgraph · depth ")
    assert canvas.status.endswith(f"frame {len(frames)}")


def test_timer_draws_latest(canvas, recorded, qtbot):
    frames, _ = recorded
    pre = [f for f in frames if f[0] == "preclean"][:2]
    canvas.begin_run()
    for f in pre:
        canvas.push_frame(*f)
    assert canvas.drawn == 0  # waits for the timer
    qtbot.waitUntil(lambda: canvas.drawn == 1, timeout=5000)
    assert _title(canvas) == pre[1][3] and canvas.dropped == 1
    qtbot.wait(250)
    assert canvas.drawn == 1  # nothing left to draw


def test_inferredgraph_never_dropped(canvas, recorded):
    frames, _ = recorded
    final = frames[-1]
    pre = next(f for f in frames if f[0] == "preclean")
    drawn = []
    canvas.frame_drawn.connect(lambda e, t: drawn.append(e))
    canvas.push_frame(*pre)
    canvas.push_frame(*final)
    canvas.push_frame(*pre)  # a later frame does not replace the drawn inferred graph
    canvas.flush()
    assert drawn == ["inferredgraph", "preclean"]


def test_frames_with_event_processing(canvas, recorded, qtbot):
    frames, _ = recorded
    canvas.begin_run()
    for f in frames:
        canvas.push_frame(*f)
        qtbot.wait(20)
    assert 1 < canvas.drawn <= len(frames)
    assert canvas.last_title == frames[-1][3] == _title(canvas)


def test_stable_positions(qtbot, recorded):
    """Laying a frame out from the previous one keeps the object nodes closer than a
    fresh draw_dot layout does."""
    frames, _ = recorded
    post = [f for f in frames if f[0] in ("postclean", "inferredgraph")]
    nobj = 8
    stable, fresh = [], []
    c = GraphCanvas(stable=True)
    qtbot.addWidget(c)
    prev_s = prev_f = None
    for ev, adj, names, title, depth in post:
        c.draw_frame(ev, adj, names, title, depth)
        _, lay, _ = layout_text(adj)
        _, _, x, y, _ = dot_positions(lay, adj.shape[0])
        s, f = c.positions[:, :nobj], np.vstack([x, y])[:, :nobj]
        if prev_s is not None:
            stable.append(np.abs(s - prev_s).sum())
            fresh.append(np.abs(f - prev_f).sum())
        prev_s, prev_f = s, f
    assert len(stable) >= 3
    assert sum(stable) < sum(fresh)


def test_unstable_and_networkx(qtbot, recorded):
    frames, _ = recorded
    final = frames[-1]
    for backend in CANVAS_BACKENDS:
        c = GraphCanvas(backend=backend, stable=False)
        qtbot.addWidget(c)
        assert not c.stable_layout()
        c.draw_frame(*final)
        assert c.drawn == 1 and _title(c) == final[3] and c.positions is None
        assert c.figure.axes[0].lines or c.figure.axes[0].patches or \
            c.figure.axes[0].collections
    c = GraphCanvas(backend="networkx")
    qtbot.addWidget(c)
    c.draw_frame(*final)
    assert c.positions.shape == (2, final[1].shape[0])
    with pytest.raises(ValueError):
        GraphCanvas(backend="plotly")
    with pytest.raises(ValueError):
        c.set_backend("pyvis")


def test_undrawable_frame(canvas):
    with pytest.warns(UserWarning, match="node coordinates"):  # dot_to_graph's
        canvas.draw_frame("preclean", np.zeros((3, 3)), ["a", "b", "c"],
                          "pre-clean: x  -1", 1)
    texts = [t.get_text() for t in canvas.figure.axes[0].texts]
    assert any(t.startswith("graph not drawn") for t in texts)
    assert _title(canvas) == "pre-clean: x  -1" and canvas.positions is None


def test_set_status_and_clear(canvas, recorded):
    canvas.draw_frame(*recorded[0][-1])
    canvas.set_status("stopped")
    assert canvas.figure.texts[-1].get_text() == "stopped" == canvas.status
    canvas.clear("hello")
    assert canvas.drawn == canvas.received == 0 and canvas.last_title is None
    assert [t.get_text() for t in canvas.figure.axes[0].texts] == ["hello"]


# --- the window ----------------------------------------------------------------------
@pytest.fixture
def win(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    yield w
    w.close()


def test_window_run_feeds_canvas(win, qtbot, recorded):
    frames, res = recorded
    win.set_forms(["chain"])
    win.backend_combo.setCurrentText("networkx")
    win.bestsplit_check.setChecked(True)
    assert win.canvas.backend == "networkx"
    s = win.run_settings()
    assert (s["backend"], s["bestsplit"]) == ("networkx", True)
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        win.run_requested.emit(s)
    assert sig.args == ["finished"]
    assert win.wait_run(TIMEOUT)
    c = win.canvas
    assert c.received == res["frames"] == win.last_result["frames"]
    assert c.last_event == "inferredgraph" and c.pending is None
    assert c.last_title == _title(c) == frames[-1][3]
    assert win.last_result["ll"] == res["ll"]
    assert 1 <= c.drawn <= c.received


def test_window_stop_keeps_last_frame(win, qtbot):
    win.set_forms(["ring"])

    class StopOnFrame(QObject):
        def __init__(self, w):
            super().__init__()
            w.frame.connect(self.on_frame)

        def on_frame(self, *args):
            win.stop_run()

    recs = []
    win.run_started.connect(lambda w: recs.append(StopOnFrame(w)))
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        win.run_requested.emit(win.run_settings())
    assert sig.args == ["cancelled"]
    assert win.wait_run(TIMEOUT)
    c = win.canvas
    assert c.received >= 1 and c.drawn >= 1 and c.pending is None
    assert c.status.startswith("stopped · last: ")
    assert c.figure.texts[-1].get_text() == c.status
    assert win.run_button.isEnabled() and not win.stop_button.isEnabled()


def test_default_backend_is_networkx(qtbot):
    from formdiscovery.gui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    assert CANVAS_BACKENDS[0] == "networkx"
    assert w.backend_combo.currentText() == "networkx" and w.canvas.backend == "networkx"
    assert GraphCanvas().backend == "networkx"
