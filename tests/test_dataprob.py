"""Parity of ``likelihood_feat.inv_covariance``, ``gplike`` and ``dataprobwsig`` (item 16,
L3-a1; the missing-data chunk path is item 17, ``test_dpmiss.py``) with Octave, and the
analytic gradient against finite differences (``checkgrad``).

The fixture ``tests/fixtures/dataprob.mat`` comes from ``tests/octave/fx_dataprob.m``
(regenerate with ``python tools/gen_fixtures.py dataprob``):

- ``gr``: 29 graphs over 10 objects with random weights (one-cluster graphs, seeded
  ``split_node`` sequences for chain, ring, tree, hierarchy, partition, connected, grid
  and cylinder, and two graphs with unassigned objects);
- ``dat``/``cs``: per graph, 7 data variants (``variants``: feature data via ``d*d'`` or
  ``runps.SS``, similarity data, ``zglreg``, and 7 observed rows of 10 for the
  ``nmiss > 0`` branch) in tying mode 1 and 'feat'/'miss' in the other 7 modes. Each case
  stores ``dataprobwsig``'s three outputs (and the one-output value), Octave's
  ``checkgrad`` value, ``inv_covariance`` of the combined graph and ``gplike``, or
  Octave's error message;
- ``ic``: ``inv_covariance`` on random weight matrices with isolated ('hole') nodes;
- ``bl``: ``dataprobwsig`` calls captured by a spy while re-running the chain, ring and
  tree feature baselines (every 97th call).

Tolerances (PLAN.md §2): rtol 1e-10 for values and gradients. The finite-difference
check uses ``e = 1e-5`` as ``graph_like_conn.m:45`` does.
"""

from collections import Counter

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, load_fixture
from formdiscovery.likelihood_feat import dataprobwsig, gplike, hessiangrad, inv_covariance
from formdiscovery.params import Params, RunPs
from formdiscovery.util import inv_posdef
from tests.helpers import assert_graph_equal, checkgrad

FX = load_fixture("dataprob")
PS = Params.default().replace(missingdata=0, overrideSS=0)
MODES = [tuple(int(x) for x in m) for m in np.atleast_2d(FX["modes"])]
VARIANTS = [str(v) for v in FX["variants"]]
GRAPHS = [graph_from_mat(g["graph"]) for g in FX["gr"]]
OK = [r for r in FX["cs"] if not np.size(r["err"])]
FD_TOL = 1e-6  # Octave's checkgrad reaches at most ~1e-9 on the fixture


def _vec(x):
    return np.atleast_1d(np.asarray(x, dtype=float)).ravel()


def _err(x):
    return str(x) if np.size(x) else ""


def _case_ps(mode, variant, nobj=10, simdim=30, SS=None):
    fa, fi, fe, pt = mode
    runps = RunPs(type="feat", chunkcount=-1, SS=None)
    if variant in ("sim", "simmiss"):
        runps.type, runps.dim = "sim", simdim
    if variant == "featSS":
        runps.chunkcount, runps.SS = nobj, np.atleast_2d(SS)
    return PS.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt,
                      zglreg=int(variant in ("featz", "missz")), runps=runps)


def case_inputs(r, fx=FX, graphs=GRAPHS):
    g = graphs[int(r["graph"]) - 1]
    dat = fx["dat"][int(r["data"]) - 1]
    variant = VARIANTS[int(r["variant"]) - 1]
    ps = _case_ps(MODES[int(r["mode"]) - 1], variant, SS=dat["SS"])
    return g, np.atleast_2d(np.asarray(dat["d"], dtype=float)), ps, variant


def _msg(r):
    return f"graph {int(r['graph'])} mode {int(r['mode'])} {VARIANTS[int(r['variant']) - 1]}"


def assert_vec(a, b, msg=""):
    b = _vec(b)
    assert a.ndim == 1 and len(a) == len(b), f"{msg}: length {len(a)} != {len(b)}"
    np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-10, err_msg=msg)


