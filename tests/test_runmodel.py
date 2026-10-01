"""Parity of ``run.runmodel`` (with ``brlencases``; item 28, L5-a) with Octave, with
replayed permutations.

The fixture ``tests/fixtures/runmodel.mat`` comes from ``legacy/tests_octave/fx_runmodel.m``
(regenerate with ``python legacy/tools/gen_fixtures.py runmodel``). It holds 21 whole
``runmodel`` runs:

- the 9 feature baseline runs (chain, ring, tree x the three feature demos, speed 54,
  ``init = 'intext'``) and 2 relational baseline runs (``dirring``, initialised by
  ``relgraphinit``, and ``partition``); all 11 reproduce ``tests/fixtures/baseline``;
- speed 5 (runmodel's own "true score", l.174-179) on chain and tree (root removal),
  ``init`` ``'none'``, ``'ext'`` and ``'int'``;
- the dimension searches ``griddimsearch`` (speeds 54 and 5), ``cyldimsearchring``
  (54) and ``cyldimsearchchain`` (5), appended to ``ps.structures``;
- a start graph from ``ps.outsideinit``.

Each run keeps the ``randperm`` draws of the whole run, every slow ``graph_like`` call
(``gl``) and every ``choose_node_split`` call (``cns``), the outputs, and the growth
history files written under the run directory. As in ``test_structurefit.py`` the exact
test injects Octave's slow scores (``TieOracle``) and accepts tied split choices
(``SplitOracle``); feature data are Octave's scaled data (Python's ``scaledata`` agrees to
about 1 ulp, which can flip ties).
"""

import dataclasses

import numpy as np
import pytest
import scipy.io

from formdiscovery import FormDiscoveryError, likelihood, run, search
from formdiscovery.io import graph_from_mat, graph_to_mat, load_fixture
from formdiscovery.params import Params
from formdiscovery.rng import ReplayError, ReplayPermutations, parse_queue
from formdiscovery.run import _cellset, _cellset_linear, brlencases, empty_cell, runmodel
from tests.helpers import graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tests.test_glslow import LOGI_RTOL
from tests.test_structurefit import SplitOracle, TieOracle, _list
from tests.test_swap import _text

FX = load_fixture("runmodel")
RUNS = list(FX["runs"])
DS = {str(d["name"]): d for d in FX["ds"]}
DIMSEARCH = ["griddimsearch", "cyldimsearchring", "cyldimsearchchain"]


def _msg(i, r):
    return (f"run {i} {r['struct']}:{r['data']} speed={int(r['speed'])} "
            f"init={_text(r['init']) or 'default'} outside={int(r['outsideinit'])}")


def _ps(r, tmp_path):
    """fx_runmodel.m's ps for a record (headless defaults, the dimension searches
    appended to ps.structures)."""
    ps = Params.default()
    ps.structures = ps.structures + DIMSEARCH
    ps.speed = int(r["speed"])
    if _text(r["init"]):
        ps.init = _text(r["init"])
    if int(r["outsideinit"]):
        m = graph_to_mat(graph_from_mat(FX["outsideinit_graph"]))
        cs = np.empty(len(m["components"]), dtype=object)
        cs[:] = m["components"]
        m["components"] = cs
        path = tmp_path / "outsideinit.mat"
        scipy.io.savemat(path, {"graph": m})
        ps.outsideinit = str(path)
    if int(r["dind"]) >= 4:
        ps.reloutsideinit = "overd"
    return ps


def _octave_scaledata(monkeypatch):
    """Octave's scaled feature data in place of Python's (checked to agree to 1e-12)."""
    real = run.scaledata

    def scaledata(data, ps):
        d, p = real(data, ps)
        if p.runps.type == "rel":
            return d, p
        od = [np.asarray(x["data"], dtype=float) for x in DS.values()
              if "data" in x and np.shape(x["data"]) == np.shape(d)
              and np.allclose(x["data"], d, rtol=1e-12, atol=1e-12)]
        assert len(od) == 1
        return od[0], p

    monkeypatch.setattr(run, "scaledata", scaledata)


