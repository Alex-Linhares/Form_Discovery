"""Parity of ``search.addnearmiss``, ``choose_seedpairs``, ``best_split`` and
``choose_node_split`` (item 23, L4-a) with Octave, with replayed permutations.

The fixture ``tests/fixtures/search.mat`` comes from ``tests/octave/fx_search.m``
(regenerate with ``python tools/gen_fixtures.py search``). Every ``randperm`` draw Octave
makes inside a call is logged by the shim (``matlab/octave_shims/randperm.m``) and
replayed here with :class:`formdiscovery.rng.ReplayPermutations`, which must then be
used up exactly. The parts are:

- ``an``: ``addnearmiss`` on seeded lists, including its ``lower(1)`` error;
- ``sq``: seeded growth sequences over the 6 demo data sets. They cover partition, chain,
  ring, tree, hierarchy, grid, cylinder and connected on feature data, 7 relational
  forms, the high-level (``compind = -1``) vacant-neighbour splits, productions that do
  not apply, one-member nodes, and speeds 5, 4 and 3;
- ``er``: speeds that match no ``case`` (KI-1);
- ``bl``: calls spied in four baseline runs.

Fixture indices are 1-based; the port is 0-based (``CONVENTIONS.md``). Scores at speeds
4 and 5 are fast mode and match to rtol 1e-10. Speed 3 rescores the chosen split in slow
mode, so its ``ll`` is compared with the slow-mode tolerance of ``test_glslow`` and its
graph by structure only (PLAN.md §2).
"""

import dataclasses

import numpy as np
import pytest

from formdiscovery import FormDiscoveryError, likelihood, search
from formdiscovery.graph import COMPONENT_FIELDS, GRAPH_FIELDS, simplify_graph
from formdiscovery.io import graph_from_mat, load_dataset, load_fixture, to0
from formdiscovery.matlab_compat import stable_argsort
from formdiscovery.params import DATASETS, Params, graph_prior, setrunps, structcounts
from formdiscovery.preprocess import scaledata
from formdiscovery.rng import IdentityPermutations, ReplayPermutations, parse_queue
from formdiscovery.search import addnearmiss, best_split, choose_node_split, choose_seedpairs
from tests.helpers import assert_graph_equal, graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tests.test_glslow import LOGI_RTOL

FX = load_fixture("search")
MODES = [tuple(int(x) for x in m) for m in np.atleast_2d(FX["modes"])]
STRUCT_FIELDS = [f for f in GRAPH_FIELDS if f not in {"sigma", "Wcluster", "W",
                                                     "leaflengths", "extlen", "intlen",
                                                     "Wclustersym"}]


def _err(x):
    return str(x) if np.size(x) else ""


def _text(x):
    return str(x) if np.size(x) else ""


def _prep(name):
    """fx_search.m's prep (runmodel.m:27-95 without the graph initialisation)."""
    data = load_dataset(name)
    nobj, ps = setrunps(data, DATASETS.index(name), Params.default())
    data, ps = scaledata(data, ps)
    ps = ps.replace(overrideSS=0 if ps.overrideSS is None else ps.overrideSS, cleanstrong=0)
    return data, structcounts(nobj, ps)


DSNAMES = [str(d["name"]) for d in FX["ds"]]
PREP = {}
for _d in FX["ds"]:
    _data, _ps = _prep(str(_d["name"]))
    if "data" in _d:  # exact Octave data (Python scaledata agrees to ~1 ulp)
        _data = np.asarray(_d["data"], dtype=float)
    PREP[str(_d["name"])] = (_data, _ps)


def _ps(k, mode=1, structname=None, speed=5, **kw):
    data, ps = PREP[DSNAMES[k - 1]]
    fa, fi, fe, pt = MODES[mode - 1]
    ps = ps.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt,
                    speed=speed, **kw)
    ps.runps = dataclasses.replace(ps.runps, structname=structname)
    return data, ps


def _comp(v):
    v = int(v)
    return v - 1 if v > 0 else v


def _args(r):
    """(compind, c, pind) in the port's convention: for a high-level split ``pind`` is
    the 0-based neighbour node, otherwise a production number."""
    ci = _comp(r["compind"])
    pind = int(r["pind"]) - 1 if ci < 0 else int(r["pind"])
    return ci, int(r["c"]) - 1, pind


def _replay(text):
    return ReplayPermutations(parse_queue(_text(text)))


def _idx(v):
    return to0(np.atleast_1d(np.asarray(v, dtype=np.int64))) if np.size(v) else \
        np.empty(0, dtype=np.int64)


TIE_RTOL = 1e-10


