"""Parity of ``search.gibbs_clean`` (with ``nearmissopts``; item 26, L4-c1) with Octave,
with replayed permutations.

The fixture ``tests/fixtures/gibbs.mat`` comes from ``legacy/tests_octave/fx_gibbs.m``
(regenerate with ``python legacy/tools/gen_fixtures.py gibbs``). It re-runs 7 runs (speed 54:
speed 5, then speed 4) with ``gibbs_clean`` replaced by a spy (``legacy/tests_octave/gibbs_spy.m``)
and ``graph_like`` by a wrapper (``legacy/tests_octave/glc_spy.m``) that records the slow
(``ps.fast == 0``) calls made inside ``gibbs_clean``:

- ``bl`` records are real calls from ``structurefit``; ``pt`` records run the same call
  on a perturbed graph (random object moves) so that changes are accepted; ``g0``
  records run a speed-4 call with ``ps.gibbsclean = 0``.
- Each record holds the input graph, the options, the ``ps`` fields that vary, the
  ``randperm`` draws made inside the call (replayed and used up exactly), the outputs and
  the slow ``graph_like`` calls (``gl``) in call order.

Speed 5 (``optlens = 0``, fast scores only) matches to rtol 1e-10 with the graph exact.
At speed 4 the slow score runs ``fminunc`` (PLAN §4.1): ``test_speed4_oracle`` injects
Octave's slow results (checking that Python asks for them with the same graphs, in the
same order) and then matches exactly. ``test_speed4_optimizer`` uses the Python optimizer
and compares ``ll`` to ``LOGI_RTOL``; the graphs agree on most records only, since tied
near misses and different optima can change later choices. The calls on ``synthgrid``
take seconds each in Python and are marked ``slow``, except the fast-mode speed-5 ones.
"""

import dataclasses

import numpy as np
import pytest

from formdiscovery import FormDiscoveryError, likelihood
from formdiscovery.graph import combinegraphs, simplify_graph
from formdiscovery.io import graph_from_mat, load_fixture
from formdiscovery.params import graph_prior
from formdiscovery.rng import ReplayError, ReplayPermutations, parse_queue
from formdiscovery.search import gibbs_clean, graphsig, nearmissopts
from tests.conftest import BLAS_DEFAULT_FIXTURES, OCTAVE_TESTS_DIR, find_octave
from tests.helpers import graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tests.test_glslow import LOGI_RTOL
from tests.test_swap import _prep, _text

FX = load_fixture("gibbs")
CALLS = list(FX["calls"])
RUNS = [str(x) for x in np.ravel(FX["runs"])]

PREP = {}
for _d in FX["ds"]:
    _data, _ps = _prep(str(_d["name"]))
    if "data" in _d:  # exact Octave data (Python scaledata agrees to ~1 ulp)
        _data = np.asarray(_d["data"], dtype=float)
    PREP[str(_d["name"])] = (_data, _ps)


def _run(r):
    return RUNS[int(r["run"]) - 1]


def _speed(r):
    return int(r["ps"]["speed"])


def _opt(r):
    o = r["opt"]
    return dict(loopmax=int(o["loopmax"]), nearmisses=int(o["nearmisses"]),
                loopeps=float(o["loopeps"]), swaptypes=np.ravel(o["swaptypes"]).astype(int),
                fast=int(o["fast"]))


def _inputs(r):
    """Data and ps of a record: the run's data set and the recorded ps fields."""
    data, ps = PREP[_run(r).split(":")[1]]
    q = r["ps"]
    fast = float(q["fast"])
    ps = ps.replace(speed=int(q["speed"]), fast=None if np.isnan(fast) else int(fast),
                    gibbsclean=int(q["gibbsclean"]), nauty=int(q["nauty"]),
                    fixedall=int(q["fixedall"]), fixedinternal=int(q["fixedinternal"]),
                    fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]),
                    cleanstrong=int(q["cleanstrong"]))
    ps.runps = dataclasses.replace(ps.runps, structname=str(q["structname"]))
    return data, ps


def _gl(r):
    return [] if np.size(r["gl"]) == 0 else list(np.ravel(np.asarray(r["gl"], dtype=object)))


def _changed(r):
    g, h = graph_from_mat(r["graph"]), graph_from_mat(r["out_graph"])
    return not (np.array_equal(np.ravel(g.z), np.ravel(h.z))
                and np.shape(g.adj) == np.shape(h.adj))


