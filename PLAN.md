# Plan: test-driven translation of `formdiscovery1.0` (Kemp & Tenenbaum 2008) to Python

Date: 2026-09-28

## 0. Current state of this repo (facts that shape the plan)

- **The MATLAB sources are not in this repo.** `MATLAB DO DANIEL/formdiscovery1.0/` contains only an
  empty, recursively-nested `data/results/chainout/...` tree (a botched copy). The real sources
  (74 `.m` files, 5,390 lines, plus 20 `.mat` data sets) are at
  `/home/al/Dropbox/AL Cognitive Model Course/MathModels/formdiscovery1.0/`.
  Step 1 below copies them into this repo.
- **Octave is not installed.** Available: `apt install octave` (11.1.0, needs sudo) or
  `conda create -n fd -c conda-forge octave=10.3` (no sudo). Neither `oct2py` nor `pygraphviz`
  is installed. Graphviz `dot`/`neato` 14.1.2 is installed. Python 3.12, numpy 1.26, scipy 1.17,
  networkx 3.3 are present.
- **Not a git repo yet.** Step 1 initialises one.
- An `octave-core` crash dump from 2008 sits in the source dir: someone tried this code in
  Octave 3.x and it crashed. Expect to patch a few things for Octave 10/11 (see §3).
- All `.mat` files are MATLAB v5 format; `scipy.io.loadmat` reads them. Values are stored as
  uint8/uint16 but are `double` in MATLAB, so load with `mat_dtype=True`.

## 1. Repository layout (target)

```
Kemp_Tanembaum_matlab_code/
├── PLAN.md
├── pyproject.toml                 # package "formdiscovery", pytest config, deps
├── environment.yml                # conda: python, numpy, scipy, octave, oct2py, pygraphviz, networkx, matplotlib
├── matlab/formdiscovery1.0/       # verbatim copy of the Dropbox sources (+ data/)
│   └── octave_shims/              # tiny .m files that shadow randperm etc. for tests (§4.3)
├── src/formdiscovery/
│   ├── __init__.py
│   ├── util.py                    # L0: sumlogs, meanlogs, mysetdiff, subv2ind, stirling2, vec, inv_triu, ...
│   ├── params.py                  # L1: setps, defaultps, setrunps, structcounts, gridpriors, graph_prior
│   ├── preprocess.py              # L1: scaledata, simpleshiftscale, makesimlike, makechunks
│   ├── graph.py                   # L2: Graph/Component dataclasses, combinegraphs, makeemptygraph, expand_graph,
│   │                              #     add_element, empty_graph, split_node, subtreeattach, simplify_graph,
│   │                              #     get_edgemap, find_descendants, filloutrelgraph, relgraphinit, reordermissing
│   ├── weights.py                 # L2/3: mat2vec, combineWs, extract_weights, matrixpartition, triplepartition, weightprior
│   ├── likelihood_feat.py         # L3: inv_covariance, gplike, dataprobwsig, graph_like_conn (fminunc + Laplace), hessiangrad
│   ├── likelihood_rel.py          # L3: countmatrix, bbloglike, bblikesumhyps, dirmultloglike, rellikebin, rellikefreqs, makehyps, graph_like_rel
│   ├── likelihood.py              # graph_like dispatcher
│   ├── search.py                  # L4: choose_seedpairs, best_split, choose_node_split, swapobjclust, spr, collapsedims,
│   │                              #     addnearmiss, gibbs_clean, structurefit
│   ├── run.py                     # L5: runmodel, masterrun (CLI entry point)
│   ├── io.py                      # load_dataset (.mat → numpy/dict), save results (.npz/.json), load Octave fixtures
│   ├── rng.py                     # permutation provider abstraction (§4.3)
│   └── viz/
│       ├── dot.py                 # graph_to_dot / dot_to_graph equivalents (pure text, testable)
│       ├── pygraphviz_backend.py  # Phase A: neato layout via pygraphviz
│       ├── networkx_backend.py    # Phase B: networkx + matplotlib (and optional plotly/ipysigma)
│       └── draw.py                # draw_dot facade choosing a backend
├── tests/
│   ├── conftest.py                # octave session fixture (oct2py), fixture loader, tolerance helpers
│   ├── octave/                    # .m scripts that generate golden fixtures (one per translation step)
│   ├── fixtures/                  # committed golden outputs (.mat or .npz) produced by tests/octave
│   ├── test_l0_util.py ... test_l5_run.py, test_viz.py
│   └── parity/                    # live Octave-vs-Python tests (skipped if Octave missing)
└── tools/
    ├── gen_fixtures.py            # runs every tests/octave/fx_*.m through Octave (--jobs N), writes tests/fixtures
    ├── gen_baselines.py           # run_baseline grid, one Octave per pair (--jobs N), merged into tests/fixtures/baseline
    ├── compare_live.py            # Octave run_baseline + Python runmodel (replayed draws) per triple, side by side (--jobs N)
    └── compare_runs.py            # diff a Python run against an Octave run (scores, graphs, z)
```

