"""Toolchain smoke tests (iteration 02): Octave via oct2py, pygraphviz, conftest wiring.

Environment split (loop0004 item 04): ``environment.yml`` is Python-only and
``legacy/environment-octave.yml`` adds Octave and oct2py to the same env.
"""

import re

import numpy as np
import pytest

from tests.conftest import LEGACY_DIR, MATLAB_DIR, REPO_ROOT


def conda_pins(path):
    """``{package: version}`` for the ``- name=version`` conda lines of an env file."""
    pins = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*-\s+([A-Za-z0-9_.-]+)=([^=\s#]+)", line)
        if m:
            pins[m.group(1)] = m.group(2)
    return pins


def test_environment_split():
    py = conda_pins(REPO_ROOT / "environment.yml")
    oct_ = conda_pins(LEGACY_DIR / "environment-octave.yml")
    assert "octave" not in py and "oct2py" not in py
    assert {"octave", "oct2py"} <= set(oct_)
    # the update must not move a package the Python-only env already pins
    assert {k: v for k, v in oct_.items() if k in py} == {k: py[k] for k in oct_ if k in py}
    assert {"python", "numpy", "scipy"} <= set(oct_) & set(py)


def test_matlab_sources_present():
    assert (MATLAB_DIR / "masterrun.m").is_file()


def test_pygraphviz_import():
    pgv = pytest.importorskip("pygraphviz")
    g = pgv.AGraph(directed=False)
    g.add_edge("a", "b")
    assert g.number_of_edges() == 1


@pytest.mark.octave
def test_oct2py_matrix_roundtrip(octave):
    a = np.arange(12.0).reshape(3, 4)
    b = octave.feval("transpose", a)
    np.testing.assert_array_equal(b, a.T)
    # column-major linear indexing survives the round trip
    octave.eval("x = reshape(1:6, 2, 3);")
    assert octave.eval("x(2)", nout=1) == 2.0


@pytest.mark.octave
def test_formdiscovery_on_octave_path(octave):
    path = octave.eval("which('masterrun')", nout=1)
    assert path.endswith("masterrun.m")
