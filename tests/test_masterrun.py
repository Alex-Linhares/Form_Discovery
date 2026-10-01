"""End-to-end parity of ``run.masterrun`` and the ``formdiscovery run`` CLI (item 29, L5-b;
PLAN.md §7.1) with Octave.

The fixture ``tests/fixtures/masterrun.mat`` comes from ``legacy/tests_octave/fx_masterrun.m``
(regenerate with ``python legacy/tools/gen_fixtures.py masterrun``): the unmodified
``masterrun.m`` script, run headless in a temporary directory (chain, ring, tree x the
three feature demos, ``rand('state', 1)`` before each run). It keeps every ``randperm``
draw of the whole script (``logtext``), every slow ``graph_like`` call (``gl``), every
``choose_node_split`` call (``cns``), the variables of the ``resultsdemo.mat`` masterrun
wrote and the growth-history files. The 9 scores reproduce ``tests/fixtures/baseline``.

- **Replay** (gate): the whole masterrun is replayed with one provider for all runs,
  Octave's slow scores (``TieOracle``), tied splits (``SplitOracle``) and Octave's scaled
  data, as in ``test_runmodel.py``. Everything matches exactly, so §7.1's criteria (score
  within 1e-3 rel, cluster count, ARI = 1) hold with room to spare.
- **No replay** (``slow``): scipy's optimizer and numpy permutations, seeds 1-3. Each
  pair must be within 1e-3 rel of Octave's score, with Octave's cluster count, and the
  mean ARI over the seeds must be >= 0.9 (PLAN §7.1).
"""

import json
import subprocess
import sys

import numpy as np
import pytest

from formdiscovery import cli, likelihood, run, search
from formdiscovery.io import REPO_ROOT, graph_from_mat, load_fixture
from formdiscovery.rng import NumpyPermutations, ReplayPermutations, parse_queue
from formdiscovery.run import (MasterResults, graph_summary, load_results, masterrun,
                               masterrun_pairs, masterrun_ps, save_results)
from tests.helpers import adjusted_rand_index, graph_diff
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_runmodel import _cell, _empty, _octave_scaledata
from tests.test_structurefit import SplitOracle, TieOracle, _list
from tests.test_swap import _text

FX = load_fixture("masterrun")
ORDER = [(int(s) - 1, int(d) - 1) for s, d in np.asarray(FX["order"])]  # 0-based
PS0 = masterrun_ps()
PAIRS = [(PS0.structures[s], PS0.data[d]) for s, d in ORDER]
E2E_RTOL = 1e-3  # PLAN §7.1


def _octave(field, s, d):
    shape = tuple(int(x) for x in np.ravel(FX[f"{field}_size"]))
    return _cell(FX[field], shape)[s, d]


def _ograph(s, d):
    return graph_from_mat(_octave("structure", s, d))


def _summary(g):
    return graph_summary(g if hasattr(g, "z") else graph_from_mat(g))


@pytest.fixture(scope="module")
def replayed(tmp_path_factory):
    """One replayed masterrun (the draws of the whole script, Octave's slow scores and
    tied splits), saved under a temporary ``outdir``."""
    out = tmp_path_factory.mktemp("masterrun")
    rec = {"cns": FX["cns"], "gl": FX["gl"]}
    with pytest.MonkeyPatch.context() as m:
        _octave_scaledata(m)
        split = SplitOracle(rec, "masterrun")
        slow = TieOracle(rec, "masterrun")
        m.setattr(search, "choose_node_split", split)
        m.setattr(likelihood, "graph_like", slow)
        rng = ReplayPermutations(parse_queue(_text(FX["logtext"])))
        ps = masterrun_ps()
        res = masterrun(ps, outdir=out, rng=rng)
    rng.assert_exhausted()
    assert split.used == len(split.cns) and slow.used == len(slow.gl)
    return {"res": res, "out": out, "ps": ps, "ties": split.ties + slow.swaps}


# --- contents ------------------------------------------------------------------------------

def test_contents_match_baseline():
    """masterrun.m itself, through the spies and the pass-through shim, reproduces the
    9 feature baseline scores; pss holds masterrun's own ps."""
    assert PAIRS == [(s, d) for d in ["demo_chain_feat", "demo_ring_feat", "demo_tree_feat"]
                     for s in ["chain", "ring", "tree"]]
    ml = np.asarray(FX["modellike"], dtype=float)
    assert ml.shape == (6, 3)
    for (s, d), key in zip(ORDER, PAIRS):
        assert ml[s, d] == pytest.approx(FEAT_LL[key], rel=1e-12), key
    assert np.count_nonzero(ml) == 9
    for p in _list(FX["pss_check"]):
        assert (int(p["speed"]), _text(p["init"]), _text(p["reloutsideinit"])) == \
            (54, "intext", "overd")
        assert int(p["showinferredgraph"]) == 0 and int(p["hasrunps"]) == 0
    assert len(_list(FX["gl"])) > 0 and len(_list(FX["cns"])) > 0


