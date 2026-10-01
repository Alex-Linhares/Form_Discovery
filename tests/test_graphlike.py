"""Parity of ``graph_like`` (dispatcher, ``graph_like.m``) and ``graph_like_conn`` in fast
mode (``ps.fast = 1``, ``graph_like_conn.m:6-32``; item 18, L3-b1) with Octave.

The fixture ``tests/fixtures/graphlike.mat`` comes from ``legacy/tests_octave/fx_graphlike.m``
(regenerate with ``python legacy/tools/gen_fixtures.py graphlike``):

- ``ds``: the three demo feature sets after runmodel's preprocessing;
- ``gh``: every ``bestgraph`` of the 19 feature baseline growth histories, scored in the
  tying mode its file was grown in and, for tied files, also untied; with
  ``graph_prior`` and the file's ``bestgraphlls`` entry;
- ``sy``: the 29 ``dataprob.mat`` graphs over 10 objects (some with unassigned objects)
  with random feature and similarity data in 4 tying modes;
- ``jd``: the 25 ``dpmiss.mat`` graphs with judges (missing-data chunk path);
- ``bl``: fast-mode ``graph_like`` calls captured by a spy in chain x demo_chain_feat and
  tree x demo_tree_feat (run_baseline.m's settings); ``bl_ll`` the runs' final scores.

Tolerances (PLAN.md §2): rtol 1e-10 for ``logI`` and the weights of the returned graph,
structure exact.
"""

import dataclasses

import numpy as np
import pytest

import formdiscovery.likelihood_feat as lf
from formdiscovery import FormDiscoveryError
from formdiscovery.io import graph_from_mat, load_dataset, load_fixture
from formdiscovery.likelihood import graph_like
from formdiscovery.params import DATASETS, Params, RunPs, graph_prior, setrunps, structcounts
from formdiscovery.preprocess import scaledata
from tests.helpers import assert_graph_equal

FX = load_fixture("graphlike")
MODES = [tuple(int(x) for x in m) for m in np.atleast_2d(FX["modes"])]
BASELINE_LL = {"chain:demo_chain_feat": -8247.204813441429,
               "tree:demo_tree_feat": -8707.813669003906}


def _err(x):
    return str(x) if np.size(x) else ""


def _mode(ps, mi):
    fa, fi, fe, pt = MODES[int(mi) - 1]
    return ps.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt)


def _prep(name):
    """runmodel.m:27-95 without the graph initialisation (as fx_graphlike.m's prep)."""
    data = load_dataset(name)
    nobj, ps = setrunps(data, DATASETS.index(name), Params.default())
    data, ps = scaledata(data, ps)
    ps = ps.replace(overrideSS=0 if ps.overrideSS is None else ps.overrideSS, cleanstrong=0)
    return data, structcounts(nobj, ps)


PREP = {str(d["name"]): _prep(str(d["name"])) for d in FX["ds"]}
DSNAMES = [str(d["name"]) for d in FX["ds"]]
# exact Octave data (Python scaledata agrees to ~1 ulp, see test_python_data)
DSDATA = [np.asarray(d["data"], dtype=float) for d in FX["ds"]]
JDATA, PJ = _prep("judges")


def _check(logI, g, r, msg):
    np.testing.assert_allclose(logI, float(r["logI"]), rtol=1e-10, err_msg=msg)
    assert_graph_equal(g, r["out"], msg)


def _expect_chol(octmsg, fn):
    assert "positive definite" in octmsg, octmsg
    with pytest.raises(FormDiscoveryError, match="positive definite"):
        fn()


def test_fixture_contents():
    assert len(FX["gh_file"]) == 19
    assert len(FX["gh"]) == 82 and not any(_err(r["err"]) for r in FX["gh"])
    assert len(FX["sy"]) == 29 * 2 * 4 and len(FX["jd"]) == 25 * 2
    assert sum(bool(_err(r["err"])) for r in FX["sy"]) == 24
    assert sum(bool(_err(r["err"])) for r in FX["jd"]) == 2
    assert len(FX["bl"]) == 30
    assert DSNAMES == ["demo_chain_feat", "demo_ring_feat", "demo_tree_feat"]


def test_python_data():
    """Python's preprocessing gives the fixture's data and runps fields."""
    for d, name in zip(FX["ds"], DSNAMES):
        data, ps = PREP[name]
        np.testing.assert_allclose(data, d["data"], rtol=1e-12, atol=1e-14)
        assert ps.runps.type == str(d["type"])
        assert float(ps.runps.chunkcount) == float(d["chunkcount"])
    np.testing.assert_allclose(JDATA, FX["jdata"], rtol=1e-12, atol=1e-14)


