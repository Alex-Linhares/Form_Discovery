"""Parity of the L0-b functions (item 08) with Octave: ``util.stirling2``,
``util.dijkstra``, ``likelihood_feat.hessiangrad``, ``graph.get_edgemap``,
``graph.find_descendants``, ``graph.expand_graph``, and ``likelihood_rel.makehyps``,
``bbloglike``, ``bblikesumhyps``, ``dirmultloglike``.

The fixture ``tests/fixtures/l0b.mat`` comes from ``legacy/tests_octave/fx_l0b.m`` (regenerate with
``python legacy/tools/gen_fixtures.py l0b``). It covers the adjacency matrices of the six demo data
sets and of every final graph in the Octave baselines (``tests/fixtures/baseline``). The
live tests rerun the script (the committed fixture must be current) and compare on fresh
random inputs.
"""

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.graph import expand_graph, find_descendants, get_edgemap
from formdiscovery.io import load_fixture, to0
from formdiscovery.likelihood_feat import hessiangrad
from formdiscovery.likelihood_rel import bbloglike, bblikesumhyps, dirmultloglike, makehyps
from formdiscovery.util import dijkstra, stirling2

FX = load_fixture("l0b", simplify=False)
TOL = dict(rtol=1e-10, atol=1e-12)


def cell(name):
    """A cell array from the fixture as a flat list of float arrays (shapes kept)."""
    return [np.asarray(c) for c in FX[name].ravel()]


def names(name):
    return [str(c[0]) for c in FX[name].ravel()]


def ids(v):
    """A (possibly empty) 1-based index vector from the fixture, as 0-based ints."""
    return to0(np.asarray(v).ravel()).astype(np.int64)


ADJS = cell("adjs")
ADJNAMES = names("adjnames")


def hessfun(X, A, b, shape):
    """Python twin of ``legacy/tests_octave/l0b_hessfun.m``."""
    X = np.asarray(X, dtype=float).ravel()
    Y = 0.5 * X @ A @ X + b @ X + np.sum(np.sin(X)) + 0.25 * np.sum(X ** 4)
    g = A @ X + b + np.cos(X) + X ** 3
    return Y, g.reshape(tuple(int(s) for s in np.ravel(shape)), order="F")


# --- stirling2 ---------------------------------------------------------------------------

def test_stirling2_exact():
    for (n, m), want in zip(FX["s2_nm"], cell("s2")):
        got = stirling2(n, m)
        if n <= 0 or m <= 0:
            assert got.size == 0 and want.size == 0
            continue
        assert got.shape == want.shape, (n, m)
        np.testing.assert_array_equal(got, want, err_msg=f"stirling2({n},{m})")


def test_stirling2_40_is_bit_identical_and_rounds_like_matlab():
    s2 = stirling2(40, 40)
    want = cell("s2")[0]
    assert np.array_equal(s2.view(np.int64), want.view(np.int64))  # bit for bit
    assert s2[7, 2] == 966 and s2[39, 0] == 1 and s2[39, 39] == 1 and s2[2, 5] == 0
    assert s2.max() > 2 ** 53  # large entries are rounded floats, as in MATLAB


# --- hessiangrad ------------------------------------------------------------------------

def test_hessiangrad():
    A, b = FX["hg_A"], FX["hg_b"].ravel()
    for X, e, shape, want in zip(cell("hg_X"), FX["hg_e"].ravel(), cell("hg_shape"),
                                 cell("hg_H")):
        got = hessiangrad(hessfun, X, e, A, b, shape)
        assert got.shape == want.shape
        np.testing.assert_allclose(got, want, rtol=1e-9, atol=1e-9)
    # length(dY) rows: a 2x2 gradient fails in both languages
    assert FX["hg_matrix_err"] == 1
    with pytest.raises(ValueError):
        hessiangrad(hessfun, cell("hg_X")[0], 1e-5, A, b, [2, 2])


# --- dijkstra ------------------------------------------------------------------------------