def test_masterrun_pairs():
    assert masterrun_pairs((1, 3, 5), (0, 1, 2)) == ORDER
    assert masterrun_pairs((1, 3), (0,), extraspairs=(7,), extradpairs=(10,)) == \
        [(7, 10), (1, 0), (3, 0)]
    with pytest.raises(Exception, match="differ in length"):
        masterrun_pairs((1,), (0,), extraspairs=(7,), extradpairs=())


# --- replay (gate) -------------------------------------------------------------------------

def test_replay_modellike(replayed):
    res = replayed["res"]
    assert res.modellike.shape == (6, 3, 1)
    np.testing.assert_allclose(res.modellike[:, :, 0], np.asarray(FX["modellike"], float),
                               rtol=1e-10, atol=0)
    assert [(r["sind"], r["dind"], r["rind"]) for r in res.runs] == \
        [(s, d, 1) for s, d in ORDER]


def test_replay_structures_names_histories(replayed):
    res = replayed["res"]
    assert res.structure.shape == res.llhistory.shape == res.pss.shape == (6, 3, 1)
    for s, d in ORDER:
        msg = f"{PS0.structures[s]}:{PS0.data[d]}"
        assert graph_diff(res.structure[s, d, 0], _octave("structure", s, d)) is None, msg
        oh, h = _octave("llhistory", s, d), res.llhistory[s, d, 0]
        oh = np.asarray(oh, dtype=object)
        assert h.shape == oh.shape, (msg, h.shape, oh.shape)
        for idx in np.ndindex(h.shape):
            if _empty(h[idx]) or _empty(oh[idx]):
                assert _empty(h[idx]) and _empty(oh[idx]), (msg, idx)
            else:
                np.testing.assert_allclose(np.ravel(h[idx]),
                                           np.ravel(np.asarray(oh[idx], float)),
                                           rtol=1e-10, atol=0, err_msg=f"{msg} {idx}")
    # empty cells stay empty (structure{1,1}, ...), as in resultsdemo.mat
    assert res.structure[0, 0, 0] is None and res.llhistory[4, 2, 0] is None
    names = _cell(FX["names"], np.ravel(FX["names_size"]))
    assert res.names.shape == names.shape == (1, 3)
    for d in range(3):
        assert res.names[0, d] == [str(x) for x in np.ravel(names[0, d])]


def test_replay_pss_is_masterruns_ps(replayed):
    """masterrun.m:65 stores its own ps, not runmodel's (no runps.structname)."""
    res, ps = replayed["res"], replayed["ps"]
    for s, d in ORDER:
        p = res.pss[s, d, 0]
        assert p is not ps and p.runps.structname is None
        assert (p.speed, p.init, p.reloutsideinit) == (54, "intext", "overd")
    assert ps.runps.structname is None  # the input is not mutated


def test_replay_growth_history_files(replayed):
    out = replayed["out"]
    got = sorted(str(p.relative_to(out / "results")) for p in
                 (out / "results").rglob("growthhistory*"))
    files = [str(x) for x in np.ravel(np.asarray(FX["files"], dtype=object))]
    assert got == sorted(f + ".mat" for f in files)  # Octave does not add .mat


def test_replay_end_to_end_criteria(replayed):
    """PLAN §7.1 with replay: score within 1e-3 rel, same cluster count, ARI = 1."""
    res = replayed["res"]
    for r in res.runs:
        s, d = r["sind"], r["dind"]
        o = _summary(_ograph(s, d))
        oll = float(np.asarray(FX["modellike"], float)[s, d])
        assert abs(r["ll"] - oll) <= E2E_RTOL * abs(oll)
        assert r["nclusters"] == o["nclusters"] and r["nnodes"] == o["nnodes"]
        assert adjusted_rand_index(r["z"], o["z"]) == pytest.approx(1.0)


def test_replay_ties_are_rare(replayed):
    """The tie rules (item 27) are needed a few times only (the runmodel fixture needs
    them 11 times in its 9 feature baseline and 12 other runs)."""
    assert replayed["ties"] <= 12


