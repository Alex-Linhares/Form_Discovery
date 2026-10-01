"""Parity of ``countmatrix``, ``rellikebin``, ``rellikefreqs`` and ``graph_like_rel``
(``likelihood_rel.py``; item 20, L3-c) with Octave, and of ``graph_like``'s ``'rel'``
dispatch.

The fixture ``tests/fixtures/rellike.mat`` comes from ``legacy/tests_octave/fx_rellike.m``
(regenerate with ``python legacy/tools/gen_fixtures.py rellike``):

- ``ri``: ``relgraphinit`` graphs for the 24 ``ps.structures`` names and the 4 domtree
  names on the 7 relational data sets (4 relbin, 3 relfreq), with ``z = 1:n``, one cluster,
  two seeded partitions and a partition with two unassigned objects;
- ``sq``: seeded ``split_node`` sequences for the order, connected and domtree names
  (which ``relgraphinit`` cannot build) and a few others on the 7 data sets;
- ``sy``: the ``ri`` recipe on seeded random relations run as relbin and as relfreq,
  including relations with self links and a NaN entry;
- ``pv``: ``ri`` graphs under 4 non-default hyperparameter grids;
- ``gh``: every ``bestgraph`` of the 54 relational baseline growth histories, with
  ``graph_prior`` and the file's ``bestgraphlls`` entry;
- ``rb``/``rf``: direct ``rellikebin``/``rellikefreqs`` calls;
- ``rd``: the unused ``'reldom'`` branch on seeded 3-D relations, ``lowdiag`` 0 and 1;
- ``bl``: ``graph_like_rel`` calls spied during four baseline runs.

Each record holds ``logI``, the returned graph, ``countmatrix`` and ``graph_like``'s
``logI``, or Octave's error message. Tolerances (PLAN.md §2): rtol 1e-10 for ``logI``,
exact for counts and graph structure.
"""

import dataclasses

import numpy as np
import pytest

import formdiscovery.likelihood_rel as lr
from formdiscovery import FormDiscoveryError
from formdiscovery.io import graph_from_mat, load_dataset, load_fixture
from formdiscovery.likelihood import graph_like
from formdiscovery.likelihood_rel import (_SELF, _UNDIR, countmatrix, graph_like_rel,
                                          rellikebin, rellikefreqs)
from formdiscovery.params import DATASETS, Params, graph_prior, setrunps, structcounts
from tests.helpers import assert_graph_equal
from tests.test_baseline_rel import EXPECTED_LL

FX = load_fixture("rellike")
PS = Params.default()
NAMES = [str(n) for n in FX["names"]]
RELSETS = [str(d) for d in FX["relsets"]]
DATA = {d: load_dataset(d) for d in RELSETS}
NANSCORE = "graph_like_rel: logI is inf or NaN"


def _err(x):
    return str(x) if np.size(x) else ""


def _prep(name):
    """fx_rellike.m's prep: setrunps + structcounts (scaledata leaves rel data alone)."""
    nobj, ps = setrunps(DATA[name], DATASETS.index(name), PS)
    ps = ps.replace(overrideSS=0 if ps.overrideSS is None else ps.overrideSS, cleanstrong=0)
    return structcounts(nobj, ps)


DPS = {d: _prep(d) for d in RELSETS}


def _data(part, r):
    if part in ("ri", "sq", "gh", "pv"):
        return DATA[RELSETS[int(r["data"]) - 1]]
    R = np.atleast_2d(np.asarray(FX["Rsy"][int(r["data"]) - 1], dtype=float))
    return {"R": R, "type": _err(r["dtype"])}


def _ps(part, r):
    if part in ("ri", "sq", "gh"):
        return DPS[RELSETS[int(r["data"]) - 1]]
    return PS


