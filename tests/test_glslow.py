"""``graph_like_conn`` in slow mode (``graph_like_conn.m:35-110``: optimizer + Laplace
approximation; item 19, L3-b2) against Octave.

The fixture ``tests/fixtures/glslow.mat`` comes from ``tests/octave/fx_glslow.m``
(regenerate with ``python tools/gen_fixtures.py glslow``). Octave runs an instrumented copy
of ``graph_like_conn.m`` that records ``Xinit``, the ``fminunc`` optimum ``X``/``fX``, the
gradient ``g`` at ``X``, the full finite-difference ``H``, ``includeind``, ``ll``, ``logI0``
(l.89) and ``logI``:

- ``gh``: the 47 growth-history ``bestgraph``s (82 records, as in ``graphlike.mat``);
- ``sy``: the 29 ``dataprob.mat`` graphs x feature/similarity data x modes none and
  fixedexternal (116 records, 12 chol errors);
- ``jd``: 9 ``dpmiss.mat`` graphs with judges (the missing-data chunk path);
- ``bl``: slow-mode calls captured in chain x demo_chain_feat (all 43) and
  tree x demo_tree_feat (every 4th of 128);
- ``lp``: the Laplace code alone (l.76-93, extracted from the source) at non-optimal
  points (``Xinit`` and a perturbation of it), where the ``~isreal`` fallback runs;
- ``qd``: the same code with a quadratic objective (``tests/octave/glc_quad.m``) at points
  with entries above ``upper_bound - 5`` (``includeind`` truncation, 'sigma blows up', the
  empty-``includeind`` error) and with indefinite Hessians.

Tolerances (PLAN.md §2, §4.1):

- Everything after the optimizer is deterministic given ``X``. At Octave's ``X``, Python's
  ``laplace_logI`` and ``slow_graph`` match Octave to rtol 1e-10: ``ll``, ``logI``,
  ``logI0`` (complex or not), ``includeind`` exact, the returned graph, and ``H`` (rtol
  1e-6 with atol max(1e-8 max|H|, 5e-9 |ll|): a central difference, step 1e-5, of
  gradients whose terms are of size ~|ll|, so rounding of ~100 ulps of |ll| reaches ~1e-5
  at the non-optimal ``lp`` points).
- The optimum is compared by optimality: Python's objective is at most Octave's
  ``fX + 1e-6``, and its gradient norm is at most Octave's.
- ``logI`` from the two optima: rel ``LOGI_RTOL`` = 2e-4. PLAN §4.1 suggested 1e-4 to
  start. The worst records are 1.6e-4 (a spied tree-run call) and 1.06e-4 (gh 64, a
  growth-history graph). The gap is Octave's: its ``fminunc`` (TolFun = TolX = 1e-6)
  stops with gradient norms up to ~15, and objectives up to 0.08 above the optimum that
  every scipy method finds.
  The Laplace term at Octave's ``X`` is exact, so the whole gap comes from the optimum.

Which scipy method tracks Octave best: ``trust-exact`` (with the symmetrised finite-
difference Hessian), ``trust-ncg``, ``BFGS`` and ``L-BFGS-B`` all reach the same optimum
(objectives within 1e-8 of each other) and so the same distance from Octave's ``logI``.
None of them follows Octave's early stop. ``L-BFGS-B`` is ~3x faster (on judges, 44 s
against 138 s for the 9 records, because each finite-difference Hessian costs 2n chunked
gradients). ``BFGS`` fails on two records (a judges one and bl 43): its line search
probes a point where ``chol`` fails in ``dataprobwsig``. ``trust-exact`` stays the
default (the item's choice). ``test_methods_agree`` pins this on gh/sy/bl.
"""

import dataclasses
import functools
import warnings

import numpy as np
import pytest

import formdiscovery.likelihood_feat as lf
from formdiscovery import FormDiscoveryError
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.likelihood import graph_like
from formdiscovery.likelihood_feat import (dataprobwsig, graph_like_conn, laplace_logI,
                                           slow_graph)
from formdiscovery.params import Params, RunPs
from tests.helpers import assert_graph_equal
from tests.test_graphlike import BASELINE_LL, _bl_ps, _mode, _prep

FX = load_fixture("glslow")
LOGI_RTOL = 2e-4
DSNAMES = [str(d["name"]) for d in FX["ds"]]
DSDATA = [np.asarray(d["data"], dtype=float) for d in FX["ds"]]
PREP = {n: _prep(n) for n in DSNAMES}
JDATA = np.asarray(FX["jdata"], dtype=float)
PJ = _prep("judges")[1]
RUNS = [str(x) for x in np.ravel(FX["bl_run"])]


def _err(r):
    x = r["err"] if "err" in r else ""
    return str(x) if np.size(x) else ""


