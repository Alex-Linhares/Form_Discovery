"""The gate's toolchain (loop0002 item 01): oct2py importable, Octave found, one live call.

The first three are marked ``octave``, so outside strict mode (see ``conftest.py``) these skip when the
toolchain is missing, and in strict mode (``RALPH_REQUIRE_OCTAVE=1`` or the ``fd`` env)
they fail instead.

BLAS pinning (item 02): the Oct2Py session, an ``octave-cli`` started the way the tools
start it, and the Python side all run one BLAS/OpenMP thread.
"""

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

import tests.conftest as conftest
from formdiscovery.threads import PIN_ENV, pinned_env
from tests.conftest import MATLAB_DIR, REPO_ROOT, find_octave


@pytest.mark.octave
def test_interpreter_has_oct2py():
    assert importlib.util.find_spec("oct2py") is not None, "oct2py not importable"


@pytest.mark.octave
def test_octave_executable_found():
    exe = find_octave()
    assert exe is not None, "no Octave executable found"


@pytest.mark.octave
def test_trivial_live_call(octave):
    assert float(octave.eval("1 + 1;")) == 2.0
    assert octave.exist("masterrun") == 2  # the original sources are on the path
    assert str(MATLAB_DIR) in octave.path()


@pytest.mark.octave
def test_octave_session_pinned(octave):
    for k, v in PIN_ENV.items():
        assert octave.getenv(k) == v, k
    # nproc() honours OMP_NUM_THREADS
    assert int(octave.nproc()) == 1


@pytest.mark.octave
def test_octave_cli_pinned():
    """``tools/gen_paperlevel.py`` and ``tools/gen_fixtures.py`` start ``octave-cli``
    with ``pinned_env()`` (``fixture_env``), which wins over the caller's own thread
    settings."""
    exe = find_octave()
    env = pinned_env(dict(os.environ, OMP_NUM_THREADS="8", OPENBLAS_NUM_THREADS="8"))
    res = subprocess.run([exe, "--no-gui", "--quiet", "--no-window-system", "--eval",
                          "printf('%d %s\\n', nproc(), getenv('OPENBLAS_NUM_THREADS'));"],
                         env=env, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert res.stdout.split() == ["1", "1"]
    assert "env=pinned_env()" in (REPO_ROOT / "tools" / "gen_paperlevel.py").read_text()
    assert "env=fixture_env(name)" in (REPO_ROOT / "tools" / "gen_fixtures.py").read_text()


def test_fixture_env():
    """``gen_fixtures.py`` pins every fixture except ``BLAS_DEFAULT_FIXTURES`` (A19), which
    gets the library default back even when the caller is pinned (as the test session is)."""
    assert conftest.BLAS_DEFAULT_FIXTURES == {"gibbs"}
    pinned = conftest.fixture_env("swap")
    assert all(pinned[k] == v for k, v in PIN_ENV.items())
    free = conftest.fixture_env("gibbs")
    assert not set(PIN_ENV) & set(free)
    assert free["PATH"] == os.environ["PATH"]


def test_python_blas_pinned():
    """``conftest.pytest_sessionstart`` limits every loaded BLAS to one thread."""
    tpc = pytest.importorskip("threadpoolctl")
    import numpy  # noqa: F401  (make sure a BLAS is loaded)
    blas = [i for i in tpc.threadpool_info() if i["user_api"] == "blas"]
    assert blas and {i["num_threads"] for i in blas} == {1}, blas
    for k, v in PIN_ENV.items():
        assert os.environ.get(k) == v, k


@pytest.mark.parametrize("flag", ["1", "0"])
def test_strict_mode_turns_skip_into_failure(tmp_path, flag):
    """With this conftest, a skipped octave test fails under RALPH_REQUIRE_OCTAVE=1 and
    skips under =0; unmarked skips are untouched. Needs no Octave, so it always runs."""
    shutil.copy(conftest.__file__, tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text(
        f"[pytest]\npythonpath = {REPO_ROOT / 'src'}\nmarkers =\n    octave: live\n")
    (tmp_path / "test_x.py").write_text(
        "import pytest\n"
        "@pytest.mark.octave\n"
        "def test_live():\n"
        "    pytest.skip('no octave here')\n"
        "def test_plain():\n"
        "    pytest.skip('ok to skip')\n")
    env = dict(os.environ, RALPH_REQUIRE_OCTAVE=flag)
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "-o", "addopts="], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=120)
    out = res.stdout + res.stderr
    if flag == "1":
        # a skip in setup (the collection-time marker) is reported as an error, one in
        # the call as a failure; either way the run fails
        assert res.returncode == 1, out
        assert "1 skipped" in out and "passed" not in out, out
        assert "Octave test skipped in strict mode (" in out
    else:
        assert res.returncode == 0 and "2 skipped" in out, out
