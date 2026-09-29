"""Parity of ``search.structurefit`` (with ``bestsplit``, ``graphscorenoopt``,
``optimizebranches`` and ``optimizedepth``; item 27, L4-c2) with Octave, with replayed
permutations.

The fixture ``tests/fixtures/structurefit.mat`` comes from
``tests/octave/fx_structurefit.m`` (regenerate with ``python tools/gen_fixtures.py
structurefit``). It re-runs 6 runs with ``structurefit`` replaced by a spy
(``tests/octave/sf_spy.m``), and adds 4 crafted calls (``cr``) on cylinders with vacant
neighbours, since the real runs never try a vacant-neighbour move. Every call is kept, with its input graph (``gempty`` for
MATLAB's ``[]``), the ``ps`` fields that vary, the ``randperm`` draws made inside the call,
the outputs (``out_ll``, ``out_graph``, the growth history ``out_lls``/``out_bestgraph``)
and two lists, both in call order:

- ``gl``: the slow ``graph_like`` calls (``tests/octave/glc_spy.m``, item 26);
- ``cns``: the ``choose_node_split`` calls (``tests/octave/cns_spy.m``).

Slow scores go through ``fminunc`` (PLAN §4.1), and ``structurefit`` makes them at both
speeds, so the exact test injects Octave's slow results (``test_gibbs.Oracle``, which checks
that Python asks for them with the same graphs, in the same order). Tied split candidates
(mirror-image seed pairs, item 23) can make Python pick the other child order; a
``SplitOracle`` then hands on Octave's graph, but only when it is one of Python's own
candidates tied with the best to ``TIE_RTOL``. The committed fixture needs this at the first
split of both ``chain:demo_chain_feat`` runs and of the cylinder run. A ``TieOracle`` also
lets mirror-image near misses reach their slow scores in the other order. ``test_python_optimizer`` runs
scipy's optimizer instead of the oracle.
"""

import dataclasses

import numpy as np
import pytest
import scipy.io

from formdiscovery import FormDiscoveryError, likelihood, search
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.rng import ReplayError, ReplayPermutations, parse_queue
from formdiscovery.search import bestsplit, structurefit
from tests.helpers import graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tests.test_gibbs import Oracle
from tests.test_glslow import LOGI_RTOL
from tests.test_search import TIE_RTOL
from tests.test_swap import _prep, _text

FX = load_fixture("structurefit")
CALLS = list(FX["calls"])
RUNS = [str(x) for x in np.ravel(FX["runs"])]
RUN_SPEED = [int(x) for x in np.ravel(FX["run_speed"])]

PREP = {}
for _d in FX["ds"]:
    _data, _ps = _prep(str(_d["name"]))
    if "data" in _d:  # exact Octave data (Python scaledata agrees to ~1 ulp)
        _data = np.asarray(_d["data"], dtype=float)
    PREP[str(_d["name"])] = (_data, _ps)


def _run(r):
    return RUNS[int(r["run"]) - 1]


def _inputs(r):
    """Data, ps and start graph (``None`` for MATLAB's ``[]``) of a record."""
    data, ps = PREP[_run(r).split(":")[1]]
    q = r["ps"]
    fast = float(q["fast"])
    ps = ps.replace(speed=int(q["speed"]), fast=None if np.isnan(fast) else int(fast),
                    gibbsclean=int(q["gibbsclean"]), nauty=int(q["nauty"]),
                    fixedall=int(q["fixedall"]), fixedinternal=int(q["fixedinternal"]),
                    fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]),
                    cleanstrong=int(q["cleanstrong"]), init=str(q["init"]))
    ps.runps = dataclasses.replace(ps.runps, structname=str(q["structname"]))
    graph = None if int(r["gempty"]) else graph_from_mat(r["graph"])
    return data, ps, graph


def _list(v):
    return [] if np.size(v) == 0 else list(np.ravel(np.asarray(v, dtype=object)))


def _lls(r):
    return np.atleast_1d(np.asarray(r["out_lls"], dtype=float)).ravel()


def _msg(i, r):
    return f"call {i} {_run(r)} n={int(r['n'])} speed={int(r['ps']['speed'])}"


