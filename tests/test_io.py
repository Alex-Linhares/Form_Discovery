"""``formdiscovery.io``: data-set loading, fixture loading and the index boundary."""

import numpy as np
import pytest

from formdiscovery.io import DATA_DIR, load_dataset, load_fixture, load_mat, to0, to1

RELATIONAL = {
    "bushcabinet": ("relfreq", 13),
    "kularing": ("relbin", 20),
    "mangabeys": ("relfreq", 24),
    "prisoners": ("relbin", 67),
    "demo_ring_rel_bin": ("relbin", 8),
    "demo_hierarchy_rel_bin": ("relbin", 28),
    "demo_order_rel_freq": ("relfreq", 8),
}
FEATURE_SHAPES = {
    "demo_chain_feat": (8, 1000),
    "demo_ring_feat": (8, 1000),
    "demo_tree_feat": (8, 1000),
    "animals": (33, 102),
    "judges": (13, 1596),
    "synthtree": (40, 2000),
    "colors": (14, 14),
    "cities": (35, 35),
    "faces": (16, 16),
}


def test_every_dataset_is_covered():
    names = {p.stem for p in DATA_DIR.glob("*.mat")}
    assert set(RELATIONAL) | set(FEATURE_SHAPES) <= names
    assert len(names) == 20


def test_data_dir_is_repo_data_and_matlab_side_links_to_it():
    """loop0004 item 01: the data sets live in ``data/`` at the repo root
    (``$FORMDISCOVERY_DATA`` overrides); the MATLAB tree reaches them through the
    relative symlink ``matlab/formdiscovery1.0/data -> ../../data`` (PATCHES.md)."""
    import os
    import subprocess
    import sys

    from formdiscovery.io import REPO_ROOT

    if "FORMDISCOVERY_DATA" not in os.environ:
        assert DATA_DIR == REPO_ROOT / "data"
    link = REPO_ROOT / "matlab" / "formdiscovery1.0" / "data"
    if link.parent.is_dir():
        assert link.is_symlink() and os.readlink(link) == "../../data"
        assert link.resolve() == (REPO_ROOT / "data").resolve()
    code = "from formdiscovery.io import DATA_DIR; print(DATA_DIR)"
    env = dict(os.environ, FORMDISCOVERY_DATA="/x/y",
               PYTHONPATH=os.pathsep.join([str(REPO_ROOT / "src"), os.environ.get("PYTHONPATH", "")]))
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                         text=True, check=True).stdout.strip()
    assert out == "/x/y"


@pytest.mark.parametrize("name", sorted(FEATURE_SHAPES))
def test_feature_and_similarity_sets(name):
    data = load_dataset(name)
    assert isinstance(data, np.ndarray) and data.dtype == np.float64
    assert data.shape == FEATURE_SHAPES[name]


@pytest.mark.parametrize("name", sorted(RELATIONAL))
def test_relational_sets(name):
    d = load_dataset(name)
    typ, nobj = RELATIONAL[name]
    assert set(d) == {"R", "type", "nobj", "names"}
    assert d["type"] == typ and d["nobj"] == nobj
    assert d["R"].dtype == np.float64 and d["R"].shape[:2] == (nobj, nobj)


def test_names_and_integer_data_become_float():
    data, names = load_dataset("animals", with_names=True)
    assert len(names) == 33 and all(isinstance(n, str) and n for n in names)
    assert set(np.unique(data)) <= {0.0, 1.0}
    assert load_dataset("mangabeys")["names"] is not None
    assert load_dataset("prisoners")["names"] is None
    # judges: inf marks missing values (scaledata makechunks path)
    assert np.isinf(load_dataset("judges")).any()


def test_load_mat_keeps_other_variables():
    d = load_mat("demo_chain_feat")
    assert {"data", "adj", "W", "sigma", "graph"} <= set(d)


def test_load_fixture():
    fx = load_fixture("dot_to_graph")
    assert "A1" in fx and fx["A1"].shape == (6, 6)
    raw = load_fixture("matlab_compat", simplify=False)
    assert raw["find_k"].shape == (6, 1)


def test_index_shift_roundtrip():
    k = np.array([[1.0, 3.0], [2.0, 5.0]])
    z = to0(k)
    assert z.dtype == np.int64 and z.tolist() == [[0, 2], [1, 4]]
    np.testing.assert_array_equal(to1(z), k)
    assert to1(z).dtype == np.float64
    cells = [np.array([1.0, 2.0]), np.array([4.0])]
    assert [c.tolist() for c in to0(cells)] == [[0, 1], [3]]
    assert to0(3.0) == 2
    with pytest.raises(ValueError):
        to0([1.5])