def check(part, r, msg):
    """One record: logI, the returned graph (the input), countmatrix, graph_like."""
    g = graph_from_mat(r["graph"])
    d, ps = _data(part, r), _ps(part, r)
    err = _err(r["err"])
    if err:
        assert err == NANSCORE, err
        with pytest.raises(FormDiscoveryError, match=NANSCORE):
            graph_like_rel(d, g, ps)
        return
    logI, out = graph_like_rel(d, g, ps)
    np.testing.assert_allclose(logI, float(r["logI"]), rtol=1e-10, err_msg=msg)
    assert out is g
    assert_graph_equal(out, r["out"], msg, rtol=0, atol=0)
    if "counts" in r:
        np.testing.assert_array_equal(countmatrix(d["R"], g), np.atleast_2d(r["counts"]),
                                      err_msg=msg)
        gl, gout = graph_like(d, g, ps.replace(runps=dataclasses.replace(ps.runps, type="rel")))
        assert gl == logI and gout is g
        np.testing.assert_allclose(gl, float(r["gllogI"]), rtol=1e-10, err_msg=msg)


def _scored(recs):
    return [r for r in recs if not _err(r["err"]).startswith("init")]


def test_fixture_contents():
    assert len(NAMES) == 28 and len(RELSETS) == 7
    assert {DATA[d]["type"] for d in RELSETS} == {"relbin", "relfreq"}
    assert len(FX["ri"]) == 7 * 28 * 5 and len(_scored(FX["ri"])) == 644
    assert not any(_err(r["err"]) for r in _scored(FX["ri"]))
    assert len(FX["sq"]) == 455 and not any(_err(r["err"]) for r in FX["sq"])
    assert len(FX["sy"]) == 7 * 2 * 28 * 5
    assert sum(_err(r["err"]) == NANSCORE for r in FX["sy"]) == 476
    assert len(FX["gh_file"]) == 54 and len(FX["gh"]) == 79
    assert len(FX["pv"]) == 392 and len(FX["rb"]) == len(FX["rf"]) == 12
    assert _err(FX["unknown_err"]) == "unknown relational type"


def test_every_variant_covered():
    """Every dir/undir/noself form is scored on every data set, including the self-link
    (l.107-111) and symmetrisation (l.113-119) lists and the filloutrelgraph types."""
    seen = {(r["name"], int(r["data"])) for r in _scored(FX["ri"]) + FX["sq"]}
    relnames = [n for n in NAMES if n not in ("chain", "ring", "tree", "hierarchy", "grid",
                                              "cylinder")]
    for n in relnames:
        for d in range(1, 8):
            assert (n, d) in seen, (n, d)
    assert set(_SELF) <= set(relnames) and set(_UNDIR) <= set(relnames)


@pytest.mark.parametrize("name", NAMES)
def test_ri(name):
    for i, r in enumerate(_scored(FX["ri"])):
        if str(r["name"]) == name:
            check("ri", r, f"ri {name} {RELSETS[int(r['data']) - 1]} z{int(r['zkind'])}")


@pytest.mark.parametrize("name", [str(n) for n in FX["sqnames"]])
def test_sq(name):
    for r in FX["sq"]:
        if str(r["name"]) == name:
            check("sq", r, f"sq {name} {RELSETS[int(r['data']) - 1]} step {int(r['step'])}")


@pytest.mark.parametrize("name", NAMES)
def test_sy(name):
    for r in _scored(FX["sy"]):
        if str(r["name"]) == name:
            check("sy", r, f"sy {name} R{int(r['data'])} {_err(r['dtype'])} z{int(r['zkind'])}")


def test_pv():
    ri = FX["ri"]
    for s in FX["pv"]:
        r = ri[int(s["ri"]) - 1]
        steps, off, lam = FX["pvs"][int(s["pv"]) - 1]
        ps = DPS[RELSETS[int(r["data"]) - 1]].replace(edgesumsteps=int(steps),
                                                        edgeoffset=off, edgesumlambda=lam)
        logI, _ = graph_like_rel(_data("ri", r), graph_from_mat(r["graph"]), ps)
        np.testing.assert_allclose(logI, float(s["logI"]), rtol=1e-10)