def test_replay_saved_results(replayed):
    """The .npz/.json written after the last run hold every run and read back."""
    res, out = replayed["res"], replayed["out"]
    summary = json.loads((out / "resultsdemo.json").read_text())
    assert summary["format"] == run.RESULTS_FORMAT
    assert summary["structures"] == PS0.structures and summary["data"] == PS0.data
    assert [(r["structure"], r["data"]) for r in summary["runs"]] == PAIRS
    back = load_results(out / "resultsdemo")
    np.testing.assert_array_equal(back.modellike, res.modellike)
    for s, d in ORDER:
        g, bg = res.structure[s, d, 0], back.structure[s, d, 0]
        np.testing.assert_array_equal(bg["z"], g.z)
        np.testing.assert_array_equal(bg["adj"], np.asarray(g.adj, float))
        np.testing.assert_array_equal(bg["W"], g.W)
        h, bh = res.llhistory[s, d, 0], back.llhistory[s, d, 0]
        assert h.shape == bh.shape
        for idx in np.ndindex(h.shape):
            assert (h[idx] is None) == (bh[idx] is None)
            if h[idx] is not None:
                np.testing.assert_array_equal(np.ravel(bh[idx]), np.ravel(h[idx]))
        assert back.pss[s, d, 0]["speed"] == 54
    assert back.names[0, 0] == res.names[0, 0]


# --- masterrun details (cheap relational runs: no optimizer) -------------------------------

REL = (PS0.structures.index("dirring"), PS0.data.index("demo_ring_rel_bin"))
REL2 = (PS0.structures.index("partition"), PS0.data.index("demo_hierarchy_rel_bin"))


def test_seeds_per_run(monkeypatch):
    """rand('state', rind) before each run -> NumpyPermutations(seed + rind - 1); a
    provider is shared by all runs; a callable gets rind."""
    seen = []

    def fake(ps, sind, dind, rind, outdir=None, rng=None, show=None):
        seen.append((rind, rng))
        g = run.graph_from_mat({"type": "partition", "objcount": 2.0, "z": np.array([1., 2.]),
                                "adj": np.zeros((4, 4)), "W": np.zeros((4, 4))})
        return -1.0, g, ["a", "b"], run.empty_cell(), run.empty_cell()

    monkeypatch.setattr(run, "runmodel", fake)
    res = masterrun(thisstruct=(0,), thisdata=(0, 1), repeats=2, seed=5)
    assert [r["seed"] for r in res.runs] == [5, 5, 6, 6]
    for (rind, rng), sd in zip(seen, [5, 5, 6, 6]):
        assert isinstance(rng, NumpyPermutations)
        np.testing.assert_array_equal(rng.randperm(10),
                                      np.random.default_rng(sd).permutation(10))
    assert res.modellike.shape == (1, 2, 2)
    seen.clear()
    shared = NumpyPermutations(0)
    masterrun(thisstruct=(0,), thisdata=(0, 1), rng=shared)
    assert [r for _, r in seen] == [shared, shared]
    seen.clear()
    masterrun(thisstruct=(0,), thisdata=(0, 1), rng=7)  # a seed: one shared stream
    assert seen[0][1] is seen[1][1] and isinstance(seen[0][1], NumpyPermutations)
    seen.clear()
    masterrun(thisstruct=(0,), thisdata=(0,), repeats=2, rng=lambda rind: ("p", rind))
    assert [r for _, r in seen] == [("p", 1), ("p", 2)]


def test_masterfile_is_merged(tmp_path):
    """masterrun.m:62-65: an existing masterfile is loaded before each store, so a new
    session adds its runs to it (modellike keeps the old entries)."""
    a = masterrun(thisstruct=(REL[0],), thisdata=(REL[1],), outdir=tmp_path)
    b = masterrun(thisstruct=(REL2[0],), thisdata=(REL2[1],), outdir=tmp_path)
    back = load_results(tmp_path / "resultsdemo")
    assert [(r["sind"], r["dind"]) for r in back.runs] == [REL, REL2]
    assert back.modellike.shape == (REL[0] + 1, REL2[1] + 1, 1)
    assert back.modellike[REL + (0,)] == a.modellike[REL + (0,)]
    assert back.modellike[REL2 + (0,)] == b.modellike[REL2 + (0,)]
    assert b.modellike[REL + (0,)] == a.modellike[REL + (0,)]  # loaded into b
    assert isinstance(b.structure[REL + (0,)], dict)  # from the file
    # the same pair again replaces its entry
    masterrun(thisstruct=(REL[0],), thisdata=(REL[1],), outdir=tmp_path, seed=2)
    back = load_results(tmp_path / "resultsdemo")
    assert [(r["sind"], r["dind"], r["seed"]) for r in back.runs] == \
        [REL2 + (1,), REL + (2,)]


def test_no_outdir_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = masterrun(thisstruct=(REL[0],), thisdata=(REL[1],))
    assert list(tmp_path.iterdir()) == []
    assert np.isfinite(res.modellike[REL + (0,)])