def _gh_inputs(r):
    name = DSNAMES[int(r["data"]) - 1]
    g = graph_from_mat(r["graph"])
    ps = _mode(PREP[name][1], r["mode"])
    ps = ps.replace(fast=1, runps=dataclasses.replace(ps.runps, structname=g.type))
    return DSDATA[int(r["data"]) - 1], g, ps


@pytest.mark.parametrize("i", range(len(FX["gh"])))
def test_growth_history_graphs(i):
    r = FX["gh"][i]
    d, g, ps = _gh_inputs(r)
    msg = f"{FX['gh_file'][int(r['file']) - 1]} depth {int(r['depth'])} mode {int(r['mode'])}"
    logI, out = graph_like(d, g, ps)
    _check(logI, out, r, msg)
    np.testing.assert_allclose(graph_prior(out, ps), float(r["prior"]), rtol=1e-10,
                               err_msg=msg)


def test_growth_history_scores():
    """Speed-5 growth histories mostly store the fast-mode score (structurefit.m:248-250):
    in the file's own tying mode, logI + graph_prior equals bestgraphlls for 36 of the 47
    graphs. The exceptions are the 8 graphs of the speed-4 noinit files (slow-mode scores)
    and depth 2 of three demo_ring_feat alltie5 files, whose score does not come from a
    fast-mode call on the stored graph (probably a slow gibbs_clean pass; not checked)."""
    eq, other = [], []
    for r in FX["gh"]:
        if int(r["mode"]) != int(r["filemode"]):
            continue
        d, g, ps = _gh_inputs(r)
        logI, out = graph_like(d, g, ps)
        fname = FX["gh_file"][int(r["file"]) - 1]
        if abs(logI + graph_prior(out, ps) - float(r["bgll"])) < 1e-8:
            eq.append(fname)
        elif "noinit4" not in fname:
            other.append((fname, int(r["depth"])))
    assert len(eq) == 36 and not any("noinit4" in f for f in eq)
    assert sorted(other) == [("chainout/demo_ring_feat1/growthhistoryalltie5.mat", 2),
                             ("ringout/demo_ring_feat1/growthhistoryalltie5.mat", 2),
                             ("treeout/demo_ring_feat1/growthhistoryalltie5.mat", 2)]


@pytest.mark.parametrize("i", range(len(FX["sy"])))
def test_synthetic(i):
    r = FX["sy"][i]
    g = graph_from_mat(r["graph"])
    runps = RunPs(type="feat", chunkcount=-1, SS=None)
    if int(r["variant"]) == 2:
        runps.type, runps.dim = "sim", 30
    ps = _mode(Params.default().replace(missingdata=0, overrideSS=0, zglreg=0, fast=1,
                                        runps=runps), r["mode"])
    d = np.asarray(r["d"], dtype=float)
    msg = f"sy {i} {r['src']} variant {int(r['variant'])} mode {int(r['mode'])}"
    if _err(r["err"]):
        _expect_chol(_err(r["err"]), lambda: graph_like(d, g, ps))
        return
    logI, out = graph_like(d, g, ps)
    _check(logI, out, r, msg)


@pytest.mark.parametrize("i", range(len(FX["jd"])))
def test_judges(i):
    r = FX["jd"][i]
    g = graph_from_mat(r["graph"])
    ps = _mode(PJ, r["mode"]).replace(fast=1)
    d = np.asarray(FX["jdata"], dtype=float)
    if _err(r["err"]):
        _expect_chol(_err(r["err"]), lambda: graph_like(d, g, ps))
        return
    logI, out = graph_like(d, g, ps)
    _check(logI, out, r, f"jd {i} {r['src']} mode {int(r['mode'])}")


def _bl_ps(q, base):
    q = {k: (np.asarray(v).item() if np.size(v) == 1 and not isinstance(v, str) else v)
         for k, v in q.items()}
    assert str(q["type"]) == "feat" and not int(q["missingdata"])
    return base.replace(lbeta=q["lbeta"], sigbeta=q["sigbeta"], zglreg=int(q["zglreg"]),
                        overrideSS=int(q["overrideSS"]), fixedall=int(q["fixedall"]),
                        fixedinternal=int(q["fixedinternal"]),
                        fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]),
                        fast=1)


