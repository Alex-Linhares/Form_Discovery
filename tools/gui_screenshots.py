"""Save the loop0003 GUI screenshots in ``examples/gui/`` (offscreen ``grab()``).

    QT_QPA_PLATFORM=offscreen python tools/gui_screenshots.py [--outdir examples/gui]

``01_picker.png``: the window with ``demo_chain_feat`` loaded and the default forms
(chain, ring, tree) selected. ``02_run.png``: the same window after Run has fitted chain
in a worker thread (status line with the final score, frame count and time).
``03_live_mid.png``: the live canvas during a chain run with best splits drawn, at the
first graph it draws (frames come faster than
the canvas draws, so earlier ones are coalesced away); ``03_live_end.png``: the same run's inferred graph.
"""

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", default=str(REPO / "examples" / "gui"))
    args = ap.parse_args(argv)
    from PySide6.QtCore import QEventLoop
    from PySide6.QtWidgets import QApplication

    from formdiscovery.gui.app import screenshot
    from formdiscovery.gui.main_window import MainWindow
    from formdiscovery.io import DATA_DIR

    app = QApplication.instance() or QApplication(sys.argv[:1])
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    win = MainWindow(path=DATA_DIR / "demo_chain_feat.mat")
    win.show()
    print(screenshot(win, out / "01_picker.png"))
    win.close()

    win = MainWindow(path=DATA_DIR / "demo_chain_feat.mat")
    win.set_forms(["chain"])
    win.show()
    win.start_run(win.run_settings())
    win.wait_run(120000)
    app.processEvents()  # deliver the worker's queued signals
    if win.last_result is None:
        raise RuntimeError("the chain run did not finish: " + str(win.last_error))
    print(screenshot(win, out / "02_run.png"))
    win.close()

    win = MainWindow(path=DATA_DIR / "demo_chain_feat.mat")
    win.set_forms(["chain"])
    win.bestsplit_check.setChecked(True)
    win.show()
    mid = []

    def grab_mid(event, title):  # frame_drawn is emitted in the GUI thread
        if not mid and event != "inferredgraph":
            mid.append(screenshot(win, out / "03_live_mid.png"))

    win.canvas.frame_drawn.connect(grab_mid)
    win.start_run(win.run_settings())
    while win.running():  # keep the GUI thread drawing while the worker runs
        app.processEvents(QEventLoop.AllEvents, 20)
        if win.thread is not None and win.thread.isFinished():
            win.wait_run(1000)
    app.processEvents()
    if win.last_result is None or not mid:
        raise RuntimeError("the live run drew no frame before the end: " + str(win.last_error))
    print(mid[0])
    print(screenshot(win, out / "03_live_end.png"))
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
