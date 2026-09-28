"""Shared pytest fixtures.

The ``octave`` session fixture starts one oct2py session with the original MATLAB
sources (``matlab/formdiscovery1.0``) on the Octave path. Tests marked
``@pytest.mark.octave`` are skipped when oct2py or an Octave executable is not
available (e.g. when running under the base interpreter instead of the ``fd`` env).

Octave is located in this order: ``$OCTAVE_EXECUTABLE``; ``octave-cli`` next to the
running Python (the ``fd`` env); ``octave-cli``/``octave`` on ``PATH``; the conda env
``fd`` under ``~/anaconda3``/``~/miniconda3``/``~/miniforge3``. conda-forge Octave
needs ``OCTAVE_HOME`` pointing at its prefix when the env is not activated, so it is
set from the executable's location if missing.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MATLAB_DIR = REPO_ROOT / "matlab" / "formdiscovery1.0"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OCTAVE_TESTS_DIR = REPO_ROOT / "tests" / "octave"


def find_octave():
    """Return the path to an Octave executable, or None."""
    env = os.environ.get("OCTAVE_EXECUTABLE")
    if env and Path(env).is_file():
        return env
    candidates = [Path(sys.executable).parent / "octave-cli"]
    for name in ("octave-cli", "octave"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    home = Path.home()
    for base in ("anaconda3", "miniconda3", "miniforge3"):
        candidates.append(home / base / "envs" / "fd" / "bin" / "octave-cli")
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def _configure_octave_env(exe):
    os.environ["OCTAVE_EXECUTABLE"] = exe
    prefix = Path(exe).resolve().parent.parent
    if "OCTAVE_HOME" not in os.environ and (prefix / "conda-meta").is_dir():
        os.environ["OCTAVE_HOME"] = str(prefix)


def pytest_configure(config):
    """Point oct2py at Octave before it is first imported (its import creates a session)."""
    exe = find_octave()
    if exe is not None:
        _configure_octave_env(exe)


def pytest_collection_modifyitems(config, items):
    """Skip octave-marked tests up front when the toolchain is missing."""
    reason = None
    try:
        import oct2py  # noqa: F401
    except ImportError:
        reason = "oct2py not installed (use the 'fd' conda env)"
    else:
        if find_octave() is None:
            reason = "Octave executable not found"
    if reason is None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "octave" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def octave():
    """Session-wide Oct2Py instance with the original MATLAB code on the path."""
    oct2py = pytest.importorskip("oct2py")
    if find_octave() is None:
        pytest.skip("Octave executable not found")
    try:
        oc = oct2py.Oct2Py()
    except Exception as e:  # Octave present but unusable
        pytest.skip(f"could not start Octave: {e}")
    oc.addpath(str(MATLAB_DIR))
    oc.addpath(str(OCTAVE_TESTS_DIR))
    yield oc
    oc.exit()