def test_spied_runs():
    """The spy does not change the runs, and fast mode is most of the calls."""
    runs = [str(x) for x in np.ravel(FX["bl_run"])]
    for run, ll in zip(runs, np.ravel(FX["bl_ll"])):
        assert ll == pytest.approx(BASELINE_LL[run], rel=1e-12)
    assert [int(x) for x in np.ravel(FX["bl_nfast"])] == [1065, 2186]
    assert [int(x) for x in np.ravel(FX["bl_nslow"])] == [43, 128]


def test_baseline_calls():
    runs = [str(x) for x in np.ravel(FX["bl_run"])]
    for b in FX["bl"]:
        name = runs[int(b["run"]) - 1].split(":")[1]
        data, base = PREP[name]
        d = DSDATA[DSNAMES.index(name)]
        ps = _bl_ps(b["ps"], base)
        g = graph_from_mat(b["graph"])
        logI, out = graph_like(d, g, ps)
        _check(logI, out, b, f"run {int(b['run'])} call {int(b['n'])}")


def test_returned_graph_roundtrip():
    """Only Wsym and sigma change, by exp(log(.)) rounding (graph_like_conn.m:29-30)."""
    r = FX["gh"][0]
    d, g, ps = _gh_inputs(r)
    _, out = graph_like(d, g, ps)
    assert_graph_equal(out, g, rtol=1e-14)
    fields = [f for f in vars(g) if f not in ("Wsym", "sigma")]
    assert_graph_equal(out, g, rtol=0, atol=0, fields=fields)


def test_data_subsetting(monkeypatch):
    """graph_like.m:7-14: feat rows / sim rows+columns of the assigned objects (z >= 0);
    rel data are passed whole to graph_like_rel."""
    seen = []
    monkeypatch.setattr(lf, "graph_like_conn", lambda d, g, p: seen.append(d) or (0.0, g))
    r = next(r for r in FX["sy"] if "missing" in str(r["src"]) and int(r["variant"]) == 2)
    g = graph_from_mat(r["graph"])
    obs = np.flatnonzero(g.z >= 0)
    assert len(obs) < len(g.z)
    D = np.arange(100.0).reshape(10, 10)
    ps = Params.default().replace(fast=1, runps=RunPs(type="sim", dim=30))
    graph_like(D, g, ps)
    np.testing.assert_array_equal(seen[-1], D[np.ix_(obs, obs)])
    graph_like(D, g, ps.replace(runps=RunPs(type="feat")))
    np.testing.assert_array_equal(seen[-1], D[obs, :])
    import formdiscovery.likelihood_rel as lr
    monkeypatch.setattr(lr, "graph_like_rel", lambda d, g, p: seen.append(d) or (0.0, g))
    rel = {"R": D, "type": "relbin"}
    graph_like(rel, g, ps.replace(runps=RunPs(type="rel")))
    assert seen[-1] is rel


def test_inputs_not_mutated():
    d, g, ps = _gh_inputs(FX["gh"][0])
    g0, d0 = g.copy(), d.copy()
    graph_like(d, g, ps)
    assert_graph_equal(g, g0, rtol=0, atol=0)
    np.testing.assert_array_equal(d, d0)


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "graphlike.mat"
    octave.eval(f"fx_graphlike('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for k in ("gh", "sy", "jd", "bl"):
        assert len(fx[k]) == len(FX[k])
        for a, b in zip(fx[k], FX[k]):
            assert _err(a["err"] if "err" in a else "") == _err(b["err"] if "err" in b else "")
            if "err" in a and _err(a["err"]):
                continue
            assert float(a["logI"]) == float(b["logI"])
            assert_graph_equal(graph_from_mat(a["out"]), graph_from_mat(b["out"]), rtol=0,
                               atol=0)


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "graphlike7919.mat"
    octave.eval(f"fx_graphlike('{out}', 7919);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for i, r in enumerate(fx["sy"]):
        g = graph_from_mat(r["graph"])
        runps = RunPs(type="feat", chunkcount=-1, SS=None)
        if int(r["variant"]) == 2:
            runps.type, runps.dim = "sim", 30
        ps = _mode(Params.default().replace(missingdata=0, overrideSS=0, zglreg=0, fast=1,
                                            runps=runps), r["mode"])
        d = np.asarray(r["d"], dtype=float)
        if _err(r["err"]):
            _expect_chol(_err(r["err"]), lambda: graph_like(d, g, ps))
            continue
        logI, o = graph_like(d, g, ps)
        _check(logI, o, r, f"fresh sy {i}")
