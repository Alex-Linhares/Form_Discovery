"""Octave relational baseline (item 05): fixtures written by ``run_baseline('rel')``.

masterrun.m's relational grid with ``ps.reloutsideinit = 'overd'``: structures
[1,9,10:13,3,14:24] x demo_ring_rel_bin, demo_hierarchy_rel_bin,
demo_order_rel_freq. ``undirhierarchy x demo_hierarchy_rel_bin`` crashes in
Octave in the same way as the feature tree runs (KNOWN_ISSUES.md KI-9, item 03b). run_baseline
catches the crash and records it in timings.mat, and the run is missing from resultsdemo.mat.
After 03b, rerun ``run_baseline('rel')`` and move that run into EXPECTED_LL.
"""
import numpy as np
import pytest
import scipy.io

from tests.conftest import FIXTURES_DIR, REPO_ROOT

BASE = FIXTURES_DIR / "baseline" / "rel"
DATA = {4: "demo_ring_rel_bin", 5: "demo_hierarchy_rel_bin", 6: "demo_order_rel_freq"}
# ps.structures indices (1-based, as in MATLAB) in masterrun.m's order
STRUCTS = {
    1: "partition", 9: "partitionnoself", 10: "dirchain", 11: "dirchainnoself",
    12: "undirchain", 13: "undirchainnoself", 3: "order", 14: "ordernoself",
    15: "connected", 16: "connectednoself", 17: "dirring", 18: "dirringnoself",
    19: "undirring", 20: "undirringnoself", 21: "dirhierarchy",
    22: "dirhierarchynoself", 23: "undirhierarchy", 24: "undirhierarchynoself",
}
CRASHED = {("undirhierarchy", "demo_hierarchy_rel_bin")}

# Final log probabilities from Octave 10.3.0, ps.speed = 54, rand('state', 1).
EXPECTED_LL = {
    ("partition", "demo_ring_rel_bin"): -33.90047986928382,
    ("partitionnoself", "demo_ring_rel_bin"): -34.77093406114762,
    ("dirchain", "demo_ring_rel_bin"): -25.24349214897594,
    ("dirchainnoself", "demo_ring_rel_bin"): -20.509795996934173,
    ("undirchain", "demo_ring_rel_bin"): -36.18052422065801,
    ("undirchainnoself", "demo_ring_rel_bin"): -24.108644017448825,
    ("order", "demo_ring_rel_bin"): -36.83486225778202,
    ("ordernoself", "demo_ring_rel_bin"): -35.26799978316711,
    ("connected", "demo_ring_rel_bin"): -35.617543751559396,
    ("connectednoself", "demo_ring_rel_bin"): -31.71024170253919,
    ("dirring", "demo_ring_rel_bin"): -22.187234774139817,
    ("dirringnoself", "demo_ring_rel_bin"): -16.571442556121905,
    ("undirring", "demo_ring_rel_bin"): -23.967558619971726,
    ("undirringnoself", "demo_ring_rel_bin"): -22.01200711253429,
    ("dirhierarchy", "demo_ring_rel_bin"): -25.697327590616183,
    ("dirhierarchynoself", "demo_ring_rel_bin"): -20.963631438574417,
    ("undirhierarchy", "demo_ring_rel_bin"): -25.86610506974244,
    ("undirhierarchynoself", "demo_ring_rel_bin"): -24.1827360361876,
    ("partition", "demo_hierarchy_rel_bin"): -137.8399845197348,
    ("partitionnoself", "demo_hierarchy_rel_bin"): -135.48393266888434,
    ("dirchain", "demo_hierarchy_rel_bin"): -67.16682365179967,
    ("dirchainnoself", "demo_hierarchy_rel_bin"): -63.026923468279826,
    ("undirchain", "demo_hierarchy_rel_bin"): -65.79509248990367,
    ("undirchainnoself", "demo_hierarchy_rel_bin"): -63.04691123042926,
    ("order", "demo_hierarchy_rel_bin"): -145.76410547472454,
    ("ordernoself", "demo_hierarchy_rel_bin"): -145.27042409050125,
    ("connected", "demo_hierarchy_rel_bin"): -136.72041038006014,
    ("connectednoself", "demo_hierarchy_rel_bin"): -136.70906119616106,
    ("dirring", "demo_hierarchy_rel_bin"): -66.90033380167696,
    ("dirringnoself", "demo_hierarchy_rel_bin"): -65.1536875958685,
    ("undirring", "demo_hierarchy_rel_bin"): -64.29236857114523,
    ("undirringnoself", "demo_hierarchy_rel_bin"): -62.28627824858109,
    ("dirhierarchy", "demo_hierarchy_rel_bin"): -70.24666024467271,
    ("dirhierarchynoself", "demo_hierarchy_rel_bin"): -63.33275738083697,
    ("undirhierarchynoself", "demo_hierarchy_rel_bin"): -67.09830541701561,
    ("partition", "demo_order_rel_freq"): -3685.6622070086487,
    ("partitionnoself", "demo_order_rel_freq"): -3683.7810012247446,
    ("dirchain", "demo_order_rel_freq"): -3685.4663299642825,
    ("dirchainnoself", "demo_order_rel_freq"): -3682.3230958864115,
    ("undirchain", "demo_order_rel_freq"): -3685.8516088532374,
    ("undirchainnoself", "demo_order_rel_freq"): -3685.337242646336,
    ("order", "demo_order_rel_freq"): -3682.1985318223296,
    ("ordernoself", "demo_order_rel_freq"): -3663.6162765549,
    ("connected", "demo_order_rel_freq"): -3683.78062162844,
    ("connectednoself", "demo_order_rel_freq"): -3684.1415437187497,
    ("dirring", "demo_order_rel_freq"): -3684.9381528879453,
    ("dirringnoself", "demo_order_rel_freq"): -3683.447011944542,
    ("undirring", "demo_order_rel_freq"): -3685.126414106697,
    ("undirringnoself", "demo_order_rel_freq"): -3684.7175706445055,
    ("dirhierarchy", "demo_order_rel_freq"): -3685.9201654059225,
    ("dirhierarchynoself", "demo_order_rel_freq"): -3682.7769313280514,
    ("undirhierarchy", "demo_order_rel_freq"): -3685.925700871978,
    ("undirhierarchynoself", "demo_order_rel_freq"): -3685.411334665076,
}