def _expect_error(octmsg, fn, degenerate=False):
    """Python raises where Octave errored, with a matching kind of message.

    ``degenerate``: the graph has fewer counted objects than ``d`` has rows (the
    unassigned-object graphs), so ``nmiss < 0`` and l.155-236 slice overlapping blocks;
    ``Y`` (l.172) is then singular (smallest eigenvalue ~4e-16), and whether ``chol``
    fails there or a later product is nonconformant depends on rounding. Either error
    is accepted."""
    with pytest.raises(FormDiscoveryError) as exc:
        fn()
    if degenerate and ("chol" in octmsg or "nonconformant" in octmsg):
        assert "positive definite" in str(exc.value) or "nonconformant" in str(exc.value)
    elif "chol" in octmsg:
        assert "positive definite" in str(exc.value)
    elif "out of bound" in octmsg:
        assert "out of bound" in str(exc.value)
    elif "nonconformant" in octmsg:
        assert "nonconformant" in str(exc.value)
    else:  # pragma: no cover
        raise AssertionError(f"unexpected Octave error {octmsg!r}")


def check_case(r, fx=FX, graphs=GRAPHS):
    g, d, ps, _ = case_inputs(r, fx, graphs)
    msg = _msg(r)
    Wvec = _vec(r["Wvec"])
    if _err(r["err"]):
        _expect_error(_err(r["err"]), lambda: dataprobwsig(Wvec, d, g, ps),
                      degenerate=g.objcount < d.shape[0])
    else:
        ll, dW, dWp = dataprobwsig(Wvec, d, g, ps)
        np.testing.assert_allclose(ll, float(r["ll"]), rtol=1e-10, err_msg=msg)
        assert_vec(dW, r["dW"], msg + " dWvec")
        assert_vec(dWp, r["dWp"], msg + " dWvecprior")
        np.testing.assert_allclose(dataprobwsig(Wvec, d, g, ps, nargout=1), float(r["ll1"]),
                                   rtol=1e-10, err_msg=msg)
    if not np.size(r["Wvec"]):
        return
    from formdiscovery.weights import combineWs
    if _err(r["gperr"]):
        def run():
            cw = combineWs(g, np.exp(Wvec[1:]), ps)
            J, _ = inv_covariance(cw.Wsym, g.objcount, np.exp(Wvec[0]), ps)
            gplike(d, inv_posdef(J), 0, ps)
        _expect_error(_err(r["gperr"]), run)
        return
    cw = combineWs(g, np.exp(Wvec[1:]), ps)
    J, L = inv_covariance(cw.Wsym, g.objcount, np.exp(Wvec[0]), ps)
    np.testing.assert_allclose(J, np.atleast_2d(r["J"]), rtol=1e-10, atol=1e-12, err_msg=msg)
    np.testing.assert_allclose(L, np.atleast_2d(r["L"]), rtol=1e-10, atol=1e-12, err_msg=msg)
    dim = ps.runps.dim if ps.runps.type == "sim" else d.shape[1]
    np.testing.assert_allclose(gplike(d, inv_posdef(J), dim, ps), float(r["gp"]), rtol=1e-10,
                               err_msg=msg)


# --- fixture contents ---------------------------------------------------------------------

def test_fixture_contents():
    assert len(FX["gr"]) == 29 and len(FX["cs"]) == 29 * (7 + 7 * 2) and len(FX["ic"]) == 24
    assert VARIANTS == ["feat", "featSS", "sim", "featz", "miss", "simmiss", "missz"]
    assert len(OK) == 514
    errs = Counter(_err(r["err"]).split(":")[0] for r in FX["cs"] if _err(r["err"]))
    assert errs == {"chol": 83, "G(10,_)": 11, "operator *": 1}
    # every tying mode and variant has error-free cases
    assert {(int(r["mode"]), int(r["variant"])) for r in OK} == {
        (m, v) for m in range(1, 9) for v in ([1, 2, 3, 4, 5, 6, 7] if m == 1 else [1, 5])}
    assert sum(g.ncomp == 2 for g in GRAPHS) >= 8
    assert sum(g.adj.shape[0] - g.objcount >= 8 for g in GRAPHS) >= 4