def _sy_ps(r):
    runps = RunPs(type="feat", chunkcount=-1, SS=None)
    if int(r["variant"]) == 2:
        runps.type, runps.dim = "sim", 30
    return _mode(Params.default().replace(missingdata=0, overrideSS=0, zglreg=0, fast=0,
                                          runps=runps), r["mode"])


def _inputs(kind, r):
    """(data, graph, ps) as graph_like receives them."""
    g = graph_from_mat(r["graph"])
    if kind == "gh":
        ps = _mode(PREP[DSNAMES[int(r["data"]) - 1]][1], r["mode"])
        ps = ps.replace(fast=0, runps=dataclasses.replace(ps.runps, structname=g.type))
        return DSDATA[int(r["data"]) - 1], g, ps
    if kind == "sy":
        return np.asarray(r["d"], dtype=float), g, _sy_ps(r)
    if kind == "jd":
        return JDATA, g, _mode(PJ, r["mode"]).replace(fast=0)
    name = RUNS[int(r["run"]) - 1].split(":")[1]
    return DSDATA[DSNAMES.index(name)], g, _bl_ps(r["ps"], PREP[name][1]).replace(fast=0)


def _conn_inputs(kind, r):
    """(data, log-weight graph, graph, ps) as graph_like_conn's slow mode sees them."""
    d, g, ps = _inputs(kind, r)
    obs = np.flatnonzero(g.z >= 0)
    d = d[np.ix_(obs, obs)] if ps.runps.type == "sim" else d[obs, :]
    gl = g.copy()
    W = np.array(np.atleast_2d(gl.Wsym), dtype=float)
    m = np.atleast_2d(np.asarray(gl.adjsym)) > 0
    W[m] = np.log(W[m])
    gl.Wsym, gl.sigma = W, np.log(float(g.sigma))
    return d, gl, g, ps


def _records(kinds=("gh", "sy", "jd", "bl")):
    return [(k, i) for k in kinds for i, r in enumerate(FX[k]) if not _err(r)]


def _vec(x):
    return np.atleast_1d(np.asarray(x, dtype=float)).ravel()


def _check_laplace(logI, lap, q, msg):
    """Compare laplace_logI's outputs with Octave's (q: logI, logI0, ll, H, includeind)."""
    np.testing.assert_array_equal(lap["includeind"], _vec(q["includeind"]).astype(int) - 1,
                                  err_msg=msg)
    np.testing.assert_allclose(lap["ll"], float(q["ll"]), rtol=1e-10, err_msg=msg)
    Ho = np.atleast_2d(np.asarray(q["H"], dtype=float))
    # finite difference (step 1e-5) of gradients whose terms are of size ~|ll|
    atol = max(1e-8 * np.abs(Ho).max(), 5e-9 * abs(float(q["ll"])))
    np.testing.assert_allclose(lap["H"], Ho, rtol=1e-6, atol=atol, err_msg=msg)
    o0 = np.asarray(q["logI0"]).item()
    assert isinstance(lap["logI0"], complex) == np.iscomplexobj(q["logI0"]), msg
    np.testing.assert_allclose(lap["logI0"], o0, rtol=1e-10, err_msg=msg)
    assert isinstance(logI, float), msg
    np.testing.assert_allclose(logI, float(q["logI"]), rtol=1e-10, err_msg=msg)


def test_fixture_contents():
    assert len(FX["gh"]) == 82 and not any(_err(r) for r in FX["gh"])
    assert len(FX["sy"]) == 29 * 2 * 2 and sum(bool(_err(r)) for r in FX["sy"]) == 12
    assert all("positive definite" in _err(r) for r in FX["sy"] if _err(r))
    assert len(FX["jd"]) == 9 and not any(_err(r) for r in FX["jd"])
    assert [int(x) for x in np.ravel(FX["bl_nslow"])] == [43, 128]
    assert len(FX["bl"]) == 43 + 32
    for run, ll in zip(RUNS, np.ravel(FX["bl_ll"])):  # the spy does not change the runs
        assert ll == pytest.approx(BASELINE_LL[run], rel=1e-12)
    assert float(FX["fminunc_tolfun"]) == 1e-6 and float(FX["fminunc_tolx"]) == 1e-6
    # the fallback runs at some of the non-optimal points, never at an Octave optimum
    lp = [q for q in FX["lp"] if not _err(q)]
    assert len(lp) == len(FX["lp"]) == 80
    assert sum(np.iscomplexobj(q["logI0"]) for q in lp) == 25
    assert not any(np.iscomplexobj(FX[k][i]["glc"]["logI0"]) for k, i in _records())