## 2. Testing architecture (the core of the approach)

Two complementary test modes, both driven by pytest:

1. **Golden-fixture tests (default, fast, no Octave needed at test time).**
   For each MATLAB function, an Octave script in `tests/octave/` builds inputs (loaded from the
   real `.mat` data or constructed deterministically), calls the MATLAB function, and saves
   inputs + outputs to `tests/fixtures/<func>.mat` (v7, via `save -v7`). The Python test loads the
   fixture, runs the Python translation on the same inputs, and compares.
   Fixtures are committed so CI and other machines do not need Octave.

2. **Live parity tests (`tests/parity/`, marked `@pytest.mark.octave`).**
   `oct2py` runs the Octave function and the Python function on identical, freshly generated
   inputs (including randomised ones) in the same test and compares. This catches cases fixtures
   miss and is the mode used while translating each function. Skipped automatically when
   Octave is absent.

Comparison rules:
- Integer/structural outputs (adjacency, `z`, `nodemap`, `edgemap`, `illegal`, indices): exact,
  after the 1-based → 0-based shift that `io.py` applies uniformly.
- Floating outputs of deterministic code (log-likelihoods, gradients, priors, covariances):
  `np.testing.assert_allclose(rtol=1e-10, atol=1e-12)` (differences only from summation order).
- Anything downstream of `fminunc` (MAP weights, Laplace `logI`): tolerance-based, see §4.1.
- Graph structs: a `graph_equal(g_oct, g_py)` helper that compares field by field and reports
  the first differing field, so failures are diagnosable.

Conventions fixed up front (write them in `src/formdiscovery/CONVENTIONS.md`):
- Indices are 0-based in Python; `io.py` converts at the boundary and nowhere else.
- All "find"/flatten operations that MATLAB does column-major use `order='F'` explicitly
  (`mat2vec`, `combineWs`, `get_edgemap`, `extract_weights`, `relgraphinit`).
- `chol` is upper-triangular in MATLAB; use `scipy.linalg.cholesky(A, lower=False)`.
- `hist(z, 1:n)` → a helper `hist_centres(z, centres)` replicating MATLAB's end-bin lumping;
  do not silently use `np.bincount`.
- `unique`, `setdiff`, `intersect`, `union` return sorted row vectors in MATLAB; use numpy
  equivalents (all sorted) and never rely on insertion order. `mysetdiff` is the one
  order-preserving exception and gets its own helper.
- `max`/`sort` tie-breaking: first index on ties, stable sort (`kind='stable'`); NaN handling
  matches MATLAB (`nanmax`-like) where it can occur.
- `keyboard` → raise `FormDiscoveryError`.
- `nchoosek(v,2)` → `itertools.combinations` (same lexicographic order); guard the scalar case.
- `graph` is a `@dataclass` with the same field names as the MATLAB struct (README lists them);
  components are a list of `Component` dataclasses. Keep MATLAB names so cross-referencing
  is trivial.

## 3. Phase 0: environment and Octave baseline (before any translation)