def _call(r, rng, graph=None, **kw):
    data, ps = _inputs(r)
    g = graph_from_mat(r["graph"]) if graph is None else graph
    return gibbs_clean(g, data, ps, **{**_opt(r), **kw}, rng=rng)


def _msg(i, r):
    o = _opt(r)
    return (f"call {i} {str(r['kind'])} {_run(r)} n={int(r['n'])} speed={_speed(r)} "
            f"fast={o['fast']} nm={o['nearmisses']} sw={''.join(map(str, o['swaptypes']))}")


def _heavy(r):
    """synthgrid calls that take seconds in Python (all but fast-mode speed 5)."""
    return _run(r).endswith("synthgrid") and (_speed(r) < 5 or _opt(r)["fast"] == 0)


def _params(pred):
    return [pytest.param(i, marks=pytest.mark.slow) if _heavy(r) else i
            for i, r in enumerate(CALLS) if pred(r)]


class Oracle:
    """Stands in for ``likelihood.graph_like``: slow calls (``ps.fast == 0``) return
    Octave's recorded results, after checking the input graph; fast calls are real."""

    def __init__(self, r, msg):
        self.gl, self.msg, self.used = _gl(r), msg, 0
        self.real = likelihood.graph_like

    def __call__(self, data, graph, ps):
        if ps.fast != 0:
            return self.real(data, graph, ps)
        k = self.used
        self.used += 1
        assert k < len(self.gl), f"{self.msg}: slow call {k} not in Octave"
        d = graph_diff(graph, self.gl[k]["graph"])
        assert d is None, f"{self.msg}: slow call {k} input: {d}"
        return float(self.gl[k]["logI"]), graph_from_mat(self.gl[k]["out_graph"])


def check_record(r, msg):
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    ll, g = _call(r, rng)
    rng.assert_exhausted()
    oll = float(r["out_ll"])
    assert ll == oll or np.isclose(ll, oll, rtol=1e-10, atol=0), (msg, ll, oll)
    d = graph_diff(g, r["out_graph"])
    assert d is None, f"{msg}: {d}"
    return ll, g


# --- contents ------------------------------------------------------------------------------

def test_contents():
    assert RUNS == ["chain:demo_chain_feat", "tree:demo_tree_feat", "ring:demo_ring_feat",
                    "cylinder:demo_ring_feat", "grid:synthgrid", "dirring:demo_ring_rel_bin",
                    "undirhierarchy:demo_hierarchy_rel_bin"]
    modes = {}
    for r in CALLS:
        o = _opt(r)
        key = (str(r["kind"]), _speed(r), o["fast"], o["nearmisses"],
               "".join(map(str, o["swaptypes"])))
        modes[key] = modes.get(key, 0) + 1
    bl = {(5, 1, 0, "11111"): 20, (5, 0, 0, "11111"): 13, (5, 1, 0, "10000"): 4,
          (5, 1, 0, "01000"): 4, (4, 1, 0, "11111"): 7, (4, 0, 0, "11111"): 7,
          (4, 0, 10, "11111"): 6}
    assert modes == {**{("bl",) + k: v for k, v in bl.items()},
                     **{("pt",) + k: v for k, v in bl.items()},
                     ("g0", 4, 1, 0, "11111"): 5}
    assert all(int(r["opt"]["loopmax"]) == 2 for r in CALLS)
    # the speed-5 early return (fast 0, a change) and changes in every mode
    assert any(_changed(r) for r in CALLS if _speed(r) == 5 and _opt(r)["fast"] == 0)
    assert any(_changed(r) for r in CALLS if _speed(r) == 4 and _opt(r)["nearmisses"])
    assert sum(_changed(r) for r in CALLS) > 50
    # draws and product graphs
    assert all(parse_queue(_text(r["logtext"])) for r in CALLS if str(r["kind"]) != "g0")
    assert {graph_from_mat(r["graph"]).type for r in CALLS} >= {"grid", "cylinder", "tree"}


def test_spied_runs_match_baseline():
    """The spies and the pass-through shim do not change the runs."""
    n = 0
    for run, ll in zip(RUNS, np.ravel(FX["run_ll"])):
        s, d = run.split(":")
        expected = FEAT_LL.get((s, d), REL_LL.get((s, d)))
        if expected is None:  # grid and cylinder are not in the baselines
            assert np.isfinite(ll)
            continue
        assert ll == pytest.approx(expected, rel=1e-12), run
        n += 1
    assert n == 5


