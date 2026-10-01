"""loop0003 item 06: polish, offscreen (pytest-qt).

Error boxes (a bad file, a failed run, a failed export) open without blocking; the last
data directory is remembered in ``QSettings`` (a file under ``tmp_path``, conftest's
``gui_settings_file``); the window title names the file and the running forms; the menu
actions carry the keyboard shortcuts and follow the buttons; ``--demo`` opens
``demo_chain_feat`` and runs chain (masterrun's score); the GUI runs with Octave and
oct2py unavailable.
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from formdiscovery import cli  # noqa: E402
from formdiscovery.gui import app as gui_app  # noqa: E402
from formdiscovery.gui import worker as gui_worker  # noqa: E402
from formdiscovery.gui.dialogs import LAST_DIR_KEY, SETTINGS_ENV, gui_settings  # noqa: E402
from formdiscovery.gui.main_window import (  # noqa: E402
    DEMO_FILE, DEMO_FORM, SHORTCUTS, MainWindow,
)
from formdiscovery.io import DATA_DIR  # noqa: E402
from formdiscovery.run import masterrun, masterrun_ps  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DEMO = DATA_DIR / DEMO_FILE
TIMEOUT = 60000


@pytest.fixture
def win(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    yield w
    w.stop_run()
    w.wait_run(TIMEOUT)


@pytest.fixture(scope="module")
def chain_ll():
    """masterrun's chain x demo_chain_feat score (seed 1, repeat 1)."""
    return float(masterrun(masterrun_ps(), thisstruct=[1], thisdata=[0]).modellike[1, 0, 0])


def _close(box):
    assert box.isVisible()
    box.close()


def test_settings_file_is_isolated(tmp_path):
    assert os.environ[SETTINGS_ENV] == str(tmp_path / "gui_settings.ini")
    s = gui_settings()
    assert s.format() == QSettings.IniFormat and s.fileName() == os.environ[SETTINGS_ENV]


def test_bad_file_opens_error_box(win, tmp_path):
    bad = tmp_path / "bad.mat"
    bad.write_bytes(b"not a mat file")
    assert win.load_file(bad) is None
    box = win.error_dialog
    assert isinstance(box, QMessageBox) and box.icon() == QMessageBox.Warning
    assert "Could not load bad.mat" in box.text() and "'data'" in box.text()
    assert not box.isModal() or box.windowModality() == Qt.WindowModal  # open(), no exec()
    _close(box)
    assert win.load_file(tmp_path / "missing.mat") is None
    assert "missing.mat" in win.error_dialog.text()
    _close(win.error_dialog)
    assert win.windowTitle() == "formdiscovery" and not win.run_action.isEnabled()


def test_failed_run_opens_error_box(win, qtbot, monkeypatch):
    def boom(*a, **k):
        raise ValueError("model exploded")

    monkeypatch.setattr(gui_worker, "runmodel", boom)
    win.load_file(DEMO)
    win.set_forms(["chain"])
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        win.run_action.trigger()
    assert sig.args == ["failed"]
    box = win.error_dialog
    assert "chain" in box.text() and "ValueError: model exploded" in box.text()
    assert "Traceback" in box.detailedText()
    _close(box)
    assert win.status_label.text() == "Run failed: ValueError: model exploded"


def test_failed_export_opens_error_box(win, qtbot, monkeypatch, tmp_path):
    win.load_file(DEMO)
    win.set_forms(["chain"])
    assert not win.export_action.isEnabled() and not win.figure_action.isEnabled()
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT):
        win.run_action.trigger()
    assert win.export_action.isEnabled() and win.figure_action.isEnabled()
    (tmp_path / "a_file").write_text("x")  # a parent that is a file: cannot write
    target = tmp_path / "a_file" / "out.npz"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (str(target), "")))
    assert win.stats.export_results_dialog() is None
    box = win.stats.error_dialog
    assert box.windowTitle() == "Export failed" and str(target) in box.text()
    _close(box)
    good = tmp_path / "res.npz"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (str(good), "")))
    npz, js = win.stats.export_results_dialog()
    assert npz.is_file() and js.is_file()


def test_last_directory_remembered(qtbot, tmp_path):
    from scipy.io import savemat

    mine = tmp_path / "mydata"
    mine.mkdir()
    savemat(mine / "mine.mat", {"data": np.arange(12.0).reshape(3, 4)})
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.data_dir == DATA_DIR  # nothing saved yet
    w.load_file(mine / "mine.mat")
    assert gui_settings().value(LAST_DIR_KEY) == str(mine.resolve())
    w2 = MainWindow()
    qtbot.addWidget(w2)
    assert w2.data_dir == mine.resolve()
    seen = {}

    def fake(parent, caption, directory, filt):
        seen["dir"] = directory
        return "", ""

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(QFileDialog, "getOpenFileName", staticmethod(fake))
        w2.open_dialog()
    assert seen["dir"] == str(mine.resolve())
    w3 = MainWindow(data_dir=DATA_DIR)  # an explicit --data-dir wins
    qtbot.addWidget(w3)
    assert w3.data_dir == DATA_DIR
    w.load_file(tmp_path / "bad.mat")  # a failed load does not change it
    _close(w.error_dialog)
    assert gui_settings().value(LAST_DIR_KEY) == str(mine.resolve())
    (mine / "mine.mat").unlink()
    mine.rmdir()
    w4 = MainWindow()  # the saved directory is gone: the shipped data
    qtbot.addWidget(w4)
    assert w4.data_dir == DATA_DIR


