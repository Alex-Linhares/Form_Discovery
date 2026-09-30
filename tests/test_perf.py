"""Performance budget (item 35, PLAN.md §7.4): the Octave timing fixture, the Python
benchmark's parity checks and the optimisations.

The fixture ``tests/fixtures/perf.mat`` comes from ``tests/octave/fx_perf.m`` (regenerate
with ``python tools/gen_fixtures.py perf``, about 1 min). It records Octave's time per
call of ``graph_like`` (fast and slow mode) and ``dataprobwsig`` on 15 graphs (``gl``), and
spied ``runmodel`` runs with identity permutations (``sf``: an event log per
``structurefit`` call and depth). ``tools/bench_perf.py`` times the same computations in
Python and prints the tables in PROGRESS.md (iteration 38). Timings are not compared by
the gate. The gate checks that the benchmark computes what Octave computed:

- ``gl``: fast score, ``dataprobwsig`` value and gradient rtol 1e-10, the start point
  ``Xinit``, slow score rel 2e-4 (``tools/compare_runs.py``'s tolerances);
- ``sf``: the event logs are consistent (a depth event per accepted depth plus the final
  one), and the Python spied run of ``chain x demo_chain_feat`` follows Octave's first
  ``structurefit`` call depth for depth (same ``graph_like`` call counts).

The optimisations must not change any result:

- ``Graph.copy``/``Component.copy`` (:func:`formdiscovery.graph._copy_struct`) equal
  ``copy.deepcopy``, field for field, dtype and memory layout included;
- ``util.inv_posdef_logdet`` equals ``(inv_posdef, logdet)`` bit for bit;
- ``laplace_logI`` reusing the optimiser's last Hessian gives the same bits as
  recomputing it, and the reuse happens;
- the BLAS thread limit (:mod:`formdiscovery.threads`) gives the same bits as the
  library's default thread count, and is applied inside ``runmodel``/``structurefit``.
"""

import copy
import os
import warnings

import numpy as np
import pytest

from formdiscovery import FormDiscoveryError, likelihood, likelihood_feat as lf, run, search
from formdiscovery import threads
from formdiscovery.graph import Component, Graph
from formdiscovery.io import load_fixture
from formdiscovery.util import inv_posdef, inv_posdef_logdet, logdet
from tools import bench_perf as bp

FX = load_fixture("perf")
GL = FX["gl"]
SF = FX["sf"]
PREPS = {}
GL_IDS = [f"{r['structure']}:{r['data']}" for r in GL]
FEAT = [i for i, r in enumerate(GL) if str(r["type"]) != "rel"]


def _inputs(i):
    return bp.gl_inputs(GL[i], PREPS)


def _num(v):
    return float(np.asarray(v).ravel()[0])


# --- fixture ------------------------------------------------------------------------------

def test_fixture_contents():
    assert str(FX["octave_version"]) == "10.3.0"
    assert list(FX["sections"]) == ["gl", "sf"]
    assert [str(r["group"]) for r in GL] == ["demo"] * 9 + ["synth"] * 3 + ["rel"] * 3
    assert GL_IDS[9:] == ["chain:synthchain", "tree:synthtree", "grid:synthgrid",
                          "dirring:demo_ring_rel_bin", "dirhierarchy:demo_hierarchy_rel_bin",
                          "order:demo_order_rel_freq"]
    for r in GL:
        assert _num(r["t_fast"]) > 0 and _num(r["n_fast"]) >= 3
        if str(r["type"]) == "rel":
            assert not np.size(r["slow"]) and not np.size(r["t_dp"])
        else:
            assert _num(r["t_slow"]) > _num(r["t_fast"]) and _num(r["n_slow"]) >= 2
            assert _num(r["n_dp"]) >= 3 and np.size(r["dp_g"]) == np.size(r["Xinit"])
    assert [f"{r['structure']}:{r['data']}:{int(_num(r['speed']))}" for r in SF] == [
        "chain:demo_chain_feat:54", "ring:demo_ring_feat:54", "tree:demo_tree_feat:54",
        "dirring:demo_ring_rel_bin:54", "chain:synthtree:5"]