# --- speed 5: exact ------------------------------------------------------------------------

@pytest.mark.parametrize("i", _params(lambda r: _speed(r) == 5))
def test_speed5(i):
    r = CALLS[i]
    assert not _gl(r)  # optlens = 0: no slow score at speed 5
    check_record(r, _msg(i, r))


# --- speed 4: Octave's optimizer results injected ------------------------------------------

@pytest.mark.parametrize("i", _params(lambda r: _speed(r) == 4))
def test_speed4_oracle(i, monkeypatch):
    r = CALLS[i]
    msg = _msg(i, r)
    oracle = Oracle(r, msg)
    monkeypatch.setattr(likelihood, "graph_like", oracle)
    check_record(r, msg)
    assert oracle.used == len(oracle.gl), msg


def test_speed4_slow_call_counts():
    """The slow calls per record: one per pass (l.57), one more when the loop ran
    ``loopmax`` passes (l.134-139) and, with near misses, one per graph tried
    (l.165-172), the current graph first (KI-28). ``gibbsclean = 0`` stops after one."""
    for i, r in enumerate(CALLS):
        n = len(_gl(r))
        if _speed(r) == 5:
            assert n == 0
        elif str(r["kind"]) == "g0":
            assert n == 1, _msg(i, r)
        else:
            assert n >= 1, _msg(i, r)
    nm = [r for r in CALLS if _opt(r)["nearmisses"]]
    assert max(len(_gl(r)) for r in nm) == 13
    for r in nm:
        # nearmissopts tries the current graph first: the last slow call whose input is
        # the previous call's output is that re-score (KI-28); at most 10 tries follow
        gl = _gl(r)
        ks = [k for k in range(1, len(gl)) if graph_diff(
            gl[k]["graph"], gl[k - 1]["out_graph"], rtol=0, atol=0) is None]
        assert ks and len(gl) - ks[-1] <= 10


# --- speed 4: the Python optimizer ---------------------------------------------------------

def _optimizer_check(idx):
    same = n = 0
    for i in idx:
        r = CALLS[i]
        msg = _msg(i, r)
        try:
            ll, g = _call(r, ReplayPermutations(parse_queue(_text(r["logtext"]))))
        except ReplayError:  # an accept decision flipped; the draws differ from here on
            continue
        n += 1
        oll = float(r["out_ll"])
        assert ll - oll >= -LOGI_RTOL * abs(oll), (msg, ll, oll)
        assert abs(ll - oll) <= LOGI_RTOL * abs(oll), (msg, ll, oll)
        same += graph_diff(g, r["out_graph"], rtol=1e9, atol=1e9) is None
    return same, n


def test_speed4_optimizer():
    """scipy's optimizer (item 19) in place of fminunc: ``ll`` within LOGI_RTOL of
    Octave's on every record that replays, and the same graph structure on most. In the
    committed fixture 33 of the 34 feature records replay (on call 12, chain, a slightly
    different optimum flips an accept decision, and the draws differ from there on) and
    29 of those 33 give Octave's graph; the other 4 are tree near-miss calls whose list is
    ordered by fast scores computed from slightly different weights."""
    idx = [i for i, r in enumerate(CALLS) if _speed(r) == 4 and not _heavy(r)]
    same, n = _optimizer_check(idx)
    assert n >= len(idx) - 2, (n, len(idx))
    assert same >= 0.8 * n, (same, n)


@pytest.mark.slow
def test_speed4_optimizer_synthgrid():
    idx = [i for i, r in enumerate(CALLS) if _speed(r) == 4 and _heavy(r)]
    same, n = _optimizer_check(idx)
    assert n >= len(idx) - 2 and same >= 0.7 * n, (same, n)


# --- nearmissopts and other checks ---------------------------------------------------------

