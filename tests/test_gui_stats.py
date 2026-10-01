"""loop0003 item 04: the statistics panel, offscreen (pytest-qt).

:mod:`formdiscovery.gui.stats` on worker runs of chain and tree x demo_chain_feat: the
score parts (``graph_prior`` + ``graph_like``) add up to the final ll, the numbers and the
panel text match ``masterrun``'s :class:`MasterResults` for the same pairs, the exported
results load back with ``load_results`` as ``formdiscovery run``'s do, and the figure
exports as PNG/SVG. The window fills the panel when a run finishes.
"""

import json

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QFileDialog  # noqa: E402

from formdiscovery.gui import stats as gstats  # noqa: E402
from formdiscovery.gui.app import screenshot  # noqa: E402
from formdiscovery.gui.canvas import GraphCanvas  # noqa: E402
from formdiscovery.gui.main_window import MainWindow  # noqa: E402
from formdiscovery.gui.stats import (  # noqa: E402
    StatsPanel, clusters, export_figure, export_results, history_stages, run_stats,
    score_parts, stats_text,
)
from formdiscovery.gui.worker import RunWorker  # noqa: E402
from formdiscovery.io import DATA_DIR  # noqa: E402
from formdiscovery.run import load_results, masterrun, masterrun_ps, save_results  # noqa: E402

DEMO = DATA_DIR / "demo_chain_feat.mat"
TIMEOUT = 60000
FORMS = {"chain": 1, "tree": 5}  # form -> sind


@pytest.fixture(scope="module")
def master():
    """masterrun's results for chain and tree x demo_chain_feat (seed 1, repeat 1)."""
    return masterrun(masterrun_ps(), thisstruct=list(FORMS.values()), thisdata=[0])


@pytest.fixture(scope="module")
def results(qapp):
    """Worker ``finished`` results (run synchronously in this thread) by form."""
    out = {}
    for form in FORMS:
        w = RunWorker(DEMO, form)
        got = []
        w.finished.connect(got.append)
        w.run()
        assert len(got) == 1
        out[form] = got[0]
    return out


@pytest.mark.parametrize("form", list(FORMS))
def test_parts_add_up(results, master, form):
    r = results[form]
    assert r["ll"] == float(master.modellike[FORMS[form], 0, 0])
    assert r["prior"] + r["likelihood"] == pytest.approx(r["ll"], abs=1e-8)
    assert r["prior"] < 0 and r["likelihood"] > r["ll"]
    assert score_parts(DEMO, form, r["graph"], r["speed"]) == (r["prior"], r["likelihood"])


@pytest.mark.parametrize("form", list(FORMS))
def test_stats_match_master(results, master, form):
    s = FORMS[form]
    st = run_stats(results[form])
    run = next(x for x in master.runs if x["sind"] == s)
    assert st["ll"] == run["ll"]
    assert (st["nclusters"], st["nnodes"], st["nobjects"]) == \
        (run["nclusters"], run["nnodes"], run["nobjects"])
    z = np.asarray(master.structure[s, 0, 0].z).ravel()
    names = master.names[0, 0]
    assert st["clusters"] == [(int(c), [names[k] for k in np.flatnonzero(z == c)])
                              for c in sorted(set(z.tolist()))]
    hist = master.llhistory[s, 0, 0]
    want = [np.asarray(hist[i, j], dtype=float).ravel()
            for j in range(hist.shape[1] - 1, -1, -1) for i in range(hist.shape[0])
            if hist[i, j] is not None]
    assert len(st["history"]) == len(want)
    for (_, got), w in zip(st["history"], want):
        np.testing.assert_array_equal(got, w)
    assert st["frames"] == results[form]["frames"] and st["wall"] > 0
    assert (st["form"], st["data"], st["seed"], st["speed"]) == \
        (form, "demo_chain_feat", 1, results[form]["speed"])


