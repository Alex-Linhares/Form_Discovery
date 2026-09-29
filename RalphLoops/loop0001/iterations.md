# Iterations — loop0001

Legend: `[ ]` pending · `[x]` solved · `[~]` blocked (details in PROGRESS.md).
Work on the first `[ ]` item only. Section references are to `/PLAN.md`.

## Phase 0 — environment and Octave baseline (PLAN §3)

- [x] 01. **Import sources and scaffold the repo.** Copy `formdiscovery1.0/` (all `.m` files,
      `README.txt`, `data/`) from the Dropbox path in TASK.md to `matlab/formdiscovery1.0/`;
      delete `octave-core`; delete the empty `MATLAB DO DANIEL/` tree. Create `pyproject.toml`
      (package `formdiscovery`, src layout, pytest config with markers `slow` and `octave`),
      `environment.yml` (python 3.12, numpy, scipy, networkx, matplotlib, pytest, hypothesis,
      octave, oct2py, pygraphviz from conda-forge), `.gitignore` (results dirs, `_GtDout.dot`,
      `_LAYout.dot`, `*.pyc`, `.pytest_cache`), `src/formdiscovery/__init__.py`,
      `tests/__init__.py`, `tests/octave/`, `tests/fixtures/.gitkeep`, `tools/`. Verify
      `python -m pytest -q` runs (exit code 5, no tests, is fine).
- [x] 02. **Install Octave toolchain.** Create conda env `fd` from `environment.yml`
      (conda-forge `octave`, `oct2py`, `pygraphviz`). Verify `octave --version`, `oct2py`
      round-trip of a matrix, `import pygraphviz`. Write `tests/conftest.py` with an
      `octave` session fixture (oct2py `Oct2Py` with `matlab/formdiscovery1.0` on the path) that
      skips `octave`-marked tests when Octave is unavailable. Record exact versions in
      PROGRESS.md and in `environment.yml` pins.
- [x] 03. **Octave compatibility patches.** In `matlab/formdiscovery1.0/`: `dijkstra.m:33`
      `nargchk` → `narginchk`; replace `keyboard` with `error(...)` in `graph_like_rel.m`,
      `dataprobwsig.m`, `choose_node_split.m`, `best_split.m`, `swapobjclust.m`, `spr.m`,
      `collapsedims.m`; `draw_dot.m` `my_setdiff` → `mysetdiff`; make `dot_to_graph.m` work
      without the statistics package (`range` → `max-min`) and with current string functions.
      Smoke-test in Octave: `setps; defaultps; structcounts(12, ps); makeemptygraph` for every
      structure name; `scaledata` on `demo_chain_feat`. Write each patch as a minimal diff and
      document all of them in `matlab/PATCHES.md`.
- [x] 03b. **Octave set-op orientation patch (found by item 04).** Octave's `union(row, [])`
      returns a *column* (MATLAB treats a 0×0 `[]` as orientation-neutral and returns a row;
      `union([],[])` is 0×1 in Octave vs 0×0 in MATLAB). In `find_descendants.m:29` leaf
      `descendants{c}` are `[]`, so `descendants{j}` becomes a column and
      `spr.m:87` `jds = [j, descendants{j}]` crashes every `tree` run:
      `error: horizontal dimensions mismatch (1x1 vs 2x1)` (from `spr>makers` line 87 ←
      `spr` 24 ← `gibbs_clean` 92 ← `structurefit` 142 ← `runmodel>brlencases` 224 ←
      `runmodel` 153). Smallest repro: `find_descendants([0 1 1; 0 0 0; 0 0 0])`, then
      `[1, ans{1}]`. Fix as a PATCH(octave) in `find_descendants.m` (`ds = ds(:)';` after the
      union — verified in a scratch copy: all 9 feature runs then finish). Also audit the other
      36 `union/intersect/setdiff/unique` calls (14 files: best_split, addnearmiss,
      empty_graph, structurefit, combinegraphs, spr, scaledata, collapsedims, relgraphinit,
      split_node, simplify_graph, makelcfreq, swapobjclust) for empty-input orientation
      differences that change results without crashing; patch or record in PATCHES.md.
      Add a test in `tests/test_patches.py` pinning the repro. Afterwards, regenerate the
      baselines blocked by this bug: `run_baseline('feat')` (item 04, tree runs) and
      `run_baseline('rel')` (item 05, `undirhierarchy × demo_hierarchy_rel_bin`).
