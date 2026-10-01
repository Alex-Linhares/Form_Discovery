"""Error dialogs and saved preferences (loop0003 item 06).

:func:`error_box` shows a warning box that does not block: it is opened with
``QMessageBox.open()`` (window-modal), not ``exec()``, so a caller (and an offscreen test)
goes on at once; the box is returned so it can be inspected or closed.

:func:`gui_settings` is the ``QSettings`` store of the window's preferences (the last data
directory, :data:`LAST_DIR_KEY`): ``$FORMDISCOVERY_GUI_SETTINGS`` (an ini file) if set
(the tests point it at ``tmp_path``), else the user's store
(``~/.config/formdiscovery/gui.ini`` on Linux).
"""

import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QMessageBox

__all__ = ["error_box", "gui_settings", "SETTINGS_ENV", "LAST_DIR_KEY"]

SETTINGS_ENV = "FORMDISCOVERY_GUI_SETTINGS"
LAST_DIR_KEY = "last_dir"


def gui_settings():
    """The ``QSettings`` holding the GUI's preferences (see the module docstring)."""
    path = os.environ.get(SETTINGS_ENV)
    if path:
        return QSettings(path, QSettings.IniFormat)
    return QSettings(QSettings.IniFormat, QSettings.UserScope, "formdiscovery", "gui")


def error_box(parent, title, text, detail=None):
    """Open a non-blocking warning box (``detail``: e.g. a traceback, behind "Show
    Details…"); returns the ``QMessageBox``."""
    box = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, parent)
    if detail:
        box.setDetailedText(detail)
    box.setAttribute(Qt.WA_DeleteOnClose)
    box.open()
    return box
