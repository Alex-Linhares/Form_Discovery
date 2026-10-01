"""The gate's toolchain (loop0002 item 01): oct2py importable, Octave found, one live call.

The first three are marked ``octave``, so outside strict mode (see ``conftest.py``) these skip when the
toolchain is missing, and in strict mode (``RALPH_REQUIRE_OCTAVE=1`` or the ``fd`` env)
they fail instead.

BLAS pinning (item 02): the Oct2Py session, an ``octave-cli`` started the way the tools
start it, and the Python side all run one BLAS/OpenMP thread.

Parallel gate (item 05): under pytest-xdist every worker has its own Octave, the long
tests are scheduled first (``conftest.long_first``, ``--maxschedchunk 1``), and a run that
leaves a new file under ``tests/`` fails.
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
    """``tools/gen_paperlevel.py``, ``tools/gen_fixtures.py`` and ``tools/bench_perf.py
    --live`` start ``octave-cli`` with ``pinned_env()`` (``fixture_env``), which wins over
    the caller's own thread settings."""
    exe = find_octave()
    env = pinned_env(dict(os.environ, OMP_NUM_THREADS="8", OPENBLAS_NUM_THREADS="8"))
    res = subprocess.run([exe, "--no-gui", "--quiet", "--no-window-system", "--eval",
                          "printf('%d %s\\n', nproc(), getenv('OPENBLAS_NUM_THREADS'));"],
                         env=env, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert res.stdout.split() == ["1", "1"]
    assert "env=pinned_env()" in (REPO_ROOT / "tools" / "gen_paperlevel.py").read_text()
    assert "env=fixture_env(name)" in (REPO_ROOT / "tools" / "gen_fixtures.py").read_text()
    # bench_perf.py --live regenerates perf.mat through gen_fixtures.run_one (pinned)
    bench = (REPO_ROOT / "tools" / "bench_perf.py").read_text()
    assert "run_one(exe, \"perf\"" in bench and "perf" not in conftest.BLAS_DEFAULT_FIXTURES


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


class _Item:
    def __init__(self, nodeid):
        self.nodeid = nodeid


def test_long_first():
    items = [_Item(n) for n in ("a", "L2", "b", "c", "L1", "d", "L3")]
    out = conftest.long_first(items, {"L1": 9, "L2": 5, "L3": 7})
    assert [it.nodeid for it in out] == ["L1", "a", "L3", "b", "L2", "c", "d"]
    assert conftest.long_first(items[:2], {"L1": 9, "L2": 5}) == [items[1], items[0]]
    assert conftest.long_first(items, {}) == items


def test_long_tests_exist():
    """Every ``LONG_TESTS`` entry names a test function that exists."""
    for nodeid in conftest.LONG_TESTS:
        path, name = nodeid.split("::")
        assert f"\ndef {name}(" in (REPO_ROOT / path).read_text(), nodeid


def _inner_run(tmp_path, test_src, *args):
    """pytest in ``tmp_path/run`` with a copy of this conftest and ``test_src``."""
    run = tmp_path / "run"
    run.mkdir()
    shutil.copy(conftest.__file__, run / "conftest.py")
    (run / "pytest.ini").write_text(
        f"[pytest]\npythonpath = {REPO_ROOT / 'src'}\nmarkers =\n    octave: live\n")
    (run / "test_x.py").write_text(test_src)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "-o", "addopts=", *args], cwd=run,
                          capture_output=True, text=True, timeout=300)


@pytest.mark.octave
def test_xdist_one_octave_per_worker(tmp_path):
    """``-n 2``: two workers, each with its own Octave process."""
    pytest.importorskip("xdist")
    out = tmp_path / "seen"
    out.mkdir()
    src = ("import os\nimport pytest\n"
           "@pytest.mark.parametrize('k', range(6))\n"
           "def test_pid(octave, k):\n"
           "    import time; time.sleep(0.3)\n"
           "    pid = int(octave.eval('getpid();'))\n"
           "    w = os.environ['PYTEST_XDIST_WORKER']\n"
           f"    (__import__('pathlib').Path({str(out)!r}) / f'{{k}}').write_text(\n"
           "        f'{w} {pid}')\n")
    res = _inner_run(tmp_path, src, "-n", "2")
    assert res.returncode == 0 and "6 passed" in res.stdout, res.stdout + res.stderr
    seen = [p.read_text().split() for p in out.iterdir()]
    assert len(seen) == 6
    workers = {w: pid for w, pid in seen}
    assert sorted(workers) == ["gw0", "gw1"]
    assert len(set(workers.values())) == 2  # one Octave per worker
    assert all(pid == workers[w] for w, pid in seen)  # and one only


def test_maxschedchunk_default(monkeypatch):
    """The controller of an xdist run gets ``--maxschedchunk 1`` unless one was given;
    serial runs and workers are left alone."""
    import types
    monkeypatch.setattr(conftest, "find_octave", lambda: None)
    for numprocesses, given, worker, want in ((16, None, False, 1), (16, 4, False, 4),
                                              (None, None, False, None),
                                              (16, None, True, None)):
        cfg = types.SimpleNamespace(option=types.SimpleNamespace(
            numprocesses=numprocesses, maxschedchunk=given))
        if worker:
            cfg.workerinput = {}
        conftest.pytest_configure(cfg)
        assert cfg.option.maxschedchunk == want


def test_new_file_under_tests_fails(tmp_path):
    """A test that leaves a new file next to the conftest fails the run (serial)."""
    src = ("from pathlib import Path\n"
           "def test_ok():\n    pass\n"
           "def test_writes():\n"
           "    (Path(__file__).parent / 'stray.png').write_bytes(b'x')\n")
    res = _inner_run(tmp_path, src)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "2 passed" in res.stdout
    assert "wrote new files under tests/" in res.stderr and "stray.png" in res.stderr


def test_xdist_shared(tmp_path, monkeypatch):
    """``helpers.xdist_shared`` (item 07): computed once across concurrent "workers", and
    every worker gets the serial value to all digits."""
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    from tests.helpers import xdist_shared
    value = [[-8247.204813441429, 4, 0.1 + 0.2], [1e-300, 0, -0.0]]
    calls = []

    def compute():
        calls.append(1)
        return [list(v) for v in value]

    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    assert xdist_shared("x", None, compute) == value and len(calls) == 1
    calls.clear()
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    factories = [SimpleNamespace(getbasetemp=lambda i=i: tmp_path / f"popen-gw{i}")
                 for i in range(8)]
    with ThreadPoolExecutor(8) as ex:
        outs = list(ex.map(lambda f: xdist_shared("x", f, compute), factories))
    assert len(calls) == 1
    assert all(o == value for o in outs)