def test_dijkstra_matches_octave():
    """KI-6 pin: all-pairs distances on every demo/baseline/constructed matrix."""
    assert len(ADJS) > 200
    for A, want, nm in zip(ADJS, cell("dijk"), ADJNAMES):
        got = dijkstra(A)
        assert got.shape == want.shape, nm
        np.testing.assert_allclose(got, want, **TOL, err_msg=nm)


def test_dijkstra_subsets():
    for k, s, t, want in zip(FX["dst_k"].ravel(), cell("dst_s"), cell("dst_t"), cell("dst")):
        A = ADJS[int(k) - 1]
        got = dijkstra(A, ids(s), ids(t) if t.size else None)
        assert got.shape == want.shape, ADJNAMES[int(k) - 1]
        np.testing.assert_allclose(got, want, **TOL)


def test_dijkstra_errors_and_paths():
    assert np.all(FX["dijk_err"] == 1)
    R = ADJS[ADJNAMES.index("rand_nan")]
    for args in ((np.ones((2, 3)),), (np.array([[0, -1], [1, 0]]),), (R, [9]), (R, [0], [-1])):
        with pytest.raises(FormDiscoveryError):
            dijkstra(*args)
    with pytest.raises(NotImplementedError):
        dijkstra(R, paths=True)


# --- get_edgemap --------------------------------------------------------------------------

def test_get_edgemap_both_modes():
    for A, want, wsym, nm in zip(ADJS, cell("emap"), cell("emapsym"), ADJNAMES):
        np.testing.assert_array_equal(get_edgemap(A), want, err_msg=nm)
        np.testing.assert_array_equal(get_edgemap(A, sym=1), wsym, err_msg=nm)


def test_get_edgemap_is_column_major():
    A = np.array([[0, 1], [1, 0]])
    np.testing.assert_array_equal(get_edgemap(A), [[0, 2], [1, 0]])
    np.testing.assert_array_equal(get_edgemap(A, sym=1), [[0, 1], [1, 0]])


# --- find_descendants ------------------------------------------------------------------

def test_find_descendants():
    fdn = names("fd_names")
    assert len(fdn) > 50
    for A, want, n, nm in zip(cell("fd_adj"), FX["fd"].ravel(), FX["fd_len"].ravel(), fdn):
        assert n == A.shape[0], nm  # every node gets a cell entry in these inputs
        got = find_descendants(A)
        assert len(got) == A.shape[0], nm
        for i, (g, w) in enumerate(zip(got, want.ravel())):
            np.testing.assert_array_equal(g, ids(w), err_msg=f"{nm} node {i}")
            assert g.ndim == 1


def test_find_descendants_repro_and_cycle():
    d = find_descendants([[0, 1, 1], [0, 0, 0], [0, 0, 0]])  # item 03b repro
    np.testing.assert_array_equal(np.concatenate([[0], d[0]]), [0, 1, 2])
    # KI-15: MATLAB never returns here (node 1 waits for node 0, which waits for node 1)
    with pytest.raises(FormDiscoveryError):
        find_descendants([[0, 1, 0], [1, 0, 1], [0, 0, 0]])
    # no leaves at all: the queue starts empty, every entry stays empty (both languages)
    assert all(x.size == 0 for x in find_descendants([[0, 1], [1, 0]]))


# --- expand_graph ------------------------------------------------------------------------

def test_expand_graph():
    for adj, zs, want, oc in zip(cell("eg_adj"), FX["eg_zs"].ravel(), cell("eg_new"),
                                 FX["eg_objcount"].ravel()):
        got, objcount = expand_graph(adj, [ids(z) for z in zs.ravel()], "x")
        assert objcount == oc
        np.testing.assert_array_equal(got, want)
    with pytest.raises(FormDiscoveryError):
        expand_graph(np.zeros((2, 3)), [[0], [1]])
    with pytest.raises(FormDiscoveryError):
        expand_graph(np.zeros((2, 2)), [[0]])


# --- relational likelihood building blocks ----------------------------------------------

def test_makehyps():
    for p, s, a, b in zip(cell("mh_props"), cell("mh_sums"), cell("mh_alphas"),
                          cell("mh_betas")):
        ga, gb = makehyps(p, s)
        np.testing.assert_allclose(ga, a.ravel(), **TOL)
        np.testing.assert_allclose(gb, b.ravel(), **TOL)