class SplitOracle:
    """Wraps ``search.choose_node_split``. Each call must have Octave's arguments and
    score (rtol 1e-10). When the graphs differ, Octave's graph must be one of Python's
    ``best_split`` candidates tied with the best to ``TIE_RTOL``; that candidate is then
    returned in place of Python's choice (``ties`` counts these).

    With ``strict=False`` (the Python optimizer, whose weights differ slightly) scores
    need only agree to ``LOGI_RTOL`` and graphs by structure; a call that is not
    Octave's next one, or a score outside ``LOGI_RTOL``, raises ``ReplayError`` (the
    searches have diverged)."""

    def __init__(self, r, msg, strict=True):
        self.cns, self.msg, self.used, self.ties = _list(r["cns"]), msg, 0, 0
        self.strict = strict
        self.tol = {} if strict else dict(rtol=1e9, atol=1e9)  # structure only
        self.real = search.choose_node_split

    def __call__(self, graph, compind, splitind, pind, data, ps, rng=None, info=None):
        k = self.used
        self.used += 1
        msg = f"{self.msg}: split {k}"
        c = self.cns[k] if k < len(self.cns) else None
        if c is not None:
            oci = int(c["compind"])
            args = ((oci - 1) if oci > 0 else oci, int(c["splitind"]) - 1,
                    int(c["pind"]) - 1 if oci < 0 else int(c["pind"]))
        if c is None or (compind, splitind, pind) != args:
            if not self.strict:
                raise ReplayError(f"{msg}: not Octave's next split")
            raise AssertionError(f"{msg}: {(compind, splitind, pind)} is not Octave's")
        info = {}
        ll, p1, p2, ng = self.real(graph, compind, splitind, pind, data, ps, rng=rng,
                                   info=info)
        oll = float(c["ll"])
        if self.strict:
            assert ll == oll or np.isclose(ll, oll, rtol=1e-10, atol=0), (msg, ll, oll)
        elif not (ll == oll or abs(ll - oll) <= LOGI_RTOL * abs(oll)):
            raise ReplayError(f"{msg}: score {ll} vs {oll} (the input graphs differ)")
        if int(c["gempty"]):
            assert ng is None, msg
            return ll, p1, p2, ng
        d = graph_diff(ng, c["newgraph"], **self.tol)
        if d is None:
            return ll, p1, p2, ng
        ls = np.asarray(info.get("ls", []), dtype=float)
        tied = np.flatnonzero(ls >= np.max(ls) - TIE_RTOL * abs(np.max(ls))) if ls.size else []
        js = [j for j in tied if graph_diff(info["gs"][j], c["newgraph"], **self.tol) is None]
        assert js, f"{msg}: {d}"
        self.ties += 1
        return ll, p1, p2, info["gs"][js[0]]


class TieOracle(Oracle):
    """``test_gibbs.Oracle`` (Octave's slow results, checked input graphs) with one more
    rule: tied near misses (item 24) can reach ``nearmissopts`` in the other order, so a
    request that is not the next recorded slow call may be a later unused one, provided
    the two recorded slow scores tie to ``TIE_RTOL`` (mirror images). ``swaps`` counts
    these."""

    def __init__(self, r, msg):
        super().__init__(r, msg)
        self.done, self.swaps = set(), 0

    def __call__(self, data, graph, ps):
        if ps.fast != 0:
            return self.real(data, graph, ps)
        k = min(set(range(len(self.gl) + 1)) - self.done)
        assert k < len(self.gl), f"{self.msg}: slow call {k} not in Octave"
        j = k
        d = graph_diff(graph, self.gl[k]["graph"])
        if d is not None:
            lk = float(self.gl[k]["logI"])
            js = [j for j in range(k + 1, len(self.gl)) if j not in self.done
                  and np.isclose(float(self.gl[j]["logI"]), lk, rtol=TIE_RTOL, atol=0)
                  and graph_diff(graph, self.gl[j]["graph"]) is None]
            assert js, f"{self.msg}: slow call {k} input: {d}"
            j = js[0]
            self.swaps += 1
        self.done.add(j)
        self.used += 1
        return float(self.gl[j]["logI"]), graph_from_mat(self.gl[j]["out_graph"])


def replay(r, msg, monkeypatch, oracle=True, **kw):
    """Run one record with its draws replayed (and used up), the split oracle and, with
    ``oracle``, Octave's slow scores. Returns the outputs and the tie count."""
    data, ps, graph = _inputs(r)
    split = SplitOracle(r, msg, strict=oracle)
    monkeypatch.setattr(search, "choose_node_split", split)
    slow = TieOracle(r, msg)
    if oracle:
        monkeypatch.setattr(likelihood, "graph_like", slow)
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    out = structurefit(data, ps, graph, rng=rng, **kw)
    rng.assert_exhausted()
    if oracle:
        assert split.used == len(split.cns), msg
    if oracle:
        assert slow.used == len(slow.gl), msg
    return out, split.ties + slow.swaps