def test_gh():
    """The baseline bestgraphs: logI and graph_prior match; their sum is the stored
    bestgraphlls entry (rel runs score in fast mode only, speed 5)."""
    for r in FX["gh"]:
        msg = f"gh {FX['gh_file'][int(r['file']) - 1]} depth {int(r['depth'])}"
        check("gh", r, msg)
        g = graph_from_mat(r["graph"])
        ps = DPS[RELSETS[int(r["data"]) - 1]]
        ps = ps.replace(runps=dataclasses.replace(ps.runps, structname=g.type))
        prior = graph_prior(g, ps)
        np.testing.assert_allclose(prior, float(r["prior"]), rtol=1e-10, err_msg=msg)
        logI, _ = graph_like_rel(_data("gh", r), g, ps)
        np.testing.assert_allclose(logI + prior, float(r["bgll"]), rtol=1e-10, err_msg=msg)


def test_rellikebin_direct():
    for r in FX["rb"]:
        ll = rellikebin(r["countvec"], r["adjvec"], r["sizevec"], FX["mags"], FX["thetas"])
        np.testing.assert_allclose(ll, float(r["ll"]), rtol=1e-10)


def test_rellikefreqs_direct():
    for r in FX["rf"]:
        ll = rellikefreqs(r["countvec"], r["adjvec"], r["sizevec"], FX["ae"], FX["be"])
        np.testing.assert_allclose(ll, float(r["ll"]), rtol=1e-10)


def test_reldom():
    n_low = 0
    for i, r in enumerate(FX["rd"]):
        rr = FX["Rrd"][int(r["R"]) - 1]
        data = {"R": np.asarray(rr["R"], dtype=float), "type": "reldom",
                "lowdiag": int(rr["lowdiag"])}
        g = graph_from_mat(r["graph"])
        if _err(r["err"]):
            assert _err(r["err"]) == "data not lower diagonal!"
            with pytest.raises(FormDiscoveryError, match="not lower diagonal"):
                graph_like_rel(data, g, PS)
            continue
        n_low += data["lowdiag"]
        logI, out = graph_like_rel(data, g, PS)
        np.testing.assert_allclose(logI, float(r["logI"]), rtol=1e-10, err_msg=f"rd {i}")
        assert_graph_equal(out, r["out"], f"rd {i}", rtol=0, atol=0)
    assert n_low > 50
    # two-cluster one-edge graphs, where MATLAB's discarded direction flip (KI-22) runs
    two = [r for r in FX["rd"] if graph_from_mat(r["graph"]).adjcluster.shape == (2, 2)
           and graph_from_mat(r["graph"]).adjcluster.sum() == 1]
    assert len(two) >= 4