def test_hole_hack_is_exercised():
    """inv_covariance.m:24-26: a single hole (partition:3, an empty cluster) scores fine;
    two holes make J singular, the source of the 'chol' errors for partition:4-6."""
    single = multi = 0
    for r in FX["cs"]:
        if not np.size(r["J"]) and not _err(r["gperr"]):
            continue
        g, _, ps, _ = case_inputs(r)
        from formdiscovery.weights import combineWs
        try:
            cw = combineWs(g, np.exp(_vec(r["Wvec"])[1:]), ps)
        except FormDiscoveryError:
            continue
        nh = int(np.sum(np.sum(cw.Wsym != 0, axis=0) == 0))
        single += nh == 1 and not _err(r["err"])
        multi += nh >= 2 and "chol" in _err(r["err"])
    assert single >= 10 and multi >= 30


# --- inv_covariance -----------------------------------------------------------------------

@pytest.mark.parametrize("k", range(24))
def test_inv_covariance(k):
    r = FX["ic"][k]
    ps = PS.replace(zglreg=int(r["zglreg"]))
    J, L = inv_covariance(np.atleast_2d(r["W"]), int(r["nobj"]), float(r["sigma"]), ps)
    np.testing.assert_allclose(J, np.atleast_2d(r["J"]), rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(L, np.atleast_2d(r["L"]), rtol=1e-10, atol=1e-12)


def test_inv_covariance_holes_block():
    W = np.zeros((5, 5))
    W[0, 3] = W[3, 0] = 2.0
    W[1, 3] = W[3, 1] = 1.0
    J, _ = inv_covariance(W, 3, 0.5, PS)
    holes = [2, 4]
    np.testing.assert_array_equal(J[np.ix_(holes, holes)], np.ones((2, 2)))
    assert np.linalg.matrix_rank(J) == 4


# --- dataprobwsig / gplike / inv_covariance on the cases ----------------------------------

@pytest.mark.parametrize("variant", range(1, 8), ids=lambda v: ["feat", "featSS", "sim",
                         "featz", "miss", "simmiss", "missz"][v - 1])
def test_cases(variant):
    rs = [r for r in FX["cs"] if int(r["variant"]) == variant]
    assert rs
    for r in rs:
        check_case(r)


def test_one_output_equals_first_output():
    for r in OK:
        assert float(r["ll1"]) == float(r["ll"])


def test_featSS_uses_runps_SS():
    """gplike.m:45-46 and dataprobwsig.m:67-69 read ps.runps.SS, not d*d'/dim."""
    r = next(r for r in OK if VARIANTS[int(r["variant"]) - 1] == "featSS")
    g, d, ps, _ = case_inputs(r)
    Wvec = _vec(r["Wvec"])
    ll = dataprobwsig(Wvec, d, g, ps, nargout=1)
    ll2 = dataprobwsig(Wvec, d, g, ps.replace(overrideSS=1), nargout=1)
    ps3 = ps.replace(runps=RunPs(type="feat", chunkcount=-1))
    ll3 = dataprobwsig(Wvec, d, g, ps3, nargout=1)
    assert ll != ll3 and abs(ll - float(r["ll"])) < 1e-8 * abs(ll)
    # overrideSS only switches gplike; the gradient's SS still comes from runps.SS
    assert ll2 == pytest.approx(ll3, rel=1e-12)


def test_two_outputs():
    """nargout=2 returns (ll, dWvec), as graph_like_conn's fminunc call asks for (the
    missing-data chunk path is tested in test_dpmiss.py)."""
    r = OK[0]
    g, d, ps, _ = case_inputs(r)
    ll, dW = dataprobwsig(_vec(r["Wvec"]), d, g, ps, nargout=2)
    assert ll == float(r["ll"]) or abs(ll - float(r["ll"])) < 1e-10 * abs(ll)
    assert_vec(dW, r["dW"], "nargout 2")


def test_inputs_not_mutated():
    for r in OK[::25]:
        g, d, ps, _ = case_inputs(r)
        g0, d0, ps0 = g.copy(), d.copy(), ps.copy()
        Wvec = _vec(r["Wvec"])
        W0 = Wvec.copy()
        dataprobwsig(Wvec, d, g, ps)
        assert_graph_equal(g, g0, rtol=0, atol=0)
        np.testing.assert_array_equal(d, d0)
        np.testing.assert_array_equal(Wvec, W0)
        assert repr(ps) == repr(ps0)


def test_hessiangrad_accepts_dataprobwsig():
    """graph_like_conn.m:81 feeds dataprobwsig to hessiangrad; its Hessian of -log P is
    symmetric up to finite-difference error."""
    r = next(r for r in OK if int(r["mode"]) == 1 and int(r["variant"]) == 1
             and len(_vec(r["Wvec"])) >= 5)
    g, d, ps, _ = case_inputs(r)
    H = hessiangrad(lambda x: dataprobwsig(x, d, g, ps)[:2], _vec(r["Wvec"]), 1e-5)
    assert H.shape == (len(_vec(r["Wvec"])),) * 2
    np.testing.assert_allclose(H, H.T, rtol=1e-4, atol=1e-4 * np.abs(H).max())


# --- finite-difference gradient check (checkgrad) -----------------------------------------

def test_octave_checkgrad_values():
    cg = np.array([float(r["cg"]) for r in OK])
    assert len(cg) == len(OK) and cg.max() < FD_TOL


@pytest.mark.parametrize("mode", range(1, 9), ids=lambda m: "fa%d-fi%d-fe%d-pt%d" % MODES[m - 1])
def test_checkgrad(mode):
    """The analytic gradient matches central differences on every error-free case, in
    every tying mode, for both gradient branches (nmiss == 0 and nmiss > 0)."""
    n = 0
    for r in OK:
        if int(r["mode"]) != mode:
            continue
        g, d, ps, _ = case_inputs(r)
        dval, dy, dh = checkgrad(lambda x: dataprobwsig(x, d, g, ps)[:2], _vec(r["Wvec"]),
                                 1e-5)
        assert dval < FD_TOL, (_msg(r), dval, dy, dh)
        n += 1
    assert n >= 20


def test_checkgrad_detects_a_wrong_gradient():
    r = OK[0]
    g, d, ps, _ = case_inputs(r)

    def bad(x):
        ll, dW, _ = dataprobwsig(x, d, g, ps)
        dW = dW.copy()
        dW[0] *= 1.01
        return ll, dW

    assert checkgrad(bad, _vec(r["Wvec"]), 1e-5)[0] > 1e-4


# --- spied baseline runs ------------------------------------------------------------------

def _bl_ps(q):
    q = {k: (np.asarray(v).item() if np.size(v) == 1 and not isinstance(v, str) else v)
         for k, v in q.items()}
    runps = RunPs(type=str(q["type"]), dim=q["dim"] if np.size(q["dim"]) else None,
                  SS=np.atleast_2d(np.asarray(q["SS"], dtype=float)),
                  chunkcount=q["chunkcount"])
    return PS.replace(lbeta=q["lbeta"], sigbeta=q["sigbeta"], missingdata=int(q["missingdata"]),
                      zglreg=int(q["zglreg"]), overrideSS=int(q["overrideSS"]),
                      fixedall=int(q["fixedall"]), fixedinternal=int(q["fixedinternal"]),
                      fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]),
                      runps=runps)