1. Copy `formdiscovery1.0/` (code + data) from Dropbox into `matlab/formdiscovery1.0/`; remove
   `octave-core`; `git init`, commit.
2. Install Octave (conda-forge recommended, no sudo) + `oct2py` + `pygraphviz` + `pytest`;
   write `environment.yml` and `pyproject.toml`.
3. Make the MATLAB code run under Octave 10/11 and record the patches (each as a small,
   commented change in the copy):
   - `dijkstra.m:33` uses `nargchk` (removed) → `narginchk` or delete the check.
   - `dot_to_graph.m` uses `textread`, `strread`, `strvcat`, `findstr`, `strmatch`, `range`
     (`range` needs the Octave `statistics` package) → only matters for display; fix or
     replace with `fileread`/`strsplit`/`max-min`.
   - `draw_dot.m` calls a nonexistent `my_setdiff` (only for singleton nodes) → `mysetdiff`.
   - `fminunc` with `optimset('LargeScale','on','GradObj','on')`: Octave accepts `GradObj`
     and ignores `LargeScale`. Verify it converges on the demo data; otherwise pin
     `MaxIter`/`TolFun`.
   - `display(sprintf(...))`, `disp` of cell arrays, `rand('state', n)`: all accepted by Octave.
   - `graph_like_rel.m:160`, `dataprobwsig.m:239`, `choose_node_split.m:22` call `keyboard`
     → replace with `error()` so headless runs cannot hang.
   - `masterrun.m` uses `system('which neato')` and figure windows → run with
     `ps.show* = 0` in the baseline.
4. Run the full Octave baseline headless: `masterrun` default (chain, ring, tree × the three
   demo feature sets), then relational demos (`ps.reloutsideinit='overd'`, structures
   `[1,9,10:13,3,14:24]` on datasets 4–6). Save `resultsdemo.mat` and the `results/` growth
   histories as `tests/fixtures/baseline/`. These are the end-to-end reference outputs.
   Record wall-clock times; they dictate how big the integration tests can be.
5. Note known bugs in the original and decide, per bug, "replicate" or "fix" (default:
   replicate, document in `KNOWN_ISSUES.md`, add a test that pins the behaviour):
   - `best_split.m:120` `case{'1,2'}` is a string, so speeds 1 and 2 are broken (only 3,4,5 work).
   - `combinegraphs.m:48,66` operator-precedence bug in the `illegal` handling for product
     graphs (works only because component 2 always has an empty illegal list).
   - `structurefit.m:38,59` writes `part{depth,c,pind,2}` without the `i` index (harmless).
   - `structurefit.m:239` uses a stale `pind` in the product-graph branch.
   - `zinit_rel.m` references an undefined `irmdatadir`.
   - `dijkstra.m` calls a missing `pred2path` on a path never reached.

## 4. Three cross-cutting hazards and how the tests handle them

### 4.1 The optimizer (`fminunc`) and the Laplace approximation

`graph_like_conn.m` in slow mode finds MAP log-branch-lengths with the Optimization Toolbox
trust-region `fminunc`, then computes a Laplace approximation using a finite-difference Hessian
(`hessiangrad`, step 1e-5) and `mylogdet(inv(-H))`. Octave's `fminunc` is a different algorithm
and scipy's will be different again, so bitwise parity is impossible here. Strategy:

- Test the **objective and analytic gradient** (`dataprobwsig`) exactly. This is the
  deterministic heart; parity there is what really matters. Also port `checkgrad` as a Python
  test that the analytic gradient matches finite differences.
- Test `hessiangrad` and `mylogdet` exactly on fixed inputs.
- For the optimizer, test **optimality, not the path**: on fixture inputs assert that
  (a) the Python optimum's objective is ≤ Octave's + 1e-6 (or equal within 1e-6),
  (b) the gradient norm at the Python optimum is below the same threshold Octave reached,
  (c) the resulting `logI` agrees with Octave within a documented tolerance (start at 1e-4
  relative; tighten if achievable).