def test_stats_text(results, master):
    st = run_stats(results["chain"])
    text = stats_text(st)
    ll = float(master.modellike[1, 0, 0])
    assert text.splitlines()[0] == "chain on demo_chain_feat  (seed 1, speed 54)"
    assert f"log score (ll)    {ll:.4f}" in text
    assert f"log prior       {st['prior']:.4f}" in text
    assert f"log likelihood  {st['likelihood']:.4f}" in text
    assert "prior + likelihood - ll" not in text  # they add up
    assert f"clusters {st['nclusters']}," in text
    for c, members in st["clusters"]:
        assert f"cluster {c + 1}" in text and ", ".join(members) in text
    for label, lls in st["history"]:
        assert label in text
    first = st["history"][0][1]
    assert ", ".join(f"{v:.2f}" for v in first) in text
    assert f"frames {st['frames']}" in text and "wall time" in text


def test_run_stats_computes_missing_parts(results):
    r = {k: v for k, v in results["tree"].items() if k not in ("prior", "likelihood")}
    st = run_stats(r)
    assert (st["prior"], st["likelihood"]) == \
        (results["tree"]["prior"], results["tree"]["likelihood"])


def test_clusters_unassigned_and_padding():
    class G:
        z = np.array([1, 0, -1, 1])
    assert clusters(G, ["a", "b", "c", "d", "", ""]) == \
        [(0, ["b"]), (1, ["a", "d"]), (-1, ["c"])]
    assert clusters(G, ["a"]) == [(0, ["2"]), (1, ["a", "4"]), (-1, ["3"])]


def test_history_stages_order():
    cell = np.empty((2, 5), dtype=object)
    cell[0, 4], cell[1, 4], cell[0, 3] = [1.0, 2.0], [], [3.0]
    got = history_stages(cell)
    assert [lab for lab, _ in got] == ["speed 5, stage 1", "speed 5, stage 2",
                                       "speed 4, stage 1"]
    assert got[1][1].size == 0
    assert history_stages(None) == []


@pytest.mark.parametrize("suffix", ["", ".npz", ".json"])
def test_export_results_load_back(results, master, tmp_path, suffix):
    r = results["tree"]
    npz, js = export_results(r, tmp_path / f"out{suffix}")
    assert npz == tmp_path / "out.npz" and js == tmp_path / "out.json"
    got = load_results(tmp_path / "out")
    s = FORMS["tree"]
    assert got.modellike[s, 0, 0] == r["ll"] == master.modellike[s, 0, 0]
    g = got.structure[s, 0, 0]
    np.testing.assert_array_equal(g["z"], r["graph"].z)
    np.testing.assert_array_equal(g["adj"], r["graph"].adj)
    np.testing.assert_array_equal(g["W"], r["graph"].W)
    assert list(got.names[0, 0]) == r["names"]
    h, want = got.llhistory[s, 0, 0], master.llhistory[s, 0, 0]
    assert h.shape == want.shape
    for idx in np.ndindex(h.shape):
        assert (h[idx] is None) == (want[idx] is None)
        if h[idx] is not None:
            np.testing.assert_array_equal(h[idx], want[idx])
    # the same file layout as `formdiscovery run` (masterrun + save_results)
    mine = masterrun(masterrun_ps(), thisstruct=[s], thisdata=[0])
    save_results(mine, tmp_path / "cli", masterrun_ps())
    a, b = json.loads(js.read_text()), json.loads((tmp_path / "cli.json").read_text())
    assert a.keys() == b.keys()
    ra, rb = a["runs"][0], b["runs"][0]
    assert ra.keys() == rb.keys()
    assert {k: v for k, v in ra.items() if k not in ("seconds", "ps")} == \
        {k: v for k, v in rb.items() if k not in ("seconds", "ps")}
    with np.load(npz) as x, np.load(tmp_path / "cli.npz") as y:
        assert set(x.files) == set(y.files)


def test_export_user_file(qapp, tmp_path):
    import shutil
    user = tmp_path / "mydata.mat"
    shutil.copy(DEMO, user)
    w = RunWorker(user, "chain")
    got = []
    w.finished.connect(got.append)
    w.run()
    r = got[0]
    assert r["prior"] + r["likelihood"] == pytest.approx(r["ll"], abs=1e-8)
    export_results(r, tmp_path / "res")
    back = load_results(tmp_path / "res")
    assert back.runs[0]["data"] == "mydata" and back.modellike[1, r["dind"], 0] == r["ll"]