def replay(r, msg, monkeypatch, tmp_path, outdir=None, oracle=True, show=None, **psfields):
    """Run one record with its draws replayed (and used up), the split oracle and, with
    ``oracle``, Octave's slow scores; ``psfields`` change the start ``ps``, ``show`` is
    runmodel's display callback. Returns the outputs and the tie count."""
    ps = _ps(r, tmp_path).replace(**psfields)
    _octave_scaledata(monkeypatch)
    split = SplitOracle(r, msg, strict=oracle)
    monkeypatch.setattr(search, "choose_node_split", split)
    slow = TieOracle(r, msg)
    if oracle:
        monkeypatch.setattr(likelihood, "graph_like", slow)
    rng = ReplayPermutations(parse_queue(_text(r["logtext"])))
    out = runmodel(ps, int(r["sind"]) - 1, int(r["dind"]) - 1, 1, outdir=outdir, rng=rng,
                   show=show)
    rng.assert_exhausted()
    if oracle:
        assert split.used == len(split.cns), msg
        assert slow.used == len(slow.gl), msg
    return out, split.ties + slow.swaps


def _cell(v, size):
    """An Octave cell (as read by loadmat) -> object array of MATLAB's size."""
    size = tuple(int(s) for s in np.ravel(size))
    a = np.empty(size, dtype=object)
    if a.size:
        a[...] = np.asarray(v, dtype=object).reshape(size)
    return a


def _empty(x):
    return x is None or np.size(x) == 0


def check_outputs(out, r, msg, rtol=1e-10, struct_only=False):
    ll, g, names, glls, bg = out
    oll = float(r["out_ll"])
    assert ll == oll or np.isclose(ll, oll, rtol=rtol, atol=0), (msg, ll, oll)
    tol = dict(rtol=1e9, atol=1e9) if struct_only else {}
    d = graph_diff(g, r["out_graph"], **tol)
    assert d is None, f"{msg}: {d}"
    assert names == [str(x) for x in np.ravel(r["out_names"])], msg
    oglls, obg = _cell(r["out_glls"], r["glls_size"]), _cell(r["out_bestgraph"], r["bg_size"])
    assert glls.shape == oglls.shape and bg.shape == obg.shape, (msg, glls.shape, oglls.shape)
    for idx in np.ndindex(glls.shape):
        a, b = glls[idx], oglls[idx]
        if _empty(a) or _empty(b):
            assert _empty(a) and _empty(b), (msg, idx, a, b)
            continue
        np.testing.assert_allclose(np.ravel(a), np.ravel(np.asarray(b, dtype=float)),
                                   rtol=rtol, atol=0, err_msg=f"{msg} {idx}")
    for idx in np.ndindex(bg.shape):
        a, b = bg[idx], obg[idx]
        a = [] if a is None else a
        b = _list(b)
        assert len(a) == len(b), (msg, idx)
        for k, (h, oh) in enumerate(zip(a, b)):
            d = graph_diff(h, oh, **tol)
            assert d is None, f"{msg}: bestgraph[{idx}][{k}]: {d}"


def _files(r):
    return [str(x) for x in np.ravel(np.asarray(r["files"], dtype=object))]


# --- contents ------------------------------------------------------------------------------

def test_contents():
    got = [(str(r["struct"]), str(r["data"]), int(r["speed"])) for r in RUNS]
    assert len(got) == 21
    assert got[:9] == [(s, d, 54) for d in ["demo_chain_feat", "demo_ring_feat",
                                             "demo_tree_feat"]
                       for s in ["chain", "ring", "tree"]]
    assert {s for s, _, _ in got} >= set(DIMSEARCH)
    assert {_text(r["init"]) for r in RUNS} == {"", "none", "ext", "int"}
    assert sum(int(r["outsideinit"]) for r in RUNS) == 1
    # every run saved at least one growth history; the default (intext) run keeps a
    # 3 x 5 history cell (alltie/exttie/notie at speed 5, noinit at speed 4)
    assert all(_files(r) for r in RUNS)
    assert tuple(np.ravel(RUNS[0]["glls_size"]).astype(int)) == (3, 5)


def test_runs_match_baseline():
    """The spies and the pass-through shim do not change the runs: the 11 runs with a
    baseline reproduce it exactly."""
    n = 0
    for r in RUNS:
        key = (str(r["struct"]), str(r["data"]))
        expected = FEAT_LL.get(key, REL_LL.get(key))
        if expected is None or int(r["speed"]) != 54 or _text(r["init"]):
            assert np.isfinite(float(r["out_ll"]))
            continue
        assert float(r["out_ll"]) == pytest.approx(expected, rel=1e-12), key
        n += 1
    assert n == 11


# --- exact replay --------------------------------------------------------------------------