def load(path):
    return scipy.io.loadmat(path, mat_dtype=True)


@pytest.fixture(scope="module")
def results():
    return load(BASE / "resultsdemo.mat")


@pytest.fixture(scope="module")
def timings():
    return scipy.io.loadmat(BASE / "timings.mat", squeeze_me=True)["timings"]


def test_grid_is_complete():
    assert len(EXPECTED_LL) + len(CRASHED) == len(STRUCTS) * len(DATA)


def test_resultsdemo_contents(results):
    for key in ["modellike", "structure", "names", "pss", "llhistory"]:
        assert key in results
    ml = results["modellike"]
    assert ml.shape == (24, 6)
    for s, name in STRUCTS.items():
        for d, dname in DATA.items():
            if (name, dname) in CRASHED:
                assert ml[s - 1, d - 1] == 0  # never written
            else:
                assert ml[s - 1, d - 1] == pytest.approx(EXPECTED_LL[(name, dname)], rel=1e-10)
    assert np.all(ml[:, :3] == 0)  # feature sets not run here


def test_timings_match_results(timings):
    assert len(timings) == len(STRUCTS) * len(DATA)
    for t in timings:
        key = (str(t["structure"]), str(t["data"]))
        if key in CRASHED:
            assert np.isnan(float(t["ll"]))
            err = str(t["error"])
            assert err.startswith("horizontal dimensions mismatch (1x1 vs 2x1)")
            assert "spr>makers at line 87" in err
        else:
            assert float(t["ll"]) == pytest.approx(EXPECTED_LL[key], rel=1e-10)
            assert np.size(t["error"]) == 0
        assert 0 < float(t["seconds"]) < 120


def test_reloutsideinit_overd(results):
    ps = results["pss"][0, 3][0, 0]  # partition x demo_ring_rel_bin
    assert str(ps["reloutsideinit"][0]) == "overd"


def test_best_form(results):
    ml = results["modellike"].copy()
    ml[ml == 0] = -np.inf
    best = {d: STRUCTS[int(np.argmax(ml[:, d - 1])) + 1] for d in DATA}
    assert best[4] == "dirringnoself"
    assert best[6] == "ordernoself"
    # Octave's winner on the hierarchy data is not a hierarchy (see PROGRESS.md
    # iteration 7); pinned so that any change shows up.
    assert best[5] == "undirringnoself"


def test_structure_graphs(results):
    for s, name in STRUCTS.items():
        for d, dname in DATA.items():
            if (name, dname) in CRASHED:
                continue
            g = results["structure"][s - 1, d - 1][0, 0]
            assert str(g["type"][0]) == name
            adj = g["adj"]
            assert adj.shape[0] == adj.shape[1]


def test_growth_histories():
    for name in STRUCTS.values():
        for dname in DATA.values():
            run = BASE / "results" / f"{name}out" / f"{dname}1"
            files = sorted(run.glob("growthhistory*.mat"))
            # relational runs only go through the 'noinit' stage, and in this
            # grid the speed-4 refinement never improves, so only the speed-5
            # history is saved (the crashed run saved it before crashing)
            assert files == [run / "growthhistorynoinit5.mat"]
            for f in files:
                g = load(f)
                assert {"bestgraphlls", "bestgraph"} <= set(g)


@pytest.mark.octave
def test_live_rel_run_reproduces(octave, tmp_path):
    octave.addpath(str(REPO_ROOT / "matlab"))
    octave.eval(f"run_baseline('rel', 18, 4, '{tmp_path}');", nout=0)
    t = scipy.io.loadmat(tmp_path / "timings.mat", squeeze_me=True)["timings"]
    assert float(t["ll"]) == pytest.approx(
        EXPECTED_LL[("dirringnoself", "demo_ring_rel_bin")], rel=1e-10
    )
