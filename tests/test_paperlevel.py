"""Paper-level checks (item 30, PLAN.md §7.2), all marked ``slow``.

Kemp & Tenenbaum (2008), Fig. 2/3: on the synthetic data sets the true form scores highest
among partition, chain, ring, tree and grid; on ``animals`` the tree wins and on
``colors`` the ring wins (among the 8 feature forms).

The fixture ``tests/fixtures/paperlevel.mat`` comes from ``tests/octave/fx_paperlevel.m``
(regenerate with ``python tools/gen_paperlevel.py``, parallel Octave processes, about
8 min on 32 cores; ``python tools/gen_fixtures.py paperlevel`` splits it the same way). It
holds one original ``runmodel`` run per (form, data set) pair, with ``rand('state', 1)``:

- synthetic sets (masterrun.m's option a, 5 x 5) at ``ps.speed = 5``. The default speed
  54 adds a speed-4 refinement that costs several times more on 40 x 2000 data; speed 5
  still ends with runmodel's slow "true score" (optimised lengths + Laplace), so the
  scores are comparable across forms;
- ``animals`` and ``colors`` x the 8 feature forms (option b) at the default speed 54;
- ``animals`` x tree, hierarchy with seeds 2 and 3.

**Finding (KNOWN_ISSUES.md KI-30).** The original code does *not* reproduce the paper
on ``animals``: the hierarchy beats the tree. With seed 1 the tree search stops at
-3231.95 (19 clusters) against the hierarchy's -3223.66; with seeds 2 and 3 the tree
reaches -3223.30 but the hierarchy reaches -3220.62. The tree is the runner-up, less than
3 nats behind. The hierarchy form (objects may sit at internal nodes) contains the tree
(objects at leaves only) as a special case up to the prior, so the two are close on data
this size. ``EXPECTED`` follows the code; ``TRUE_FORM`` is the paper's answer. Recovery is
judged on the best score of each form over the runs made (``_best``).

Python's own searches (other permutations) do not find the -3220.6 hierarchy: over its 3
seeds its best tree (-3223.33) beats its best hierarchy (-3223.49) by 0.16 nats. The
scoring agrees: Python scores each of Octave's final animals/colors graphs within
``RESCORE_RTOL`` of Octave (``test_python_rescores_octave_graphs``), and then ranks the
hierarchy first. So on animals the Python test only requires tree and hierarchy to be
the top two forms.

Python runs the same 45 runs (``run.runmodel``, numpy permutations seeded like
``rand('state', seed)``, scipy's optimizer) in a process pool. No replay: the searches
may take different paths, so the comparison is by outcome (PLAN §7.1): the winning form,
and per run the score within ``E2E_RTOL`` and the same cluster count, except for the
runs in ``DIVERGENT`` where the two searches end in different local optima (grid and
cylinder, whose searches are the most path-dependent, and the animals tree). Those must
still be within ``DIVERGENT_RTOL``.
"""

import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from formdiscovery.io import graph_from_mat, load_dataset, load_fixture
from formdiscovery.likelihood import graph_like
from formdiscovery.params import DATASETS as PS_DATA
from formdiscovery.params import graph_prior, setrunps, structcounts
from formdiscovery.preprocess import scaledata
from formdiscovery.run import graph_summary, masterrun_ps, runmodel

pytestmark = pytest.mark.slow

FX = load_fixture("paperlevel")
RUNS = [dict(r) for r in FX["runs"]]
NRUNS = 45
TRUE_FORM = {"synthpartition": "partition", "synthchain": "chain", "synthring": "ring",
             "synthtree": "tree", "synthgrid": "grid", "animals": "tree", "colors": "ring"}