def check_call(r, data, ps, msg):
    """Replay one choose_node_split record. When Octave's chosen candidate is tied with
    others to within ``TIE_RTOL`` (mirror-image seed pairs give the same split with the
    children swapped, and rounding decides which ``max`` sees first), any tied Python
    candidate whose graph and parts equal Octave's is accepted. Failing that, Octave's
    graph is accepted if Python scores it within ``TIE_RTOL`` of Python's own result:
    the same kind of tie inside the greedy loop. The committed fixture never needs this
    last rule with numpy 1.26 (base env); numpy 2.5 (fd env) needs it once on the
    fresh-seed live run (a 7e-15 tie on relational data)."""
    g = graph_from_mat(r["graph"])
    ci, c, pind = _args(r)
    rng = _replay(r["logtext"])
    info = {}
    ll, p1, p2, ng = choose_node_split(g, ci, c, pind, data, ps, rng=rng, info=info)
    rng.assert_exhausted()
    oll = float(r["ll"])
    if ps.speed == 3 and np.isfinite(oll):
        assert abs(ll - oll) <= LOGI_RTOL * abs(oll), (msg, ll, oll)
    else:
        assert ll == oll or np.isclose(ll, oll, rtol=1e-10, atol=0), (msg, ll, oll)
    # speed 3: the weights come from the optimiser; compare structure only
    tol = dict(rtol=0, atol=np.inf) if ps.speed == 3 else {}
    op1, op2 = _idx(r["part1"]), _idx(r["part2"])
    if not isinstance(r["newgraph"], dict):
        assert ng is None, msg
        cands = [(ng, p1, p2)]
    else:
        cands = [(ng, p1, p2)]
        # speed 3 rescored the chosen graph; ties are only checked at speeds 4/5
        if "ls" in info and ps.speed != 3:
            ls, top = info["ls"], np.max(info["ls"])
            for k in np.flatnonzero(ls >= top - TIE_RTOL * abs(top)):
                h = info["gs"][k]
                if ci < 0:
                    cands.append((h, p1, p2))
                else:
                    z = np.asarray(h.components[ci].z)
                    cands.append((h, np.flatnonzero(z == info["c1"]),
                                  np.flatnonzero(z == info["c2"])))
    errs = []
    for h, q1, q2 in cands:
        d = graph_diff(h, r["newgraph"], **tol) if h is not None else None
        if d is None and np.array_equal(q1, op1) and np.array_equal(q2, op2):
            return ll, ng
        errs.append(d or f"parts {q1} {q2} vs {op1} {op2}")
    if isinstance(r["newgraph"], dict) and ps.speed != 3:
        # a tie inside the greedy loop (max([g1l, g2l]) on equal scores) can send an
        # object to the other child; accept Octave's graph if it scores the same here
        og = graph_from_mat(r["newgraph"])
        logI, _ = likelihood.graph_like(data, og, ps.replace(fast=1))
        if np.isclose(logI + graph_prior(og, ps), ll, rtol=TIE_RTOL, atol=0):
            return ll, ng
    raise AssertionError(f"{msg}: {errs}")


# --- addnearmiss ---------------------------------------------------------------------------

def test_addnearmiss():
    kinds = set()
    for t, r in enumerate(FX["an"]):
        scores = np.atleast_1d(np.asarray(r["scores"], dtype=float))
        graphs = [str(x) for x in np.atleast_1d(r["graphs"])]
        args = (scores, graphs, f"new{t + 1}", float(r["score"]), "curr",
                float(r["currscore"]), float(r["epsilon"]))
        if _err(r["err"]):
            assert "lower(1): out of bound" in _err(r["err"])
            with pytest.raises(FormDiscoveryError, match="lower"):
                addnearmiss(*args)
            kinds.add("err")
            continue
        s2, g2 = addnearmiss(*args)
        np.testing.assert_array_equal(s2, np.atleast_1d(np.asarray(r["out"], dtype=float)))
        assert g2 == [str(x) for x in np.atleast_1d(r["outg"])], t
        kinds.add("same" if g2 == graphs else f"insert{g2.index(f'new{t + 1}')}")
        assert s2 is not scores
    assert {"err", "same", "insert0", "insert1", "insert2"} <= kinds


def test_addnearmiss_inputs_not_mutated():
    s, g = np.array([3.0, 1.0, -np.inf]), ["a", "b", "c"]
    s2, g2 = addnearmiss(s, g, "x", 2.0, None, 10.0, 1e-3)
    assert list(s2) == [3.0, 2.0, 1.0] and g2 == ["a", "x", "b"]
    assert list(s) == [3.0, 1.0, -np.inf] and g == ["a", "b", "c"]
    with pytest.raises(FormDiscoveryError, match="differ in length"):
        addnearmiss(s, g[:2], "x", 2.0, None, 10.0, 1e-3)


