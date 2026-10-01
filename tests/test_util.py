"""Parity of ``formdiscovery.util`` / ``formdiscovery.weights`` (item 07, L0-a) with Octave.

The fixture ``tests/fixtures/util.mat`` comes from ``legacy/tests_octave/fx_util.m`` (regenerate
with ``python legacy/tools/gen_fixtures.py util``). Indices are compared after ``to0``. The live
tests rerun the script (the committed fixture must be current) and compare the Python port
with Octave on fresh random inputs.
"""

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery import util as U
from formdiscovery.io import load_fixture, to0
from formdiscovery.weights import weightprior

FX = load_fixture("util", simplify=False)
TOL = dict(rtol=1e-10, atol=1e-12)


def cell(name):
    """A cell array from the fixture as a flat list of float arrays (shapes kept)."""
    return [np.asarray(c) for c in FX[name].ravel()]


def scalars(name):
    return np.asarray(FX[name], dtype=float).ravel()


def test_vec_is_column_major():
    for a, v in (("vec_a", "vec_v"), ("vec_a3", "vec_v3")):
        np.testing.assert_array_equal(U.vec(FX[a]), FX[v].ravel())
    assert not np.array_equal(U.vec(FX["vec_a"]), FX["vec_a"].ravel())


def test_inv_triu_inv_posdef_logdet_on_spd():
    spd = cell("spd")
    for k, (A, Uo, iU, iA) in enumerate(zip(spd, cell("chol_U"), cell("inv_triu"),
                                           cell("inv_posdef"))):
        np.testing.assert_allclose(U.inv_triu(Uo), iU, **TOL, err_msg=f"case {k}")
        np.testing.assert_allclose(U.inv_posdef(A), iA, **TOL, err_msg=f"case {k}")
    np.testing.assert_allclose([U.logdet(A) for A in spd], scalars("logdet"), **TOL)
    np.testing.assert_allclose([U.mylogdet(A) for A in spd], scalars("mylogdet"), **TOL)
    assert all(isinstance(U.mylogdet(A), float) for A in spd)


def test_chol_reads_upper_triangle_only():
    # spd{5} is spd{2} with its strict lower triangle overwritten (fx_util.m)
    spd = cell("spd")
    assert not np.allclose(spd[4], spd[4].T)
    np.testing.assert_allclose(U.logdet(spd[4]), U.logdet(spd[1]), **TOL)
    np.testing.assert_allclose(U.inv_posdef(spd[4]), U.inv_posdef(spd[1]), **TOL)


def test_logdet_ill_conditioned():
    np.testing.assert_allclose(U.logdet(FX["hilb"]), scalars("hilb_logdet")[0], rtol=1e-10)
    np.testing.assert_allclose(U.mylogdet(FX["hilb"]), scalars("hilb_mylogdet")[0], rtol=1e-10)


def test_mylogdet_fallback_replicates_complex_log_det():
    # KI-12: chol fails -> log(det(A)); complex when det < 0, which graph_like_conn.m:90
    # detects with isreal.
    for k, (A, y, isreal) in enumerate(zip(cell("npd"), cell("npd_logdet"),
                                           scalars("npd_isreal"))):
        got = U.mylogdet(A)
        want = y.ravel()[0]
        assert isinstance(got, complex) == (not isreal), f"case {k}"
        if np.isinf(want):
            assert got == want
        else:
            np.testing.assert_allclose(got, want, **TOL, err_msg=f"case {k}")


def test_logdet_and_inv_posdef_raise_on_non_pd():
    assert np.all(scalars("npd_logdet_err") == 1)
    for A in cell("npd"):
        with pytest.raises(FormDiscoveryError):
            U.logdet(A)
        with pytest.raises(FormDiscoveryError):
            U.inv_posdef(A)


def test_sumlogs_meanlogs():
    for k, (x, s, m) in enumerate(zip(cell("logs_x"), cell("sumlogs"), cell("meanlogs"))):
        for f, want in ((U.sumlogs, s), (U.meanlogs, m)):
            got = np.atleast_1d(f(x))
            np.testing.assert_allclose(got, want.ravel(), **TOL, err_msg=f"{f.__name__} {k}")
    # vectors of either orientation reduce to a float; a matrix gives per-column values
    assert isinstance(U.sumlogs(cell("logs_x")[1]), float)
    assert U.sumlogs(cell("logs_x")[-1]).shape == (3,)


