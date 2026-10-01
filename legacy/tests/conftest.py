"""pytest wiring for ``legacy/tests/`` (loop0004 item 03).

These tests only make sense with the original MATLAB sources and the Octave tools next to
them. Collection rule: ``testpaths = ["tests", "legacy/tests"]`` in ``pyproject.toml``;
pytest expands ``testpaths`` as globs, so when ``legacy/`` is deleted the entry matches
nothing and only ``tests/`` is collected (no hook, no error).

``tests/conftest.py`` only applies below ``tests/``, so this file re-exports what the legacy
tests need from it:

- the ``octave`` and ``replay`` fixtures (a separate session-scoped ``octave`` per xdist
  worker for this directory);
- ``pytest_runtest_makereport``: strict mode (``RALPH_REQUIRE_OCTAVE=1`` or the fd env)
  turns a skipped ``octave`` test here into a failure too (per-item hooks are path-scoped);
- ``pytest_configure`` (idempotent: BLAS pinning, ``OCTAVE_EXECUTABLE``/``OCTAVE_HOME``),
  for a run of ``legacy/tests`` alone, where ``tests/conftest.py`` is not loaded.

``pytest_collection_modifyitems`` (skip ``octave`` tests when the toolchain is missing) is a
session-wide hook, so the one in ``tests/conftest.py`` already covers these items in a full
run; it is re-exported for the ``legacy/tests``-alone case only.

The directory has no ``__init__.py`` (pytest's ``prepend`` import mode would otherwise
name it ``tests`` and clash with the top-level package), so the repository root is put on
``sys.path`` for ``from tests.conftest import ...`` and ``from legacy.tools import ...``.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests import conftest as _top  # noqa: E402
from tests.conftest import octave, pytest_configure, pytest_runtest_makereport, replay  # noqa: E402,F401


def pytest_collection_modifyitems(config, items):
    """Only when ``tests/conftest.py`` is not loaded (``pytest legacy/tests``): skip
    ``octave`` tests without a toolchain. In a full run that conftest's hook does it."""
    if not config.pluginmanager.has_plugin(_top.__name__) and not any(
            getattr(p, "__file__", None) == _top.__file__
            for p in config.pluginmanager.get_plugins()):
        _top.pytest_collection_modifyitems(config, items)
