"""M3 checkpoint (item 21): the true graph of every demo data set, scored in Octave and
Python in fast and slow mode (``tools/compare_runs.py --score-true-graphs``).

The fixture ``tests/fixtures/truegraphs.mat`` comes from ``legacy/tests_octave/fx_truegraphs.m``
(regenerate with ``python legacy/tools/gen_fixtures.py truegraphs``):

- ``fe``: the three feature demos' true graphs (built from the file's ``adj``/``W``/
  ``sigma`` with ``makeemptygraph`` + ``combinegraphs``) in tying modes none, exttie and
  alltie;
- ``re``: the three relational demos' ``graph`` structs under every relational form of
  the generating family (ring: dir/undir x self/noself, hierarchy likewise, order and
  ordernoself).

Tolerances: fast ``logI``, ``graph_prior`` and the built graphs rtol 1e-10 (PLAN.md §2);
slow ``logI`` rel 2e-4 plus an optimality check (``test_glslow.py``'s rules, see
``compare_runs.py``).
"""

import numpy as np
import pytest

from formdiscovery.io import load_fixture
from tests.test_baseline import EXPECTED_LL as FEAT_LL
from tests.test_baseline_rel import EXPECTED_LL as REL_LL
from tools import compare_runs as cr

FX = load_fixture("truegraphs")
ROWS = cr.score_true_graphs(FX)
IDS = [f"{r['data']}:{r['form']}:{r['mode']}" for r in ROWS]


def test_fixture_contents():
    assert len(FX["fe"]) == 9 and len(FX["re"]) == 10
    assert not any(np.size(r["err"]) for r in FX["fe"] + FX["re"])
    assert [str(r["name"]) for r in FX["fe"][::3]] == list(cr.FEAT_DEMOS)
    assert [(str(r["name"]), str(r["structure"])) for r in FX["re"]] == [
        (d, f) for d, fs in cr.REL_FORMS.items() for f in fs]
    assert list(FX["modenames"]) == list(cr.MODES)
    assert np.array_equal(np.atleast_2d(FX["modes"]), np.array(list(cr.MODES.values())))


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_row(row):
    """Graph built as in Octave; fast exact; slow within tolerance and at least as good."""
    assert row["ok"], row["fail"]


def test_fast_is_exact_to_rounding():
    assert max(r["fast_rel"] for r in ROWS) < 1e-14


def test_slow_feature_gap_and_optimum():
    fe = [r for r in ROWS if r["kind"] == "fe"]
    assert max(r["slow_rel"] for r in fe) < 1e-5   # far inside SLOW_RTOL on these graphs
    # Python's optimum is never worse than fminunc's stopping point
    assert min(r["opt_gain"] for r in fe) >= -cr.OPT_TOL


def test_rel_slow_is_fast():
    for r in ROWS:
        if r["kind"] == "re":
            assert r["py_slow"] == r["py_fast"] and r["oct_slow"] == r["oct_fast"]


def test_true_scores_vs_baseline_search():
    """Where the Octave baseline search found the generating form, its final score
    (``logI + graph_prior``, untied slow mode for feature data) is the true graph's up to
    optimiser noise (feature) or exactly (dirring, order: the search recovered the true
    graph). For dirhierarchy the search found a better-scoring graph than the truth."""
    by = {(r["data"], r["form"], r["mode"]): r for r in ROWS}
    for (form, data), ll in FEAT_LL.items():
        if (data, form, "none") in by and data == f"demo_{form}_feat":
            r = by[(data, form, "none")]
            np.testing.assert_allclose(r["py_slow"] + r["prior"], ll, rtol=2e-6)
    for form, data in (("dirring", "demo_ring_rel_bin"), ("order", "demo_order_rel_freq")):
        r = by[(data, form, "-")]
        np.testing.assert_allclose(r["py_fast"] + r["prior"], REL_LL[(form, data)], rtol=1e-12)
    r = by[("demo_hierarchy_rel_bin", "dirhierarchy", "-")]
    assert r["py_fast"] + r["prior"] < REL_LL[("dirhierarchy", "demo_hierarchy_rel_bin")] - 10


def test_checks_catch_perturbations():
    """The comparison itself fails on a perturbed Octave score or graph."""
    import copy
    for field, part, scale in (("fast", "fe", 1 + 1e-9), ("slow", "fe", 1 + 1e-3),
                               ("fast", "re", 1 + 1e-9), ("prior", "re", 1 + 1e-9)):
        fx = copy.deepcopy(FX)
        fx[part][0][field] = float(fx[part][0][field]) * scale
        rows = cr.score_true_graphs(fx)
        idx = 0 if part == "fe" else len(FX["fe"])
        assert not rows[idx]["ok"], (field, part)
        assert sum(not r["ok"] for r in rows) == 1
    fx = copy.deepcopy(FX)
    fx["fe"][0]["graph"]["sigma"] = 2.5
    assert not cr.score_true_graphs(fx)[0]["ok"]


def test_main_prints_table(capsys):
    assert cr.main(["--score-true-graphs"]) == 0
    out = capsys.readouterr().out
    assert out.count("| yes |") == len(ROWS)
    assert f"{len(ROWS)}/{len(ROWS)} rows pass" in out


def test_main_needs_mode():
    with pytest.raises(SystemExit):
        cr.main([])


@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "truegraphs.mat"
    octave.eval(f"fx_truegraphs('{out}');", nout=0)
    new = load_fixture(str(out))
    for part in ("fe", "re"):
        for a, b in zip(FX[part], new[part]):
            for f in ("fast", "slow", "prior"):
                assert float(a[f]) == float(b[f]), (part, a["name"], f)


@pytest.mark.octave
def test_live_compare_runs(octave):
    assert cr.main(["--score-true-graphs", "--live"]) == 0