def test_bbloglike():
    got = bbloglike(FX["bb_alpha"], FX["bb_beta"], FX["bb_ns"], FX["bb_ys"])
    np.testing.assert_allclose(got, FX["bb_mat"].ravel(), **TOL)
    al, be = FX["bs_al"].ravel(), FX["bs_be"].ravel()
    # a column (1-D) sums to a scalar; a 1-row matrix is not reduced (sum(..., 1))
    col = bbloglike(al, be, np.full(25, 10.0), np.full(25, 3.0))
    np.testing.assert_allclose(col, FX["bb_col"].ravel()[0], **TOL)
    row = bbloglike(al[None, :], be[None, :], np.full((1, 25), 10.0), np.full((1, 25), 3.0))
    np.testing.assert_allclose(row, FX["bb_row"].ravel(), **TOL)


def test_bblikesumhyps():
    hyps = {1: (FX["bs_al"], FX["bs_be"]), 2: (FX["bs_aln"], FX["bs_ben"])}
    for ys, ns, h, want in zip(cell("bs_ys"), cell("bs_ns"), FX["bs_hyp"].ravel(),
                               FX["bs"].ravel()):
        got = bblikesumhyps(ys, ns, *hyps[int(h)])
        assert isinstance(got, float)
        np.testing.assert_allclose(got, want, **TOL)


def test_dirmultloglike():
    for a, c, want in zip(cell("dm_alpha"), cell("dm_counts"), cell("dm")):
        got = np.atleast_1d(dirmultloglike(a, c))
        np.testing.assert_allclose(got, want.ravel(), **TOL)


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "l0b.mat"
    octave.feval("fx_l0b", str(out), nout=0)
    new = loadmat(out)

    def same(a, b, k):
        if a.dtype == object:
            assert a.shape == b.shape, k
            for x, y in zip(a.ravel(), b.ravel()):
                same(np.asarray(x), np.asarray(y), k)
        else:
            np.testing.assert_array_equal(a, b, err_msg=k)

    for k, v in FX.items():
        if k != "octave_version":
            same(v, new[k], k)


@pytest.mark.octave
def test_live_random_parity(octave):
    rng = np.random.default_rng(20260930)
    for n in (5, 11):
        W = rng.random((n, n)) * (rng.random((n, n)) > 0.5)
        np.fill_diagonal(W, 0)
        np.testing.assert_allclose(dijkstra(W), octave.dijkstra(W), **TOL)
        np.testing.assert_array_equal(get_edgemap(W), octave.get_edgemap(W))
        np.testing.assert_array_equal(get_edgemap(W, sym=1),
                                      octave.get_edgemap(W, "sym", 1.0))
        dag = np.triu(rng.random((n, n)) > 0.6, 1).astype(float)
        want = octave.find_descendants(dag)
        want = list(np.asarray(want, dtype=object).ravel())
        got = find_descendants(dag)
        for i, g in enumerate(got):
            w = np.asarray(want[i], dtype=float).ravel() if i < len(want) else np.empty(0)
            np.testing.assert_array_equal(g, ids(w))
    props, sums = rng.random(4), 2.0 ** rng.integers(-3, 5, 3)
    a, b = makehyps(props, sums)
    oa, ob = octave.makehyps(props[None, :], sums[None, :], nout=2)
    np.testing.assert_allclose(a, np.ravel(oa), **TOL)
    np.testing.assert_allclose(b, np.ravel(ob), **TOL)
    ns = rng.integers(0, 30, 9).astype(float)
    ys = np.floor(rng.random(9) * (ns + 1))
    np.testing.assert_allclose(
        bblikesumhyps(ys, ns, a, b),
        octave.bblikesumhyps(ys[:, None], ns[:, None], a[:, None], b[:, None]), **TOL)
    al = rng.random((4, 6)) * 2
    c = rng.integers(0, 5, (4, 6)).astype(float)
    np.testing.assert_allclose(dirmultloglike(al, c), np.ravel(octave.dirmultloglike(al, c)),
                               **TOL)
    np.testing.assert_array_equal(stirling2(25, 30), octave.stirling2(25.0, 30.0))