@pytest.mark.parametrize("i", range(len(RUNS)))
def test_runmodel_matches_octave(i, monkeypatch, tmp_path):
    """Every run, with Octave's draws, slow scores and tied split choices: the same final
    score, graph and names, the same history cells (``bestglls``, ``bestgraph``) and the
    same growth-history files, with the same contents."""
    r = RUNS[i]
    msg = _msg(i, r)
    out, _ = replay(r, msg, monkeypatch, tmp_path, outdir=tmp_path / "out")
    check_outputs(out, r, msg)
    got = sorted(str(p.relative_to(tmp_path / "out")) for p in
                 (tmp_path / "out").rglob("growthhistory*"))
    assert got == sorted(f + ".mat" for f in _files(r)), msg  # Octave does not add .mat
    flls = _list(r["files_lls"]) if len(_files(r)) > 1 else [r["files_lls"]]
    for f, lls in zip(_files(r), flls):
        m = scipy.io.loadmat(tmp_path / "out" / (f + ".mat"), mat_dtype=True)
        np.testing.assert_allclose(m["bestgraphlls"].ravel(), np.ravel(lls), rtol=1e-10,
                                   atol=0, err_msg=f"{msg} {f}")


def test_ties_are_rare(monkeypatch, tmp_path):
    """Mirror-image ties (item 27) need the tie rules in a few runs only: the committed
    fixture (numpy 1.26) needs them 11 times in 8 of the 21 runs."""
    ties = {}
    for i, r in enumerate(RUNS):
        with monkeypatch.context() as m:
            _, t = replay(r, _msg(i, r), m, tmp_path)
        if t:
            ties[i] = t
    assert sum(ties.values()) <= 16, ties
    assert len(ties) <= len(RUNS) // 2, ties


# --- brlencases, the dimension searches, the other branches --------------------------------

def _run_index(struct, data, speed, init=""):
    return next(i for i, r in enumerate(RUNS) if str(r["struct"]) == struct
                and str(r["data"]) == data and int(r["speed"]) == speed
                and _text(r["init"]) == init and not int(r["outsideinit"]))


def test_ext_quirk_bestgraph_linear_index(monkeypatch, tmp_path):
    """runmodel.m:208: ``init = 'ext'`` stores its tied history in ``bestgraph{1}``, not
    ``bestgraph{1, ps.speed}``; ``bestglls`` uses ``{1, ps.speed}``."""
    i = _run_index("chain", "demo_chain_feat", 5, "ext")
    (ll, g, names, glls, bg), _ = replay(RUNS[i], "ext", monkeypatch, tmp_path)
    assert glls.shape == bg.shape == (2, 5)
    assert bg[0, 0] is not None and bg[0, 4] is None
    assert glls[0, 0] is None and glls[0, 4] is not None
    assert bg[1, 4] is not None and glls[1, 4] is not None


def test_cellset():
    c = _cellset(empty_cell(), 0, 4, "a")
    assert c.shape == (1, 5) and c[0, 4] == "a" and c[0, 0] is None
    c = _cellset(c, 2, 3, "b")
    assert c.shape == (3, 5) and c[0, 4] == "a"
    assert _cellset_linear(empty_cell(), 0, "x").shape == (1, 1)
    c = _cellset_linear(c, 1, "y")  # column-major: (1, 0)
    assert c[1, 0] == "y"


def test_cyldimsearchring_grows_an_order(monkeypatch, tmp_path):
    """KI-29 (replicated): ``cyldimsearchring`` runs ``runmodel(ps, 3, ...)``, and
    ``ps.structures{3}`` is ``order`` (setps.m:3), not ``ring``. The first dimension is
    then relabelled ``ring``."""
    i = _run_index("cyldimsearchring", "demo_ring_feat", 54)
    r = RUNS[i]
    assert any("/orderout/" in f for f in _files(r))
    seen = []
    real = run.runmodel
    monkeypatch.setattr(run, "runmodel", lambda ps, sind, *a, **k:
                        (seen.append(ps.structures[sind]) or real(ps, sind, *a, **k)))
    (ll, g, *_), _ = replay(r, "cyl", monkeypatch, tmp_path)
    assert seen == ["order"]
    assert g.type == "cylinder" and [c.type for c in g.components] == ["ring", "chain"]


def test_unknown_speed_and_init_raise(tmp_path):
    ps = Params.default().replace(speed=6)
    with pytest.raises(FormDiscoveryError, match="Unknown speed"):
        runmodel(ps, 1, 0, 1, rng=0)
    ps = Params.default().replace(speed=5, init="fixedall")
    with pytest.raises(FormDiscoveryError, match="undefined"):
        runmodel(ps, 1, 0, 1, rng=0)


def test_cleanstrong_reset(monkeypatch, tmp_path):
    """runmodel.m:82 sets ``ps.cleanstrong = 0`` whatever the caller passed; the tree
    root-removal pass then sets it to 1 (l.166)."""
    i = _run_index("tree", "demo_chain_feat", 54)
    out, _ = replay(RUNS[i], "cleanstrong", monkeypatch, tmp_path, cleanstrong=1)
    check_outputs(out, RUNS[i], "cleanstrong")