def bl_inputs(b, fx=FX):
    d = fx["bl_data"][int(b["run"]) - 1] if int(b["dsame"]) else b["d"]
    return (_vec(b["Wvec"]), np.atleast_2d(np.asarray(d, dtype=float)),
            graph_from_mat(b["graph"]), _bl_ps(b["ps"]))


def check_bl(b, fx=FX):
    Wvec, d, g, ps = bl_inputs(b, fx)
    msg = f"run {int(b['run'])} call {int(b['n'])}"
    if int(b["nargout"]) > 1:
        ll, dW, dWp = dataprobwsig(Wvec, d, g, ps)
        assert_vec(dW, b["dW"], msg + " dWvec")
        assert_vec(dWp, b["dWp"], msg + " dWvecprior")
    else:
        ll = dataprobwsig(Wvec, d, g, ps, nargout=1)
    np.testing.assert_allclose(ll, float(b["ll"]), rtol=1e-10, err_msg=msg)


def test_spied_runs_match_baseline():
    """The spy does not change the runs: final scores equal the committed baselines."""
    feat = loadmat(FIXTURES_DIR / "baseline" / "feat" / "resultsdemo.mat")["modellike"]
    for r, name in enumerate(["chain", "ring", "tree"]):
        s = PS.structures.index(name)
        np.testing.assert_allclose(FX["bl_ll"][r], feat[s, r], rtol=1e-10,
                                   err_msg=FX["bl_run"][r])