- Implementation choice: `scipy.optimize.minimize(method='trust-exact' or 'trust-ncg', jac=True)`
  with the analytic gradient; fall back to `L-BFGS-B` for large graphs. Parameterise so the
  method can be swapped; the test suite will tell us which best tracks Octave.
- Replicate the `isreal(logI)` fallback branch explicitly (numpy gives NaN, not a complex
  number, for log of a negative), and the `includeind` upper-bound truncation.
- Add a parity test that toggles `ps.fast=1` (no optimizer) so the rest of the pipeline can be
  compared exactly independent of this issue.

### 4.2 Randomness

The only stochastic primitive is `randperm` (five call sites: `choose_seedpairs:24`,
`best_split:35`, `swapobjclust:33`, `spr:57/59`, `collapsedims:35`), seeded by
`rand('state', rind)` in `masterrun`. MATLAB, Octave and numpy streams all differ, so:

- Introduce `rng.py` with a `PermutationProvider` protocol; the search functions take it as a
  parameter (default: `numpy.random.Generator.permutation`).
- For parity tests, add `matlab/octave_shims/randperm.m` that shadows Octave's `randperm` and
  reads permutations from a queue file (or returns the identity), and give the Python side a
  provider that replays the same queue. Then L4 functions can be compared **exactly**, step by
  step, with identical random choices.
- For end-to-end tests, compare final log-likelihoods and structure summaries with tolerance,
  across several seeds, rather than exact graphs (§7.3).

### 4.3 MATLAB semantics that silently differ in Python

Enumerated in §2 conventions; the important ones to write helper functions and unit tests
for before translating anything else: column-major `find`, `hist` with bin centres, sorted set
ops, `chol` orientation, `sparse` accumulation of duplicate indices (`extract_weights:68`),
struct-array `cat(2, graph, nearmgraphs{:})` in `gibbs_clean:186` (becomes a list, dropping
`None`s), `median([])` = NaN, integer-vs-double data, `for c = unique(...)` iterating over a
row vector.

## 5. Translation order and per-step test contract

Every step follows the same loop:
1. Write `tests/octave/<func>.m` that exercises the MATLAB function on real data slices and
   edge cases, and save inputs/outputs to a fixture.
2. Write the failing Python test against that fixture (plus a live parity test if the function
   has randomness or takes graph structs).
3. Translate the function. Keep the MATLAB name (snake_case) and a docstring citing the source
   file and line range.
4. Green → commit. One commit per function or small group.

Layers, bottom-up (dependency order verified from the call graph; every callee of a step is
in an earlier step). Estimated size is MATLAB lines.