def test_sumlogs_is_stable():
    assert U.sumlogs([1000.0, 1000.0]) == pytest.approx(1000 + np.log(2), rel=1e-14)
    assert U.meanlogs([-1e4, -1e4]) == pytest.approx(-1e4, rel=1e-14)


def test_mysetdiff():
    for a, b, c in zip(cell("msd_a"), cell("msd_b"), cell("msd")):
        np.testing.assert_array_equal(U.mysetdiff(a, b), c.ravel(), err_msg=f"{a} \\ {b}")
    # 0-based ids work too (the MATLAB version needs positive integers)
    np.testing.assert_array_equal(U.mysetdiff([0, 3, 1, 0], [1]), [0, 3, 0])


def test_subv2ind():
    for k, (siz, subv, ndx) in enumerate(zip(cell("s2i_siz"), cell("s2i_subv"), cell("s2i"))):
        got = U.subv2ind(siz, to0(subv) if subv.size else subv)
        assert got.dtype.kind == "i"
        np.testing.assert_array_equal(got, to0(ndx.ravel()), err_msg=f"case {k}")
    np.testing.assert_array_equal(U.subv2ind([], [0, 1, 2]), to0(FX["s2i_emptysiz"].ravel()))
    # matches numpy's Fortran-order ravel_multi_index on in-range subscripts
    sub = np.array([[0, 0, 0], [2, 3, 1], [1, 0, 1]])
    np.testing.assert_array_equal(U.subv2ind([3, 4, 2], sub),
                                  np.ravel_multi_index(sub.T, (3, 4, 2), order="F"))


def test_trans2orig():
    a, b = U.trans2orig(FX["t2o_P"], FX["t2o_S"])
    np.testing.assert_allclose(a, FX["t2o_alpha"], **TOL)
    np.testing.assert_allclose(b, FX["t2o_beta"], **TOL)


def test_matrixpartition_triplepartition():
    J = FX["part_J"]
    for n, blocks in zip(scalars("mp_n"), FX["mp"]):
        for got, want in zip(U.matrixpartition(J, n), blocks):
            assert got.shape == want.shape, f"n={n}"
            np.testing.assert_array_equal(got, want)
    for (nobs, nmiss), blocks in zip(FX["tp_n"], FX["tp"]):
        for got, want in zip(U.triplepartition(J, nobs, nmiss), blocks):
            assert got.shape == want.shape, f"nobs={nobs} nmiss={nmiss}"
            np.testing.assert_array_equal(got, want)
    A, *_ = U.matrixpartition(J, 4)
    A[0, 0] = -1  # copies, not views
    assert J[0, 0] != -1


def test_weightprior():
    got = [weightprior(w, b) for w, b in zip(cell("wp_w"), scalars("wp_beta"))]
    np.testing.assert_allclose(got, scalars("wp"), **TOL)
    assert weightprior([], 0.4) == 0.0


@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "util.mat"
    octave.feval("fx_util", str(out), nout=0)
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


@pytest.mark.octave
def test_live_random_parity(octave):
    rng = np.random.default_rng(20260929)
    for n in (2, 5, 13):
        X = rng.standard_normal((n, n + 3))
        A = X @ X.T + 0.1 * np.eye(n)
        np.testing.assert_allclose(U.inv_posdef(A), octave.inv_posdef(A), rtol=1e-9, atol=1e-12)
        np.testing.assert_allclose(U.logdet(A), octave.logdet(A), **TOL)
        B = A - (np.linalg.eigvalsh(A)[0] + 0.5) * np.eye(n)  # one negative eigenvalue
        want = complex(np.asarray(octave.mylogdet(B)).ravel()[0])
        got = U.mylogdet(B)
        assert isinstance(got, complex) == (want.imag != 0)
        np.testing.assert_allclose(got, want, **TOL)
    x = rng.standard_normal((1, 40)) * 30
    np.testing.assert_allclose(U.sumlogs(x), octave.sumlogs(x), **TOL)
    np.testing.assert_allclose(U.meanlogs(x.T), octave.meanlogs(x.T), **TOL)
    w = np.exp(rng.standard_normal((17, 1)))
    np.testing.assert_allclose(weightprior(w, 0.4), octave.weightprior(w, 0.4), **TOL)
    siz = np.array([[3.0, 5.0, 2.0, 4.0]])
    sub = np.column_stack([rng.integers(0, s, 30) for s in siz.ravel().astype(int)])
    want = np.asarray(octave.subv2ind(siz, (sub + 1).astype(float))).ravel()
    np.testing.assert_array_equal(U.subv2ind(siz, sub), to0(want))
