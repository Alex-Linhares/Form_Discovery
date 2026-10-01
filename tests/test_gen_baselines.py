"""``tools/gen_baselines.py`` (loop0002 item 04): parallel Octave baselines.

The parallel path (one ``octave-cli`` per (structure, dataset) pair, then
``matlab/baseline_merge.m`` and a copy of the ``results/`` trees) must give exactly what
the serial ``run_baseline(kind)`` writes, i.e. the committed ``tests/fixtures/baseline``.
"""
import re

import numpy as np
import pytest
import scipy.io

from tests.conftest import FIXTURES_DIR, REPO_ROOT
from tools import gen_baselines as gb
from tools.mat_compare import compare_mat


def _run_baseline_grid(kind):
    """Default (structs, datas) of ``kind`` as written in run_baseline.m."""
    src = (REPO_ROOT / "matlab" / "run_baseline.m").read_text()
    block = re.search(rf"case '{kind}'(.*?)(?:case|otherwise)", src, re.S).group(1)

    def ev(var):
        expr = re.search(rf"{var}\s*=\s*([^;]+);", block).group(1).strip()
        out = []
        for part in expr.strip("[]").replace(",", " ").split():
            a, _, b = part.partition(":")
            out += list(range(int(a), int(b or a) + 1))
        return out

    return ev("defstruct"), ev("defdata")


@pytest.mark.parametrize("kind", ["feat", "rel"])
def test_grids_match_run_baseline(kind):
    assert gb.GRIDS[kind] == tuple(_run_baseline_grid(kind))


def test_serial_pairs_order():
    # run_baseline: sindpair(:) of repmat(thisstruct', 1, nd): structures vary fastest
    assert gb.serial_pairs([2, 4], [1, 3]) == [(2, 1), (4, 1), (2, 3), (4, 3)]


@pytest.mark.parametrize("kind", ["feat", "rel"])
def test_serial_pairs_match_committed_timings(kind):
    """The merge order is the serial run order recorded in the committed timings.mat."""
    t = scipy.io.loadmat(FIXTURES_DIR / "baseline" / kind / "timings.mat",
                         squeeze_me=True)["timings"]
    ps = scipy.io.loadmat(FIXTURES_DIR / "baseline" / kind / "resultsdemo.mat",
                          squeeze_me=True)["pss"]
    ps = next(p for p in ps.ravel() if isinstance(p, np.ndarray) and p.dtype.names)
    names = [str(n) for n in ps["structures"].item()]
    data = [str(n) for n in ps["data"].item()]
    got = [(names.index(str(r["structure"])) + 1, data.index(str(r["data"])) + 1)
           for r in t.ravel()]
    assert got == gb.serial_pairs(*gb.GRIDS[kind])


def test_plan_tasks(tmp_path):
    pairs = gb.serial_pairs(*gb.GRIDS["rel"])
    tasks, dirs = gb.plan_tasks("rel", pairs, tmp_path, tmp_path / "merged")
    assert len(tasks) == len(pairs) + 1 and len(set(dirs)) == len(pairs)
    keys = [t["key"] for t in tasks]
    assert len(set(keys)) == len(keys)
    merge = tasks[-1]
    assert set(merge["deps"]) == set(keys[:-1]) and "baseline_merge(" in merge["call"]
    for t, d, (s, dd) in zip(tasks, dirs, pairs):
        assert f"run_baseline('rel', {s}, {dd}, '{d}');" in t["call"]
        assert t["name"] == "baseline" and t["out"] is None
    # expected seconds come from the committed timings (longest pairs start first)
    assert any(t["expected"] != 10.0 for t in tasks[:-1])


def test_copy_results_refuses_overlap(tmp_path):
    for p in ("a", "b"):
        f = tmp_path / p / "results" / "chainout" / "x1" / "growthhistoryalltie5.mat"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="two pairs"):
        gb.copy_results([tmp_path / "a", tmp_path / "b"], tmp_path / "m")


def test_compare_baselines_sees_file_sets(tmp_path):
    for p in ("a", "b"):
        (tmp_path / p).mkdir()
    (tmp_path / "a" / "extra.txt").write_text("x")
    assert gb.compare_baselines(tmp_path / "a", tmp_path / "b") == [
        f"only in {tmp_path / 'a'}: extra.txt"]


@pytest.mark.octave
def test_parallel_feat_equals_serial_baseline(tmp_path):
    """All 9 feature pairs in parallel, merged: same file set and content (all ll values,
    graph structs, pss, llhistory, growth histories, timings but ``seconds``) as the
    committed serial ``run_baseline('feat')``."""
    out = tmp_path / "feat"
    ok, result = gb.generate("feat", out, 9, tmp_path / "logs")
    assert ok, result
    assert gb.compare_baselines(out, FIXTURES_DIR / "baseline" / "feat") == []


@pytest.mark.slow
@pytest.mark.octave
def test_parallel_rel_equals_serial_baseline(tmp_path):
    """The 54 relational pairs in parallel, merged, equal the committed serial
    ``run_baseline('rel')`` (about 30 s with 16 processes)."""
    out = tmp_path / "rel"
    ok, result = gb.generate("rel", out, 16, tmp_path / "logs")
    assert ok, result
    assert gb.compare_baselines(out, FIXTURES_DIR / "baseline" / "rel") == []


@pytest.mark.octave
def test_merge_skips_crashed_pair(octave, tmp_path):
    """A pair whose run crashed (timings.mat only, as run_baseline writes it) adds its
    timings entry and leaves its modellike/structure entries unset."""
    octave.addpath(str(REPO_ROOT / "matlab"))
    good, bad = tmp_path / "good", tmp_path / "bad"
    octave.eval(f"run_baseline('feat', 2, 1, '{good}');", nout=0)
    bad.mkdir()
    octave.eval(
        "timings = struct('structure', 'ring', 'data', 'demo_chain_feat', 'rind', 1, "
        "'seconds', 0.5, 'll', NaN, 'error', 'boom');"
        f"save('-v7', '{bad / 'timings.mat'}', 'timings');", nout=0)
    merged = tmp_path / "merged"
    octave.eval(f"baseline_merge('{merged}', [2 1; 4 1], {{'{good}', '{bad}'}});", nout=0)
    t = scipy.io.loadmat(merged / "timings.mat", squeeze_me=True)["timings"]
    assert [str(r["structure"]) for r in t] == ["chain", "ring"]
    assert np.isnan(float(t[1]["ll"])) and str(t[1]["error"]) == "boom"
    ml = scipy.io.loadmat(merged / "resultsdemo.mat")["modellike"]
    assert ml.shape == (2, 1) and ml[0, 0] == 0
    assert ml[1, 0] == pytest.approx(-8247.204813441429, rel=1e-15)
    # the crashed pair adds nothing: same resultsdemo.mat as the good pair alone
    assert compare_mat(good / "resultsdemo.mat", merged / "resultsdemo.mat") == []