def test_baseline_calls():
    assert len(FX["bl"]) == 36
    assert sum(int(b["nargout"]) > 1 for b in FX["bl"]) >= 6
    assert all(not int(b["ps"]["missingdata"]) for b in FX["bl"])
    for b in FX["bl"]:
        check_bl(b)


def test_baseline_checkgrad():
    """Near the optimum the gradient norm is < 1 while ll ~ 1e4, so checkgrad's relative
    measure is dominated by finite-difference error (it shrinks as e^2 from e = 1e-3 to
    1e-5); accept either d < FD_TOL or an absolute error below 1e-9 |ll|."""
    worst = 0.0
    for b in FX["bl"]:
        Wvec, d, g, ps = bl_inputs(b)
        dval, dy, dh = checkgrad(lambda x: dataprobwsig(x, d, g, ps)[:2], Wvec, 1e-5)
        err = np.linalg.norm(dh - dy) / abs(float(b["ll"]))
        assert dval < FD_TOL or err < 1e-9, (int(b["run"]), int(b["n"]), dval, err)
        worst = max(worst, dval)
    assert worst > FD_TOL  # the near-optimum case the absolute bound is for is present


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "dataprob.mat"
    octave.eval(f"fx_dataprob('{out}');", nout=0)
    new = load_fixture("dataprob", fixtures_dir=tmp_path)
    for key in ("gr", "cs", "ic", "bl"):
        assert len(new[key]) == len(FX[key])
    for a, b in zip(new["cs"], FX["cs"]):
        np.testing.assert_array_equal(_vec(a["Wvec"]), _vec(b["Wvec"]))
        np.testing.assert_array_equal(_vec(a["ll"]), _vec(b["ll"]))
        np.testing.assert_array_equal(_vec(a["dW"]), _vec(b["dW"]))
        assert _err(a["err"]) == _err(b["err"])
    np.testing.assert_allclose(new["bl_ll"], FX["bl_ll"], rtol=1e-12)


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    """Fresh split sequences, weights and data; every case matches and passes checkgrad."""
    out = tmp_path / "dataprob.mat"
    octave.eval(f"fx_dataprob('{out}', 7919);", nout=0)
    new = load_fixture("dataprob", fixtures_dir=tmp_path)
    graphs = [graph_from_mat(g["graph"]) for g in new["gr"]]
    nok = 0
    for r in new["cs"]:
        check_case(r, new, graphs)
        if not _err(r["err"]):
            g, d, ps, _ = case_inputs(r, new, graphs)
            f = lambda x: dataprobwsig(x, d, g, ps)[:2]  # noqa: E731
            assert checkgrad(f, _vec(r["Wvec"]), 1e-5)[0] < FD_TOL
            nok += 1
    assert nok >= 300
    for b in new["bl"]:
        check_bl(b, new)