def test_python_data():
    for d, name in zip(FX["ds"], DSNAMES):
        np.testing.assert_allclose(PREP[name][0], d["data"], rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("kind", ["gh", "sy", "jd", "bl"])
def test_laplace_and_graph_at_octave_optimum(kind):
    """Given Octave's X, l.76-101 are deterministic: Python matches to rtol 1e-10."""
    for k, i in _records([kind]):
        r = FX[k][i]
        glc = r["glc"]
        d, gl, g, ps = _conn_inputs(k, r)
        msg = f"{k} {i}"
        np.testing.assert_allclose(np.concatenate([[gl.sigma], lf.mat2vec(gl.Wsym, gl, ps)]),
                                   _vec(glc["Xinit"]), rtol=1e-12, err_msg=msg)
        X = _vec(glc["X"])
        q = dict(glc, H=glc["Hfull"])
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # no 'sigma blows up' / 'gone awry' here
            logI, lap = laplace_logI(dataprobwsig, X, d, gl, ps)
        _check_laplace(logI, lap, q, msg)
        assert float(r["logI"]) == float(glc["logI"])
        f, gr = dataprobwsig(X, d, gl, ps, nargout=2)
        np.testing.assert_allclose(f, float(glc["fX"]), rtol=1e-10, err_msg=msg)
        np.testing.assert_allclose(gr, _vec(glc["g"]), rtol=1e-8,
                                   atol=1e-10 * max(1.0, abs(f)), err_msg=msg)
        assert_graph_equal(slow_graph(gl, X, ps), r["out"], msg)


def test_laplace_nonoptimal_points():
    """lp: Xinit and a perturbation of it; the ~isreal fallback runs for 25 of them."""
    nfall = 0
    for q in FX["lp"]:
        r = FX[str(q["src"])][int(q["ind"]) - 1]
        d, gl, g, ps = _conn_inputs(str(q["src"]), r)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            logI, lap = laplace_logI(dataprobwsig, _vec(q["X"]), d, gl, ps)
        fall = np.iscomplexobj(q["logI0"])
        nfall += fall
        assert [str(x.message) for x in w] == (
            ["graph_like_conn: laplacian approx gone awry"] if fall else [])
        _check_laplace(logI, lap, q, f"lp {q['src']} {int(q['ind'])} {int(q['k'])}")
    assert nfall == 25


def _quad(x, A, b, ps, nargout=1):
    """tests/octave/glc_quad.m: f = x'Ax/2 - b'x."""
    f = x @ A @ x / 2 - b @ x
    return f if nargout == 1 else (f, A @ x - b)


def test_laplace_quadratic():
    """qd: includeind truncation, 'sigma blows up', the fallback, empty includeind."""
    seen = set()
    for q in FX["qd"]:
        A, b, X = (np.atleast_2d(np.asarray(q["A"], dtype=float)), _vec(q["b"]), _vec(q["X"]))
        msg = f"qd {int(q['k'])}"
        if _err(q):
            assert "out of bound" in _err(q)
            with pytest.raises(FormDiscoveryError, match="out of bound"):
                laplace_logI(_quad, X, A, b, None)
            seen.add("error")
            continue
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            logI, lap = laplace_logI(_quad, X, A, b, None)
        msgs = [str(x.message) for x in w]
        blows = X[0] >= 195
        fall = np.iscomplexobj(q["logI0"])
        assert msgs == (["graph_like_conn: sigma blows up"] if blows else []) + (
            ["graph_like_conn: laplacian approx gone awry"] if fall else []), msg
        _check_laplace(logI, lap, q, msg)
        seen.update({"blows"} if blows else set())
        seen.update({"fallback"} if fall else set())
        seen.update({"trunc"} if len(lap["includeind"]) < len(X) else set())
    assert seen == {"error", "blows", "fallback", "trunc"}


def test_includeind_boundary():
    """includeind = find(X < upper_bound - 5): 194.5 is kept, 195 is dropped."""
    A, b = np.diag([2.0, 3.0, 4.0]), np.ones(3)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _, lap = laplace_logI(_quad, np.array([194.5, 195.0, 1.0]), A, b, None)
    np.testing.assert_array_equal(lap["includeind"], [0, 2])
    assert not w
    np.testing.assert_allclose(lap["H"], -A, atol=1e-6)


def _optimality(k, i, method=None):
    r = FX[k][i]
    glc = r["glc"]
    d, g, ps = _inputs(k, r)
    info = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logI, out = graph_like_conn(*_conn_inputs(k, r)[:1], g, ps, method=method,
                                    info=info)
    msg = f"{k} {i} {method}"
    fo, go = float(glc["fX"]), np.linalg.norm(_vec(glc["g"]))
    assert info["fX"] <= fo + 1e-6, msg
    assert np.linalg.norm(info["g"]) <= go, msg
    assert info["fX"] == pytest.approx(dataprobwsig(info["X"], *_conn_inputs(k, r)[:2], ps,
                                                    nargout=1), rel=1e-14)
    np.testing.assert_allclose(logI, float(r["logI"]), rtol=LOGI_RTOL, err_msg=msg)
    # the returned graph: the optimum's weights on the input's structure
    assert_graph_equal(out, slow_graph(_conn_inputs(k, r)[1], info["X"], ps), msg, rtol=0,
                       atol=0)
    assert_graph_equal(out, r["out"], msg, fields=["adj", "adjsym", "z", "type"])
    return logI, info


# judges runs the chunk path in every gradient (~15 s per record with trust-exact): one in
# the gate, the rest slow
GATE = [(k, i) for k, i in _records() if k != "jd" or i == 0]


@pytest.mark.parametrize("k,i", GATE)
def test_optimum(k, i):
    """Python's optimum is at least as good as Octave's; logI within LOGI_RTOL."""
    _optimality(k, i)


@pytest.mark.slow
@pytest.mark.parametrize("k,i", [x for x in _records() if x not in GATE])
def test_optimum_rest(k, i):
    _optimality(k, i)


@pytest.mark.slow
@pytest.mark.parametrize("method", ["trust-ncg", "BFGS", "L-BFGS-B"])
def test_methods_agree(method):
    """Every method meets the same optimality tests and reaches the default's optimum,
    except BFGS on bl 43, where its line search probes a point that makes chol fail."""
    for k, i in _records(("gh", "sy", "bl")):
        if method == "BFGS" and (k, i) == ("bl", 43):
            with pytest.raises(FormDiscoveryError, match="positive definite"):
                _optimality(k, i, method)
            continue
        logI, info = _optimality(k, i, method)
        assert info["fX"] == pytest.approx(_REF(k, i), abs=1e-8, rel=1e-12)


@functools.cache
def _REF(k, i):
    return _optimality(k, i)[1]["fX"]


def test_worst_logI_gap_is_octaves():
    """The largest logI gap (gh 64): Octave stopped far from the optimum."""
    k, i = "gh", 64
    r = FX[k][i]
    logI, info = _optimality(k, i)
    rel = abs(logI - float(r["logI"])) / abs(float(r["logI"]))
    assert 1e-4 < rel < LOGI_RTOL
    assert np.linalg.norm(_vec(r["glc"]["g"])) > 10 > 1e-3 > np.linalg.norm(info["g"])
    assert float(r["glc"]["fX"]) - info["fX"] > 0.05


def test_graph_like_slow_dispatch(monkeypatch):
    """graph_like reaches slow mode for ps.fast 0 and None; fast mode is unchanged."""
    k, i = "gh", 0
    d, g, ps = _inputs(k, FX[k][i])
    for fast in (0, None):
        logI, out = graph_like(d, g, ps.replace(fast=fast))
        np.testing.assert_allclose(logI, float(FX[k][i]["logI"]), rtol=LOGI_RTOL)
    seen = []
    monkeypatch.setattr(lf, "_slow_minimize", lambda *a: seen.append(1) or 1 / 0)
    graph_like(d, g, ps.replace(fast=1))
    assert not seen


def test_inputs_not_mutated():
    k, i = _records(("sy",))[0]
    d, g, ps = _inputs(k, FX[k][i])
    g0, d0 = g.copy(), d.copy()
    graph_like(d, g, ps)
    assert_graph_equal(g, g0, rtol=0, atol=0)
    np.testing.assert_array_equal(d, d0)


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "glslow.mat"
    octave.eval(f"fx_glslow('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for k in ("gh", "sy", "jd", "bl", "lp", "qd"):
        assert len(fx[k]) == len(FX[k])
        for a, b in zip(fx[k], FX[k]):
            assert _err(a) == _err(b)
            if _err(a):
                continue
            assert np.asarray(a["logI"]).item() == np.asarray(b["logI"]).item()
            if "out" in a:
                assert_graph_equal(graph_from_mat(a["out"]), graph_from_mat(b["out"]),
                                   rtol=0, atol=0)


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "glslow7919.mat"
    octave.eval(f"fx_glslow('{out}', 7919);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for i, r in enumerate(fx["sy"]):
        d, g, ps = np.asarray(r["d"], dtype=float), graph_from_mat(r["graph"]), _sy_ps(r)
        if _err(r):
            with pytest.raises(FormDiscoveryError, match="positive definite"):
                graph_like(d, g, ps)
            continue
        info = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            obs = np.flatnonzero(g.z >= 0)
            dd = d[np.ix_(obs, obs)] if ps.runps.type == "sim" else d[obs, :]
            logI, _ = graph_like_conn(dd, g, ps, info=info)
        glc = r["glc"]
        assert info["fX"] <= float(glc["fX"]) + 1e-6
        assert np.linalg.norm(info["g"]) <= np.linalg.norm(_vec(glc["g"]))
        np.testing.assert_allclose(logI, float(r["logI"]), rtol=LOGI_RTOL, err_msg=f"sy {i}")