DATASETS = list(TRUE_FORM)
EXPECTED = {**TRUE_FORM, "animals": "hierarchy"}  # KI-30
E2E_RTOL = 1e-3  # PLAN §7.1
# (form, data set, seed): Python and Octave end in different local optima (seed 1 values:
# up to 1.5e-2 rel apart, Python better on 5 of them).
DIVERGENT = {("grid", "synthchain", 1), ("grid", "synthring", 1), ("grid", "synthgrid", 1),
             ("ring", "synthgrid", 1), ("chain", "synthgrid", 1), ("tree", "synthgrid", 1),
             ("tree", "animals", 1), ("grid", "animals", 1), ("cylinder", "animals", 1),
             ("cylinder", "colors", 1)}
DIVERGENT |= {("tree", "animals", 2), ("hierarchy", "animals", 3)}
DIVERGENT_RTOL = 2e-2
RESCORE_RTOL = 2e-4  # slow graph_like at Octave's graphs (worst seen: 1.04e-4, colors ring)


def _key(r):
    return str(r["struct"]), str(r["data"]), int(r["seed"])


def _job(spec):
    s, d, speed, seed = spec
    ps = masterrun_ps()
    ps.speed = speed
    t0 = time.time()
    ll, graph, *_ = runmodel(ps, s, d, 1, rng=seed)
    return float(ll), graph_summary(graph)["nclusters"], time.time() - t0


@pytest.fixture(scope="module")
def python_runs(tmp_path_factory):
    """All fixture runs in Python, in parallel (one BLAS thread per process):
    ``{(form, data, seed): (ll, nclusters, seconds)}``. Computed once per test run, also
    under xdist, where each worker would otherwise rerun all 45 on every core."""
    from tests.helpers import xdist_shared
    out = xdist_shared("paperlevel_python_runs", tmp_path_factory, _python_runs)
    return {_key(r): (float(o[0]), int(o[1]), float(o[2])) for r, o in zip(RUNS, out)}


