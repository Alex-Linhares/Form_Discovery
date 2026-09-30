"""Shared pytest fixtures.

The ``octave`` session fixture starts one oct2py session with the original MATLAB
sources (``matlab/formdiscovery1.0``) on the Octave path. Tests marked
``@pytest.mark.octave`` are skipped when oct2py or an Octave executable is not
available (e.g. when running under the base interpreter instead of the ``fd`` env).

Strict mode (loop0002 item 01): when ``RALPH_REQUIRE_OCTAVE=1`` (set by the Ralph loop's
gate) or the interpreter is the ``fd`` env's, a skipped ``octave`` test is reported as a
failure instead, so the gate cannot pass without exercising Octave live.
``RALPH_REQUIRE_OCTAVE=0`` turns strict mode off explicitly.

Octave is located in this order: ``$OCTAVE_EXECUTABLE``; ``octave-cli`` next to the
running Python (the ``fd`` env); ``octave-cli``/``octave`` on ``PATH``; the conda env
``fd`` under ``~/anaconda3``/``~/miniconda3``/``~/miniforge3``. conda-forge Octave
needs ``OCTAVE_HOME`` pointing at its prefix when the env is not activated, so it is
set from the executable's location if missing.

The ``replay`` fixture (item 22, PLAN §4.2) puts the ``randperm`` shim
(``matlab/octave_shims``) in front of the session's path and returns a
:class:`ReplayControl`. Its methods set the Octave and Python sides up to draw the same
permutations.
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
SHIM_DIR = REPO_ROOT / "matlab" / "octave_shims"


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


def is_fd_env():
    """True when the running interpreter belongs to a conda env named ``fd``."""
    prefix = Path(sys.prefix)
    return prefix.name == "fd" and prefix.parent.name == "envs"


def octave_required():
    """Strict mode: Octave tests must run (``RALPH_REQUIRE_OCTAVE`` wins over the env)."""
    flag = os.environ.get("RALPH_REQUIRE_OCTAVE")
    if flag is not None and flag.strip() != "":
        return flag.strip() not in ("0", "false", "no")
    return is_fd_env()


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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """In strict mode, report a skipped ``octave`` test as a failure."""
    outcome = yield
    report = outcome.get_result()
    if (report.skipped and not hasattr(report, "wasxfail")
            and "octave" in item.keywords and octave_required()):
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else report.longrepr
        reason = str(reason).removeprefix("Skipped: ")
        report.outcome = "failed"
        report.longrepr = (
            f"Octave test skipped in strict mode ({reason}). The gate requires live Octave: "
            f"run it with the fd env's Python (~/anaconda3/envs/fd/bin/python) where oct2py "
            f"and octave-cli are installed, or set RALPH_REQUIRE_OCTAVE=0 to allow skips "
            f"(interpreter: {sys.executable}).")


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


def _octq(s):
    return "'" + str(s).replace("'", "''") + "'"


class ReplayControl:
    """Drive the Octave ``randperm`` shim and build the matching Python provider.

    Each mode call reconfigures the shim with ``randperm_config`` (which rewinds it) and
    truncates the Octave log ``self.log``:

    - ``queue(perms)``: Octave replays the given 0-based permutations, and so does the
      returned :class:`~formdiscovery.rng.ReplayPermutations`.
    - ``identity()``: both sides return ``range(n)``.
    - ``record(seed)``: Octave runs its built-in ``randperm`` after
      ``rand('state', seed)`` (``masterrun.m:63``). Afterwards, ``from_log()`` replays
      what Octave drew.

    ``octave_log()`` returns the permutations Octave has drawn so far, 0-based.
    """

    def __init__(self, octave, tmp_path):
        self.octave = octave
        self.dir = tmp_path
        self.log = tmp_path / "randperm_log.txt"
        self.queue_file = tmp_path / "randperm_queue.txt"

    def _config(self, source):
        self.octave.eval(f"randperm_config({_octq(source)}, {_octq(self.log)});", nout=0)

    def queue(self, perms):
        from formdiscovery.rng import ReplayPermutations, write_queue
        write_queue(self.queue_file, perms)
        self._config(self.queue_file)
        return ReplayPermutations.from_file(self.queue_file)

    def identity(self):
        from formdiscovery.rng import IdentityPermutations
        self._config("identity")
        return IdentityPermutations()

    def record(self, seed=None):
        self._config("")
        if seed is not None:
            self.octave.eval(f"rand('state', {int(seed)});", nout=0)

    def octave_log(self):
        from formdiscovery.rng import read_queue
        return read_queue(self.log)

    def from_log(self):
        from formdiscovery.rng import ReplayPermutations
        return ReplayPermutations(self.octave_log())


@pytest.fixture
def replay(octave, tmp_path):
    """Put the ``randperm`` shim first on the Octave path for one test.

    Yields a :class:`ReplayControl`. On teardown it restores the built-in (pass-through
    and no log) and removes the shim from the path.
    """
    octave.eval("warning('off', 'Octave:shadowed-function');", nout=0)
    octave.addpath(str(SHIM_DIR))
    try:
        yield ReplayControl(octave, tmp_path)
    finally:
        octave.eval("randperm_config();", nout=0)
        octave.rmpath(str(SHIM_DIR))
        octave.eval("clear('randperm');", nout=0)