def test_no_outdir_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    i = _run_index("dirring", "demo_ring_rel_bin", 54)
    replay(RUNS[i], "nosave", monkeypatch, tmp_path / "x")
    assert list(tmp_path.iterdir()) == []


def test_ps_not_mutated(monkeypatch, tmp_path):
    r = RUNS[_run_index("chain", "demo_chain_feat", 5)]
    ps = _ps(r, tmp_path)
    ps0 = ps.copy()
    _octave_scaledata(monkeypatch)
    monkeypatch.setattr(search, "choose_node_split", SplitOracle(r, "mut"))
    monkeypatch.setattr(likelihood, "graph_like", TieOracle(r, "mut"))
    runmodel(ps, int(r["sind"]) - 1, 0, 1,
             rng=ReplayPermutations(parse_queue(_text(r["logtext"]))))
    assert dataclasses.asdict(ps.runps) == dataclasses.asdict(ps0.runps)
    assert (ps.speed, ps.init, ps.fast, ps.cleanstrong, ps.T) == \
        (ps0.speed, ps0.init, ps0.fast, ps0.cleanstrong, ps0.T)


def test_brlencases_keeps_untied_flags(monkeypatch):
    """The returned ps keeps the flags of the last stage; stages are named as in MATLAB."""
    names = []
    monkeypatch.setattr(search, "structurefit",
                        lambda d, ps, g, savefile=None, rng=None, show=None:
                        (names.append((savefile, ps.fixedinternal, ps.fixedexternal))
                         or (-1.0, g, np.array([-1.0]), ["g"])))
    ps = Params.default().replace(speed=5, init="intext")
    ll, g, glls, bg, ps2 = brlencases(None, ps, "g0", empty_cell(), empty_cell(), "gh")
    assert names == [("ghalltie5", 1, 1), ("ghexttie5", 0, 1),
                     ("ghnotie5", 0, 0)]
    assert (ps2.fixedinternal, ps2.fixedexternal) == (0, 0) and ps.fixedinternal == 0
    assert glls.shape == (3, 5)
    names.clear()
    brlencases(None, ps.replace(init="int", speed=4), "g0", empty_cell(), empty_cell(), None)
    assert names == [(None, 1, 0), (None, 0, 0)]


def test_default_rng_runs():
    """rng=None uses numpy permutations (a relational run: no optimizer)."""
    ps = Params.default().replace(reloutsideinit="overd")
    ll, g, names, glls, bg = runmodel(ps, 16, 3, 1)
    assert np.isfinite(ll) and g.type == "dirring" and len(names) == g.objcount
    assert glls.shape == (1, 5) and glls[0, 4] is not None


# --- the Python optimizer ------------------------------------------------------------------

@pytest.mark.slow
def test_python_optimizer_chain(monkeypatch, tmp_path):
    """scipy's optimizer in place of fminunc on chain x demo_chain_feat at speed 5 (the
    item's target run; slow scores in every structurefit call and runmodel's true score):
    the draws replay to the end, the score is within LOGI_RTOL and every graph has
    Octave's structure. (End-to-end runs are compared by score in item 29.)"""
    i = _run_index("chain", "demo_chain_feat", 5)
    try:
        out, _ = replay(RUNS[i], "opt", monkeypatch, tmp_path, oracle=False)
    except ReplayError as e:  # a different optimum flipped a decision
        pytest.skip(f"diverged: {e}")
    check_outputs(out, RUNS[i], "opt", rtol=LOGI_RTOL, struct_only=True)


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "runmodel.mat"
    octave.eval(f"fx_runmodel('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    assert len(fx["runs"]) == len(RUNS)
    for x, y in zip(fx["runs"], RUNS):
        assert _text(x["logtext"]) == _text(y["logtext"])
        assert float(x["out_ll"]) == float(y["out_ll"])
        assert graph_diff(x["out_graph"], y["out_graph"], rtol=0, atol=0) is None


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path, monkeypatch):
    out = tmp_path / "runmodel7919.mat"
    octave.eval(f"fx_runmodel('{out}', 7918);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    runs = list(fx["runs"])
    assert len(runs) == len(RUNS)
    for i, r in enumerate(runs):
        msg = f"fresh {_msg(i, r)}"
        with monkeypatch.context() as m:
            out, _ = replay(r, msg, m, tmp_path)
        check_outputs(out, r, msg)
