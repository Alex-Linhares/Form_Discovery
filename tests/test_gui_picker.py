"""loop0003 item 01: the GUI skeleton and data picker, offscreen (pytest-qt).

The window opens each shipped demo file through :meth:`MainWindow.load_file` (no dialog),
the info panel shows what :func:`formdiscovery.io.load_dataset` and ``setrunps`` say about
it, the form list holds ``ps.structures`` with chain/ring/tree preselected, Run emits the
settings and Stop stays disabled; ``formdiscovery gui FILE`` reaches :func:`gui.app.main`.
"""

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from formdiscovery import cli  # noqa: E402
from formdiscovery.gui import app as gui_app  # noqa: E402
from formdiscovery.gui.dataset import NAMES_SHOWN, dataset_info  # noqa: E402
from formdiscovery.gui.main_window import (  # noqa: E402
    DEFAULT_SPEED, SPEEDS, MainWindow,
)
from formdiscovery.io import DATA_DIR, load_dataset  # noqa: E402
from formdiscovery.params import STRUCTURES  # noqa: E402

# the shipped demo files: (stem, type, objects, features or (reltype, relations))
DEMOS = [
    ("demo_chain_feat", "feat", 8, 1000),
    ("demo_ring_feat", "feat", 8, 1000),
    ("demo_tree_feat", "feat", 8, 1000),
    ("demo_ring_rel_bin", "rel", 8, ("relbin", 1)),
    ("demo_hierarchy_rel_bin", "rel", 28, ("relbin", 1)),
    ("demo_order_rel_freq", "rel", 8, ("relfreq", 1)),
]