def test_reldom_direction_flip_discarded():
    """KI-22: where graph_like_rel.m:95-97 flips the single cluster edge, Octave still
    returns the input graph (l.162)."""
    nflip = 0
    for r in FX["rd"]:
        g = graph_from_mat(r["graph"])
        A = np.asarray(g.adjcluster)
        if _err(r["err"]) or A.shape != (2, 2) or A.sum() != 1:
            continue
        R = np.asarray(FX["Rrd"][int(r["R"]) - 1]["R"], dtype=float)
        mem = [np.flatnonzero(g.z == i) for i in range(2)]
        y = np.array([[R[np.ix_(mem[i], mem[j])][..., 0].sum() for j in range(2)]
                      for i in range(2)])
        n = np.array([[R[np.ix_(mem[i], mem[j])][..., 1].sum() for j in range(2)]
                      for i in range(2)])
        (rr,), (cc,) = np.nonzero(A == 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            flips = n[cc, rr] > 0 and y[cc, rr] / n[cc, rr] > y[rr, cc] / n[rr, cc]
        nflip += bool(flips)
        assert_graph_equal(graph_from_mat(r["out"]), g, rtol=0, atol=0)
        assert graph_like_rel({"R": R, "type": "reldom",
                               "lowdiag": int(FX["Rrd"][int(r["R"]) - 1]["lowdiag"])},
                              g, PS)[1] is g
    assert nflip >= 1


def test_unknown_type():
    g = graph_from_mat(FX["ri"][0]["graph"])
    with pytest.raises(FormDiscoveryError, match="unknown relational type"):
        graph_like_rel({"R": np.eye(8), "type": "relxyz"}, g, PS)


def test_bl():
    """Spied baseline calls match; the spied runs end at the committed baseline scores."""
    for r, ll in zip(FX["bl_run"], np.atleast_1d(FX["bl_ll"])):
        s, d = str(r).split(":")
        assert ll == EXPECTED_LL[(s, d)]
    assert len(FX["bl"]) == 48
    for r in FX["bl"]:
        run = str(FX["bl_run"][int(r["run"]) - 1])
        data = {"R": np.asarray(r["R"], dtype=float), "type": str(r["dtype"])}
        np.testing.assert_array_equal(data["R"], DATA[run.split(":")[1]]["R"])
        g = graph_from_mat(r["graph"])
        logI, out = graph_like_rel(data, g, PS)
        np.testing.assert_allclose(logI, float(r["logI"]), rtol=1e-10,
                                   err_msg=f"bl {run} call {int(r['n'])}")
        assert_graph_equal(out, r["out"], rtol=0, atol=0)


def test_self_and_undir_branches_matter(monkeypatch):
    """Dropping either the within-class links or the symmetrisation changes some scores
    (so the fixture pins both branches)."""
    recs = [r for r in _scored(FX["ri"]) if not _err(r["err"])][::5]

    def diffs():
        n = 0
        for r in recs:
            logI, _ = graph_like_rel(_data("ri", r), graph_from_mat(r["graph"]), _ps("ri", r))
            n += not np.isclose(logI, float(r["logI"]), rtol=1e-10)
        return n

    assert diffs() == 0
    monkeypatch.setattr(lr, "_SELF", ())
    assert diffs() > 0
    monkeypatch.setattr(lr, "_SELF", _SELF)
    monkeypatch.setattr(lr, "_UNDIR", ())
    assert diffs() > 0


def test_inputs_not_mutated():
    r = next(r for r in FX["sq"] if str(r["name"]) == "undirdomtree")
    g = graph_from_mat(r["graph"])
    d = DATA[RELSETS[int(r["data"]) - 1]]
    g0, R0 = g.copy(), d["R"].copy()
    graph_like_rel(d, g, DPS[RELSETS[int(r["data"]) - 1]])
    assert_graph_equal(g, g0, rtol=0, atol=0)
    np.testing.assert_array_equal(d["R"], R0)


def test_countmatrix_unassigned():
    """Objects with z == -1 are in no cluster (countmatrix.m:9-10)."""
    r = next(r for r in _scored(FX["ri"]) if int(r["zkind"]) == 5 and not _err(r["err"]))
    g = graph_from_mat(r["graph"])
    assert (g.z < 0).sum() == 2
    R = DATA[RELSETS[int(r["data"]) - 1]]["R"]
    c = countmatrix(R, g)
    keep = g.z >= 0
    assert c.sum() == R[np.ix_(keep, keep)].sum()


# --- live Octave ----------------------------------------------------------------------------

LIVE_PARTS = ("ri", "sq", "sy", "pv", "gh", "rb", "rf", "rd", "bl")


@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "rellike.mat"
    octave.eval(f"fx_rellike('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for k in LIVE_PARTS:
        assert len(fx[k]) == len(FX[k]), k
        for a, b in zip(fx[k], FX[k]):
            assert _err(a.get("err", "")) == _err(b.get("err", ""))
            for f in ("logI", "ll", "counts", "gllogI"):
                if f in a:
                    np.testing.assert_array_equal(a[f], b[f])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    out = tmp_path / "rellike7919.mat"
    octave.eval(f"fx_rellike('{out}', 7919);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    global FX
    old = FX
    FX = fx
    try:
        for part in ("ri", "sq", "sy"):
            for i, r in enumerate(_scored(fx[part])):
                check(part, r, f"fresh {part} {i}")
        test_pv()
        test_rellikebin_direct()
        test_rellikefreqs_direct()
        test_reldom()
    finally:
        FX = old
