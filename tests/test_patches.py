"""Octave compatibility patches (iteration 03, see ``matlab/PATCHES.md``).

Static checks run everywhere (no Octave needed): the removed or undefined calls are
gone from live code, every patched file is documented, and CRLF files kept CRLF.
Live checks (``octave`` marker) run the smoke script ``tests/octave/smoke_patches.m``
and regenerate the ``dot_to_graph`` fixture, comparing exactly.
"""

import re

import numpy as np
import pytest
from scipy.io import loadmat

from tests.conftest import FIXTURES_DIR, MATLAB_DIR, REPO_ROOT

PATCHES_MD = REPO_ROOT / "matlab" / "PATCHES.md"

# Patched file -> number of "PATCH(octave)" markers expected in it.
PATCHED = {
    "dijkstra.m": 1,
    "graph_like_rel.m": 1,
    "dataprobwsig.m": 1,
    "choose_node_split.m": 1,
    "best_split.m": 1,
    "swapobjclust.m": 1,
    "spr.m": 1,
    "collapsedims.m": 1,
    "draw_dot.m": 1,
    "dot_to_graph.m": 7,
}
CRLF_FILES = ("dijkstra.m", "dot_to_graph.m", "draw_dot.m")

FORBIDDEN = {
    "keyboard": r"(?:^|[;,]|\s)keyboard\s*(?:[;,]|$)",  # as a statement, not in strings
    "nargchk": r"\bnargchk\s*\(",
    "my_setdiff": r"\bmy_setdiff\s*\(",
    "textread": r"\btextread\s*\(",
    "strread": r"\bstrread\s*\(",
    "findstr": r"\bfindstr\s*\(",
    "strmatch": r"\bstrmatch\s*\(",
    "strvcat": r"\bstrvcat\s*\(",
    "range": r"(?<![\w.])range\s*\(",
}


def _code_lines(path):
    """Yield (lineno, code) with MATLAB '%' comments stripped (no '%' in strings here)."""
    text = path.read_bytes().decode("latin-1")
    for i, line in enumerate(text.splitlines(), 1):
        yield i, line.split("%", 1)[0]


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_no_removed_calls_in_live_code(name):
    pat = re.compile(FORBIDDEN[name])
    hits = [
        f"{p.name}:{i}"
        for p in sorted(MATLAB_DIR.glob("*.m"))
        for i, code in _code_lines(p)
        if pat.search(code)
    ]
    assert hits == []


@pytest.mark.parametrize("fname", sorted(PATCHED))
def test_patch_markers_and_docs(fname):
    text = (MATLAB_DIR / fname).read_bytes().decode("latin-1")
    assert text.count("PATCH(octave)") == PATCHED[fname]
    assert f"`{fname}`" in PATCHES_MD.read_text()


def test_every_marker_belongs_to_a_documented_file():
    marked = {
        p.name for p in MATLAB_DIR.glob("*.m") if b"PATCH(octave)" in p.read_bytes()
    }
    assert marked == set(PATCHED)


@pytest.mark.parametrize("fname", CRLF_FILES)
def test_crlf_preserved(fname):
    raw = (MATLAB_DIR / fname).read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_dot_to_graph_fixture_sanity():
    fx = loadmat(FIXTURES_DIR / "dot_to_graph.mat", mat_dtype=True)
    # lay1: undirected chain 1-2-...-6, edges numbered in file order
    a1 = np.zeros((6, 6))
    for k in range(5):
        a1[k, k + 1] = a1[k + 1, k] = k + 1
    np.testing.assert_array_equal(fx["A1"], a1)
    for k in range(1, 7):
        x, y = fx[f"x{k}"].ravel(), fx[f"y{k}"].ravel()
        assert x.min() == pytest.approx(0.05) and x.max() <= 0.95
        if k == 6:  # old2: all nodes share one y -> the range(y) == 0 branch
            np.testing.assert_array_equal(y, 0.5)
        else:
            assert y.min() == pytest.approx(0.05) and y.max() == pytest.approx(0.95)
    # lay4: the singleton node 7 is ignored by dot_to_graph
    assert fx["A4"].shape == (6, 6)
    # old2 is directed: A(1,2) set, A(2,1) not
    assert fx["A6"][0, 1] == 1 and fx["A6"][1, 0] == 0


@pytest.mark.octave
def test_smoke_patches(octave):
    out = octave.feval("smoke_patches", str(MATLAB_DIR), nout=1)
    names = [str(s) for s in np.ravel(out["structures"])]
    assert len(names) == 24 and "grid" in names and "cylinder" in names
    assert np.all(out["graph_ok"] == 1)
    ncomp = dict(zip(names, np.ravel(out["graph_ncomp"])))
    assert ncomp["grid"] == 2 and ncomp["cylinder"] == 2 and ncomp["tree"] == 1
    assert out["nlogps"] > 0
    assert tuple(np.ravel(out["scaled_size"])) == (8, 1000)
    assert np.all(np.isfinite(out["scaled"]))
    np.testing.assert_array_equal(
        out["dijkstra"], [[0, 1, 2], [1, 0, 1], [2, 1, 0]]
    )


@pytest.mark.octave
def test_dot_to_graph_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "dot_to_graph.mat"
    octave.feval("fx_dot_to_graph", str(out), nout=0)
    new = loadmat(out, mat_dtype=True)
    old = loadmat(FIXTURES_DIR / "dot_to_graph.mat", mat_dtype=True)
    keys = [k for k in old if not k.startswith("__")]
    assert sorted(keys) == sorted(k for k in new if not k.startswith("__"))
    for k in keys:
        np.testing.assert_array_equal(new[k], old[k], err_msg=k)