def test_export_figure(qtbot, tmp_path, results):
    c = GraphCanvas()
    qtbot.addWidget(c)
    r = results["chain"]
    c.draw_frame("inferredgraph", r["graph"].adj, r["names"], "t", 1)
    png = export_figure(c.figure, tmp_path / "g.png")
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    svg = export_figure(c.figure, tmp_path / "g.svg")
    assert b"<svg" in svg.read_bytes()[:500]
    assert export_figure(c.figure, tmp_path / "plain") == tmp_path / "plain.png"
    with pytest.raises(ValueError, match="png or .svg"):
        export_figure(c.figure, tmp_path / "g.pdf")


@pytest.fixture
def panel(qtbot):
    c = GraphCanvas()
    p = StatsPanel(figure_source=c)
    qtbot.addWidget(c)
    qtbot.addWidget(p)
    return p


def _lines(p):
    return p.chart.figure.axes[0].get_lines()


def test_panel_show_result(panel, results):
    assert not panel.results_button.isEnabled() and not panel.figure_button.isEnabled()
    st = panel.show_result(results["chain"])
    assert panel.text.toPlainText() == stats_text(st)
    nonempty = sum(1 for _, lls in st["history"] if lls.size)
    lines = _lines(panel)
    assert len(lines) == nonempty + 1  # + the final ll
    assert lines[-1].get_ydata()[0] == st["ll"]
    assert panel.results_button.isEnabled() and panel.figure_button.isEnabled()
    panel.clear()
    assert panel.stats is None and not panel.results_button.isEnabled()


def test_panel_live_depths(panel):
    panel.begin_run()
    for lls in ([-3.0], [-3.0, -2.0], [-1.5], [-1.5, -1.0, -0.5]):
        panel.push_depth(np.array(lls))
    assert [lab for lab, _ in panel.live] == ["stage 1", "stage 2"]
    np.testing.assert_array_equal(panel.live[1][1], [-1.5, -1.0, -0.5])
    assert len(_lines(panel)) == 2


def test_panel_dialogs(panel, results, tmp_path, monkeypatch):
    assert panel.export_results_dialog() is None  # nothing to export yet
    panel.show_result(results["chain"])
    panel.export_dir = tmp_path
    asked = []

    def fake(parent, caption, start, flt):
        asked.append((caption, start, flt))
        return answers.pop(0)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake))
    answers = [(str(tmp_path / "r.npz"), gstats.RESULTS_FILTER),
               (str(tmp_path / "fig"), "SVG image (*.svg)"), ("", "")]
    exported = []
    panel.exported.connect(lambda kind, p: exported.append(kind))
    npz, js = panel.export_results_dialog()
    assert npz.exists() and js.exists()
    assert asked[0][1] == str(tmp_path / "results_chain_demo_chain_feat.npz")
    assert panel.export_figure_dialog() == tmp_path / "fig.svg"
    assert (tmp_path / "fig.svg").exists() and asked[1][2] == gstats.FIGURE_FILTER
    assert panel.export_figure_dialog() is None  # cancelled
    assert exported == ["results", "figure"]


def test_window_fills_stats(qtbot, master, tmp_path):
    win = MainWindow(path=DEMO)
    qtbot.addWidget(win)
    win.set_forms(["chain"])
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        win.run_requested.emit(win.run_settings())
        assert win.stats.text.toPlainText().startswith("Running chain")
    assert sig.args == ["finished"]
    assert win.wait_run(TIMEOUT)
    qtbot.waitUntil(lambda: win.stats.stats is not None, timeout=TIMEOUT)
    st = win.stats.stats
    assert st["ll"] == float(master.modellike[1, 0, 0])
    assert f"{st['ll']:.4f}" in win.stats.text.toPlainText()
    assert win.stats.export_figure(tmp_path / "w.png").exists()
    assert screenshot(win, tmp_path / "stats.png").stat().st_size > 0