def test_window_title(win, qtbot):
    assert win.windowTitle() == "formdiscovery"
    win.load_file(DEMO)
    assert win.windowTitle() == f"formdiscovery — {DEMO_FILE}"
    win.set_forms(["chain", "ring"])
    titles = []
    win.run_started.connect(lambda wk: titles.append(win.windowTitle()))
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT):
        win.run_action.trigger()
    assert titles[0] == f"formdiscovery — {DEMO_FILE} · running chain, ring"
    assert win.windowTitle() == f"formdiscovery — {DEMO_FILE}"


def test_shortcuts_and_actions(win):
    for name, keys in SHORTCUTS.items():
        act = getattr(win, name)
        assert [k.toString() for k in act.shortcuts()] == \
            [QKeySequence(k).toString() for k in keys]
    menus = [a.text() for a in win.menuBar().actions()]
    assert menus == ["&File", "&Run"]
    assert win.open_action.isEnabled() and not win.run_action.isEnabled()
    assert not win.stop_action.isEnabled()
    win.load_file(DEMO)
    assert win.run_action.isEnabled()
    win.set_forms([])
    assert not win.run_action.isEnabled()
    seen = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(QFileDialog, "getOpenFileName",
                   staticmethod(lambda *a: seen.append(a) or ("", "")))
        win.open_action.trigger()
    assert len(seen) == 1


def test_keyboard_run_and_stop(win, qtbot):
    """Ctrl+R starts the run and Esc stops it, through the real key events."""
    win.load_file(DEMO)
    win.set_forms(["chain"])
    win.show()
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow, timeout=5000)  # shortcuts need the active window
    stopped = []

    def stop_on_first_frame(wk):
        QTimer.singleShot(0, lambda: (qtbot.keyClick(win, Qt.Key_Escape),
                                      stopped.append(True)))

    win.run_started.connect(stop_on_first_frame)
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        qtbot.keyClick(win, Qt.Key_R, Qt.ControlModifier)
        assert win.running()
    assert stopped and sig.args == ["cancelled"]
    assert not win.stop_action.isEnabled() and win.run_action.isEnabled()


def test_quit_action_closes(qtbot):
    w = MainWindow(path=DEMO)
    qtbot.addWidget(w)
    w.show()
    w.quit_action.trigger()
    assert not w.isVisible()


def test_start_demo(win, qtbot, chain_ll):
    with qtbot.waitSignal(win.run_ended, timeout=TIMEOUT) as sig:
        assert win.start_demo() is not None
    assert sig.args == ["finished"]
    assert win.info.stem == "demo_chain_feat" and win.selected_forms() == [DEMO_FORM]
    assert win.last_result["form"] == "chain" and win.last_result["ll"] == chain_ll
    assert win.windowTitle() == f"formdiscovery — {DEMO_FILE}"


def test_start_demo_missing_file(win, tmp_path):
    assert win.start_demo(data_dir=tmp_path) is None
    assert DEMO_FILE in win.error_dialog.text()
    _close(win.error_dialog)


def test_app_main_demo(qapp, qtbot, chain_ll):
    """``formdiscovery gui --demo`` runs chain on demo_chain_feat in the event loop."""
    seen = {}

    def hook():
        wins = [w for w in QApplication.topLevelWidgets() if isinstance(w, MainWindow)
                and w.isVisible()]
        w = wins[-1]

        def ended(outcome):
            seen.update(outcome=outcome, ll=w.last_result and w.last_result["ll"])
            w.close()
            qapp.exit(0)  # not quit(): ANOMALIES.md A24

        if w.running():
            w.run_ended.connect(ended)
        else:
            seen["outcome"] = "not started"
            w.close()
            qapp.exit(1)

    QTimer.singleShot(0, lambda: QTimer.singleShot(0, hook))  # after start_demo's timer
    assert gui_app.main(["--demo"]) == 0
    qtbot.wait(1)
    assert seen == {"outcome": "finished", "ll": chain_ll}


def test_demo_flag_parsing():
    got = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gui_app, "main",
                   lambda argv=None, args=None: got.setdefault("args", args) and 0)
        assert cli.main(["gui", "--demo"]) == 0
    assert got["args"].demo and got["args"].file is None
    assert not gui_app.build_parser().parse_args([]).demo
    with pytest.raises(SystemExit, match="--demo"):
        gui_app.main(["--demo", str(DEMO)])


OCTAVE_FREE = r"""
import builtins, os, sys
real_import = builtins.__import__
def no_octave(name, *a, **k):
    if name.split(".")[0] in ("oct2py", "octave_kernel"):
        raise ImportError("Octave is not available here")
    return real_import(name, *a, **k)
builtins.__import__ = no_octave
os.environ["PATH"] = os.pathsep.join(
    p for p in os.environ["PATH"].split(os.pathsep)
    if not any(os.path.exists(os.path.join(p, e)) for e in ("octave", "octave-cli")))
from PySide6.QtWidgets import QApplication
from formdiscovery.gui.main_window import MainWindow
app = QApplication([])
w = MainWindow()
w.start_demo()
assert w.wait_run(120000)
app.processEvents()
assert not any(m.startswith("oct2py") for m in sys.modules)
print(repr(w.last_result["ll"]))
"""


def test_gui_needs_no_octave(tmp_path, chain_ll):
    """The GUI runs a search with oct2py unimportable and no Octave on ``PATH``."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               PYTHONPATH=str(REPO / "src"), OCTAVE_EXECUTABLE="",
               **{SETTINGS_ENV: str(tmp_path / "s.ini")})
    r = subprocess.run([sys.executable, "-c", OCTAVE_FREE], env=env, capture_output=True,
                       text=True, timeout=180, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert float(r.stdout.strip().splitlines()[-1]) == chain_ll