def _python_runs():
    specs = [(int(r["sind"]) - 1, int(r["dind"]) - 1, int(r["speed"]), int(r["seed"]))
             for r in RUNS]
    old = {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")}
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    try:
        import multiprocessing as mp
        with ProcessPoolExecutor(min(len(specs), os.cpu_count() or 1),
                                 mp_context=mp.get_context("spawn")) as ex:
            out = list(ex.map(_job, specs))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return [[float(ll), int(ncl), float(t)] for ll, ncl, t in out]


OCTAVE = {_key(r): (float(r["ll"]), int(r["ncl"])) for r in RUNS}


def _best(table, data, seeds=None):
    """``{form: best score over the runs}`` for one data set."""
    best = defaultdict(lambda: -np.inf)
    for (s, d, seed), v in table.items():
        if d == data and (seeds is None or seed in seeds):
            best[s] = max(best[s], v[0])
    return dict(best)


def _winner(scores):
    return max(scores, key=scores.get)


def test_fixture_contents():
    assert len(RUNS) == NRUNS
    assert [int(r["job"]) for r in RUNS] == list(range(1, NRUNS + 1))
    for d in DATASETS:
        forms = set(_best(OCTAVE, d))
        assert forms == ({"partition", "chain", "ring", "tree", "grid"} if d.startswith("synth")
                         else set(masterrun_ps().structures[:8])), d
    assert sorted(k for k in OCTAVE if k[2] != 1) == sorted(
        (s, "animals", seed) for s in ("tree", "hierarchy") for seed in (2, 3))
    assert all(np.isfinite(v[0]) for v in OCTAVE.values())


@pytest.mark.parametrize("data", DATASETS)
def test_octave_recovers_form(data):
    """The original code: the paper's form everywhere except animals (KI-30)."""
    scores = _best(OCTAVE, data)
    assert _winner(scores) == EXPECTED[data], scores


def test_octave_animals_tree_runner_up():
    """KI-30: on animals the paper's tree is Octave's second-best form, within 3 nats of
    the hierarchy; with seed 1 alone its tree search stops in a worse optimum."""
    scores = _best(OCTAVE, "animals")
    ranking = sorted(scores, key=scores.get, reverse=True)
    assert ranking[:2] == ["hierarchy", "tree"], scores
    assert 0 < scores["hierarchy"] - scores["tree"] < 3
    seed1 = _best(OCTAVE, "animals", seeds={1})
    assert seed1["tree"] < seed1["hierarchy"] - 5


@pytest.mark.parametrize("data", DATASETS)
def test_python_recovers_form(python_runs, data):
    """Python reaches Octave's answer (EXPECTED) on every data set; on animals the tree and
    the hierarchy, 0.16 nats apart in Python's runs, must be the top two (module
    docstring)."""
    scores = _best(python_runs, data)
    if data == "animals":
        ranking = sorted(scores, key=scores.get, reverse=True)
        assert set(ranking[:2]) == {"hierarchy", "tree"}, scores
        assert abs(scores["hierarchy"] - scores["tree"]) < 3
    else:
        assert _winner(scores) == EXPECTED[data], scores


def test_python_rescores_octave_graphs():
    """Python's slow score (graph_like + graph_prior) of each of Octave's final animals
    and colors graphs matches Octave's runmodel score, so with Octave's graphs Python ranks
    the forms as Octave does (hierarchy on animals, ring on colors)."""
    cache, rescored = {}, {}
    for r in RUNS:
        d = str(r["data"])
        if d not in ("animals", "colors"):
            continue
        if d not in cache:
            data = load_dataset(d)
            nobj, ps = setrunps(data, PS_DATA.index(d), masterrun_ps())
            data, ps = scaledata(data, ps)
            ps = structcounts(nobj, ps.replace(overrideSS=0, cleanstrong=0, fast=0))
            cache[d] = data, ps
        data, ps = cache[d]
        ps = ps.copy()
        ps.runps.structname = str(r["struct"])
        g = graph_from_mat(r["graph"])
        ll, _ = graph_like(data, g, ps)
        rescored[_key(r)] = (ll + graph_prior(g, ps), 0)
        np.testing.assert_allclose(rescored[_key(r)][0], float(r["ll"]), rtol=RESCORE_RTOL,
                                   err_msg=str(_key(r)))
    for d in ("animals", "colors"):
        assert _winner(_best(rescored, d)) == EXPECTED[d]


def test_python_scores_match_octave(python_runs):
    """Each run within 1e-3 rel of Octave's score with the same number of clusters
    (PLAN §7.1), except DIVERGENT (within DIVERGENT_RTOL). DIVERGENT is kept exact: a run
    in it that starts to agree must be taken out."""
    bad, diverged = [], set()
    for k, (oll, oncl) in OCTAVE.items():
        ll, ncl, _ = python_runs[k]
        rel = abs(ll - oll) / abs(oll)
        agree = rel <= E2E_RTOL and ncl == oncl
        if not agree:
            diverged.add(k)
        if not agree and (k not in DIVERGENT or rel > DIVERGENT_RTOL):
            bad.append((k, ll, oll, rel, ncl, oncl))
    assert not bad, bad
    assert diverged == DIVERGENT, (diverged - DIVERGENT, DIVERGENT - diverged)


@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    """Three cheap jobs (partition x colors/animals, chain x colors) rerun in Octave give
    the fixture's records exactly (Octave is deterministic for a given seed)."""
    from tests.helpers import graph_diff
    out = tmp_path / "paperlevel.mat"
    jobs = [34, 26, 35]
    octave.eval(f"fx_paperlevel('{out}', [{' '.join(map(str, jobs))}]);", nout=0)
    fx = load_fixture(out.name, fixtures_dir=tmp_path)
    for new in fx["runs"]:
        old = RUNS[int(new["job"]) - 1]
        assert _key(new) == _key(old)
        assert float(new["ll"]) == float(old["ll"])
        assert graph_diff(graph_from_mat(new["graph"]), graph_from_mat(old["graph"]),
                          rtol=0, atol=0) is None
