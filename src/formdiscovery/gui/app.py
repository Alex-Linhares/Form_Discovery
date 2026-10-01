"""``formdiscovery gui [FILE]``: start the Qt application (loop0003 item 01).

:func:`main` creates (or reuses) the ``QApplication``, opens
:class:`formdiscovery.gui.main_window.MainWindow` with ``FILE`` loaded if given, and runs
the event loop; with ``--demo`` (item 06) it opens ``demo_chain_feat`` and runs chain as
soon as the loop starts (:meth:`MainWindow.start_demo`). :func:`screenshot` saves a widget as an image (offscreen ``grab()``), for
the ``examples/gui/`` pictures.
"""

import argparse
import sys

__all__ = ["main", "screenshot", "build_parser"]


def build_parser(parser=None):
    """The ``gui`` arguments, on ``parser`` (the CLI's subparser) or a new parser."""
    p = parser or argparse.ArgumentParser(prog="formdiscovery gui",
                                          description="form discovery desktop GUI")
    p.add_argument("file", nargs="?", default=None,
                   help="a .mat data file to open (data, optional names)")
    p.add_argument("--data-dir", default=None,
                   help="where the file dialog starts (default: the shipped data sets)")
    p.add_argument("--demo", action="store_true",
                   help="open demo_chain_feat and run chain at once (no FILE)")
    return p


def screenshot(widget, path):
    """Save ``widget.grab()`` to ``path`` (format from the suffix); returns the path."""
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    if not widget.grab().save(str(path)):
        raise OSError(f"could not save {path}")
    return path


def main(argv=None, args=None):
    """Run the GUI; returns the event loop's exit code. ``args`` (parsed by the CLI)
    takes precedence over ``argv``."""
    if args is None:
        args = build_parser().parse_args(argv)
    if getattr(args, "demo", False) and args.file is not None:
        raise SystemExit("formdiscovery gui: --demo opens its own file; give no FILE")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = MainWindow(path=args.file, data_dir=args.data_dir)
    win.show()
    if getattr(args, "demo", False):
        QTimer.singleShot(0, win.start_demo)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