def check_outputs(out, r, msg):
    ll, g, lls, bg = out
    oll = float(r["out_ll"])
    assert ll == oll or np.isclose(ll, oll, rtol=1e-10, atol=0), (msg, ll, oll)
    d = graph_diff(g, r["out_graph"])
    assert d is None, f"{msg}: {d}"
    olls = _lls(r)
    assert lls.shape == olls.shape, (msg, lls, olls)
    np.testing.assert_allclose(lls, olls, rtol=1e-10, atol=0, err_msg=msg)
    obg = _list(r["out_bestgraph"])
    assert len(bg) == len(obg), msg
    for k, (h, oh) in enumerate(zip(bg, obg)):
        d = graph_diff(h, oh)
        assert d is None, f"{msg}: bestgraph[{k}]: {d}"


# --- contents ------------------------------------------------------------------------------

def test_contents():
    assert RUNS == ["chain:demo_chain_feat", "ring:demo_ring_feat", "tree:demo_tree_feat",
                    "cylinder:demo_ring_feat", "dirring:demo_ring_rel_bin",
                    "chain:demo_chain_feat"]
    assert RUN_SPEED == [54, 54, 54, 54, 54, 4]
    assert [int(x) for x in np.ravel(FX["run_ncalls"])] == [4, 4, 5, 4, 1, 3]
    assert [str(r["kind"]) for r in CALLS] == ["bl"] * 21 + ["cr"] * 4
    speeds = [int(r["ps"]["speed"]) for r in CALLS]
    assert speeds.count(5) == 15 and speeds.count(4) == 10
    # growth from the empty graph at both speeds, and growth from a given graph
    assert {int(r["ps"]["speed"]) for r in CALLS if int(r["gempty"])} == {4, 5}
    assert any(_lls(r).size and not int(r["gempty"]) for r in CALLS)
    assert sum(_lls(r).size for r in CALLS) == 26
    # the Octave spy saw what structurefit saved (save(savefile, ...), l.196)
    for r in CALLS:
        saved = np.atleast_1d(np.asarray(r["saved_lls"], dtype=float)).ravel()
        if _lls(r).size:
            np.testing.assert_array_equal(saved, _lls(r))
        else:
            assert np.isnan(saved).all()


def test_spied_runs_match_baseline():
    """The spies and the pass-through shim do not change the runs."""
    n = 0
    for run, speed, ll in zip(RUNS, RUN_SPEED, np.ravel(FX["run_ll"])):
        s, d = run.split(":")
        expected = FEAT_LL.get((s, d), REL_LL.get((s, d)))
        if expected is None or speed != 54:  # cylinder and the speed-4 run: no baseline
            assert np.isfinite(ll)
            continue
        assert ll == pytest.approx(expected, rel=1e-12), run
        n += 1
    assert n == 4


# --- exact replay --------------------------------------------------------------------------

@pytest.mark.parametrize("i", range(len(CALLS)))
def test_growth_history_matches_octave(i, monkeypatch):
    """Every call, with Octave's draws, slow scores and tied split choices: the same
    final score and graph and the same growth history (``bestgraphlls``, ``bestgraph``).
    Dropping ``part`` (KI-3) does not change anything."""
    r = CALLS[i]
    msg = _msg(i, r)
    out, ties = replay(r, msg, monkeypatch)
    check_outputs(out, r, msg)


def test_demo_chain_feat_chain(monkeypatch):
    """Item 27's target: chain x demo_chain_feat grows 3 depths at speed 5 from the empty
    graph. The first split is a mirror-image tie (item 23, search.mat bl 0)."""
    r = CALLS[0]
    assert _run(r) == "chain:demo_chain_feat" and int(r["gempty"])
    out, ties = replay(r, "chain", monkeypatch)
    check_outputs(out, r, "chain")
    assert len(out[3]) == 3 and ties <= 1
    assert np.all(np.diff(out[2]) > 1e-2)  # every accepted depth gains more than loopeps
    assert [int(g.components[0].nodecount) for g in out[3]] == \
        [int(graph_from_mat(g).components[0].nodecount) for g in _list(r["out_bestgraph"])]


