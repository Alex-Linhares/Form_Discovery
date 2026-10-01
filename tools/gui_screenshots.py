"""Save the loop0003 GUI screenshots in ``examples/gui/`` (offscreen ``grab()``).

    QT_QPA_PLATFORM=offscreen python tools/gui_screenshots.py [--outdir examples/gui]

``01_picker.png``: the window with ``demo_chain_feat`` loaded and the default forms
(chain, ring, tree) selected.
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
    from PySide6.QtWidgets import QApplication

    from formdiscovery.gui.app import screenshot
    from formdiscovery.gui.main_window import MainWindow
    from formdiscovery.io import DATA_DIR

    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    win = MainWindow(path=DATA_DIR / "demo_chain_feat.mat")
    win.show()
    print(screenshot(win, out / "01_picker.png"))
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
