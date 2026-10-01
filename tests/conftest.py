"""Shared pytest fixtures.

Legacy tests (loop0004 item 03): the tests that only make sense with the MATLAB sources and
the Octave tools live in ``legacy/tests/``. ``testpaths = ["tests", "legacy/tests"]``
collects them only when that directory exists (pytest drops a ``testpaths`` glob that
matches nothing); ``legacy/tests/conftest.py`` re-exports the fixtures and the strict-mode
hook from here. Without ``legacy/``, ``octave`` tests in ``tests/`` are skipped (a failure in
strict mode, below), and ``pytest -q -m "not slow and not octave"`` needs neither Octave nor
``legacy/``.

The ``octave`` session fixture starts one oct2py session with the original MATLAB
sources (``legacy/matlab/formdiscovery1.0``) on the Octave path. Tests marked
``@pytest.mark.octave`` are skipped when oct2py or an Octave executable is not
available (e.g. when running under the base interpreter instead of the ``fd`` env).

Strict mode (loop0002 item 01): when ``RALPH_REQUIRE_OCTAVE=1`` (set by the Ralph loop's
gate) or the interpreter is the ``fd`` env's, a skipped ``octave`` test is reported as a
failure instead, so the gate cannot pass without exercising Octave live.
``RALPH_REQUIRE_OCTAVE=0`` turns strict mode off explicitly.

GUI tests (loop0003): ``pytest_configure`` sets ``QT_QPA_PLATFORM=offscreen`` before any
``QApplication`` exists, so no test opens a window; pytest-qt uses PySide6
(``qt_api`` in ``pyproject.toml``). The autouse ``gui_settings_file`` fixture points the
GUI's ``QSettings`` (``$FORMDISCOVERY_GUI_SETTINGS``, item 06) at a fresh file under the
test's ``tmp_path`` in ``tests/test_gui_*.py``, so no test reads or writes the user's
preferences and tests do not see each other's last directory.

Octave is located in this order: ``$OCTAVE_EXECUTABLE``; ``octave-cli`` next to the
running Python (the ``fd`` env); ``octave-cli``/``octave`` on ``PATH``; the conda env
``fd`` under ``~/anaconda3``/``~/miniconda3``/``~/miniforge3``. conda-forge Octave
needs ``OCTAVE_HOME`` pointing at its prefix when the env is not activated, so it is
set from the executable's location if missing.

BLAS threads (loop0002 item 02): ``pytest_configure`` puts
``formdiscovery.threads.PIN_ENV`` (``OPENBLAS_NUM_THREADS``, ``OMP_NUM_THREADS``,
``MKL_NUM_THREADS`` = 1) into ``os.environ``, so the Oct2Py session and every
``octave-cli`` started by the tools run one BLAS/OpenMP thread (``_configure_octave_env``
does the same for the tools). The exceptions are ``BLAS_DEFAULT_FIXTURES``, which
``fixture_env`` regenerates unpinned (ANOMALIES A19). ``pytest_sessionstart`` limits any
BLAS Python has already loaded to one thread (``pin_process_blas``) until the session ends.

Parallel gate (loop0002 item 05): the gate runs under pytest-xdist (``-n 16``); each worker
is its own pytest session with its own ``octave`` fixture, i.e. its own Octave process.
xdist hands out tests in contiguous chunks, which put both 300 s gibbs tests on one worker
(10 min wall for 3.5 min of work per worker). So under xdist the tests of
``LONG_TESTS`` run first, longest first, each followed by one short test
(``long_first``), and ``--maxschedchunk`` defaults to 1: every worker starts with one long
test and then takes tests one at a time. The order within a worker does not matter (each
test is independent). Without xdist the order is pytest's.

The ``replay`` fixture (item 22, PLAN §4.2) puts the ``randperm`` shim
(``legacy/matlab/octave_shims``) in front of the session's path and returns a
:class:`ReplayControl`. Its methods set the Octave and Python sides up to draw the same
permutations.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

from formdiscovery.threads import pin_blas_env, pin_process_blas, pinned_env, unpinned_env

REPO_ROOT = Path(__file__).resolve().parent.parent
# Everything Octave-specific lives under legacy/ (loop0004, PLAN_LEGACY.md phase 2).
LEGACY_DIR = REPO_ROOT / "legacy"
MATLAB_DIR = LEGACY_DIR / "matlab" / "formdiscovery1.0"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OCTAVE_TESTS_DIR = LEGACY_DIR / "tests_octave"
SHIM_DIR = LEGACY_DIR / "matlab" / "octave_shims"

# Fixtures whose committed values depend on Octave's BLAS thread count (ANOMALIES A19):
# they were generated with OpenBLAS's default (one thread per core, 32 here) and a
# pinned Octave does not reproduce them, so they are regenerated unpinned.
BLAS_DEFAULT_FIXTURES = frozenset({"gibbs"})


# Gate tests taking 30 s or more under ``-n 16`` (``--durations``, loop0002 item 05),
# with those seconds: scheduled first under xdist (``long_first``).
LONG_TESTS = {
    "tests/test_gibbs.py::test_live_fresh_seeds": 358,
    "tests/test_spr.py::test_live_fresh_seeds": 307,
    "tests/test_gibbs.py::test_live_fixture_regenerates": 290,
    "tests/test_spr.py::test_live_fixture_regenerates": 239,
    "tests/test_dpmiss.py::test_live_fresh_seeds": 189,
    "tests/test_swap.py::test_live_fresh_seeds": 98,
    "tests/test_dpmiss.py::test_live_fixture_regenerates": 95,
    "tests/test_simplify.py::test_live_fresh_sequences": 80,
    "tests/test_swap.py::test_live_fixture_regenerates": 76,
    "tests/test_runmodel.py::test_live_fresh_seeds": 73,
    "tests/test_simplify.py::test_fixture_regenerates": 72,
    "tests/test_search.py::test_live_fresh_seeds": 67,
    "tests/test_runmodel.py::test_live_fixture_regenerates": 65,
    "tests/test_glslow.py::test_live_fresh_seeds": 56,
    "tests/test_search.py::test_live_fixture_regenerates": 50,
    "tests/test_glslow.py::test_live_fixture_regenerates": 47,
    "tests/test_masterrun.py::test_live_fixture_regenerates": 39,
    "tests/test_rellike.py::test_live_fresh_seeds": 34,
    "tests/test_rellike.py::test_live_fixture_regenerates": 33,
}


def long_first(items, long_tests=LONG_TESTS):
    """``items`` with those in ``long_tests`` first, longest first, each followed by the
    next other item; the other items keep their order."""
    longs = sorted((it for it in items if it.nodeid in long_tests),
                   key=lambda it: -long_tests[it.nodeid])
    rest = [it for it in items if it.nodeid not in long_tests]
    out = []
    for k, it in enumerate(longs):
        out.append(it)
        out.extend(rest[k:k + 1])
    return out + rest[len(longs):]


def fixture_env(name):
    """Environment for the ``octave-cli`` that regenerates fixture ``name``: pinned to one
    BLAS/OpenMP thread, except for :data:`BLAS_DEFAULT_FIXTURES`."""
    return unpinned_env() if name in BLAS_DEFAULT_FIXTURES else pinned_env()


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
    pin_blas_env()
    os.environ["OCTAVE_EXECUTABLE"] = exe
    prefix = Path(exe).resolve().parent.parent
    if "OCTAVE_HOME" not in os.environ and (prefix / "conda-meta").is_dir():
        os.environ["OCTAVE_HOME"] = str(prefix)


@pytest.fixture(autouse=True)
def gui_settings_file(request, monkeypatch):
    """GUI tests: the window's QSettings live in the test's ``tmp_path`` (item 06)."""
    if request.node.path.name.startswith("test_gui"):
        path = request.getfixturevalue("tmp_path") / "gui_settings.ini"
        monkeypatch.setenv("FORMDISCOVERY_GUI_SETTINGS", str(path))
    yield


def pytest_configure(config):
    """Pin BLAS threads and point oct2py at Octave before it is first imported (its
    import creates a session)."""
    pin_blas_env()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"  # GUI tests never open a window
    exe = find_octave()
    if exe is not None:
        _configure_octave_env(exe)
    if (not hasattr(config, "workerinput") and getattr(config.option, "numprocesses", None)
            and getattr(config.option, "maxschedchunk", 0) is None):
        config.option.maxschedchunk = 1  # with long_first: one long test per worker


_blas_limit = None
_tests_files = None
TESTS_DIR = Path(__file__).resolve().parent  # tests/


def tests_tree_files():
    """Files under ``tests/``, except Python caches (``__pycache__``)."""
    return {p for p in TESTS_DIR.rglob("*")
            if p.is_file() and "__pycache__" not in p.relative_to(TESTS_DIR).parts}


def pytest_sessionstart(session):
    """One BLAS thread for the Python side too (a BLAS loaded before
    ``pytest_configure`` did not see the environment variables). Outside xdist workers,
    record the files under ``tests/`` for the check in ``pytest_sessionfinish``."""
    global _blas_limit, _tests_files
    _blas_limit = pin_process_blas(1)
    if not hasattr(session.config, "workerinput"):
        _tests_files = tests_tree_files()


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if a test left a new file under ``tests/`` (tests write to
    ``tmp_path``, so parallel workers cannot collide on a shared file; item 05)."""
    global _blas_limit, _tests_files
    if _blas_limit is not None:
        _blas_limit.restore_original_limits()
        _blas_limit = None
    if _tests_files is not None:
        new = sorted(str(p.relative_to(REPO_ROOT)) for p in tests_tree_files() - _tests_files)
        _tests_files = None
        if new:
            sys.stderr.write("\nERROR: the test run wrote new files under tests/ "
                             "(tests must write to tmp_path):\n  " + "\n  ".join(new) + "\n")
            if session.exitstatus == pytest.ExitCode.OK:
                session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_collection_modifyitems(config, items):
    """Under xdist, long tests first (``long_first``); skip octave-marked tests up front
    when the toolchain or ``legacy/`` (the MATLAB sources) is missing."""
    if os.environ.get("PYTEST_XDIST_WORKER"):
        items[:] = long_first(items)
    reason = None
    try:
        import oct2py  # noqa: F401
    except ImportError:
        reason = "oct2py not installed (use the 'fd' conda env)"
    else:
        if find_octave() is None:
            reason = "Octave executable not found"
        elif not MATLAB_DIR.is_dir():
            reason = f"legacy/ (the MATLAB sources) not present: {MATLAB_DIR}"
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