- [x] 04. **Headless feature-data baseline.** Write `matlab/run_baseline.m` that sets all
      `ps.show*=0`, seeds `rand('state', rind)`, and runs the default `masterrun` grid
      (structures chain, ring, tree × datasets 1–3) with `ps.speed` as default (54). Save
      `resultsdemo.mat` plus the per-run `growthhistory*.mat` files into
      `tests/fixtures/baseline/feat/`. Record wall-clock per run in PROGRESS.md. If a run
      crashes, capture the Octave error verbatim and file the fix as a new item after 03.
      *Status (iteration 5): chain + ring × datasets 1–3 fixtures committed and pinned by
      `tests/test_baseline.py`; remaining: tree runs, blocked on 03b. After 03b, rerun
      `run_baseline('feat')` (all 9 runs, ~30 s), add tree to `EXPECTED_LL`/`STRUCTS`. Iteration 6: marked `[~]` — still blocked on 03b, which loop.py's
      `ITEM_RE` cannot see (`03b` is not `\d+`); see PROGRESS.md iteration 6. Un-mark to `[ ]`
      once 03b is done.*
- [x] 05. **Relational baseline and known-issue decisions.** Extend `run_baseline.m` with
      `ps.reloutsideinit='overd'`, structures `[1,9,10:13,3,14:24]` × datasets 4–6, saving to
      `tests/fixtures/baseline/rel/`. Create `KNOWN_ISSUES.md` listing every bug in PLAN §3.5
      with a decision (replicate / fix) and the test that will pin it.
      *Status (iteration 7): `KNOWN_ISSUES.md` is done (KI-1 to KI-12, pinned statically by
      `tests/test_known_issues.py`). The relational baseline has 53 of 54 runs committed and
      pinned by `tests/test_baseline_rel.py`. The run `undirhierarchy × demo_hierarchy_rel_bin`
      crashes in `spr>makers` l.87 (the same `find_descendants` orientation bug), so the item is
      blocked on 03b. After 03b, rerun `run_baseline('rel')` (~2.5 min) and move that run from
      `CRASHED` to `EXPECTED_LL`, then un-mark to `[ ]`/`[x]`.*

## Foundations (PLAN §2 conventions, §4.3)

- [x] 06. **Conventions and MATLAB-semantics helpers.** Write `src/formdiscovery/CONVENTIONS.md`
      (from PLAN §2). Implement `io.py` (`load_dataset(name)` returning numpy arrays or a
      relational dict with `R`, `type`, `nobj`, `names`; `load_fixture(name)`; index-shift
      helpers) and `matlab_compat.py`: `find_F` (column-major nonzero indices), `hist_centres`
      (MATLAB `hist(x, centres)` end-bin lumping), `unique_rows` returning MATLAB's `[b,i,j]`,
      sorted `setdiff/intersect/union`, order-preserving `mysetdiff`, `chol_upper`,
      `sparse_accum`, `median_matlab` (empty → NaN), `stable_argsort`, `max_first`. Each helper
      gets an Octave fixture test. Write `tools/gen_fixtures.py` (runs every `tests/octave/*.m`
      through Octave, writes `tests/fixtures/*.mat` with `save -v7`).

## L0 — pure math and utilities (PLAN §5)

- [x] 07. **L0-a.** `vec, inv_triu, inv_posdef, logdet, mylogdet, sumlogs, meanlogs, mysetdiff,
      subv2ind, trans2orig, matrixpartition, triplepartition, weightprior` → `util.py` /
      `weights.py`. Fixtures: random SPD matrices, log-space vectors, a non-PD matrix for the
      `mylogdet` fallback (note MATLAB returns complex; decide and document).
- [x] 08. **L0-b.** `stirling2, hessiangrad, dijkstra, get_edgemap, find_descendants,
      expand_graph, makehyps, bbloglike, bblikesumhyps, dirmultloglike`. `stirling2(40,40)` must
      match exactly (it feeds the priors). `dijkstra` on every demo `adj`. `get_edgemap` in both
      normal and `'sym'` modes.

## L1 — parameters, priors, preprocessing

- [x] 09. **L1 params.** `setps, defaultps, setrunps, gridpriors, structcounts, graph_prior` →
      `params.py` with a `Params` dataclass mirroring `ps` (nested `runps`). Fixtures:
      `structcounts(n)` for n in {8, 12, 14, 28, 33, 35, 40}; `graph_prior` for every structure
      name and cluster count.