@pytest.fixture
def win(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


@pytest.mark.parametrize("stem,kind,nobj,extra", DEMOS)
def test_open_demo_file(win, qtbot, stem, kind, nobj, extra):
    path = DATA_DIR / f"{stem}.mat"
    with qtbot.waitSignal(win.dataset_changed, timeout=5000) as sig:
        info = win.load_file(path)
    assert sig.args[0] is info
    assert (info.kind, info.nobjects) == (kind, nobj)
    text = win.info_label.text()
    assert f"Type: {kind}" in text and f"Objects: {nobj}" in text
    if kind == "feat":
        assert info.nfeatures == extra and f"Features: {extra}" in text
        np.testing.assert_array_equal(info.data, load_dataset(stem))
    else:
        assert (info.reltype, info.nrelations) == extra
        assert f"Relation type: {extra[0]}, relations: {extra[1]}" in text
        assert "speed 5" in text
    assert "Names: none" in text  # the demo files carry no names
    assert win.path_label.text() == str(path)
    assert stem in win.windowTitle()
    assert win.run_button.isEnabled() and not win.stop_button.isEnabled()


def test_similarity_and_names():
    info = dataset_info(DATA_DIR / "colors.mat")
    assert (info.kind, info.nobjects) == ("sim", 14)
    assert "Similarity matrix: 14 × 14" in info.summary()
    names = load_dataset("colors", with_names=True)[1]
    assert info.names == names
    line = [s for s in info.summary_lines() if s.startswith("Names:")][0]
    assert line == ("Names: " + ", ".join(names[:NAMES_SHOWN])
                    + f" (+{len(names) - NAMES_SHOWN} more)")
    animals = dataset_info(DATA_DIR / "animals.mat")
    assert (animals.kind, animals.nobjects, animals.nfeatures) == ("feat", 33, 102)
    assert "Elephant" in animals.summary()


def test_initial_state(win):
    assert win.info is None
    assert not win.run_button.isEnabled() and not win.stop_button.isEnabled()
    assert [win.form_list.item(i).text() for i in range(win.form_list.count())] \
        == list(STRUCTURES)
    assert len(STRUCTURES) == 24
    assert win.selected_forms() == ["chain", "ring", "tree"]
    assert win.seed_spin.value() == 1 and win.speed_spin.value() == DEFAULT_SPEED


def test_form_selection(win, qtbot):
    win.load_file(DATA_DIR / "demo_chain_feat.mat")
    win.set_forms(["tree", "partition", "grid"])
    assert win.selected_forms() == ["partition", "tree", "grid"]  # ps.structures order
    # clicking toggles (MultiSelection)
    item = win.form_list.item(STRUCTURES.index("ring"))
    qtbot.mouseClick(win.form_list.viewport(), qtbot_left(),
                     pos=win.form_list.visualItemRect(item).center())
    assert "ring" in win.selected_forms()
    qtbot.mouseClick(win.form_list.viewport(), qtbot_left(),
                     pos=win.form_list.visualItemRect(item).center())
    assert "ring" not in win.selected_forms()
    win.set_forms([])
    assert not win.run_button.isEnabled()  # no form, no run
    win.set_forms(["chain"])
    assert win.run_button.isEnabled()
    with pytest.raises(ValueError):
        win.set_forms(["nosuchform"])


def qtbot_left():
    from PySide6.QtCore import Qt
    return Qt.LeftButton


def test_run_emits_settings(win, qtbot):
    win.load_file(DATA_DIR / "demo_chain_feat.mat")
    win.seed_spin.setValue(7)
    win.speed_spin.setValue(5)
    with qtbot.waitSignal(win.run_requested, timeout=5000) as sig:
        qtbot.mouseClick(win.run_button, qtbot_left())
    s = sig.args[0]
    assert s["path"] == DATA_DIR / "demo_chain_feat.mat"
    assert s["forms"] == ["chain", "ring", "tree"]
    assert (s["seed"], s["speed"]) == (7, 5)
    assert s["info"].kind == "feat"
    win.stop_run()  # Run also started chain in a worker (item 02)
    assert win.wait_run(60000) and not win.running()


def test_speed_codes(win):
    sp = win.speed_spin
    sp.setValue(3)
    for want in (4, 5, 54, 54):
        sp.stepBy(1)
        assert sp.value() == want
    sp.stepBy(-2)
    assert sp.value() == 4
    assert set(SPEEDS) == {3, 4, 5, 54}
    from PySide6.QtGui import QValidator
    assert sp.validate("23", 2)[0] != QValidator.Acceptable
    assert sp.validate("54", 2)[0] == QValidator.Acceptable


def test_bad_file(win, tmp_path):
    win.load_file(DATA_DIR / "demo_chain_feat.mat")
    bad = tmp_path / "bad.mat"
    bad.write_bytes(b"not a mat file")
    assert win.load_file(bad) is None
    assert win.info is None and "Could not load bad.mat" in win.info_label.text()
    assert not win.run_button.isEnabled()
    assert win.load_file(tmp_path / "missing.mat") is None
    from scipy.io import savemat
    savemat(tmp_path / "nodata.mat", {"x": np.ones(3)})
    assert win.load_file(tmp_path / "nodata.mat") is None
    assert "KeyError" in win.info_label.text()


def test_user_file_elsewhere(win, tmp_path):
    """A user's own file outside the data directory (features with names)."""
    from scipy.io import savemat
    names = np.empty((1, 3), dtype=object)
    names[0, :] = ["a", "b", "c"]
    savemat(tmp_path / "mine.mat", {"data": np.arange(12.0).reshape(3, 4), "names": names})
    info = win.load_file(tmp_path / "mine.mat")
    assert (info.kind, info.nobjects, info.nfeatures, info.names) == ("feat", 3, 4,
                                                                     ["a", "b", "c"])
    assert win.data_dir == tmp_path
    assert "Names: a, b, c" in win.info_label.text()


def test_open_dialog(win, monkeypatch):
    seen = {}

    def fake(parent, caption, directory, filt):
        seen.update(directory=directory, filt=filt)
        return str(DATA_DIR / "demo_ring_feat.mat"), filt

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(fake))
    assert win.open_dialog() == str(DATA_DIR / "demo_ring_feat.mat")
    assert seen["directory"] == str(DATA_DIR) and "*.mat" in seen["filt"]
    assert win.info.stem == "demo_ring_feat"
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a: ("", "")))
    assert win.open_dialog() is None and win.info.stem == "demo_ring_feat"


def test_screenshot(win, tmp_path):
    win.load_file(DATA_DIR / "demo_chain_feat.mat")
    out = gui_app.screenshot(win, tmp_path / "picker.png")
    from PySide6.QtGui import QImage
    img = QImage(str(out))
    assert not img.isNull() and img.width() > 100 and img.height() > 100


def test_cli_gui_reaches_app_main(monkeypatch):
    got = {}
    monkeypatch.setattr(gui_app, "main", lambda argv=None, args=None: got.setdefault(
        "args", args) and 0)
    assert cli.main(["gui", str(DATA_DIR / "demo_chain_feat.mat")]) == 0
    assert got["args"].file == str(DATA_DIR / "demo_chain_feat.mat")


def test_app_main_runs_event_loop(qapp, qtbot):
    """``main`` builds the window with FILE loaded and runs the loop (quit at once)."""
    from PySide6.QtCore import QTimer

    seen = {}

    def grab_and_quit():
        wins = [w for w in QApplication.topLevelWidgets() if isinstance(w, MainWindow)
                and w.isVisible()]
        seen["stems"] = [w.info.stem for w in wins if w.info is not None]
        for w in wins:
            w.close()
        qapp.exit(0)  # not quit(): ANOMALIES.md A24

    QTimer.singleShot(0, grab_and_quit)
    assert gui_app.main([str(DATA_DIR / "demo_tree_feat.mat")]) == 0
    assert "demo_tree_feat" in seen["stems"]
    qtbot.wait(1)  # and any posted event is consumed inside a loop (A24)