def _check_events(ev, lls):
    """An event log is well formed (``lls``: each structurefit call's bestgraphlls, a list
    of lists): each structurefit call starts, has one depth event
    per accepted depth plus the final (rejected) one, and returns; time and counters
    never decrease."""
    ev = np.atleast_2d(np.asarray(ev, dtype=float))
    assert ev.shape[1] == 7
    assert np.all(np.diff(ev[:, 2]) >= 0) and np.all(np.diff(ev[:, 3:], axis=0) >= 0)
    k = 0
    for call, ll in enumerate(lls, start=1):
        assert ev[k, 0] == bp.EV_START and ev[k, 1] == call
        n = 0
        k += 1
        while ev[k, 0] == bp.EV_DEPTH:
            assert ev[k, 1] == call
            n += 1
            k += 1
        assert ev[k, 0] == bp.EV_END and ev[k, 1] == call
        k += 1
        assert n == len(ll) + 1, (call, n, ll)
    assert k == len(ev)
    rows = bp.depth_rows(ev)
    assert np.isclose(sum(r[2] for r in rows), np.sum(ev[ev[:, 0] == bp.EV_END, 2] -
                                                   ev[ev[:, 0] == bp.EV_START, 2]))
    assert sum(r[3] for r in rows) == ev[-1, 3] and sum(r[5] for r in rows) == ev[-1, 5]


@pytest.mark.parametrize("i", range(len(SF)), ids=[f"{r['structure']}:{r['data']}"
                                                    for r in SF])
def test_octave_event_log(i):
    r = SF[i]
    _check_events(r["ev"], bp._cells(r["lls"]))
    assert _num(r["total"]) >= np.atleast_2d(r["ev"])[-1, 2]


# --- gl: the benchmark computes Octave's values ---------------------------------------------

@pytest.mark.parametrize("i", range(len(GL)), ids=GL_IDS)
def test_gl_fast_parity(i):
    data, g, ps = _inputs(i)
    logI = likelihood.graph_like(data, g, ps.replace(fast=1))[0]
    np.testing.assert_allclose(logI, _num(GL[i]["fast"]), rtol=bp.FAST_RTOL)


@pytest.mark.parametrize("i", FEAT, ids=[GL_IDS[i] for i in FEAT])
def test_gl_dataprob_parity(i):
    data, g, ps = _inputs(i)
    Xinit, d, gL, pf = bp.dp_inputs(data, g, ps)
    np.testing.assert_allclose(Xinit, np.ravel(GL[i]["Xinit"]), rtol=bp.FAST_RTOL)
    ll, grad = lf.dataprobwsig(Xinit, d, gL, pf, nargout=2)
    np.testing.assert_allclose(ll, _num(GL[i]["dp_ll"]), rtol=bp.FAST_RTOL)
    og = np.ravel(GL[i]["dp_g"])
    np.testing.assert_allclose(grad, og, rtol=bp.FAST_RTOL,
                               atol=bp.FAST_RTOL * np.abs(og).max())


@pytest.mark.parametrize("i", FEAT, ids=[GL_IDS[i] for i in FEAT])
def test_gl_slow_parity(i):
    data, g, ps = _inputs(i)
    logI = likelihood.graph_like(data, g, ps.replace(fast=0))[0]
    assert bp._rel(logI, _num(GL[i]["slow"])) <= bp.SLOW_RTOL


def test_bench_gl_rows(monkeypatch):
    """bench_gl's own checks pass on a cheap subset (one call per timing)."""
    monkeypatch.setattr(bp, "timeit", lambda f, mint, minn: (0.0, 1, f()))
    sub = {"gl": [GL[0], GL[12]]}
    rows = bp.bench_gl(sub)
    assert [r["fail"] for r in rows] == [[], []]
    assert "oct_slow" in rows[0] and "oct_slow" not in rows[1]
    table = bp.gl_table(rows)
    assert table.count("\n") == 3 and "| ok |" in table