| Step | Functions | Lines | Notes / test inputs |
|---|---|---|---|
| L0-a | `vec`, `inv_triu`, `inv_posdef`, `logdet`, `mylogdet`, `sumlogs`, `meanlogs`, `mysetdiff`, `subv2ind`, `trans2orig`, `matrixpartition`, `triplepartition`, `weightprior` | ~110 | random SPD matrices, log-space vectors; `mylogdet` on a non-PD matrix to hit the fallback |
| L0-b | `stirling2`, `hessiangrad`, `dijkstra`, `get_edgemap`, `find_descendants`, `expand_graph`, `makehyps`, `bbloglike`, `bblikesumhyps`, `dirmultloglike` | ~330 | `stirling2(40,40)` exact match matters for priors; `dijkstra` on the demo adjacency matrices |
| L1 | `setps`, `defaultps`, `setrunps`, `gridpriors`, `structcounts`, `graph_prior`, `simpleshiftscale`, `makesimlike`, `scaledata` (+`makechunks`) | ~380 | `ps` becomes a dataclass; `structcounts(n)` for n in {8,12,14,33,35,40}; `scaledata` on every data set incl. `judges` (missing data → chunks; check chunk order from `unique(...,'rows')`) |
| L2-a | `combinegraphs`, `makeemptygraph`, `add_element`, `empty_graph`, `split_node`, `simplify_graph`, `subtreeattach` | ~530 | `makeemptygraph` for all 24 structure names + grid/cylinder; `split_node` for every (type, pind) production on small hand-built graphs; sequences of splits recorded from Octave |
| L2-b | `filloutrelgraph`, `makelcfreq`, `relgraphinit`, `reordermissing`, `mat2vec`, `combineWs`, `extract_weights` | ~400 | round-trip `mat2vec`∘`combineWs` under all four tying modes (`fixedall/internal/external/prodtied`) |
| L3-a | `inv_covariance`, `gplike`, `dataprobwsig` (value + gradient, incl. missing-data chunk path), port `checkgrad` as a test | ~330 | graphs from the L2 fixtures; `judges` for the missing-data path; gradient vs finite differences |
| L3-b | `graph_like_conn` (fast mode exact; slow mode per §4.1), `graph_like` | ~130 | |
| L3-c | `countmatrix`, `rellikebin`, `rellikefreqs`, `graph_like_rel` | ~250 | all `relbin`/`relfreq` data sets; every dir/undir/noself variant to cover diagonal and symmetrisation branches |
| L4-a | `addnearmiss`, `choose_seedpairs`, `best_split`, `choose_node_split` | ~260 | with injected permutations: exact; also property test that best_split's chosen split has the max score among candidates |
| L4-b | `swapobjclust`, `spr`, `collapsedims` | ~470 | injected permutations; product graphs for `collapsedims` |
| L4-c | `gibbs_clean`, `structurefit` (+ subfunctions) | ~510 | speed 5 with `fast=1` first (exact), then speed 4 (tolerance) |
| L5 | `runmodel` (+`brlencases`), `masterrun` → CLI `formdiscovery run --struct chain --data demo_chain_feat --seed 1` | ~320 | compare against §3.4 baseline; drop `cd`/`mkdir` side effects in favour of an explicit output dir |
| Skip/stub | `graphsig` (needs nauty; `ps.nauty=0` default) → stub raising `NotImplementedError`; `wdconv`, `zinit_rel` (broken) → not ported; `checkgrad` → becomes a test utility | | |

Each layer ends with an integration checkpoint that runs Octave and Python side by side on the
same small input up to that layer (e.g. after L3: score the true graph stored in
`demo_chain_feat.mat` under both).

## 6. Graph display port (`draw_dot`, `graph_to_dot`, `dot_to_graph`, `graph_draw`)

The original pipeline is: adjacency → write DOT text → shell out to `neato -Tdot` → parse node
`pos` back out of the layout DOT → normalise to the unit square → draw ellipses, labels and
arrows with MATLAB graphics (`graph_draw.m`, 559 lines, mostly an `arrow` routine).
Only `draw_dot(adj, names)` is called from the model code (`runmodel`, `structurefit`,
`best_split`), always with `ps.show*` flags that default to 0, so display is fully decoupled
from correctness and can be done last (or in parallel by a second person).