- [ ] 10. **L1 preprocess.** `simpleshiftscale, makesimlike, scaledata (+makechunks)` →
      `preprocess.py`. Fixtures: every data set, including `judges` (inf = missing → chunk
      path; chunk order must match `unique(...,'rows')` lexicographic order) and the
      similarity sets with `simtransform='center'`.

## L2 — graph data structure

- [ ] 11. **L2-a1.** `Graph` and `Component` dataclasses (fields named exactly as in the MATLAB
      struct), `expand_graph, combinegraphs, makeemptygraph` → `graph.py`. Fixtures:
      `makeemptygraph` for all 24 structure names plus grid/cylinder; `combinegraphs` with and
      without `'zonly'`, with `prodtied` on/off, on product graphs from the baseline growth
      histories. Write `graph_equal()` in `tests/helpers.py` that reports the first differing
      field.
- [ ] 12. **L2-a2.** `add_element, empty_graph, split_node`. Fixtures: `split_node` for every
      (structure family, pind) production listed in PLAN §5 / the survey (partition,
      connected, chain, ring incl. first-split 2-cycle, hierarchy pind 1–3 incl. rootchain
      and domtreeflat, tree pind 1–2 incl. treever2), driven by split sequences recorded from
      the Octave baseline.
- [ ] 13. **L2-a3.** `simplify_graph (+redundantinds), subtreeattach`. Fixtures: graphs from
      the growth histories before/after cleaning; `ps.cleanstrong` 0 and 1; tree and hierarchy
      regrafts onto edges and nodes.
- [ ] 14. **L2-b1.** `filloutrelgraph, makelcfreq, relgraphinit (+subfunctions), reordermissing`.
      Fixtures: `relgraphinit(data.R, 1:n, ps)` for every relational structure name on the
      relational demos; `reordermissing` on `judges` chunks.
- [ ] 15. **L2-b2.** `mat2vec, combineWs, extract_weights` (column-major ordering!). Fixtures:
      round-trip under all tying modes (`fixedall`, `fixedinternal`, `fixedexternal`,
      `prodtied`, none) on single and product graphs.

## L3 — likelihoods

- [ ] 16. **L3-a1.** `inv_covariance, gplike, dataprobwsig` (value and gradient, no missing
      data) → `likelihood_feat.py`. Port `checkgrad` as a test utility and assert the analytic
      gradient matches finite differences on every fixture graph.
- [ ] 17. **L3-a2.** `dataprobwsig` missing-data chunk path (recursive call per chunk,
      gradient reassembly via `sind`). Fixtures from `judges`.
- [ ] 18. **L3-b1.** `graph_like_conn` fast mode (`ps.fast=1`) and `graph_like` dispatcher →
      exact parity on all baseline graphs.
- [ ] 19. **L3-b2.** `graph_like_conn` slow mode: optimizer + Laplace (PLAN §4.1). Implement
      with `scipy.optimize.minimize` (method parameterised; start with `trust-exact` using the
      analytic gradient), replicate `includeind` truncation and the `isreal` fallback. Tests:
      objective at Python optimum ≤ Octave's + 1e-6, gradient norm ≤ Octave's, `logI` within
      documented tolerance (start 1e-4 rel). Record which scipy method tracks Octave best.
- [ ] 20. **L3-c.** `countmatrix, rellikebin, rellikefreqs, graph_like_rel` →
      `likelihood_rel.py`. Fixtures: every `relbin`/`relfreq` data set × every dir/undir/noself
      variant (covers diagonal self-link and symmetrisation branches).
- [ ] 21. **M3 checkpoint.** Script `tools/compare_runs.py --score-true-graphs`: for each demo
      data set, build the true graph stored in the `.mat`, score it in Octave and in Python
      (fast and slow mode), print a table. All fast-mode scores exact, slow-mode within
      tolerance. Commit the table into PROGRESS.md.

## L4 — search heuristics (PLAN §4.2 for randomness)

- [ ] 22. **Permutation replay.** `rng.py` with a `PermutationProvider` protocol (numpy default,
      identity, and queue-replay implementations) and `matlab/octave_shims/randperm.m` that
      shadows Octave's `randperm` by reading permutations from a file set via an env var (or
      returning identity). conftest fixture `replay` that produces matching Octave/Python
      providers. Test that both sides consume the same sequence.
