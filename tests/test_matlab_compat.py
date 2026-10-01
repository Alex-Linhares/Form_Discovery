"""Parity of ``formdiscovery.matlab_compat`` with Octave's built-ins.

The fixture ``tests/fixtures/matlab_compat.mat`` comes from ``legacy/tests_octave/fx_matlab_compat.m``
(regenerate with ``python legacy/tools/gen_fixtures.py matlab_compat``). Octave indices are
1-based; the helpers return 0-based ones, so they are compared after ``to0``. The live test
reruns the script and checks the committed fixture is current.
"""

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import matlab_compat as mc
from formdiscovery.io import load_fixture, to0

FX = load_fixture("matlab_compat", simplify=False)


def cell(name):
    """A 1×K cell array from the fixture as a list of 1-D float arrays."""
    return [np.asarray(c, dtype=float).ravel() for c in FX[name].ravel()]


def vec(name):
    return np.asarray(FX[name], dtype=float).ravel()


def test_find_F_linear_and_rc():
    A = FX["find_A"]
    np.testing.assert_array_equal(mc.find_F(A), to0(vec("find_k")))
    i, j, v = mc.find_F(A, return_rc=True)
    np.testing.assert_array_equal(i, to0(vec("find_i")))
    np.testing.assert_array_equal(j, to0(vec("find_j")))
    np.testing.assert_array_equal(v, vec("find_v"))
    np.testing.assert_array_equal(mc.find_F([0, 1, 0, 1, 1]), to0(vec("find_row")))
    # column-major is not numpy's default order
    assert not np.array_equal(mc.find_F(A), np.flatnonzero(A))


def test_hist_centres():
    for x, c, n in zip(cell("hist_x"), cell("hist_c"), cell("hist_n")):
        np.testing.assert_array_equal(mc.hist_centres(x, c), n, err_msg=f"x={x} c={c}")
    z = vec("hist_z")
    np.testing.assert_array_equal(mc.hist_centres(z, np.arange(1, 7)), vec("hist_z_range"))
    np.testing.assert_array_equal(mc.hist_centres(z, np.unique(z)), vec("hist_z_unique"))


def test_hist_centres_edge_goes_up_as_in_matlab():
    # KI-13: MATLAB's histc puts 2.5 (edge between centres 2 and 3) in the upper bin;
    # Octave's hist puts it in the lower bin ([1 2 1]). The port follows MATLAB.
    np.testing.assert_array_equal(mc.hist_centres([1, 2, 2.5, 3], [1, 2, 3]), [1, 1, 2])


def test_hist_nbins_constant_even_follows_matlab():
    # MATLAB hist.m: miny = 5-2-0.5, maxy = 5+2-0.5 -> centres 3:6, all four 5s in bin 3.
    # (Octave centres them on 4:7 instead, so this case is not in the fixture.)
    np.testing.assert_array_equal(mc.hist_centres([5, 5, 5, 5], [4]), [0, 0, 4, 0])


@pytest.mark.parametrize("occ", ["first", "last"])
def test_unique_matlab(occ):
    a = vec("unique_a")
    b, i, j = mc.unique_matlab(a, occ)
    np.testing.assert_array_equal(b, vec("unique_b"))
    np.testing.assert_array_equal(i, to0(vec(f"unique_i_{occ}")))
    np.testing.assert_array_equal(j, to0(vec("unique_j")))


@pytest.mark.parametrize("occ", ["first", "last"])
def test_unique_rows(occ):
    b, i, j = mc.unique_rows(FX["urows_A"], occ)
    np.testing.assert_array_equal(b, FX["urows_b"])
    np.testing.assert_array_equal(i, to0(vec(f"urows_i_{occ}")))
    np.testing.assert_array_equal(j, to0(vec("urows_j")))


def test_unique_rows_judges_chunks():
    # scaledata.m:51 makechunks: chunk order is lexicographic row order of the mask
    from formdiscovery.io import load_dataset

    data = load_dataset("judges")
    b, _, j = mc.unique_rows((~np.isinf(data)).T.astype(float))
    np.testing.assert_array_equal(b, FX["judges_b"])
    np.testing.assert_array_equal(j, to0(vec("judges_j")))


@pytest.mark.parametrize("op", ["setdiff", "intersect", "union"])
def test_sorted_set_ops(op):
    f = getattr(mc, op)
    for a, b, want in zip(cell("set_a"), cell("set_b"), cell(op)):
        got = f(a, b)
        assert got.ndim == 1
        np.testing.assert_array_equal(got, want, err_msg=f"{op}({a}, {b})")


def test_mysetdiff_order_and_duplicates():
    for a, b, want in zip(cell("mys_a"), cell("mys_b"), cell("mys")):
        np.testing.assert_array_equal(mc.mysetdiff(a, b), want, err_msg=f"{a} \\ {b}")
    # works on 0-based indices too (0 would break the MATLAB bit-vector version)
    np.testing.assert_array_equal(mc.mysetdiff([0, 3, 0, 2], [2]), [0, 3, 0])


@pytest.mark.parametrize("suffix,A", [("", "chol_A"), ("b", "chol_B"), ("c", "chol_C")])
def test_chol_upper(suffix, A):
    U, p = mc.chol_upper(FX[A])
    assert p == int(vec(f"chol_p{suffix}")[0])
    np.testing.assert_allclose(U, FX[f"chol_U{suffix}"], rtol=1e-10, atol=1e-12)


def test_sparse_accum():
    e = to0(vec("sp_e"))
    np.testing.assert_array_equal(mc.sparse_accum(0, np.sort(e), 1).ravel(), vec("sp_counts"))
    got = mc.sparse_accum(to0(vec("sp_i")), to0(vec("sp_j")), vec("sp_v"), shape=(3, 4))
    np.testing.assert_array_equal(got, FX["sp_full"])


def test_median_matlab():
    got = [mc.median_matlab(x) for x in cell("med_x")]
    np.testing.assert_array_equal(got, vec("med"))  # NaN == NaN in assert_array_equal


def test_stable_argsort():
    for x, asc, desc in zip(cell("sort_x"), cell("sort_asc"), cell("sort_desc")):
        np.testing.assert_array_equal(mc.stable_argsort(x), to0(asc))
        np.testing.assert_array_equal(mc.stable_argsort(x, descending=True), to0(desc))


def test_max_first():
    for x, m, i in zip(cell("max_x"), vec("max_m"), vec("max_i")):
        gm, gi = mc.max_first(x)
        np.testing.assert_array_equal(gm, m)
        assert gi == int(i) - 1, x


@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "matlab_compat.mat"
    octave.feval("fx_matlab_compat", str(out), nout=0)
    new = loadmat(out)
    for k, v in FX.items():
        if k == "octave_version":
            continue
        a, b = v, new[k]
        if a.dtype == object:
            for x, y in zip(a.ravel(), b.ravel()):
                np.testing.assert_array_equal(x, y, err_msg=k)
        else:
            np.testing.assert_array_equal(a, b, err_msg=k)
