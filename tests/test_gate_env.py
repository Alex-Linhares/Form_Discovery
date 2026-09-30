"""The gate's toolchain (loop0002 item 01): oct2py importable, Octave found, one live call.

The first three are marked ``octave``, so outside strict mode (see ``conftest.py``) these skip when the
toolchain is missing, and in strict mode (``RALPH_REQUIRE_OCTAVE=1`` or the ``fd`` env)
they fail instead.
"""

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

import tests.conftest as conftest
from tests.conftest import MATLAB_DIR, find_octave


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


@pytest.mark.parametrize("flag", ["1", "0"])
def test_strict_mode_turns_skip_into_failure(tmp_path, flag):
    """With this conftest, a skipped octave test fails under RALPH_REQUIRE_OCTAVE=1 and
    skips under =0; unmarked skips are untouched. Needs no Octave, so it always runs."""
    shutil.copy(conftest.__file__, tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    octave: live\n")
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