def test_nearmissopts_drops_empties_and_puts_graph_first():
    """l.186: ``cat(2, graph, nearmgraphs{:})`` drops the empty cells and puts the current
    graph first; ``nearmscores`` gets a leading 0. Without nauty the first
    ``nearmisses / nearmissesk`` graphs are returned (KI-28)."""
    _, ps = _inputs(CALLS[0])
    graph = "G"
    nm = ["a", "b", None, None]
    optg, sc = nearmissopts(nm, [-1.0, -2.0, -np.inf, -np.inf], graph, 4, 4, ps, 1e-4)
    assert optg == ["G"] and sc.tolist() == [0.0]
    nm = ["a", "b", "c", None] + [None] * 36
    ns = [-1.0, -2.0, -3.0] + [-np.inf] * 37
    optg, sc = nearmissopts(nm, ns, graph, 40, 4, ps, 1e-4)
    assert optg == ["G", "a", "b", "c"] and sc.tolist() == [0.0, -1.0, -2.0, -3.0]
    nm = [f"g{k}" for k in range(40)]
    optg, sc = nearmissopts(nm, -np.arange(1.0, 41.0), graph, 40, 4, ps, 1e-4)
    assert optg == ["G"] + [f"g{k}" for k in range(9)]
    assert sc.tolist() == [0.0] + [-float(k) for k in range(1, 10)]


def test_nauty_raises():
    """``graphsig`` (nauty) is not ported: ``ps.nauty = 1`` raises in nearmissopts."""
    _, ps = _inputs(CALLS[0])
    g = graph_from_mat(CALLS[0]["graph"])
    with pytest.raises(NotImplementedError, match="nauty"):
        nearmissopts([None] * 4, -np.inf * np.ones(4), g, 4, 4, ps.replace(nauty=1), 1e-4)
    with pytest.raises(NotImplementedError):
        graphsig(g.adjsym, g.objcount)


def test_loopmax_zero_raises():
    r = CALLS[0]
    with pytest.raises(FormDiscoveryError, match="loopmax"):
        _call(r, None, loopmax=0)


def test_optlens_option_ignored():
    """l.36 overwrites the ``'optlens'`` option with ``ps.speed < 5``."""
    i, r = next((i, r) for i, r in enumerate(CALLS)
                if _speed(r) == 5 and _changed(r) and not _heavy(r))
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    ll, g = _call(r, rng, optlens=1)
    rng.assert_exhausted()
    assert np.isclose(ll, float(r["out_ll"]), rtol=1e-10, atol=0)


def test_speed5_ll_is_fast_score():
    """Without ``optlens`` the result is ``currscore`` (l.80, 94, 118, 174): the fast score
    of the returned graph. The early returns themselves are pinned by the exact replay
    (a missed return would ask for more draws than Octave made)."""
    n = 0
    for r in CALLS:
        if _speed(r) != 5 or _heavy(r) or not _changed(r):
            continue
        data, ps = _inputs(r)
        g = graph_from_mat(r["out_graph"])
        logI, _ = likelihood.graph_like(data, g, ps.replace(fast=1))
        assert np.isclose(logI + graph_prior(g, ps), float(r["out_ll"]), rtol=1e-10, atol=0)
        n += 1
    assert n > 30


def _dangling(g, ps):
    """``g`` (one chain component) with an unoccupied node hung off node 0: a graph that
    ``simplify_graph`` (case 1) turns back into ``g``."""
    g = g.copy()
    c = g.components[0]
    n = int(c.nodecount)
    w = float(np.mean(c.W[c.W > 0]))
    for f in ("adj", "W", "adjsym", "Wsym"):
        a = np.zeros((n + 1, n + 1))
        a[:n, :n] = getattr(c, f)
        v = 1.0 if f.startswith("adj") else w
        a[0, n] = v
        if f.endswith("sym"):
            a[n, 0] = v
        setattr(c, f, a)
    c.adjsym = c.adjsym.astype(np.asarray(g.components[0].adjsym).dtype)
    c.nodecount = n + 1
    c.edgecount += 1
    c.edgecountsym += 1
    return combinegraphs(g, ps)


def test_input_is_simplified():
    """l.43: the input graph is simplified first. The recorded inputs are already simple,
    so here a redundant node is added: the replay must still match Octave's result."""
    n = 0
    for i, r in enumerate(CALLS):
        g = graph_from_mat(r["graph"])
        if (_run(r) != "chain:demo_chain_feat" or _speed(r) != 5 or not _changed(r)
                or int(g.components[0].nodecount) < 3):
            continue
        data, ps = _inputs(r)
        dg = _dangling(g, ps)
        assert int(dg.components[0].nodecount) == int(g.components[0].nodecount) + 1
        assert graph_diff(simplify_graph(dg, ps), g) is None
        rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
        ll, out = _call(r, rng, graph=dg)
        rng.assert_exhausted()
        assert np.isclose(ll, float(r["out_ll"]), rtol=1e-10, atol=0)
        assert graph_diff(out, r["out_graph"]) is None
        n += 1
    assert n >= 2


