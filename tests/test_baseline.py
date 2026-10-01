"""Octave feature-data baseline (item 04): fixtures written by legacy/matlab/run_baseline.m.

masterrun.m's default grid: chain, ring, tree x demo_chain_feat, demo_ring_feat,
demo_tree_feat. The tree runs need Octave patch 16 (``find_descendants.m``, item 03b,
KI-9); all nine runs were regenerated together after that patch. The chain and ring
values are identical to the ones recorded before the patch.
"""
from pathlib import Path

import numpy as np
import pytest
import scipy.io

from tests.conftest import FIXTURES_DIR, LEGACY_DIR

BASE = FIXTURES_DIR / "baseline" / "feat"
DATA = ["demo_chain_feat", "demo_ring_feat", "demo_tree_feat"]
# ps.structures indices (1-based, as in MATLAB) -> name
STRUCTS = {2: "chain", 4: "ring", 6: "tree"}

# Final log probabilities from Octave 10.3.0, ps.speed = 54, rand('state', 1).
EXPECTED_LL = {
    ("chain", "demo_chain_feat"): -8247.204813441429,
    ("ring", "demo_chain_feat"): -8264.200370932087,
    ("tree", "demo_chain_feat"): -8252.886501459561,
    ("chain", "demo_ring_feat"): -8566.636516565002,
    ("ring", "demo_ring_feat"): -8500.520169536907,
    ("tree", "demo_ring_feat"): -8512.873764658598,
    ("chain", "demo_tree_feat"): -8764.165561567628,
    ("ring", "demo_tree_feat"): -8722.589003746496,
    ("tree", "demo_tree_feat"): -8707.813669003906,
}


def load(path):
    return scipy.io.loadmat(path, mat_dtype=True)


@pytest.fixture(scope="module")
def results():
    return load(BASE / "resultsdemo.mat")


@pytest.fixture(scope="module")
def timings():
    return scipy.io.loadmat(BASE / "timings.mat", squeeze_me=True)["timings"]


def test_resultsdemo_contents(results):
    for key in ["modellike", "structure", "names", "pss", "llhistory"]:
        assert key in results
    ml = results["modellike"]
    assert ml.shape == (6, 3)  # rows = ps.structures indices up to tree (6)
    for (s, name) in STRUCTS.items():
        for d, dname in enumerate(DATA):
            assert ml[s - 1, d] == pytest.approx(EXPECTED_LL[(name, dname)], rel=1e-10)


def test_timings_match_results(timings, results):
    assert len(timings) == len(EXPECTED_LL)
    for t in timings:
        key = (str(t["structure"]), str(t["data"]))
        assert float(t["ll"]) == pytest.approx(EXPECTED_LL[key], rel=1e-10)
        assert 0 < float(t["seconds"]) < 120


def test_true_form_wins(results):
    """Each demo set is best explained by the form it was generated from."""
    ml = results["modellike"].copy()
    ml[ml == 0] = -np.inf
    winner = {dname: STRUCTS[int(np.argmax(ml[:, d])) + 1] for d, dname in enumerate(DATA)}
    assert winner == {
        "demo_chain_feat": "chain",
        "demo_ring_feat": "ring",
        "demo_tree_feat": "tree",
    }


def test_structure_graphs(results):
    for s in STRUCTS:
        for d in range(3):
            g = results["structure"][s - 1, d][0, 0]
            assert str(g["type"][0]) == STRUCTS[s]
            nobj = int(g["objcount"][0, 0])
            assert nobj == 8  # demo sets have 8 objects (rows of the data)
            adj = g["adj"]
            assert adj.shape[0] == adj.shape[1] >= nobj
            assert np.all(np.isfinite(g["W"]))


def test_growth_histories(results):
    for name in STRUCTS.values():
        for dname in DATA:
            run = BASE / "results" / f"{name}out" / f"{dname}1"
            files = sorted(run.glob("growthhistory*.mat"))
            # structurefit saves a history only for stages that improved;
            # the all-tied stage always runs first and always saves.
            assert run / "growthhistoryalltie5.mat" in files
            for f in files:
                g = load(f)
                assert {"bestgraphlls", "bestgraph"} <= set(g)


@pytest.mark.octave
def test_live_chain_run_reproduces(octave, tmp_path):
    octave.addpath(str(LEGACY_DIR / "matlab"))
    octave.eval(f"run_baseline('feat', 2, 1, '{tmp_path}');", nout=0)
    t = scipy.io.loadmat(tmp_path / "timings.mat", squeeze_me=True)["timings"]
    assert float(t["ll"]) == pytest.approx(EXPECTED_LL[("chain", "demo_chain_feat")], rel=1e-10)
    assert (tmp_path / "results/chainout/demo_chain_feat1/growthhistoryalltie5.mat").exists()
