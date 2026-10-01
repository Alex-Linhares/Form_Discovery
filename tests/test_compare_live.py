"""``legacy/tools/compare_live.py`` (loop0002 item 06): Octave and Python side by side.

Each triple runs ``run_baseline`` in its own ``octave-cli`` (draws logged by the
``randperm`` shim) and then Python's ``runmodel`` replaying those draws, without oracles.
The rows must not depend on ``--jobs``; the default set (9 feature + 54 relational pairs,
seed 1) must meet PLAN §7.1 and reproduce the committed baseline scores in Octave.
"""
import numpy as np
import pytest

from tests.conftest import find_octave
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from legacy.tools import compare_live as cl
from legacy.tools import gen_baselines as gb

# cheap relational runs (about 1 s each in Octave); seed 2 has no committed baseline
QUICK = ["dirring:demo_ring_rel_bin", "partition:4", "undirchain:demo_order_rel_freq",
         "dirchain:demo_ring_rel_bin:2"]


def test_parse_pair():
    assert cl.parse_pair("chain:demo_chain_feat") == (2, 1, 1)
    assert cl.parse_pair("2:1:7") == (2, 1, 7)
    assert cl.parse_pair("dirring:4", seed=3) == (17, 4, 3)
    for bad in ["chain", "nope:1", "chain:99", "0:1", "a:b:c:d"]:
        with pytest.raises(ValueError):
            cl.parse_pair(bad)


def test_default_triples():
    """run_baseline's grids in its run order: 9 feature pairs, then 54 relational."""
    t = cl.default_triples()
    assert len(t) == 63 and len(set(t)) == 63
    assert t[:9] == [(s, d, 1) for s, d in gb.serial_pairs(*gb.GRIDS["feat"])]
    assert t[9:] == [(s, d, 1) for s, d in gb.serial_pairs(*gb.GRIDS["rel"])]
    assert cl.default_triples("rel", seed=4) == [(s, d, 4) for s, d, _ in t[9:]]
    ps = cl._ps()
    keys = {(ps.structures[s - 1], ps.data[d - 1]) for s, d, _ in t}
    assert keys == set(FEAT_LL) | set(REL_LL)
    assert all(cl.baseline_ll(s, d) is not None for s, d, _ in t)


def test_data_kind():
    assert [cl.data_kind(d) for d in range(1, 7)] == ["feat"] * 3 + ["rel"] * 3


def test_replay_then_numpy():
    from formdiscovery.rng import NumpyPermutations
    q = [np.array([1, 0, 2]), np.array([0, 1])]
    r = cl.ReplayThenNumpy(q, seed=5)
    assert r.status() == "diverged@0"
    np.testing.assert_array_equal(r.randperm(3), q[0])
    np.testing.assert_array_equal(r.randperm(2), q[1])
    assert r.status() == "full"
    # exhausted: numpy from here on
    np.testing.assert_array_equal(r.randperm(4), NumpyPermutations(5).randperm(4))
    assert r.status() == "diverged@2" and r.diverged == 2
    # a length mismatch also switches, and the queue is not used again
    r = cl.ReplayThenNumpy(q, seed=5)
    r.randperm(3)
    ref = NumpyPermutations(5)
    np.testing.assert_array_equal(r.randperm(5), ref.randperm(5))
    np.testing.assert_array_equal(r.randperm(2), ref.randperm(2))
    assert r.status() == "diverged@1"
    r = cl.ReplayThenNumpy(q, seed=5)
    r.randperm(3)
    assert r.status() == "diverged@1"  # an unused entry left over


def test_format_table():
    rows = [dict(structure="chain", data="demo_chain_feat", seed=1, oct_ll=-1.0, py_ll=-1.0,
                 rel_diff=0.0, ari=1.0, oct_clusters=2, py_clusters=2, oct_nodes=2,
                 py_nodes=2, draws=3, replay="full", oct_wall=1.0, py_wall=0.5, ok=True,
                 fail=[]),
            dict(structure="ring", data="demo_ring_feat", seed=1, draws=0, oct_wall=0.1,
                 ok=False, fail=["octave-cli failed"])]
    t = cl.format_table(rows).splitlines()
    assert len(t) == 4 and t[2].endswith("| yes |") and "FAIL: octave-cli failed" in t[3]
    assert cl.stable(rows[0]) == {k: v for k, v in rows[0].items()
                                  if k not in ("oct_wall", "py_wall")}


def _check_criteria(rows):
    """PLAN §7.1 on every row, plus Octave = committed baseline for seed 1 and exact
    relational scores (no optimizer)."""
    for r in rows:
        msg = f"{r['structure']}:{r['data']}:{r['seed']} {r['fail']}"
        assert r["ok"], msg
        assert r["rel_diff"] <= cl.E2E_RTOL, msg
        assert r["oct_clusters"] == r["py_clusters"], msg
        need = 1.0 if r["replay"] == "full" else cl.ARI_DIVERGED
        assert r["ari"] >= need - 1e-12, msg
        if r["seed"] == 1:
            assert r["oct_ll"] == cl.baseline_ll(r["sind"], r["dind"]), msg
        if cl.data_kind(r["dind"]) == "rel":
            assert r["rel_diff"] <= 1e-12, msg


@pytest.mark.octave
def test_parallel_rows_equal_serial(tmp_path):
    """``--jobs 1`` and ``--jobs 4`` give the same rows (all numbers to all digits,
    replay status, verdicts); only the times differ."""
    if find_octave() is None:
        pytest.skip("Octave executable not found")
    triples = [cl.parse_pair(p) for p in QUICK]
    serial = cl.compare(triples, 1, tmp_path / "logs1", progress=False)
    parallel = cl.compare(triples, 4, tmp_path / "logs4", progress=False)
    assert [cl.stable(r) for r in serial] == [cl.stable(r) for r in parallel]
    assert [(r["sind"], r["dind"], r["seed"]) for r in parallel] == triples
    _check_criteria(parallel)
    assert all(r["replay"] == "full" for r in parallel)
    assert sorted(p.name for p in (tmp_path / "logs4").iterdir()) == \
        sorted(f"{cl._key(*t)}.log" for t in triples)


@pytest.mark.slow
@pytest.mark.octave
def test_default_set_meets_plan_7_1(tmp_path):
    """The 63 default triples (about 30 s with 16 workers): every row meets PLAN §7.1,
    Octave reproduces the committed baseline, the relational scores are exact, and all
    but a few relational replays run to the end (loop0002 iteration 7: 53 of 54; the
    feature runs diverge where scipy's optimum differs from fminunc's, ANOMALIES A3)."""
    rows = cl.compare(cl.default_triples(), 16, tmp_path / "logs", progress=False)
    assert len(rows) == 63
    _check_criteria(rows)
    rel = [r for r in rows if cl.data_kind(r["dind"]) == "rel"]
    assert sum(r["replay"] == "full" for r in rel) >= 50