- [ ] 23. **L4-a.** `addnearmiss, choose_seedpairs, best_split, choose_node_split` →
      `search.py`. Exact parity with replayed permutations; also a property test that the
      chosen split maximises the candidate scores. Cover the >5-members branch of
      `choose_seedpairs`.
- [ ] 24. **L4-b1.** `swapobjclust (+chooseswaps, doswap, sourceobjs, sourcecls, cltypes)`.
      Replayed permutations; all five swap types; single and product graphs.
- [ ] 25. **L4-b2.** `spr (+makerp, makers), collapsedims (+getocc, get_occnodescomp, zassign)`.
      Tree/hierarchy graphs for `spr`; grid/cylinder graphs for `collapsedims`.
- [ ] 26. **L4-c1.** `gibbs_clean (+nearmissopts)` incl. near-miss list as a Python list
      (MATLAB `cat(2, graph, nearmgraphs{:})` drops empties). `graphsig` stubbed to raise
      `NotImplementedError` (only reached when `ps.nauty=1`). Parity at speed 5 fast, then
      speed 4.
- [ ] 27. **L4-c2.** `structurefit (+bestsplit, graphscorenoopt, optimizebranches,
      optimizedepth)`. Reproduce the Octave growth history (`bestgraphlls`, `bestgraph`) for
      `demo_chain_feat` × chain with replayed permutations. Replace `save(savefile, ...)` with
      an optional callback/output dir.

## L5 — drivers and end-to-end

- [ ] 28. **L5-a.** `runmodel (+brlencases)` → `run.py`; explicit `outdir` instead of
      `mkdir/cd`; the `griddimsearch`/`cyldimsearch*` branches ported but marked untested
      unless the baseline covered them. Parity vs baseline for the three feature demos.
- [ ] 29. **L5-b.** `masterrun` → CLI `formdiscovery run --structures chain,ring,tree
      --datasets 1,2,3 --seed 1 --out results/`, saving `.npz` + JSON summary. End-to-end
      regression (PLAN §7.1): final log-probability within 1e-3 rel of Octave, same cluster
      count, ARI = 1 with replay / ≥ 0.9 over 3 seeds without. Mark as `slow` if > 2 min.
- [ ] 30. **Paper-level checks and property tests** (PLAN §7.2–7.3), all marked `slow`:
      synthetic sets recover their true form; `animals` → tree, `colors` → ring; hypothesis
      tests for `simplify_graph` idempotence, `combinegraphs` objcount preservation,
      relabelling invariance of the likelihood.

## Visualisation (PLAN §6)

- [ ] 31. **Viz A1: DOT text.** `viz/dot.py`: `graph_to_dot(adj, labels, directed, ...) -> str`
      and `dot_to_graph(text) -> (adj, labels, x, y)`. Fixtures: Octave's `_GtDout.dot` for
      every baseline graph (byte parity after whitespace normalisation) and Octave's parse of
      the corresponding neato layout files (exact).
- [ ] 32. **Viz A2: pygraphviz backend.** `viz/pygraphviz_backend.py` (neato with
      `maxiter=25000, regular, minlen=5, overlap=false`, `-x` for n>100; same 0.05/0.9
      normalisation; matplotlib ellipses, grey self-loop nodes, arrows when directed),
      `viz/draw.py` facade `draw_dot(adj, labels, backend=...)`, CLI `formdiscovery draw`.
      Progress callbacks reproducing figures 1/2/3 behaviour. Smoke + low-tolerance image
      regression tests.
- [ ] 33. **Viz B1: networkx backend.** `to_networkx(graph)` with node attrs (`kind`, `label`,
      `cluster_id`) and edge weights `1/W`; layout via `graphviz_layout(prog='neato')` when
      available else `kamada_kawai_layout`; `nx.draw_networkx` rendering; `to_graphml`,
      `to_dot` exports. Round-trip tests.
- [ ] 34. **Viz B2: interactive backends and examples.** Optional `plotly` and `pyvis`
      backends behind extras; `examples/formdiscovery_demo.ipynb` reproducing the masterrun
      demo end to end with figures; README usage section.

## Wrap-up

- [ ] 35. **Performance budget.** Time Octave vs Python per `graph_like` call and per
      `structurefit` depth on the demos and one synthetic set; profile `dataprobwsig`;
      apply safe optimisations (cached inverses, avoiding repeated `inv`) only with parity
      tests still green. Record the table in PROGRESS.md. Then verify every item above,
      update the status header, and add `LOOP_COMPLETE`.
