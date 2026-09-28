"""Toolchain smoke tests (iteration 02): Octave via oct2py, pygraphviz, conftest wiring."""

import numpy as np
import pytest

from tests.conftest import MATLAB_DIR


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