def test_ties_are_rare(monkeypatch):
    """The committed fixture (numpy 1.26) needs the tie rules 4 times: the first split
    of both chain x demo_chain_feat runs (calls 0 and 18) and of the cylinder run
    (call 13), and one swapped pair of mirror-image near misses in call 18. Other numpy
    versions may round other ties differently; allow a few more."""
    ties = {}
    for i, r in enumerate(CALLS):
        with monkeypatch.context() as m:
            _, t = replay(r, _msg(i, r), m)
        if t:
            ties[i] = t
    assert sum(ties.values()) <= 8, ties
    assert len(ties) <= len(CALLS) // 3, ties


# --- bestsplit (KI-4) and the other subfunctions -------------------------------------------

def _cylinder():
    r = next(r for r in CALLS if _run(r) == "cylinder:demo_ring_feat" and _lls(r).size
             and str(r["kind"]) == "bl")
    return graph_from_mat(_list(r["out_bestgraph"])[-1])


def test_bestsplit_first_max_and_default():
    g = _cylinder()
    keys = search._cluster_keys(g)
    assert len(keys) >= 2 and all(k[2] == 1 for k in keys)
    lls = {k: -np.inf for k in keys}
    assert bestsplit(g, lls) == (-np.inf, (0, 0, 1))
    lls[keys[0]] = lls[keys[-1]] = -5.0
    assert bestsplit(g, lls) == (-5.0, keys[0])  # first strict maximum
    lls[(g.ncomp, 0, 1)] = -5.0
    lls[(g.ncomp, 1, 1)] = -4.0
    assert bestsplit(g, lls) == (-4.0, (g.ncomp, 1, 1))


def test_product_graph_vacant_move_uses_pind_1(monkeypatch):
    """KI-4: product-graph entries are read with the ``pind`` left over from the
    component loops. It is 1 for grid/cylinder (every component has ``prodcount = 1``);
    another value raises. The cylinder run does try vacant moves (``compind = -1``)."""
    g = _cylinder()
    lls = {k: -np.inf for k in search._cluster_keys(g)}
    lls[(g.ncomp, 0, 1)] = -1.0
    assert bestsplit(g, lls) == (-1.0, (g.ncomp, 0, 1))
    h = g.copy()
    h.components[-1].prodcount = 2
    lls2 = {k: -np.inf for k in search._cluster_keys(h)}
    lls2[(h.ncomp, 0, 1)] = -1.0
    with pytest.raises(FormDiscoveryError, match="KI-4"):
        bestsplit(h, lls2)
    del lls2[(h.ncomp, 0, 1)]
    assert bestsplit(h, lls2) == (-np.inf, (0, 0, 1))  # never read: no raise
    # the vacant-move branch (compind = -1) is exercised only by the crafted calls
    n = [sum(int(c["compind"]) < 0 for c in _list(r["cns"])) for r in CALLS]
    assert all(k == 0 for k, r in zip(n, CALLS) if str(r["kind"]) == "bl")
    assert all(k >= 1 for k, r in zip(n, CALLS) if str(r["kind"]) == "cr")


def test_score_helpers(monkeypatch):
    r = CALLS[1]
    data, ps, graph = _inputs(r)
    assert ps.fast is None
    ll, g = search.graphscorenoopt(graph, data, ps)
    logI, _ = likelihood.graph_like(data, graph, ps.replace(fast=1))
    assert ll == logI + search.graph_prior(g, ps)
    assert ps.fast is None  # ps not modified
    # optimizedepth only touches entries with a graph, and returns copies
    seen = []
    monkeypatch.setattr(search, "optimizebranches",
                        lambda g_, d_, p_: (seen.append(g_) or (1.0, g_)))
    keys = search._cluster_keys(graph)
    lls = {keys[0]: -2.0}
    ng = {keys[0]: None}
    if len(keys) > 1:
        lls[keys[1]] = -3.0
        ng[keys[1]] = graph
    l2, n2 = search.optimizedepth(graph, lls, ng, data, ps)
    assert lls[keys[0]] == -2.0 and l2[keys[0]] == -2.0
    assert len(seen) == (len(keys) > 1)
    if len(keys) > 1:
        assert l2[keys[1]] == 1.0 and lls[keys[1]] == -3.0