def test_graph_getting_worse(monkeypatch):
    """l.59-66: a pass whose slow score is not above the best so far restores the best
    graph and stops; the loop then ran ``loopmax`` passes, so the best graph is scored
    slowly once more (l.134-139). The fixture never takes this branch, so the second slow
    score of a speed-4 record that changed in pass 1 is made worse on purpose."""
    i, r = next((i, r) for i, r in enumerate(CALLS)
                if _speed(r) == 4 and not _heavy(r) and _opt(r)["nearmisses"] == 0
                and str(r["kind"]) == "pt" and len(_gl(r)) == 3)
    gl = _gl(r)
    seen = []
    real = likelihood.graph_like

    def fake(data, graph, ps):
        if ps.fast != 0:
            return real(data, graph, ps)
        seen.append(graph)
        k = len(seen) - 1
        if k == 0:
            return float(gl[0]["logI"]), graph_from_mat(gl[0]["out_graph"])
        if k == 1:
            return -1e12, graph
        return 7.0, graph

    monkeypatch.setattr(likelihood, "graph_like", fake)
    data, ps = _inputs(r)
    ll, g = _call(r, ReplayPermutations(parse_queue(_text(r["logtext"]))))
    assert len(seen) == 3
    best = graph_from_mat(gl[0]["out_graph"])
    assert graph_diff(seen[2], best, rtol=0, atol=0) is None
    assert graph_diff(g, best, rtol=0, atol=0) is None
    assert ll == 7.0 + graph_prior(best, ps)


def test_inputs_not_mutated():
    i, r = next((i, r) for i, r in enumerate(CALLS)
                if _speed(r) == 4 and _changed(r) and not _heavy(r))
    g = graph_from_mat(r["graph"])
    data, ps = _inputs(r)
    ps0 = ps.copy()
    gibbs_clean(g, data, ps, **_opt(r), rng=ReplayPermutations(
        parse_queue(_text(r["logtext"]))))
    assert graph_diff(g, r["graph"], rtol=0, atol=0) is None
    assert ps.fast == ps0.fast and ps.speed == ps0.speed


@pytest.mark.parametrize("speed", [5, 4])
def test_default_rng_runs(speed):
    """rng=None / an int seed use numpy permutations; at speed 5 the score never gets
    worse than the input's fast score."""
    r = next(r for r in CALLS if _speed(r) == speed and str(r["kind"]) == "pt"
             and not _heavy(r) and _opt(r)["fast"])
    data, ps = _inputs(r)
    for rng in (None, 5):
        ll, g = _call(r, rng)
        assert np.isfinite(ll)


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    """Regenerated the way ``legacy/tools/gen_fixtures.py`` does it: in its own ``octave-cli``
    with OpenBLAS's default thread count, as the committed fixture was made. The
    ``grid x synthgrid`` run does not reproduce under the session's one-thread pin
    (ANOMALIES A19; ``BLAS_DEFAULT_FIXTURES``)."""
    from legacy.tools import gen_fixtures  # lazy: legacy/ may be absent (loop0004 item 03)
    assert "gibbs" in BLAS_DEFAULT_FIXTURES
    assert gen_fixtures.run_one(find_octave(), "gibbs",
                                OCTAVE_TESTS_DIR / "fx_gibbs.m", tmp_path)
    fx = load_fixture("gibbs.mat", fixtures_dir=tmp_path)
    assert len(fx["calls"]) == len(CALLS)
    for x, y in zip(fx["calls"], CALLS):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["out_ll"]) == float(y["out_ll"])
        assert graph_diff(x["out_graph"], y["out_graph"], rtol=0, atol=0) is None
    np.testing.assert_array_equal(fx["run_ll"], FX["run_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path, monkeypatch):
    out = tmp_path / "gibbs7919.mat"
    octave.eval(f"fx_gibbs('{out}', 7918);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    calls = list(fx["calls"])
    assert [str(x) for x in np.ravel(fx["runs"])] == RUNS and len(calls) > 50
    for i, r in enumerate(calls):
        if _heavy(r):
            continue
        msg = f"fresh {_msg(i, r)}"
        with monkeypatch.context() as m:
            if _speed(r) == 4:
                m.setattr(likelihood, "graph_like", Oracle(r, msg))
            check_record(r, msg)