# --- growth sequences ----------------------------------------------------------------------

SQ = list(FX["sq"])


def _sq_inputs(r):
    name = str(FX["sq_name"][int(r["seq"]) - 1]).split(":")[0]
    return _ps(int(r["data"]), int(r["mode"]), name, int(r["speed"]))


def test_sq_contents():
    assert len(SQ) == 219 and not any(_err(r["err"]) for r in SQ)
    speeds = [int(r["speed"]) for r in SQ]
    assert speeds.count(3) == 11 and speeds.count(4) == 19
    assert sum(_comp(r["compind"]) < 0 for r in SQ) == 13
    assert sum(np.isneginf(float(r["ll"])) for r in SQ) == 47
    # the >5-members branch of choose_seedpairs draws one randperm per member
    assert sum(bool(_text(r.get("sptext", ""))) for r in SQ) == 78


@pytest.mark.parametrize("i", range(len(SQ)))
def test_sq(i):
    r = SQ[i]
    data, ps = _sq_inputs(r)
    check_call(r, data, ps, f"sq {i} {FX['sq_name'][int(r['seq']) - 1]} step "
                            f"{int(r['step'])} speed {int(r['speed'])}")


def test_sq_seedpairs():
    """choose_seedpairs alone, on every call with at least two members."""
    n = 0
    for i, r in enumerate(SQ):
        if "seedpairs" not in r:
            continue
        data, ps = _sq_inputs(r)
        ci, c, pind = _args(r)
        rng = _replay(r["sptext"])
        sp = choose_seedpairs(graph_from_mat(r["graph"]), ci, c, pind, ps, rng=rng)
        rng.assert_exhausted()
        np.testing.assert_array_equal(sp, to0(np.asarray(r["seedpairs"]).reshape(-1, 2)),
                                      err_msg=f"sq {i}")
        n += 1
    assert n == 204