Phase A: faithful port with pygraphviz
- `viz/dot.py`: `graph_to_dot(adj, node_labels, directed, ...) -> str` (pure function; test
  against Octave's `_GtDout.dot` output byte-for-byte after whitespace normalisation) and
  `dot_to_graph(text) -> (adj, labels, x, y)` (test on the same neato outputs Octave parses).
- `viz/pygraphviz_backend.py`: build `pygraphviz.AGraph(directed=...)`, apply the same neato
  attributes (`maxiter=25000`, `regular`, `minlen=5`, `overlap=false`, `-x` for n>100), call
  `.layout(prog='neato')`, read `pos` attributes, apply the same 0.05/0.9 normalisation, draw
  with matplotlib (ellipse per node, grey fill for self-loops, arrows for directed).
  Also expose `.draw(path)` so a PNG/SVG can be produced without matplotlib.
- Tests: DOT text parity; layout parity on the demo graphs is checked by feeding Octave's
  neato-layout file into both parsers (same file, so exact); rendering tested by smoke test
  (produces a file, correct node count) and an image-regression test at low tolerance.
- Convenience: `formdiscovery draw results.npz --out fig.png`, and `show_progress` callbacks
  that reproduce the "figure 1 pre-clean / figure 2 post-clean / figure 3 result" behaviour.

Phase B: widely used Python graph libraries
- `viz/networkx_backend.py`: convert `Graph` → `networkx.Graph/DiGraph` with node attributes
  (`kind` = object/cluster, `label`, `cluster_id`) and edge weights `1/W`. Layout via
  `nx.nx_agraph.graphviz_layout(prog='neato')` when pygraphviz is present, else
  `nx.kamada_kawai_layout` (closest to neato's stress model). Draw with `nx.draw_networkx`.
- Optional interactive backends behind extras: `plotly` (hover names) and `pyvis`/`ipysigma`
  for notebooks. Keep the facade `draw_dot(adj, labels, backend=...)` stable.
- Export helpers: `to_networkx`, `to_graphml`, `to_dot` so users can take results into Gephi,
  Cytoscape, etc.
- Tests: conversion round-trip (adjacency preserved, labels preserved), layout smoke tests,
  and the same image-regression harness with a per-backend baseline.

## 7. Verification beyond unit tests

7.1 **End-to-end regression against the Octave baseline (§3.4).** For each (structure, dataset)
    pair in the baseline: Python final log-probability within 1e-3 relative of Octave's, same
    number of clusters, and same partition `z` up to relabelling (compare via adjusted Rand
    index = 1) when permutations are replayed; otherwise ARI ≥ 0.9 over 3 seeds.
7.2 **Paper-level sanity checks:** on the synthetic sets (`synthchain`, `synthring`, ... 40×2000)
    the true form must score highest among {partition, chain, ring, tree, grid}; on `animals`
    the tree should win and on `colors` the ring should win (Fig. 2/3 of the PNAS paper).
    Mark these `slow`.
7.3 **Property tests** (hypothesis): `simplify_graph` is idempotent; `combinegraphs` preserves
    `objcount`; likelihood is invariant to relabelling objects consistently in data and graph;
    `graph_prior` sums to ≤ 0 in log space over cluster counts.
7.4 **Performance budget:** record Octave vs Python time per `graph_like` call and per
    `structurefit` depth; the port should not be slower than Octave. Profile `dataprobwsig`
    (matrix inversions are the hot spot) once correctness is locked.

## 8. Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Environment + Octave baseline | Octave runs `masterrun` headless; baseline fixtures committed; pytest skeleton runs with oct2py fixture |
| M1 | L0 + L1 | all utility/prior/preprocessing parity tests green |
| M2 | L2 | any graph from the baseline growth histories can be rebuilt in Python and matches field-by-field |
| M3 | L3 | scoring the true graph of every demo data set matches Octave (exact in fast mode, tolerance in slow mode) |
| M4 | L4 | `structurefit` with replayed permutations reproduces Octave's growth history on the three feature demos |
| M5 | L5 | `formdiscovery run` reproduces the whole `masterrun` demo; §7.1 and §7.2 pass |
| M6 | Viz A | pygraphviz backend renders every baseline result; DOT parity tests green |
| M7 | Viz B | networkx/matplotlib backend + exports; docs and examples notebook |

Suggested sequencing: M0 first and alone (it de-risks everything). M1–M3 are strictly
sequential. M6 can start any time after M2 (it only needs the `Graph` dataclass). M4–M5 are
the largest and messiest (the original author's own README warns the heuristics are "messy");
budget the most time there and lean on the permutation-replay mechanism.

## 9. Open decisions (defaults chosen; change if you disagree)

- Octave via conda-forge rather than apt (no sudo; pins the version alongside Python).
- Fixture format: `.mat` v7 written by Octave, read by `scipy.io` (no extra Octave dependency
  at test time). Alternative: `.npz` written by an `oct2py` generation script.
- Replicate original bugs by default, with the exceptions of `keyboard` calls (→ exceptions)
  and the `cd`/`mkdir` side effects in `runmodel` (→ explicit output directory).
- 0-based indices everywhere in Python, converted only in `io.py` and in the parity helpers.
- Package name `formdiscovery`; MATLAB function names preserved as snake_case Python names.