def test_timeit_rule():
    calls = []
    t, n, v = bp.timeit(lambda: calls.append(1) or len(calls), 0.0, 3)
    assert n == 3 and v == 3 and t >= 0
    t, n, v = bp.timeit(lambda: calls.append(1), 10.0, 1, maxn=5)
    assert n == 5


# --- sf: the Python spied run -------------------------------------------------------------

def test_spied_run_follows_octave():
    """chain x demo_chain_feat with identity permutations: the event log is well formed,
    the first structurefit call (speed 5, alltie) makes Octave's graph_like calls depth
    for depth, and its growth history and the final score agree with Octave's."""
    oc = SF[0]
    py = bp.spied_runmodel(1, 0, 54)
    _check_events(py["ev"], [list(x) for x in py["lls"]])
    od = [r for r in bp.depth_rows(oc["ev"]) if r[0] == 1]
    pd = [r for r in bp.depth_rows(py["ev"]) if r[0] == 1]
    assert [(r[1], r[3], r[5]) for r in pd] == [(r[1], r[3], r[5]) for r in od]
    np.testing.assert_allclose(py["lls"][0], bp._cells(oc["lls"])[0], rtol=1e-5)
    assert bp._rel(py["ll"], _num(oc["ll"])) <= 1e-3
    # the spies are removed afterwards
    assert search.structurefit.__wrapped__.__name__ == "structurefit"
    assert likelihood.graph_like.__module__ == "formdiscovery.likelihood"


def test_sf_tables():
    rows = [{"run": "a x b", "speed": 54, "oct": bp._sf_summary(SF[0]["ev"], 1.0),
             "py": bp._sf_summary(SF[0]["ev"], 2.0), "oct_ll": -1.0, "py_ll": -1.0,
             "oct_depths": bp.depth_rows(SF[0]["ev"]),
             "py_depths": bp.depth_rows(SF[0]["ev"])[:-1]}]
    assert "| a x b | 54 | 1.00 / 2.00 | 2.00 | 7 / 7 |" in bp.sf_table(rows)
    t = bp.depth_table(rows[0])
    assert "| 1 | start |" in t and t.rstrip().endswith("| - |")


# --- optimisations: same bits ----------------------------------------------------------------

def _assert_same(a, b, path="graph"):
    assert type(a) is type(b), path
    if isinstance(a, (Graph, Component)):
        assert a.__dict__.keys() == b.__dict__.keys(), path
        for k in a.__dict__:
            _assert_same(a.__dict__[k], b.__dict__[k], f"{path}.{k}")
    elif isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape, path
        assert a.flags.c_contiguous == b.flags.c_contiguous, path
        assert a.flags.f_contiguous == b.flags.f_contiguous, path
        assert np.array_equal(a, b, equal_nan=a.dtype.kind == "f"), path
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for k, (x, y) in enumerate(zip(a, b)):
            _assert_same(x, y, f"{path}[{k}]")
    else:
        assert a == b or (a != a and b != b), path