def test_optimizedepth_includes_product_entries(monkeypatch):
    """l.282-290: the product-graph entries with a graph are optimised too, after the
    component splits. (In the fixture no call stops at a depth that still has a vacant
    move, so the replay does not reach this.)"""
    g = _cylinder()
    keys = search._cluster_keys(g)
    seen = []
    monkeypatch.setattr(search, "optimizebranches",
                        lambda g_, d_, p_: (seen.append(g_) or (float(len(seen)), g_)))
    lls = {k: -1.0 for k in keys}
    ng = {k: None for k in keys}
    ng[keys[1]] = "comp"
    lls.update({(g.ncomp, 0, 1): -np.inf, (g.ncomp, 1, 1): -2.0, (g.ncomp, 2, 1): -3.0})
    ng.update({(g.ncomp, 0, 1): None, (g.ncomp, 1, 1): "vac1", (g.ncomp, 2, 1): "vac2"})
    l2, n2 = search.optimizedepth(g, lls, ng, None, None)
    assert seen == ["comp", "vac1", "vac2"]
    assert l2[(g.ncomp, 1, 1)] == 2.0 and l2[(g.ncomp, 2, 1)] == 3.0
    assert l2[(g.ncomp, 0, 1)] == -np.inf


@pytest.mark.parametrize("speed", [5, 4])
def test_no_splits_possible(speed, monkeypatch):
    """l.69-72: when every split scores ``-inf`` the "best split" is the current graph
    with the current score, stored at MATLAB's ``(1, 1, 1)``: the fast cleaning pass
    starts from the current graph, and ``optimizedepth`` (if reached) sees that entry.
    (Relational data: no optimizer. The stored score itself is always overwritten
    before it is compared, so a wrong value there would not change the results.)"""
    r = next(r for r in CALLS if _run(r) == "dirring:demo_ring_rel_bin")
    data, ps, graph = _inputs(r)
    ps = ps.replace(speed=speed)
    monkeypatch.setattr(search, "choose_node_split",
                        lambda *a, **k: (-np.inf, np.array([a[2]]), np.array([], int), None))
    real_od, real_gc = search.optimizedepth, search.gibbs_clean
    got, cleaned = [], []
    monkeypatch.setattr(search, "optimizedepth",
                        lambda g_, l_, n_, d_, p_: (got.append((dict(l_), dict(n_)))
                                                    or real_od(g_, l_, n_, d_, p_)))
    monkeypatch.setattr(search, "gibbs_clean",
                        lambda g_, *a, **k: (cleaned.append((g_, k)) or real_gc(g_, *a, **k)))
    ll0, g0 = search.optimizebranches(graph, data, ps)
    if speed == 5:
        ll0, g0 = search.graphscorenoopt(g0, data, ps)
    ll, g, lls, bg = structurefit(data, ps, graph, rng=0)
    assert cleaned[0][1].get("fast") == 1
    assert graph_diff(cleaned[0][0], g0) is None
    assert np.isfinite(ll) and ll >= ll0
    for l_, n_ in got:
        assert all(v == -np.inf for k, v in l_.items() if k != (0, 0, 1))
        assert n_[(0, 0, 1)] is not None
    assert got  # the last depth (no gain) always reaches optimizedepth


# --- savefile / callback, inputs, default rng ----------------------------------------------

def test_savefile_and_callback(tmp_path, monkeypatch):
    """``save(savefile, 'bestgraphlls', 'bestgraph')`` (l.196) becomes optional: a
    ``.mat`` file written after each accepted depth, and/or a callback."""
    i, r = next((i, r) for i, r in enumerate(CALLS) if _lls(r).size >= 4)
    seen = []
    out, _ = replay(r, _msg(i, r), monkeypatch, savefile=tmp_path / "growthhistory",
                    callback=lambda lls, bg: seen.append((lls.copy(), len(bg))))
    olls = _lls(r)
    assert [len(s[0]) for s in seen] == list(range(1, olls.size + 1))
    assert all(n == len(s) for s, n in seen)
    np.testing.assert_allclose(seen[-1][0], olls, rtol=1e-10, atol=0)
    m = scipy.io.loadmat(tmp_path / "growthhistory.mat", mat_dtype=True)
    np.testing.assert_allclose(m["bestgraphlls"].ravel(), olls, rtol=1e-10, atol=0)
    assert m["bestgraph"].shape == (1, olls.size)
    m = load_fixture("growthhistory.mat", fixtures_dir=tmp_path)  # MATLAB's view
    for h, oh in zip(_list(m["bestgraph"]), _list(r["out_bestgraph"])):
        assert graph_diff(h, oh) is None