def test_seedpairs_branches():
    """Every branch of choose_seedpairs.m is exercised by the fixture."""
    seen = set()
    for r in SQ:
        if "seedpairs" not in r:
            continue
        data, ps = _sq_inputs(r)
        g = graph_from_mat(r["graph"])
        ci, c, pind = _args(r)
        sp = choose_seedpairs(g, ci, c, pind, ps, rng=IdentityPermutations())
        z = g.z if ci < 0 else g.components[ci].z
        m = int(np.sum(np.asarray(z) == c))
        big = m > 5
        flip = sp.shape[0] == 2 * (m if big else m * (m - 1) // 2)
        seen.add(("big" if big else "small", "hl" if ci < 0 else ps.runps.structname
                  if ps.runps.structname in ("partition", "tree") else "other", flip))
        if big and ci >= 0:
            zc = np.asarray(g.z)
            if any(np.sum(zc == zc[o]) == 1 for o in np.flatnonzero(np.asarray(z) == c)):
                seen.add("singleton-fallback")
    want = {("big", "hl", True), ("small", "hl", True), ("big", "other", False),
            ("big", "other", True), ("small", "other", True), ("small", "partition", False),
            ("big", "partition", False), ("big", "tree", False), ("small", "tree", True),
            ("small", "tree", False), "singleton-fallback"}
    assert not want - seen, want - seen


def test_sequences_follow_best_split():
    """The sequences advance with the best speed-5 new graph, so replaying them in
    Python reproduces the next step's input graph."""
    by_step = {}
    for i, r in enumerate(SQ):
        by_step.setdefault((int(r["seq"]), int(r["step"])), []).append(i)
    for (s, step), idx in by_step.items():
        nxt = by_step.get((s, step + 1))
        if not nxt:
            continue
        best = max((i for i in idx if int(SQ[i]["speed"]) == 5), key=lambda i: float(SQ[i]["ll"]))
        assert_graph_equal(SQ[best]["newgraph"], SQ[nxt[0]]["graph"], f"seq {s} step {step}")


# --- property: the chosen split has the highest candidate score -----------------------------

PROP = [i for i, r in enumerate(SQ) if int(r["speed"]) == 5 and np.isfinite(float(r["ll"]))
        and int(r["data"]) != 5][::3]


@pytest.mark.parametrize("i", PROP)
def test_best_split_maximises_candidates(i):
    r = SQ[i]
    data, ps = _sq_inputs(r)
    g = graph_from_mat(r["graph"])
    ci, c, pind = _args(r)
    info = {}
    ll, p1, p2, ng = choose_node_split(g, ci, c, pind, data, ps, rng=_replay(r["logtext"]),
                                       info=info)
    gs, ls0, ls, mind = info["gs"], info["ls0"], info["ls"], info["mind"]
    assert ll == ls[mind] == np.max(ls) and ng is gs[mind]
    assert mind == int(np.flatnonzero(ls == np.max(ls))[0])
    fast = ps.replace(fast=1)
    part = np.flatnonzero(np.asarray(g.z if ci < 0 else g.components[ci].z) == c)
    for k, (gk, lk) in enumerate(zip(gs, ls0)):
        # each candidate's score is its graph's full-data score
        logI, _ = likelihood.graph_like(data, gk, fast)
        assert np.isclose(lk, logI + graph_prior(gk, fast), rtol=1e-10, atol=0), k
    # the -inf pass removes a best-first prefix of candidates that collapse to one cluster
    order = stable_argsort(ls0, descending=True)
    dropped = [k for k in order if ls[k] == -np.inf and ls0[k] != -np.inf]
    assert dropped == list(order[:len(dropped)])
    clean = ps.replace(cleanstrong=1)
    for k in dropped:
        assert np.unique(np.asarray(simplify_graph(gs[k], clean).z)[part]).size == 1
    assert np.array_equal(ls[ls != -np.inf], ls0[ls != -np.inf])


# --- speeds, errors and edge cases ---------------------------------------------------------

def test_speed_errors():
    """KI-1: speeds 1, 2 (and 54) match no case in best_split.m; Octave fails at l.141."""
    assert len(FX["er"]) == 3
    data, ps = _ps(1, structname="chain")
    for r in FX["er"]:
        assert "'mind' undefined" in _err(r["err"])
        with pytest.raises(FormDiscoveryError, match="matches no case"):
            choose_node_split(graph_from_mat(r["graph"]), 0, 0, 1, data,
                              ps.replace(speed=int(r["speed"])), rng=0)


def test_best_split_speed_1_2_raises():
    """KNOWN_ISSUES.md KI-1 pin."""
    data, ps = _ps(1, structname="chain")
    g = graph_from_mat(FX["er"][0]["graph"])
    sp = choose_seedpairs(g, 0, 0, 1, ps, rng=0)
    for speed in (1, 2):
        with pytest.raises(FormDiscoveryError, match="KI-1"):
            best_split(g, 0, 0, 1, data, sp, ps.replace(speed=speed), rng=0)


def test_one_member_and_inapplicable():
    """One member: (-inf, [node], [], None) with no draws. A production that does not
    apply: (-inf, [], [], None) after choose_seedpairs's draws. Every candidate collapsing
    to one cluster after simplify_graph: ll = -inf with a new graph (best_split.m:141)."""
    ones = [r for r in SQ if np.isneginf(float(r["ll"])) and "seedpairs" not in r]
    inapp = [r for r in SQ if np.isneginf(float(r["ll"])) and "seedpairs" in r
             and not isinstance(r["newgraph"], dict)]
    collapsed = [r for r in SQ if np.isneginf(float(r["ll"])) and isinstance(r["newgraph"], dict)]
    assert (len(ones), len(inapp), len(collapsed)) == (15, 18, 14)
    for r in ones:
        assert not _text(r["logtext"]) and int(r["part1"]) == int(r["c"])


def test_high_level_parts_from_input_graph():
    """KI-24: for compind = -1, part1/part2 are read from the input graph, so part1 is
    every member of the split node and part2 (the vacant neighbour) is empty."""
    hl = [r for r in SQ if _comp(r["compind"]) < 0]
    assert hl
    for r in hl:
        g = graph_from_mat(r["graph"])
        c = int(r["c"]) - 1
        np.testing.assert_array_equal(_idx(r["part1"]), np.flatnonzero(np.asarray(g.z) == c))
        assert np.size(r["part2"]) == 0
        ng = graph_from_mat(r["newgraph"])
        assert np.sum(np.asarray(ng.z) == int(r["pind"]) - 1) > 0


def test_rel_data_not_masked(monkeypatch):
    """KI-23: best_split passes relational data to graph_like unmasked."""
    r = next(r for r in SQ if int(r["data"]) == 4 and np.isfinite(float(r["ll"])))
    data, ps = _sq_inputs(r)
    seen = []
    orig = likelihood.graph_like

    def spy(d, g, p):
        seen.append(d is data)
        return orig(d, g, p)

    monkeypatch.setattr(likelihood, "graph_like", spy)
    ci, c, pind = _args(r)
    choose_node_split(graph_from_mat(r["graph"]), ci, c, pind, data, ps,
                      rng=_replay(r["logtext"]))
    assert seen and all(seen)


def test_seedpairs_too_few_members():
    """KI-25: fewer than two members raises (MATLAB's nchoosek returns a count)."""
    r = next(r for r in SQ if "seedpairs" not in r and _comp(r["compind"]) >= 0)
    data, ps = _sq_inputs(r)
    ci, c, pind = _args(r)
    with pytest.raises(FormDiscoveryError, match="KI-25"):
        choose_seedpairs(graph_from_mat(r["graph"]), ci, c, pind, ps, rng=0)


def test_nan_score_raises(monkeypatch):
    r = next(r for r in SQ if np.isfinite(float(r["ll"])) and int(r["data"]) == 1)
    data, ps = _sq_inputs(r)
    monkeypatch.setattr(likelihood, "graph_like", lambda d, g, p: (np.nan, g))
    ci, c, pind = _args(r)
    with pytest.raises(FormDiscoveryError, match="NaN log-likelihood"):
        choose_node_split(graph_from_mat(r["graph"]), ci, c, pind, data, ps, rng=0)


def test_inputs_not_mutated():
    r = next(r for r in SQ if np.isfinite(float(r["ll"])) and int(r["data"]) == 1)
    data, ps = _sq_inputs(r)
    g = graph_from_mat(r["graph"])
    d0, ps0 = data.copy(), ps.copy()
    ci, c, pind = _args(r)
    choose_node_split(g, ci, c, pind, data, ps, rng=_replay(r["logtext"]))
    assert graph_diff(g, r["graph"], rtol=0, atol=0) is None
    assert np.array_equal(data, d0)
    assert (ps.fast, ps.cleanstrong, ps.speed) == (ps0.fast, ps0.cleanstrong, ps0.speed)


def test_default_rng_runs():
    """rng=None / an int seed use numpy permutations; the result is still a valid split."""
    r = next(r for r in SQ if "sptext" in r and _text(r["sptext"]) and int(r["data"]) == 1)
    data, ps = _sq_inputs(r)
    ci, c, pind = _args(r)
    ll, p1, p2, ng = choose_node_split(graph_from_mat(r["graph"]), ci, c, pind, data, ps,
                                       rng=3)
    assert np.isfinite(ll) and ng is not None


# --- spied baseline calls ------------------------------------------------------------------

BL_RUNS = [str(x) for x in np.ravel(FX["bl_run"])]


def test_spied_runs_match_baseline():
    """The spy and the pass-through shim do not change the runs."""
    for run, ll in zip(BL_RUNS, np.ravel(FX["bl_ll"])):
        s, d = run.split(":")
        expected = FEAT_LL.get((s, d), REL_LL.get((s, d)))
        assert ll == pytest.approx(expected, rel=1e-12), run
    assert [int(x) for x in np.ravel(FX["bl_ncalls"])] == [22, 76, 12, 114]
    assert len(FX["bl"]) == 24


def _bl_inputs(b):
    run = BL_RUNS[int(b["run"]) - 1]
    s, d = run.split(":")
    q = b["ps"]
    k = DSNAMES.index(d) + 1
    data, ps = _ps(k, structname=str(q["structname"]), speed=int(q["speed"]),
                   cleanstrong=int(q["cleanstrong"]))
    ps = ps.replace(fixedall=int(q["fixedall"]), fixedinternal=int(q["fixedinternal"]),
                    fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]))
    return data, ps, run


@pytest.mark.parametrize("i", range(len(FX["bl"])))
def test_baseline_calls(i):
    b = FX["bl"][i]
    data, ps, run = _bl_inputs(b)
    check_call(b, data, ps, f"bl {run} call {int(b['n'])}")


# --- live Octave ---------------------------------------------------------------------------

def _same_records(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["ll"]) == float(y["ll"]) or np.isnan(float(x["ll"]))
        np.testing.assert_array_equal(np.atleast_1d(x["part1"]), np.atleast_1d(y["part1"]))


@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "search.mat"
    octave.eval(f"fx_search('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    _same_records(fx["sq"], FX["sq"])
    _same_records(fx["bl"], FX["bl"])
    np.testing.assert_array_equal(fx["bl_ll"], FX["bl_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "search7919.mat"
    octave.eval(f"fx_search('{out}', 7919);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    sq = list(fx["sq"])
    assert sum(bool(_text(r.get("sptext", ""))) for r in sq) > 0
    for i, r in enumerate(sq):
        data, ps = _sq_inputs(r)
        check_call(r, data, ps, f"fresh sq {i}")