def _arrays(obj):
    if isinstance(obj, (Graph, Component)):
        for v in obj.__dict__.values():
            yield from _arrays(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _arrays(v)
    elif isinstance(obj, np.ndarray):
        yield obj


@pytest.mark.parametrize("i", range(len(GL)), ids=GL_IDS)
def test_graph_copy_equals_deepcopy(i):
    g = _inputs(i)[1]
    g.W = np.asfortranarray(g.W)  # a Fortran-ordered field keeps its layout
    g.extra = {"k": [1, 2]}       # an attribute outside the fields goes to deepcopy
    fast, deep = g.copy(), copy.deepcopy(g)
    _assert_same(fast, deep)
    assert fast.W.flags.f_contiguous
    ids = {id(a) for a in _arrays(g)}
    assert not ids & {id(a) for a in _arrays(fast)}
    assert fast.extra == g.extra and fast.extra is not g.extra
    fast.components[0].adj[...] = 7  # no sharing with the source
    assert not np.any(g.components[0].adj == 7)
    _assert_same(g.components[0].copy(), copy.deepcopy(g.components[0]))


def test_inv_posdef_logdet_same_bits():
    rng = np.random.default_rng(35)
    mats = [_inputs(i)[1] for i in (0, 9, 11)]
    for n in (1, 3, 14, 40, 89):
        A = rng.standard_normal((n, n))
        mats.append(A @ A.T + n * np.eye(n))
    for A in mats:
        if isinstance(A, Graph):
            A = lf.inv_covariance(A.Wsym, A.objcount, A.sigma, _inputs(0)[2])[0]
        iA, ld = inv_posdef_logdet(A)
        assert np.array_equal(iA, inv_posdef(A)) and ld == logdet(A)
    with pytest.raises(FormDiscoveryError, match="inv_posdef: chol"):
        inv_posdef_logdet(np.array([[1.0, 2.0], [2.0, 1.0]]))


@pytest.mark.parametrize("i", FEAT, ids=[GL_IDS[i] for i in FEAT])
def test_laplace_reuses_hessian(i, monkeypatch):
    """graph_like_conn's slow mode gives the same bits with and without the Hessian
    reuse, and the reuse saves laplace_logI's hessiangrad (on every benchmark graph: 4
    stop on convergence, 8 on a rejected step, where the optimum's Hessian is not the
    last one)."""
    data, g, ps = _inputs(i)
    d = np.asarray(data)[np.asarray(g.z).ravel() >= 0]
    ps0 = ps.replace(fast=0)
    real = lf.hessiangrad
    n = {"calls": 0}

    def counting(*a, **kw):
        n["calls"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(lf, "hessiangrad", counting)
    info = {}
    logI, out = lf.graph_like_conn(d, g, ps0, info=info)
    with_cache = n["calls"]
    real_lap = lf.laplace_logI
    monkeypatch.setattr(lf, "laplace_logI", lambda *a, hcache=None: real_lap(*a))
    n["calls"] = 0
    info2 = {}
    logI2, out2 = lf.graph_like_conn(d, g, ps0, info=info2)
    assert logI2 == logI and np.array_equal(info2["H"], info["H"])
    _assert_same(out2, out)
    assert n["calls"] == with_cache + 1  # one hessiangrad saved


def test_laplace_cache_ignored_at_other_points():
    data, g, ps = _inputs(0)
    d = np.asarray(data)[np.asarray(g.z).ravel() >= 0]
    Xinit, _, gL, pf = bp.dp_inputs(data, g, ps)
    ref, lap = lf.laplace_logI(lf.dataprobwsig, Xinit, d, gL, ps)
    bad = {(Xinit + 1).tobytes(): np.zeros((len(Xinit), len(Xinit)))}
    got, lap2 = lf.laplace_logI(lf.dataprobwsig, Xinit, d, gL, ps, hcache=bad)
    assert got == ref and np.array_equal(lap2["H"], lap["H"])


# --- BLAS thread limit -------------------------------------------------------------------------

def _blas_threads_now():
    from threadpoolctl import threadpool_info
    return {i["filepath"]: i["num_threads"] for i in threadpool_info()
            if i["user_api"] == "blas"}


def _scores(idx):
    out = []
    for i in idx:
        data, g, ps = _inputs(i)
        out.append(likelihood.graph_like(data, g, ps.replace(fast=1))[0])
        if str(GL[i]["type"]) != "rel":
            Xinit, d, gL, pf = bp.dp_inputs(data, g, ps)
            ll, grad = lf.dataprobwsig(Xinit, d, gL, pf, nargout=2)
            s, gs = likelihood.graph_like(data, g, ps.replace(fast=0))
            out += [ll, *grad, s, gs.sigma, *np.ravel(gs.Wsym)]
    return np.array(out)


def test_blas_threads_same_bits():
    """1 thread vs all cores. The session runs pinned to 1 thread (conftest, loop0002
    item 02), so the multithreaded side sets its limit explicitly."""
    pytest.importorskip("threadpoolctl")
    idx = [0, 5, 10, 11, 13]
    with threads.blas_threads(os.cpu_count() or 1):
        ref = _scores(idx)
    with threads.blas_threads(1):
        one = _scores(idx)
    assert np.array_equal(ref, one)


def test_blas_threads_limits_and_restores(monkeypatch):
    pytest.importorskip("threadpoolctl")
    before = _blas_threads_now()
    with threads.blas_threads(1):
        assert set(_blas_threads_now().values()) == {1}
        with threads.blas_threads(2):
            assert set(_blas_threads_now().values()) <= {1, 2}
        assert set(_blas_threads_now().values()) == {1}
    assert _blas_threads_now() == before
    for off in (None, 0):
        with threads.blas_threads(off):
            assert _blas_threads_now() == before
    monkeypatch.setattr(threads, "BLAS_THREADS", None)
    with threads.blas_threads():
        assert _blas_threads_now() == before


def test_drivers_run_under_the_limit(monkeypatch):
    """runmodel and structurefit run under blas_threads (the limit read at call time)."""
    pytest.importorskip("threadpoolctl")
    seen = []

    def fake_brlencases(data, ps, graph, *a, **kw):
        seen.append(set(_blas_threads_now().values()))
        raise RuntimeError("stop")

    monkeypatch.setattr(run, "brlencases", fake_brlencases)
    ps = run.Params.default()
    with pytest.raises(RuntimeError, match="stop"):
        run.runmodel(ps, 1, 0, 1)
    assert seen == [{1}]
    monkeypatch.setattr(search, "optimizebranches",
                        lambda *a: seen.append(set(_blas_threads_now().values())) or 1 / 0)
    ps.runps.structname, ps.runps.nobjects = "chain", 4
    with pytest.raises(ZeroDivisionError):
        search.structurefit(None, ps)
    assert seen[-1] == {1}
    assert run.runmodel.__wrapped__.__name__ == "runmodel"


def test_blas_threads_without_threadpoolctl(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_tpc(name, *a, **kw):
        if name == "threadpoolctl":
            raise ImportError(name)
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_tpc)
    monkeypatch.setattr(threads, "_warned", False)
    assert not threads.have_threadpoolctl()
    with pytest.warns(UserWarning, match="threadpoolctl is not installed"):
        with threads.blas_threads(1):
            pass
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # warned once only
        with threads.blas_threads(1):
            pass


def test_cli_blas_threads(monkeypatch, tmp_path):
    from formdiscovery import cli
    seen = []
    monkeypatch.setattr(cli, "masterrun", lambda *a, **kw: seen.append(
        threads.BLAS_THREADS) or run.MasterResults.__new__(run.MasterResults))
    monkeypatch.setattr(threads, "BLAS_THREADS", 1)
    for arg, want in (([], 1), (["--blas-threads", "0"], None), (["--blas-threads", "4"], 4)):
        cli.main(["run", "--structures", "chain", "--datasets", "1", "--out",
                  str(tmp_path), "-q", *arg])
        assert seen[-1] == want


# --- timing (slow: depends on the machine) --------------------------------------------------

@pytest.mark.slow
def test_fast_mode_within_octave_budget():
    """PLAN §7.4: per call, fast graph_like is not slower than Octave's (with 50% slack
    for machine load) on the demo and synthetic graphs."""
    with threads.blas_threads():
        for i in range(12):
            data, g, ps = _inputs(i)
            pf = ps.replace(fast=1)
            t, _, _ = bp.timeit(lambda: likelihood.graph_like(data, g, pf), 0.3, 5)
            assert t <= 1.5 * _num(GL[i]["t_fast"]), GL_IDS[i]


@pytest.mark.octave
def test_live_gl_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "perf.mat"
    octave.eval(f"fx_perf('{out}', {{'gl'}});", nout=0)
    new = load_fixture(str(out))
    assert len(new["gl"]) == len(GL)
    for a, b in zip(GL, new["gl"]):
        assert _num(a["fast"]) == _num(b["fast"])
        if str(a["type"]) != "rel":
            assert _num(a["slow"]) == _num(b["slow"]) and _num(a["dp_ll"]) == _num(b["dp_ll"])
            assert np.array_equal(np.ravel(a["dp_g"]), np.ravel(b["dp_g"]))