def test_no_savefile_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = CALLS[4]
    replay(r, "nosave", monkeypatch)
    assert list(tmp_path.iterdir()) == []


def test_inputs_not_mutated(monkeypatch):
    i, r = next((i, r) for i, r in enumerate(CALLS)
                if not int(r["gempty"]) and _lls(r).size)
    data, ps, graph = _inputs(r)
    d0 = np.array(data, copy=True)
    ps0 = ps.copy()
    monkeypatch.setattr(likelihood, "graph_like", Oracle(r, "mut"))
    structurefit(data, ps, graph, rng=ReplayPermutations(parse_queue(_text(r["logtext"]))))
    assert graph_diff(graph, r["graph"], rtol=0, atol=0) is None
    np.testing.assert_array_equal(data, d0)
    assert ps.fast == ps0.fast and ps.speed == ps0.speed and ps.init == ps0.init


def test_default_rng_runs():
    """rng=None uses numpy permutations; the growth history only goes up by more than
    loopeps per depth."""
    r = next(r for r in CALLS if _run(r) == "dirring:demo_ring_rel_bin")
    data, ps, graph = _inputs(r)
    ll, g, lls, bg = structurefit(data, ps, graph)
    assert np.isfinite(ll) and len(bg) == lls.size
    assert np.all(np.diff(lls) > 1e-2)
    if lls.size:
        assert ll == lls[-1]


# --- the Python optimizer ------------------------------------------------------------------

def _optimizer_check(r, msg, monkeypatch):
    (ll, g, lls, bg), _ = replay(r, msg, monkeypatch, oracle=False)
    oll = float(r["out_ll"])
    assert abs(ll - oll) <= LOGI_RTOL * abs(oll), (msg, ll, oll)
    assert lls.size == _lls(r).size, msg
    np.testing.assert_allclose(lls, _lls(r), rtol=LOGI_RTOL, atol=0, err_msg=msg)
    assert graph_diff(g, r["out_graph"], rtol=1e9, atol=1e9) is None, msg
    for h, oh in zip(bg, _list(r["out_bestgraph"])):
        assert graph_diff(h, oh, rtol=1e9, atol=1e9) is None, msg


@pytest.mark.parametrize("i", [0, 18])
def test_python_optimizer(i, monkeypatch):
    """scipy's optimizer (item 19) in place of fminunc, on the target run
    chain x demo_chain_feat from the empty graph at speed 5 (call 0) and at speed 4
    (call 18): the draws still replay, the final score and the growth history are within
    LOGI_RTOL of Octave's (committed fixture: at most 1e-6 rel), and every graph has
    Octave's structure."""
    _optimizer_check(CALLS[i], _msg(i, CALLS[i]), monkeypatch)


@pytest.mark.slow
def test_python_optimizer_all(monkeypatch):
    """The same on every call. A slightly different optimum can flip a decision, and
    the draws then differ (``ReplayError``). In the committed fixture 14 of the 25 calls
    replay to the end, all within 3e-6 rel of Octave's score with Octave's structure."""
    n = 0
    for i, r in enumerate(CALLS):
        with monkeypatch.context() as m:
            try:
                _optimizer_check(r, _msg(i, r), m)
            except ReplayError:
                continue
        n += 1
    assert n >= 12, n


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "structurefit.mat"
    octave.eval(f"fx_structurefit('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    assert len(fx["calls"]) == len(CALLS)
    for x, y in zip(fx["calls"], CALLS):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["out_ll"]) == float(y["out_ll"])
        assert graph_diff(x["out_graph"], y["out_graph"], rtol=0, atol=0) is None
    np.testing.assert_array_equal(fx["run_ll"], FX["run_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path, monkeypatch):
    out = tmp_path / "structurefit7919.mat"
    octave.eval(f"fx_structurefit('{out}', 7918);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    calls = list(fx["calls"])
    assert [str(x) for x in np.ravel(fx["runs"])] == RUNS and len(calls) >= 15
    for i, r in enumerate(calls):
        msg = f"fresh {_msg(i, r)}"
        with monkeypatch.context() as m:
            out, _ = replay(r, msg, m)
        check_outputs(out, r, msg)