def test_graph_summary():
    g = graph_from_mat({"type": "tree", "objcount": 4.0, "z": np.array([1., 1., 3., -1.]),
                        "adj": np.zeros((7, 7))})
    s = graph_summary(g)
    assert (s["nclusters"], s["nnodes"], s["z"]) == (2, 3, [0, 0, 2, -1])


def test_empty_results_save(tmp_path):
    save_results(MasterResults(), tmp_path / "x")
    back = load_results(tmp_path / "x")
    assert back.runs == [] and back.modellike.size == 0


def test_adjusted_rand_index():
    assert adjusted_rand_index([0, 0, 1, 1], [5, 5, 2, 2]) == pytest.approx(1.0)
    assert adjusted_rand_index([0, 0, 1, 1], [0, 1, 0, 1]) == pytest.approx(-0.5)
    sk = pytest.importorskip("sklearn.metrics")
    rs = np.random.default_rng(0)
    for _ in range(20):
        a, b = rs.integers(0, 4, 30), rs.integers(0, 5, 30)
        assert adjusted_rand_index(a, b) == pytest.approx(sk.adjusted_rand_score(a, b))


# --- CLI -----------------------------------------------------------------------------------

def test_parse_list():
    names = PS0.structures
    assert cli.parse_list("chain,ring,tree", names, "s") == [1, 3, 5]
    assert cli.parse_list("2, 4,6", names, "s") == [1, 3, 5]
    for bad in ["nope", "0", "99", ""]:
        with pytest.raises(ValueError):
            cli.parse_list(bad, names, "s")


def test_cli_run(tmp_path, capsys):
    out = tmp_path / "res"
    assert cli.main(["run", "--structures", "dirring,partition", "--datasets",
                     "demo_ring_rel_bin,5", "--seed", "3", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "demo_ring_rel_bin dirring" in text and "saved" in text
    summary = json.loads((out / "resultsdemo.json").read_text())
    runs = [(r["structure"], r["data"], r["seed"]) for r in summary["runs"]]
    assert runs == [("dirring", "demo_ring_rel_bin", 3), ("partition", "demo_ring_rel_bin", 3),
                    ("dirring", "demo_hierarchy_rel_bin", 3),
                    ("partition", "demo_hierarchy_rel_bin", 3)]
    assert (out / "resultsdemo.npz").is_file()
    assert any((out / "results" / "dirringout").rglob("growthhistory*.mat"))
    # the same seed gives the same results as the API
    res = masterrun(thisstruct=(REL[0],), thisdata=(REL[1],), seed=3)
    assert summary["runs"][0]["ll"] == res.runs[0]["ll"]


def test_cli_errors(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["run", "--structures", "nope", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        cli.main([])


def test_cli_module_help():
    env = {"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"}
    p = subprocess.run([sys.executable, "-m", "formdiscovery", "run", "--help"],
                       capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert p.returncode == 0 and "--structures" in p.stdout and "--seed" in p.stdout


# --- no replay (slow) ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def unreplayed(tmp_path_factory):
    """masterrun with scipy's optimizer and numpy permutations, seeds 1, 2 and 3."""
    return {seed: masterrun(masterrun_ps(), seed=seed) for seed in (1, 2, 3)}


@pytest.mark.slow
def test_no_replay_end_to_end(unreplayed):
    """PLAN §7.1 without replay: for every pair and seed, the final score is within
    1e-3 rel of Octave's and the cluster count is Octave's; the mean ARI over the seeds
    is >= 0.9."""
    rows = []
    for s, d in ORDER:
        o = _summary(_ograph(s, d))
        oll = float(np.asarray(FX["modellike"], float)[s, d])
        aris = []
        for seed, res in unreplayed.items():
            r = next(x for x in res.runs if (x["sind"], x["dind"]) == (s, d))
            rows.append((PS0.structures[s], PS0.data[d], seed, r["ll"], oll,
                         r["nclusters"], o["nclusters"]))
            assert abs(r["ll"] - oll) <= E2E_RTOL * abs(oll), rows[-1]
            assert r["nclusters"] == o["nclusters"], rows[-1]
            aris.append(adjusted_rand_index(r["z"], o["z"]))
        assert np.mean(aris) >= 0.9, (PS0.structures[s], PS0.data[d], aris)


# --- live Octave ---------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "masterrun.mat"
    octave.eval(f"fx_masterrun('{out}');", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    assert _text(fx["logtext"]) == _text(FX["logtext"])
    np.testing.assert_array_equal(fx["modellike"], FX["modellike"])
    assert len(fx["gl"]) == len(FX["gl"]) and len(fx["cns"]) == len(FX["cns"])
    for s, d in ORDER:
        a = _cell(fx["structure"], np.ravel(fx["structure_size"]))[s, d]
        assert graph_diff(a, _octave("structure", s, d), rtol=0, atol=0) is None
