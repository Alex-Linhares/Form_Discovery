# Progress Log

## Ralph Loop 0001 Status
- **Started**: 2026-09-28
- **Target**: 36 items (see iterations.md)
- **Current**: 35/36 SOLVED

---

## Iteration 1 — 2026-09-28 21:24
### Completed
- Item 01: imported sources and scaffolded the repo.
  - Copied `formdiscovery1.0/` from the Dropbox path to `matlab/formdiscovery1.0/`
    (74 `.m` files, `README.txt`, `data/` with 21 `.mat`/`.tar.gz` files plus `README.txt` and
    `.svnignore`). `diff -rq` against the source shows `octave-core` as the only difference;
    it was deleted.
  - Deleted the `MATLAB DO DANIEL/` tree (it contained only nested empty directories, no files).
  - Created `pyproject.toml` (package `formdiscovery`, src layout via setuptools, pytest config
    with `pythonpath = ["src"]`, `--strict-markers`, markers `slow` and `octave`),
    `environment.yml` (env `fd`, conda-forge, unpinned; pins come in item 02),
    `src/formdiscovery/__init__.py`, `tests/__init__.py`, `tests/octave/.gitkeep`,
    `tests/fixtures/.gitkeep`, `tools/.gitkeep`; extended `.gitignore` (results dirs,
    `_GtDout.dot`, `_LAYout.dot`, `*.pyc`, `.pytest_cache`, `octave-core`, build dirs).
  - `python -m pytest -q` and `python -m pytest -q -m "not slow"` both exit 5 (no tests), as allowed in Phase 0.
- Note: the base Python has pytest 7.4.4, so `minversion` is set to 7.0 (not 8). The `fd`
  env built in item 02 will have a newer pytest.
- Note: the repo was already a git repo, so the `git init` step in PLAN §3.1 was not needed.
### Blockers
- None.
### Next
- Item 02: create conda env `fd` from `environment.yml` (octave, oct2py, pygraphviz), verify,
  write `tests/conftest.py` with the `octave` session fixture, and pin versions.

## Iteration 2 — 2026-09-28 21:33
### Completed
- Item 02: Octave toolchain installed and wired into pytest.
  - Created conda env `fd` (`/home/al/anaconda3/envs/fd`) from `environment.yml` (first attempt
    failed on a truncated download; the retry succeeded).
  - Exact versions (now pinned in `environment.yml`, verified to resolve with `--dry-run`):
    Octave 10.3.0, oct2py 6.1.1, pygraphviz 2.0.2, graphviz 14.1.2, Python 3.12.14,
    numpy 2.5.3, scipy 1.18.1, networkx 3.7, matplotlib 3.11.2, pytest 9.1.1,
    hypothesis 6.168.3, pip 26.2.1.
  - Checked: `octave --version` gives 10.3.0; an oct2py matrix round-trip (`transpose`) is exact;
    `import pygraphviz` works and builds an AGraph.
  - Gotcha: conda-forge Octave needs `OCTAVE_HOME=<env prefix>` (its activate script sets it).
    Without it `octave-cli` starts but reports `'version' undefined`, and oct2py says
    "does not point to a valid octave". `tests/conftest.py` handles this: `pytest_configure`
    finds Octave (`$OCTAVE_EXECUTABLE` → `octave-cli` next to `sys.executable` → `PATH` →
    `~/{anaconda3,miniconda3,miniforge3}/envs/fd/bin/octave-cli`) and sets
    `OCTAVE_EXECUTABLE`/`OCTAVE_HOME` before oct2py is imported, because importing oct2py
    starts a default session.
  - `tests/conftest.py`: `REPO_ROOT`, `MATLAB_DIR`, `FIXTURES_DIR`, `OCTAVE_TESTS_DIR` constants;
    a session fixture `octave` (Oct2Py with `matlab/formdiscovery1.0` and `tests/octave` on the
    path); `octave`-marked tests are skipped when oct2py or Octave is missing.
  - `tests/test_toolchain.py`: sources present, pygraphviz (importorskip), and octave-marked tests
    for the oct2py round-trip, column-major indexing, and `which('masterrun')`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 1 passed, 3 skipped (exit 0).
    fd python gives 4 passed; `-m octave` gives 2 passed.
- Note: the `fd` env has numpy 2.5 while the base interpreter (which the loop gate uses) has
  numpy 1.26. Package code must work on both. Live parity tests run only under the `fd` python
  (`/home/al/anaconda3/envs/fd/bin/python -m pytest -m octave`).
### Blockers
- None.
### Next
- Item 03: Octave compatibility patches in `matlab/formdiscovery1.0/` + `matlab/PATCHES.md`.

## Iteration 3 — 2026-09-28 21:38
### Completed
- Item 03: Octave compatibility patches in `matlab/formdiscovery1.0/`, documented one by one
  (table + full diff) in `matlab/PATCHES.md`. Each edited line has a `PATCH(octave)` marker.
  CRLF line endings were kept in `dijkstra.m`, `dot_to_graph.m` and `draw_dot.m`.
  - `dijkstra.m:33` `error(nargchk(1,3,nargin))` → `narginchk(1,3)`.
  - `keyboard` → `error('formdiscovery:...', ...)` in `graph_like_rel.m:160`,
    `dataprobwsig.m:239`, `choose_node_split.m:22` and `best_split.m:88` (inside `if 0`), and
    `if debug keyboard; end` → `if debug error(...); end` in `swapobjclust.m:46`, `spr.m:34`
    and `collapsedims.m:47`. Commented-out `keyboard`s are left as they are.
  - `draw_dot.m:58` `my_setdiff` → `mysetdiff`.
  - `dot_to_graph.m`: `textread`+`strvcat` → `fileread` + C-comment regexp + `strsplit`/`strtrim`
    + drop empty lines + `char`; `findstr` → `strfind`; the unused `strread` is commented out;
    `strmatch(...,'exact')` → `find(strcmp(...))`; `range` → `max-min`.
  - **Extra fix needed:** the unpatched `dot_to_graph` crashes on *every* Graphviz 14 layout
    (`node_pos(2): out of bound`), because it reads `pos` with `%d,%d` and current neato writes
    float coordinates. Changed to `%f,%f`, which parses integer coordinates the same way. It was
    checked in two steps (details in PATCHES.md): with only the `%f` fix, results on old-format
    files matched the unpatched file; after the string-function patches, all 6 test layouts gave
    `isequal` results.
  - Smoke test `tests/octave/smoke_patches.m`: `setps; defaultps; structcounts(12, ps)`;
    `makeemptygraph` for all 24 names in `ps.structures` (grid and cylinder are among them and
    give `ncomp=2`); `setrunps` + `scaledata` on `demo_chain_feat` (8×1000, all finite);
    `dijkstra` on a 3-node path. All pass in Octave 10.3.0.
  - Fixture `tests/fixtures/dot_to_graph.mat` (from `tests/octave/fx_dot_to_graph.m`) with input
    layouts in `tests/fixtures/dot_to_graph/`: 4 neato-14 layouts (chain6, ring12, directed
    tree7, chain6 + singleton) and 2 hand-written old-format layouts. Items 31–32 can reuse
    these.
  - `tests/test_patches.py`: static checks (no live `keyboard`/`nargchk`/`my_setdiff`/`textread`/
    `strread`/`findstr`/`strmatch`/`strvcat`/`range` calls; marker counts; every marked file is
    in PATCHES.md; CRLF kept), a fixture sanity test, and octave-marked tests (smoke script;
    regenerating `dot_to_graph.mat` gives an exact match).
  - Gate: base python `python -m pytest -q -m "not slow"` gives 25 passed, 5 skipped;
    fd python `python -m pytest -q` gives 30 passed.
- Notes for later items:
  - `/usr/bin/neato` (system Graphviz 14.1.2) has **no neato layout plugin**; only `dot` works.
    The fd env's `neato` works, but Octave appends the env's `bin` at the end of `PATH`, so
    `draw_dot` would pick up the broken binary. Put `/home/al/anaconda3/envs/fd/bin` first on
    PATH for any display work (items 31–32). Affects the "Graphviz 14.1 (`dot`, `neato`)"
    toolchain claim in TASK.md.
  - `dot_to_graph` only finds node positions in multi-line Graphviz output because `lst_node`
    carries over between lines, and it assumes no label is a substring of another (ring12 breaks
    this: `1` vs `10..12`). Replicated as is; item 31 should pin it (and add it to
    KNOWN_ISSUES.md in item 05).
  - Harmless Octave warnings (vec shadows a builtin, `dijk` vs `dijkstra.m` name, Matlab-style
    `&`/`|` short-circuit) are listed in PATCHES.md and not patched.
### Blockers
- None.
### Next
- Item 04: headless feature-data baseline (`matlab/run_baseline.m`, masterrun grid chain/ring/tree
  × datasets 1–3, fixtures in `tests/fixtures/baseline/feat/`).

## Iteration 4 — 2026-09-28 21:43
### Completed
- Item 04 (partial, still `[ ]`): wrote `matlab/run_baseline.m` (`run_baseline(kind, thisstruct,
  thisdata)`, kind `'feat'` = structures [2,4,6] × datasets 1:3, same loop, `rand('state', rind)`
  seeding and `resultsdemo.mat` contents as `masterrun.m`). Deviations from masterrun, all
  listed in its header: every `ps.show*` is 0; output goes to `tests/fixtures/baseline/<kind>/`
  (runmodel's `results/<struct>out/<data><rind>/` is created under it); `save_default_options('-v7')`
  (Octave otherwise writes its text format); growth history files, which Octave saves without
  an extension, are renamed to `*.mat`; no retry/pause loop around the masterfile save;
  `timings.mat` stores wall-clock and ll per run. Run with
  `cd matlab; octave-cli --eval "run_baseline('feat')"` (fd env's `bin` first on PATH,
  `OCTAVE_HOME` set).
- **The tree runs crash in Octave** (verbatim):
  ```
  error: horizontal dimensions mismatch (1x1 vs 2x1)
  error: called from
      spr>makers at line 87 column 3
      spr at line 24 column 6
      gibbs_clean at line 92 column 5
      structurefit at line 142 column 10
      runmodel>brlencases at line 224 column 6
      runmodel at line 153 column 6
      run_baseline at line 78 column 6
  ```
  Cause: Octave's `union([1 2], [])` is 2×1 (MATLAB: 1×2), and `find_descendants.m:29`
  unions a row with the leaves' `[]`. Filed as new item **03b** (inserted before 04, target
  now 36), as item 04 requires. Per the one-item rule, the source was **not** patched this iteration.
- Probe (scratch copy in `/tmp`, repo sources untouched): with `ds = ds(:)';` added after the
  union, all 9 runs finish (Octave 10.3.0, `ps.speed=54`, total 27 s). Wall-clock / final ll:

  | data \ structure | chain | ring | tree |
  |---|---|---|---|
  | demo_chain_feat | 1.7 s / −8247.2048 | 1.8 s / −8264.2004 | 5.0 s / −8252.8865 |
  | demo_ring_feat  | 2.0 s / −8566.6365 | 1.9 s / −8500.5202 | 4.7 s / −8512.8738 |
  | demo_tree_feat  | 1.9 s / −8764.1656 | 2.5 s / −8722.5890 | 5.3 s / −8707.8137 |

  Each data set's true form wins. The runs are fast enough for a non-slow integration test.
- Observation: `structurefit` saves `growthhistory<tag><speed>` only when a depth improves,
  so a run leaves files only for the stages that improved (e.g. chain × demo_chain_feat only
  wrote `growthhistoryalltie5`; exttie5/notie5/noinit4 found no improvement). MATLAB does the same.
  Item 27 should expect this.
- Partial fixtures from the crashed run were deleted; `tests/fixtures/baseline/` is not committed.
- Gate: `python -m pytest -q -m "not slow"` passes (no Python changes this iteration).
### Blockers
- Item 04 needs item 03b (the `find_descendants` orientation patch) before the tree runs work.
### Next
- Item 03b: patch `find_descendants.m`, audit the other set-op calls, pin with a test. Then
  re-run item 04: `run_baseline('feat')` and commit the fixtures, plus a pytest that loads
  `resultsdemo.mat`/`timings.mat`.

## Iteration 5 — 2026-09-28 21:46
### Completed
- Item 04 (partial, still `[ ]`): committed the chain and ring part of the feature baseline.
  - Ran `run_baseline('feat', [2 4])` (chain, ring × demo_chain/ring/tree_feat, Octave 10.3.0,
    `ps.speed=54`, `rand('state',1)`, 12 s in total). Final ll values are the same as iteration 4's scratch probe, to 10
    significant digits. Wall-clock per run: chain 1.7 / 2.0 / 1.9 s and ring 1.9 / 1.9 / 2.5 s
    (on demo_chain / ring / tree_feat respectively).
  - Fixtures in `tests/fixtures/baseline/feat/`: `resultsdemo.mat` (modellike 4×3, rows 1 and 3
    are zero because those structures were not run), `timings.mat`, and 12 `growthhistory*.mat` files under
    `results/<struct>out/<data>1/`. `.gitignore` ignored every `results/` directory, so I added the negation
    `!tests/fixtures/baseline/**/results/`.
  - `matlab/run_baseline.m`: new optional 4th argument `outdir`, used by the live test. The header now
    documents Octave's harmless `optimset: unrecognized option: 'LargeScale'` warning, which comes
    from `graph_like_conn.m:50` on every call. Octave's fminunc ignores `LargeScale`; relevant for item 19.
  - `tests/test_baseline.py`: pins modellike and timings to the Octave values (rtol 1e-10), checks
    that the true form wins between chain and ring, checks the graph structs (type, objcount=8, finite W) and
    the growth-history keys (`bestgraphlls`, `bestgraph`; `alltie5` is always present). The live test
    `@pytest.mark.octave` reruns chain × demo_chain_feat into a temp dir and matches exactly.
    It passes in the fd env (6 passed).
  - Gate: base python `python -m pytest -q -m "not slow"` gives 30 passed, 6 skipped.
### Blockers
- The tree runs still need item 03b (`find_descendants.m` orientation patch).
- **Loop-script bug:** `loop.py` uses `ITEM_RE = r"^- \[( |x|~)\] (\d+)\."`, which does not match
  `03b.`. The loop never sees item 03b, so it gives item 04 again every iteration, and 04 cannot
  finish without 03b. Fix: change the regex to `(\d+[a-z]?)\.` (and restart the loop), or have a
  human do 03b. I did not edit `loop.py`, because the running process has already compiled the regex.
### Next
- Item 03b, then finish 04: `run_baseline('feat')` for all 9 runs, and extend `tests/test_baseline.py`
  with the tree values (iteration 4's probe: −8252.8865 / −8512.8738 / −8707.8137).

## Iteration 6 — 2026-09-28 21:48
### Completed
- Item 04: marked **`[~]` (blocked)**. Nothing about the blocker changed since iteration 5.
  - Checked again: `find_descendants.m:29` is still unpatched. The smallest repro still fails in
    Octave 10.3.0:
    `d = find_descendants([0 1 1; 0 0 0; 0 0 0]); size(d{1})` → `2 1`, then `[1, d{1}]` →
    `error: horizontal dimensions mismatch (1x1 vs 2x1)`. Every `tree` run crashes the same way
    (full stack trace in iteration 4).
  - What is already done and stays green: chain + ring × datasets 1–3 fixtures in
    `tests/fixtures/baseline/feat/`, pinned by `tests/test_baseline.py`.
  - Why `[~]` and not `[ ]` again: `loop.py`'s `ITEM_RE = r"^- \[( |x|~)\] (\d+)\."` never matches
    `03b.`, so the loop gave item 04 in iterations 4, 5 and 6, and 04 cannot finish without 03b.
    I did not patch `find_descendants.m` here: that is item 03b's work, and the one-item rule
    applies. With 04 marked `[~]` the loop can continue to 05.
  - Gate: `python -m pytest -q -m "not slow"` gives 30 passed, 6 skipped (exit 0). No code changes.
### Blockers
- **Human action needed.** Item 03b is invisible to the loop. Also, `loop.py`'s completion check
  ignores 03b, so the loop could reach "all done" with 03b still pending.
  Fix: in `loop.py` change `ITEM_RE` to `r"^- \[( |x|~)\] (\d+[a-z]?)\."` and restart the loop,
  or do 03b by hand. Afterwards set 04 back to `[ ]`. Finishing it is small: run
  `run_baseline('feat')` for all 9 runs (~30 s), commit the tree growth histories, and add tree to
  `EXPECTED_LL`/`STRUCTS` in `tests/test_baseline.py` (expected ll from iteration 4:
  −8252.8865 / −8512.8738 / −8707.8137).
- Risk for item 05: the relational grid includes structure 3 and other tree/hierarchy forms. If any
  of them reach `spr`/`find_descendants`, they will hit the same crash until 03b is in.
### Next
- The loop will give item 05 (relational baseline + KNOWN_ISSUES.md). Items 03b and 04 still need
  the loop fix described above.

## Iteration 7 — 2026-09-28 21:49
### Completed
- Item 05: marked **`[~]` (blocked on 03b)**. Both parts were done; 1 of the 54 runs cannot be
  produced until 03b is in.
  - `matlab/run_baseline.m`: new kind `'rel'` (`ps.reloutsideinit = 'overd'`, structures
    `[1,9,10:13,3,14:24]` × datasets 4–6, output in `tests/fixtures/baseline/rel/`). A run that crashes
    is now caught: `timings.mat` gets `ll = NaN` and the error message with its stack in a new
    `error` field, the run is left out of `resultsdemo.mat`, and the loop goes on.
    masterrun would stop at the first crash. The live test `test_baseline.py` still reproduces the feature chain run
    exactly with the changed script.
  - Ran `run_baseline('rel')` twice in Octave 10.3.0 (about 2.5 min each). The ll values were identical both
    times. 53/54 runs finish. **The crash** (verbatim, same bug as item 04):
    ```
    demo_hierarchy_rel_bin undirhierarchy: CRASHED after 8.0 s: horizontal dimensions mismatch (1x1 vs 2x1)
        spr>makers at line 87
        spr at line 24
        gibbs_clean at line 92
        structurefit at line 142
        runmodel>brlencases at line 204
        runmodel at line 149
    ```
    The other hierarchy runs (including all 4 on demo_ring_rel_bin and undirhierarchynoself on
    demo_hierarchy_rel_bin) finish. Whether the crash happens depends on the data.
  - Wall-clock time per run: 0.4–1.1 s on demo_ring_rel_bin and 0.5–1.1 s on demo_order_rel_freq.
    On demo_hierarchy_rel_bin it is 3.5–12.8 s (dirhierarchy 12.8 s, order 9.3 s).
    The full per-run table is in `timings.mat`. Best forms (Octave): demo_ring_rel_bin →
    dirringnoself (−16.5714), demo_order_rel_freq → ordernoself (−3663.6163),
    **demo_hierarchy_rel_bin → undirringnoself (−62.2863)**. No hierarchy form wins there:
    dirhierarchynoself gets −63.3328, and undirhierarchy crashed. This can be re-checked after 03b.
    It may be an Octave `fminunc` effect (KI-10) or it may be the real behaviour at `ps.speed=54`, so it is pinned and not asserted as the paper's result.
  - Every relational run saves exactly one history, `growthhistorynoinit5.mat` (54 files, 544 KB
    in total). The crashed run saved its history before crashing.
  - `tests/test_baseline_rel.py`: pins all 53 ll values (rtol 1e-10) in `resultsdemo.mat` and
    `timings.mat`, the crash record, `reloutsideinit`, the graph types, the growth-history files and the best form per data set. The
    live `@pytest.mark.octave` test reruns dirringnoself × demo_ring_rel_bin.
  - `KNOWN_ISSUES.md` (repo root): KI-1 to KI-6 are the six PLAN §3.5 bugs, each checked in the code,
    with the reachable/unreachable path, a decision and a pin. Decisions: best_split speed 1/2 →
    raise; combinegraphs illegal precedence → replicate the empty-list path and raise on non-empty;
    `part` without `i` → dropped (write-only); stale `pind` → replicate and assert `pind == 1`;
    zinit_rel → not ported; `pred2path` → single output only. Also KI-7/8 for dot_to_graph
    (line carry-over, label substrings, from iteration 3), KI-9 for the Octave `union` orientation, KI-10 for
    `LargeScale`, and KI-11 for the duplicate `ps.fixedall`. KI-12 (`mylogdet` on non-PD input) is deferred to item 07.
    Future pin tests are named, with the item that has to add them.
  - `tests/test_known_issues.py`: checks that each quirk is still at its cited file:line, that every KI entry
    has a decision and a pin, that `zinit_rel` is unreferenced, and that every `dijkstra` call has one output.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 52 passed, 7 skipped. fd env:
    baseline, baseline_rel and known_issues give 29 passed, including the live Octave tests.
### Blockers
- Item 03b is still invisible to `loop.py` (`ITEM_RE` does not match `03b.`; see iteration 6).
  Items 04 and 05 are both waiting for it. I added to 03b's description that it must regenerate both baselines
  afterwards.
### Next
- Item 06 (conventions + MATLAB-semantics helpers). A human still needs to fix `loop.py`'s `ITEM_RE`
  or do 03b by hand. After that, rerun `run_baseline('feat')` and `run_baseline('rel')` and update
  `EXPECTED_LL`/`CRASHED` in the two baseline tests.

## Iteration 8 — 2026-09-28 21:58
### Completed
- Item 06 **solved** (`[x]`).
  - `src/formdiscovery/matlab_compat.py`: `find_F` (column-major; linear or `(i, j, v)`),
    `hist_centres` (MATLAB `hist(x, centres)`: open end bins, edge values go to the upper bin,
    length-1 centres = MATLAB's nbins branch), `unique_matlab`/`unique_rows` (`[b,i,j]`,
    `occurrence='first'|'last'`), sorted `setdiff/intersect/union` (always 1-D),
    order-preserving `mysetdiff` (keeps duplicates, works on 0-based ids), `chol_upper`
    (MATLAB `[U,p]`, including the partial factor and the 1-based `p` on failure),
    `sparse_accum` (duplicates summed), `median_matlab` (empty/NaN → NaN), `stable_argsort`
    (stable in both directions, NaN last ascending / first descending), `max_first`.
    Each docstring cites the MATLAB call sites.
  - `src/formdiscovery/io.py`: `load_dataset(name, with_names=False)` (float ndarray, or a
    `{'R','type','nobj','names'}` dict for the 7 relational sets), `load_mat`,
    `load_fixture(name, simplify=True)`, `to0`/`to1` (they also handle lists of index vectors,
    i.e. cell arrays). `FormDiscoveryError` is in `formdiscovery/__init__.py`.
  - `src/formdiscovery/CONVENTIONS.md`: indices, dtypes, the MATLAB→helper table, tolerances,
    fixture-script convention.
  - `tests/octave/fx_matlab_compat.m` → `tests/fixtures/matlab_compat.mat` (Octave 10.3.0).
    It includes the real call-site cases: `hist(z, 1:n)`, `hist(z, unique(z))`, and
    `unique(~isinf(judges)', 'rows')`, which gives 38 chunks.
  - `tools/gen_fixtures.py`: runs every `tests/octave/fx_<name>.m` as `fx_<name>(outfile)` in a
    fresh `octave-cli` and writes `tests/fixtures/<name>.mat`. Supports `--list`, `--outdir`, and
    names as arguments. Other `.m` files in `tests/octave` are helpers and are not run. Both
    fixtures were regenerated this iteration. `dot_to_graph.mat`'s contents are unchanged
    (only the file header differs).
  - Tests: `tests/test_matlab_compat.py` (fixture parity for every helper, the MATLAB-only
    cases, and a live `octave` test that regenerates the fixture and compares it exactly), and
    `tests/test_io.py` (all 20 data sets: shapes, types, names, the index round trip).
  - **Octave ≠ MATLAB findings**, filed in `KNOWN_ISSUES.md`, and `test_known_issues.py` now
    expects KI-1..14:
    - KI-13: Octave's `hist` puts values on a bin edge in the lower bin; MATLAB puts them in the
      upper bin. For `hist(x, n)` on constant `x` with even `n`, Octave also centres the bins
      differently. Neither can happen at the current call sites, which count integer labels.
      The port follows MATLAB.
    - KI-14: `unique`'s `i` is the first occurrence in Octave and MATLAB R2013a+, and the last
      occurrence in MATLAB 7. The only caller (`scaledata.m:51`) does not use `i`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 95 passed, 8 skipped. The fd env
    gives 103 passed, including the live Octave tests.
  - Note: `RalphLoops/loop0001/loop.py` has an uncommitted edit I did not make.
    `ITEM_RE` now accepts `\d+[a-z]?`, so item 03b is visible to the loop again. It is the first
    `[ ]` item.
### Blockers
- None for item 06. Items 04 and 05 are still `[~]` waiting for 03b. The loop can now reach
  03b, provided it was restarted with the patched regex.
### Next
- Item 03b (first `[ ]` item): patch `find_descendants.m`, audit the set ops, rerun
  `run_baseline('feat')` / `run_baseline('rel')`, then set 04/05 back to `[ ]` and finish them.
  After that, item 07 (L0-a utilities, using `matlab_compat.chol_upper` for
  `logdet`/`mylogdet`, and deciding KI-12).

## Iteration 9 — 2026-09-28 22:30 (done by hand in the parent session, not by loop.py)
### Completed
- Item 03b **solved** (`[x]`), and with it the remaining parts of items 04 and 05 (both `[x]`).
  - `matlab/formdiscovery1.0/find_descendants.m:29`: PATCH(octave) #16, `ds = ds(:)';` after the
    `union`. Repro `find_descendants([0 1 1; 0 0 0; 0 0 0])` now gives a 1×2 row and
    `[1, d{1}]` works. `matlab/PATCHES.md` has the table row, the diff hunk and a new section
    "Set-operation orientation audit".
  - Audit of the other 36 `union/intersect/setdiff/unique` call sites (14 files) against
    Octave 10.3.0 measurements: `union(row, [])` → column, `intersect(row, [])` → 0×0,
    `setdiff(1×0, row)`/`unique(1×0)` → 0×1, everything else as MATLAB. `for` over a 0×1 runs
    once and over 0×3 three times in **both** Octave and MATLAB, so loop semantics do not
    differ. Only `find_descendants.m:29` receives a 0×0 operand whose result is later
    concatenated horizontally (`spr.m:87`). `combinegraphs.m:67` gets a column in both
    languages and only uses the result shape-agnostically. No other patch needed.
  - Pins: `tests/test_patches.py::test_find_descendants_patch_present` (static) and
    `::test_find_descendants_returns_rows` (live Octave: the repro, the `spr.m:87` expression,
    and a 5-node tree). `PATCHED` now includes `find_descendants.m`. KI-9 in `KNOWN_ISSUES.md`
    updated to "fixed, patch 16".
  - Baselines regenerated from scratch with the patch (`rm -rf tests/fixtures/baseline/{feat,rel}`,
    then `run_baseline('feat'); run_baseline('rel')`, 2 min 45 s in total):
    - feat: all 9 runs finish. Tree: −8252.886501459561 / −8512.873764658598 /
      −8707.813669003906 on demo_chain/ring/tree_feat (5.0 / 4.6 / 5.2 s). Chain and ring values
      unchanged to all digits. Each demo set is won by its true form.
      `tests/test_baseline.py`: `STRUCTS` includes tree, `modellike` is 6×3,
      `test_true_form_wins` checks the winner per data set.
    - rel: 54/54 finish, none crashed. `undirhierarchy × demo_hierarchy_rel_bin` = −71.81545785312964
      (8.5 s). All 53 other values unchanged (rtol 1e-10). Best forms unchanged: dirringnoself,
      **undirringnoself** (the hierarchy data is still not won by a hierarchy; the formerly crashing
      undirhierarchy run scores −71.8, well below undirringnoself −62.3), ordernoself.
      `tests/test_baseline_rel.py`: `CRASHED = set()`, new entry added, crash-branch assertions generalised.
  - Gate: base python 97 passed, 9 skipped; fd env 106 passed including all live Octave tests.
- Also this iteration: committed item 06 (iteration 8) by hand because loop.py had been stopped,
  and fixed `loop.py` (`ITEM_RE` accepts `03b`-style items; log output flushed).
### Blockers
- None. The loop can be restarted; the next item is 07.
### Next
- Item 07 (L0-a utilities).

## Iteration 10 — 2026-09-29 12:14
### Completed
- Item 07 **solved** (`[x]`).
  - `src/formdiscovery/util.py`: `vec` (column-major, 1-D), `inv_triu` (triangular solve),
    `inv_posdef`, `logdet`, `mylogdet`, `sumlogs`, `meanlogs`, `mysetdiff` (re-exported from
    `matlab_compat`), `subv2ind` (0-based in/out, keeps the all-twos branch that takes `d` from
    `subv`, no bounds check, empty `siz` → `[0]`), `trans2orig`, `matrixpartition`,
    `triplepartition` (copies, MATLAB output order `A1, A2, B1, B2, D`), and a small
    `matlab_reduce` helper for MATLAB's `sum`/`mean` dimension choice.
    `src/formdiscovery/weights.py`: `weightprior`. Each docstring cites the file and lines.
  - **KI-12 decided: replicate.** `mylogdet` on non-PD input returns `log(det(A))` of the full
    matrix: a Python `complex` when det < 0, a `float` when det > 0, and `-inf` when det = 0.
    That way the `~isreal(logI)` fallback at `graph_like_conn.m:90` ports as
    `isinstance(logI, complex)`. `logdet`/`inv_posdef` raise `FormDiscoveryError` where
    MATLAB's `chol` errors. Written up in `KNOWN_ISSUES.md`. `test_known_issues.py` no longer
    skips KI-12, so it now needs the Decision and Pin lines. `CONVENTIONS.md` has two new
    rows (`matlab_reduce`, `~isreal`).
  - Fixture `tests/octave/fx_util.m` → `tests/fixtures/util.mat` (Octave 10.3.0, generated
    this iteration). Contents: seeded SPD matrices of size 1/3/8/20; one SPD whose lower
    triangle was overwritten with garbage (checks that only the upper triangle is read); the
    inverse of an SPD, i.e. the `inv(-H)` kind of input; `hilb(6)`; five non-PD cases (det < 0,
    det > 0 indefinite, singular, non-symmetric, negative definite); log-space vectors
    including ±1000-scale values, `-Inf` entries, all `-Inf` (→ NaN), and a matrix
    (per-column results); `subv2ind` in both branches plus the empty cases; partitions
    including the empty-block edge cases; `weightprior` including empty `w`.
  - `tests/test_util.py`: 13 fixture tests (rtol 1e-10 / atol 1e-12, exact for indices and
    blocks) and 2 live `octave` tests (the fixture regenerates identically; random-input parity
    for `inv_posdef`, `logdet`, complex `mylogdet`, `sumlogs`, `meanlogs`, `weightprior`,
    `subv2ind`).
  - Gate: base python `python -m pytest -q -m "not slow"` gives 110 passed, 11 skipped. fd env
    gives 121 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 08 (L0-b: `stirling2`, `hessiangrad`, `dijkstra`, `get_edgemap`, `find_descendants`,
  `expand_graph`, `makehyps`, `bbloglike`, `bblikesumhyps`, `dirmultloglike`). `makehyps` can use
  `util.trans2orig`.

## Iteration 11 — 2026-09-29 12:18
### Completed
- Item 08 **solved** (`[x]`).
  - `util.py`: `stirling2`, which uses the same float recursion as MATLAB. `stirling2(40,40)` matches Octave
    **bit for bit**, including the entries above 2^53. Also `dijkstra` (distance output only, per KI-6; `paths=True` →
    `NotImplementedError`). `dijkstra` keeps the upper/lower-triangular "acyclic" scan (negative
    lengths allowed), NaN = zero-length arc, MATLAB `min` first-tie/NaN-skipping, the early stop
    when `len(t) < n`, and the four `error` branches → `FormDiscoveryError`.
  - New `graph.py`: `expand_graph`, `get_edgemap` (column-major; `sym=1` numbers the strict
    lower triangle and symmetrises), and `find_descendants` (the MATLAB queue order, sorted
    0-based rows, patch 16 semantics).
  - New `likelihood_feat.py`: `hessiangrad`. Rows come from `length(dY)` as in MATLAB, so a
    matrix-shaped gradient errors in both languages; this is pinned. New `likelihood_rel.py`:
    `makehyps`, `bbloglike` (`sum(...,1)`: a 1-row matrix is not reduced), `bblikesumhyps`,
    `dirmultloglike` (an all-zero row gives NaN, as in MATLAB).
  - Deviation **KI-15** (find_descendants loops forever on a cycle above a queued node): the port
    raises instead, once the queue makes a full pass with no progress, and always returns `n`
    entries. No caller can reach it. Added to `KNOWN_ISSUES.md`; `test_known_issues.py`
    now expects KI-1..15. KI-6 pin updated (it now exists).
  - `CONVENTIONS.md`: edge maps are an exception to 0-based indexing. They keep MATLAB's edge
    numbers 1..k with 0 = no edge, because `kron` in `combinegraphs` and `find(emap)` need 0 as the
    empty value. Callers subtract 1 when indexing weights.
  - Fixture `tests/octave/fx_l0b.m` (+ helper `l0b_hessfun.m`) → `tests/fixtures/l0b.mat`,
    generated this iteration with Octave 10.3.0. `dijkstra` and `get_edgemap` (both modes) run on
    212 matrices: every demo `adj`/`W`/`graph.adjcluster`, the `adjcluster`/`adjclustersym`/
    `Wclustersym` of all 63 final baseline graphs (feat + rel), and six constructed cases
    (triangular with negative lengths, NaN arcs, disconnected, 1×1). The fixture also covers
    `s`/`t` subsets and the error branches. `find_descendants` runs on 72 inputs: the 03b repro,
    a tree, a diamond DAG, a lower-triangular DAG, all leaves, every tree/chain/order/hierarchy
    baseline component `adj` and `adjcluster`, and a 25-node random DAG. `expand_graph` covers
    empty clusters. `makehyps` uses the `graph_like_rel` grids. `bblikesumhyps` covers ns=0,
    all-zero and empty input.
  - `tests/test_l0b.py`: 15 fixture tests (exact for stirling2, maps, descendants and
    adjacency; rtol 1e-10 otherwise; 1e-9 for the finite-difference Hessian) and 2 live
    `octave` tests: the fixture regenerates identically, and fresh random dijkstra, edgemap,
    find_descendants, makehyps, bblikesumhyps, dirmultloglike and stirling2 match.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 126 passed, 13 skipped. The fd env
    gives 139 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 09 (L1 params: `setps, defaultps, setrunps, gridpriors, structcounts, graph_prior`).
  `structcounts` can use `util.stirling2`.

## Iteration 12 — 2026-09-29 12:25
### Completed
- Item 09 **solved** (`[x]`).
  - New `src/formdiscovery/params.py`: a `Params` dataclass mirroring `ps` with the MATLAB field
    names (fields not set yet are `None`, as MATLAB's `isfield` would say) and a nested `RunPs`.
    `copy()`/`replace()` give deep copies, since MATLAB passes `ps` by value. Also
    `Params.default()` (`defaultps(setps())`), the `STRUCTURES`/`DATASETS` tuples, and the
    functions `setps` (the `dlocs` come from `io.DATA_DIR`, not `pwd`), `defaultps`,
    `setrunps` (0-based `dind`; relational data sets `speed=5`, `init='none'`; a square array is
    `sim` unless `featforce`), `gridpriors` (grid/cylinder, column-major `occind`),
    `structcounts` (`T` plus the 10 `logps`; `factorial` is correctly rounded, which matches
    Octave's `round(gamma(n+1))` for n ≤ 40, while `cumprod` would be off by one ulp at
    28-30 and 34-39), `prior_index` and `graph_prior` (accepts a dict, an object or a scipy
    `mat_struct`; a count ≤ 0 or past the end raises instead of wrapping around).
  - Deviation **KI-16**: for `structcounts(1)`, `counts(3,1:2)=[0,0]` grows `counts` to 2
    columns. MATLAB 7 would raise a dimension error. Octave broadcasts and returns wrong priors,
    and the tree prior comes out complex. The port raises for `nobjects < 2`, which no data set
    reaches (the smallest has 8 objects). `test_known_issues.py` now expects KI-1..16.
  - Fixture `tests/octave/fx_params.m` → `tests/fixtures/params.mat` (Octave 10.3.0, generated
    this iteration). Contents:
    - `setps` and `defaultps` (the `dlocs` are saved relative to `pwd`);
    - `setrunps` on all 20 data sets, plus the featforce, rectangular and square cases;
    - `structcounts` for n ∈ {1, 2, 3, 8, 12, 14, 28, 33, 35, 40};
    - `gridpriors` directly with theta 0.3, n ∈ {1, 2, 5, 9}, plus the bad-type error;
    - `graph_prior` for all 24 structure names plus the 4 domtree names, with every cluster count
      up to 12 (up to 144 for grid and cylinder) and trees that have illegal nodes, plus the
      unknown-type error;
    - `graph_prior` on the 63 final baseline graphs (feat and rel), each with
      `structcounts(objcount)`.
  - `tests/test_params.py` has 20 fixture tests and 2 live `octave` tests: one checks that the
    fixture regenerates identically, the other runs structcounts and graph_prior with random
    theta through oct2py. `T` matches exactly and the priors to rtol 1e-10.
  - `CONVENTIONS.md`: the `Params` conventions, including value semantics, the `logps`
    indexing and the 0-based `dind`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 147 passed, 15 skipped. The fd
    env gives 162 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 10 (L1 preprocess: `simpleshiftscale`, `makesimlike`, `scaledata` (+`makechunks`)).
  It can use `params.setrunps` and `matlab_compat.unique_rows` (for the `judges` chunk order).

## Iteration 13 — 2026-09-29 12:32
### Completed
- Item 10 **solved** (`[x]`).
  - New `src/formdiscovery/preprocess.py`: `simpleshiftscale`, `makesimlike`, `makechunks`
    and `scaledata`, each with its source lines in the docstring. `scaledata` returns
    `(data, ps)` with `ps` a copy. Relational data comes back untouched and `missingdata`
    stays unset. The unused `dmean`/`stdev` are dropped. The chunks follow
    `matlab_compat.unique_rows` on `~isinf(data)'`, so their order is lexicographic.
    `featind`/`objind` are 0-based int arrays, and every chunk field is a list with one entry
    per chunk (a new bullet in `CONVENTIONS.md` covers this). `makesimlike` keeps the
    per-pair quadratic loop, the zero-filled `kmins`/`fmins` (`fmins == 0 → inf`, first
    argmin), the unused `lb`, and the choice of the largest chunk with the first tie winning.
  - Two MATLAB error paths, found by the live random test, now raise `FormDiscoveryError`,
    and a test pins that Octave errors too:
    - A feature missing for every object gives an empty chunk. In Octave `maxs(ch) = max([])`
      fails with "nonconformant".
    - `makesimlike` with no negative discriminant anywhere, e.g. every chunk has one feature,
      where `b^2 − 4ac` is exactly 0. Octave fails with "'fmins' undefined" at l.48.
    
    No data set reaches either path: judges has at least 6 observed objects per feature, and
    some of its chunks have more than one feature. Both languages error, so neither is a
    deviation and no KI was added.
  - Fixture `tests/octave/fx_preprocess.m` → `tests/fixtures/preprocess.mat` (Octave 10.3.0,
    generated this iteration). It runs `scaledata` in 44 configurations:
    - all 20 data sets with the defaults;
    - `makesimlike` and `none` on the 10 feature sets (judges included: 38 chunks);
    - `simtransform='center'` on colors, faces and cities;
    - colors with `featforce`.
    
    It also has constructed inputs:
    - identical rows, for the `ub == inf` branch;
    - a constant row, where delta = 0 exactly;
    - direct random calls;
    - a missing-data case with three 2-feature chunks, to check the `max(csize)` first tie;
    - a 4-chunk case where the largest chunks tie at positions 3 and 4 and one object is seen
      in only one chunk.
  - `tests/test_preprocess.py` has 55 non-live tests. The output data and `SS`/`chunkSS`
    match to rtol 1e-10. `featind`, `objind`, `chunksize`, `chunknum` and `missingdata` match
    exactly, and the test also checks which fields exist. There are extra checks on the judges
    chunk order and on not mutating inputs. 3 live `octave` tests: the fixture regenerates
    identically; random feature data with and without missing entries, under both transforms,
    plus a centred similarity matrix; the two error paths.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 202 passed, 18 skipped. The fd
    env gives 220 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 11 (L2-a1: `Graph`/`Component` dataclasses, `combinegraphs`, `makeemptygraph`,
  `tests/helpers.py::graph_equal`).

## Iteration 14 — 2026-09-29 12:37
### Completed
- Item 11 **solved** (`[x]`).
  - `src/formdiscovery/graph.py`: the `Graph` and `Component` dataclasses, with the MATLAB field
    names (21 graph fields, 14 component fields; unset = `None`) and `copy()`/`replace()` for
    value semantics. Also `combinegraphs` (`combinegraphs.m:14-131`; the options are keywords
    `origgraph`, `compind` (0-based), `imap` (0-based), `zonly`) and `makeemptygraph`.
    `expand_graph` was already ported in item 08.
  - Replicated quirks: `Wclustersym` comes from the product `W` before the copy from
    `origgraph`; the leaf edges go to object columns `0..nobj-1`, not to `obsind`; the median
    fallback is `1` for a 1×1 `oldW` and NaN when it has no positive entry; `globinds` is `N×N`
    for one component (`zeros(compsizes)` with a scalar).
  - KI-2 is now pinned. With a non-empty component `illegal` in a product graph, Python raises
    `NotImplementedError`. The fixture records what Octave does: a first-component list is
    dropped silently, and a second-component one fails with `illind(0): subscripts must be ...`.
  - `io.py`: `graph_from_mat` / `component_from_mat` / `graph_to_mat`. They accept loadmat
    dicts, scipy `mat_struct` and oct2py structs. `CONVENTIONS.md` now says:
    - `graph.z` uses -1 for a missing object (MATLAB `z < 0` → -1, else `z - 1`).
    - `globinds` has -1 where MATLAB has an unused 0.
    - `compinds` is always `N × ncomp`.
    - `adj`/`adjsym` are bool.
  - `tests/helpers.py`: `graph_diff` (describes the first differing field, component fields
    included, with the first differing entry in column-major order), `graph_equal` and
    `assert_graph_equal`. Structure is compared exactly; `W*`, `leaflengths` and `sigma` to
    rtol 1e-10.
  - Fixture `tests/octave/fx_graph.m` → `tests/fixtures/graph.mat` (Octave 10.3.0, generated
    this iteration). Contents:
    - `makeemptygraph` for the 24 `ps.structures` names (grid and cylinder included) plus the 4
      extra domtree names, with 1 and 5 objects, and the unknown-name error.
    - `combinegraphs` with `zonly` 0 and 1 on all 126 graphs of the 77 baseline growth histories.
    - 36 product cases.
    - 135 `combinegraphs` calls captured from seeded `split_node` sequences.
    - The two KI-2 cases.
  - **Deviation from the item text**: the baseline growth histories contain no product graphs.
    The baseline ran only chain/ring/tree and the relational structures, and `runmodel`'s
    grid/cylinder branches were never run. The product fixtures are therefore built two ways:
    - **From baseline components**: for each feature demo, the final chain component of
      `chainout/<d>` and the final ring component of `ringout/<d>` form a cylinder
      (ring × chain) and a grid (chain × chain). A variant marks two objects missing. For
      `zonly = 1` the input is the combined graph with one object moved to another cluster in
      component 2. Each case runs with `prodtied` 0 and 1.
    - **From split sequences**: 6 seeded `split_node` steps from `makeemptygraph`
      (grid, cylinder, chain, ring, tree) and from the 6 baseline products, with `prodtied` 0
      and 1. Before each split, `Wcluster` is given random weights, so the `origgraph` copy
      path moves distinct values; it changes `Wcluster` in at least 30 calls, which the test
      asserts.

    A spy `combinegraphs.m` records the real `origgraph`, `compind` and `imap` inputs. It is
    written to a temp dir that shadows the original, which is copied and renamed to
    `combinegraphs_orig`. The sources are not modified. `fx_graph(outfile, seedoffset)` takes
    a seed offset for the live test.
  - `tests/test_graph.py` has 69 fixture tests and 2 live `octave` tests. The live tests check
    that the fixture regenerates identically, and they rerun the split sequences with fresh
    seeds (`seedoffset = 7919`), comparing every captured call.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 271 passed, 20 skipped. The fd
    env gives 291 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 12 (L2-a2: `add_element`, `empty_graph`, `split_node`). The spy in `fx_graph.m`
  (`make_spy`) can be reused to capture `split_node` inputs. Split sequences must use
  `graph_from_mat` and `graph_diff`. `empty_graph` produces `z = -1`, which `combinegraphs`
  already handles.

## Iteration 15 — 2026-09-29 12:45
### Completed
- Item 12 **solved** (`[x]`).
  - `src/formdiscovery/graph.py` gains four functions, each with its source lines in the
    docstring:
    - `add_element` (`add_element.m`).
    - `empty_graph` (`empty_graph.m`).
    - `split_production`: the pind → production-name table of `split_node.m:9-57`. It
      returns `None` where MATLAB returns `-inf`.
    - `split_node` (`split_node.m`). It returns `(graph, c1, c2)`, or `(None, None, None)`
      when the production does not apply. `disp(structname)` is dropped.
    
    Indices are 0-based. `pind` stays a production number (1-3). A negative `compind` keeps
    MATLAB's "high-level split" meaning. A new `CONVENTIONS.md` bullet covers both.
  - Replicated quirks:
    - the marker/stable-sort weight bookkeeping;
    - `oldps`/`oldchild` are computed *after* the row/column copy;
    - `treever2`'s `find(origadj(cpar,:))`;
    - `empty_graph` removes `adj`/`W` rows by object index.
  - New **KI-17** (replicate) in `split_node.m:66-149`. The old edges are marked 1..nold,
    then the old weights go to the first `nold` positions of a sort of those markers.
    `connected` and `domtreeflat` splits duplicate a marker, so later weights shift and raw
    marker values (small integers) end up as weights. `treever2` deletes a marker, so the
    weights shift by one and the first new edge gets the last old weight instead of the
    median. Octave output confirms this: 14 connected and 23 domtreeflat splits in the
    fixture have stray integer weights. The relational baselines reach it.
    `test_known_issues.py` now expects KI-1..17 and pins `split_node.m:70,148`.
  - Fixture `tests/octave/fx_split.m` → `tests/fixtures/split.mat` (Octave 10.3.0,
    generated this iteration, ~20 s). It has two parts:
    - **Seeded sequences (`sq_*`)**: 8 steps from `makeemptygraph(12 objects)` for the 26
      single-component names, plus grid and cylinder with prodtied 0 and 1. Each step:
      - component W and the graph `Wcluster` get random weights;
      - a random production, node and partition are chosen and `split_node` is called;
      - then `empty_graph` and two `add_element` calls, as in `best_split.m:26-32`;
      - then the `compind = -1` variants of `empty_graph` and `add_element`.
      
      This gives 240 split_node, 442 empty_graph and 663 add_element calls.
    - **Spied baseline runs (`bl_*`)**: spies shadow the three functions while `runmodel`
      re-runs chain/ring/tree × `demo_chain_feat` and the 18 relational structures ×
      `demo_ring_rel_bin`, with the settings and seed of `run_baseline.m`. The calls are
      capped per run. `run_baseline` itself cannot be used, because its `addpath(srcdir)`
      moves the sources ahead of the spies (the first attempt captured nothing). Each
      run's final score equals the committed baseline `modellike`, which is tested.
  - `tests/test_split.py` has 45 fixture tests and 2 live `octave` tests (the fixture
    regenerates identically; fresh sequences with `seedoffset = 7919`). Every call matches
    exactly, with weights to rtol 1e-10, and so do `c1`/`c2` and the -inf cases. The tests
    also check:
    - coverage of every production: partition, connected, chain, ring (including the
      first-split 2-cycle), hierarchy pind 1-3 (including rootchain, domtreeflat and both
      -inf cases), and tree pind 1-2 (including treever2 and its -inf case);
    - the KI-17 stray weights;
    - the unknown-production error;
    - that inputs are not mutated.
  - Finding: `ordernoself` appears in `split_node`'s pind-2 list, but its `prodcount` is 1,
    so that branch is unreachable. This is noted in the test.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 316 passed, 22 skipped. The fd
    env gives 338 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 13 (L2-a3: `simplify_graph (+redundantinds)`, `subtreeattach`). The spy pattern in
  `fx_split.m` (`make_spies` + `spied_run`, which calls `runmodel` directly) can capture
  `simplify_graph` inputs from real runs.

## Iteration 16 — 2026-09-29 12:54
### Completed
- Item 13 **solved** (`[x]`).
  - `src/formdiscovery/graph.py` gains three functions, each with its source lines in the
    docstring:
    - `simplify_graph` (`simplify_graph.m:1-60`).
    - `redundantinds` (`simplify_graph.m:62-148`). It is a module-level function, so tests
      can wrap it to see which cleaning case fired.
    - `subtreeattach` (`subtreeattach.m`), with `objflag` as a keyword. `j` is a 0-based node
      when `objflag` is 0 and a 0-based object when it is 1.
  - Replicated quirks:
    - every component is recombined against the *input* graph as `origgraph`, even after an
      earlier component changed;
    - case 2 joins the neighbours with weight `1/sum(1./w)` (`inf` if no positive weight),
      and a 2-cycle or self-loop just drops the node;
    - the tree case 3 ignores `runps.type`;
    - `subtreeattach` leaves `edgecount`/`edgecountsym` stale and builds `imap` from the
      old `adj` with the `[..., 1, 1, 1]` padding;
    - a parentless `j` with `objflag` 0 returns before the type check.
  - Error paths that MATLAB/Octave also error on now raise `FormDiscoveryError`:
    - `subtreeattach` on a type missing from its list (`dirdomtreenoself`, which
      `makeemptygraph` accepts): 'unexpected structure'. The live fresh-seed run hits this
      in Octave, and the test pins the same error message.
    - a `j` with several parents (nonconformant assignment in MATLAB).
    - the tree case 3 with fewer than two children.

    No new KI.
  - Fixture `tests/octave/fx_simplify.m` → `tests/fixtures/simplify.mat` (Octave 10.3.0,
    generated this iteration, ~56 s). It has three parts:
    - **gh**: every `bestgraph` of the 73 baseline growth histories, simplified with
      cleanstrong 0 and 1 (252 records).
    - **sq/st** (seeded sequences): 7 `split_node` steps for the 26 single-component names
      and grid/cylinder with prodtied 0/1. After steps 3 and 7 the graph is simplified raw,
      after moving one node's members to another legal node, and after emptying two nodes
      into a third. The configs are cs0/feat, cs1/feat and cs0/rel, plus fixedall and
      fixedinternal for trees (513 records). Then come tree and hierarchy-family regrafts:
      nodes onto edges/nodes chosen as `spr>makers` would, objects, and the parentless
      no-op. Each is followed by simplify with cs 0 and 1 (94 records).
    - **bl** (spied runs): spies on `simplify_graph`/`subtreeattach` during chain,
      ring, tree×2 feature runs and dirhierarchy..undirhierarchynoself × `demo_hierarchy_rel_bin`
      (142 simplify, 48 subtreeattach calls). Each run's final score equals the committed
      baseline, which is tested.
  - `tests/test_simplify.py` has 41 fixture tests and 3 live `octave` tests. The fixture
    tests check:
    - every call matches exactly, with weights to rtol 1e-10;
    - coverage of redundantinds cases 1-3 for trees and for other types, and of case 2 on
      trees with cleanstrong 0 and 1;
    - regrafts of subtrees and objects, onto tree edges and hierarchy nodes, including
      no-ops;
    - the tree root is removed only with cleanstrong;
    - rel and fixed* disable case 3;
    - the error path;
    - inputs are not mutated.

    The live tests: the fixture regenerates identically; fresh sequences with
    `seedoffset = 7919`; the 'unexpected structure' error in Octave. A mutation check
    confirmed that the tests catch each of these deliberate breaks: the case-2 weight
    formula, the objflag leaf weight, the tree edge weight, the `origgraph` choice and the
    case-3 merge direction.
  - `CONVENTIONS.md`: a bullet on keyword options, the meaning of `j` in `subtreeattach`,
    and subfunctions exposed at module level.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 357 passed, 25 skipped. The
    fd env gives 382 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 14 (L2-b1: `filloutrelgraph`, `makelcfreq`, `relgraphinit` (+subfunctions),
  `reordermissing`). The spy pattern in `fx_simplify.m` also works for these. Note that
  `subtreeattach`'s `imap` padding matters only for product graphs, and it never receives
  one, so that padding cannot be tested.

## Iteration 17 — 2026-09-29 13:10
### Completed
- Item 14 **solved** (`[x]`).
  - `src/formdiscovery/graph.py` gains these functions, each with its source lines in the
    docstring:
    - `filloutrelgraph` (`filloutrelgraph.m`).
    - `makelcfreq` (`makelcfreq.m`).
    - `relgraphinit` (`relgraphinit.m:1-49`), with the subfunctions `_chooseinithead`,
      `_growgraph` and `_finishgraph` (l.52-141).
    - `reordermissing` (`reordermissing.m`).

    `z` labels are 0-based and contiguous, and `obsind`/`missind` are 0-based. A
    CONVENTIONS.md bullet covers this, plus the 1-D `Wvec` and the fact that
    `filloutrelgraph` returns a float `adjcluster` (MATLAB's `A | A'` gives a logical one).
  - Replicated behaviour:
    - lcprop ties go to the first entry in column-major order, and the head side wins only
      when it is strictly larger. With an all-zero relation, a chain therefore grows
      tail-first as 1→2→…→n.
    - A hierarchy keeps one head, and each new head is also added to the tail list.
    - For `undir*` names the relation is symmetrised; the diagonal of `lc` is zeroed.
    - Row sums go through `_rowsum_seq`, which adds left to right. Numpy's pairwise sum
      could break `max` ties on lcprop fractions differently from Octave.
    - The component's `Wsym` is the all-zero `adjclustersym`.
    - `hist(z, unique(z))` gets MATLAB labels, so the one-cluster case is `hist(z, 1)`.
  - MATLAB error paths now raise `FormDiscoveryError`, and the fixture records Octave's
    message for each:
    - `growgraph` with two or more clusters raises 'unexpected structure type' for
      connected/connectednoself, the feature structures and grid/cylinder, and 'init not
      implemented for domtree' for the four domtree names. `runmodel` never calls
      `relgraphinit` for these names.
    - `makelcfreq` with non-contiguous labels. Unlike assignment, the RHS read
      `lc(zs(r), zs(c))` does not grow `lc`, so a nonzero R entry that touches a label
      above `length(unique(z))` fails with 'out of bound'. The item text assumed growth.
    - `reordermissing` when `obsind` and `missind` together do not have `objcount`
      entries.

    No new KI.
  - Fixture `tests/octave/fx_relinit.m` → `tests/fixtures/relinit.mat` (Octave 10.3.0,
    generated this iteration, ~8 s). It has four parts:
    - **ri**: `relgraphinit` for the 24 `ps.structures` names plus the 4 domtree names.
      Inputs are the 7 relational data sets and 13 seeded random relations (binary, counts,
      and an all-zero matrix). Each input is run with 4 z's: `1:n` (the 'overd' init),
      one cluster, and two seeded partitions (the 'external' init). That gives 2240
      records, 720 of them errors.
    - **lc**: `makelcfreq` on the data sets (R and R + R', with z = 1:n and a partition),
      plus 6 non-contiguous cases, 3 of which error.
    - **fo**: `filloutrelgraph` on 242 graphs:
      - the `ri` outputs of the order and one-cluster connected/domtree names;
      - seeded `split_node` sequences for the 8 order/domtree/connected names;
      - spied calls from order, ordernoself, connected and connectednoself ×
        demo_ring_rel_bin and demo_order_rel_freq. Each run's final score equals the
        committed baseline, which is tested.
    - **rm**: `reordermissing` on 17 graphs over judges' 13 objects × the 38 judges chunks
      × fixedexternal 0/1 (1292 records). The graphs are seeded split sequences for chain,
      ring, tree, hierarchy, partition, connected, grid and cylinder. 9 of them have
      unassigned objects (empty_graph + 2 add_element, as in `best_split.m:26-32`).
      `obsind`/`missind` are built as in `dataprobwsig.m:31-34`.
  - `tests/test_relinit.py` has 38 fixture tests and 2 live `octave` tests:
    - Every output matches: graph structure exactly, weights and Wvec to rtol 1e-10, and
      every error case raises.
    - Coverage and structure checks: chains and orders have n-1 edges, rings have n,
      hierarchies n-1; the all-zero tie case; errors are counted per name.
    - The recorded obsind/missind equal what the Python judges chunks (`scaledata`) give.
    - Inputs are not mutated.
    - Live: the fixture regenerates identically, and a fresh-seed run (`seedoffset = 7919`)
      matches.

    A mutation check confirmed that the tests catch each of these deliberate breaks: `>`
    → `>=` in growgraph, a lost hierarchy tail append, no undir symmetrisation, a skipped
    W column permutation in reordermissing, and a diagonal that is not zeroed.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 395 passed, 27 skipped. The
    fd env gives 422 passed, live Octave tests included.
### Blockers
- None.
### Next
- Item 15 (L2-b2: `mat2vec`, `combineWs`, `extract_weights`, column-major order). The
  `rm_graphs` in `relinit.mat` (judges graphs with random weights, grid/cylinder included)
  and the split fixtures can be used as round-trip inputs. Remember that edge maps keep
  MATLAB's edge numbers (subtract 1 when indexing `Wvec`).

## Iteration 17b — 2026-09-29 13:2x (item 15; entry written afterwards by the parent session)
### Completed
- Item 15 **solved** (`[x]`) by the loop session, which ended before writing its PROGRESS
  entry (it backgrounded the fd-env gate and exited). The work itself is complete and was
  committed by loop.py as `bb06602` ("iteration 18: item 15"; the number repeats because this
  section was missing when the next iteration was numbered).
  - `src/formdiscovery/weights.py`: `mat2vec`, `combineWs`, `extract_weights` (+ column-major
    helpers), all tying modes. `tests/octave/fx_weights.m` → `tests/fixtures/weights.mat`;
    `tests/test_weights.py` (20 tests incl. round trips and live Octave parity) pass in the fd env.
    `KNOWN_ISSUES.md` gained entries from this item; `CONVENTIONS.md` updated.
  - A stray `octave-workspace` dump was committed by that session; removed and added to
    `.gitignore` in the follow-up commit.
### Blockers
- None.
### Next
- Item 16 (done in iteration 18).

## Iteration 18 — 2026-09-29 13:34
### Completed
- Item 16 **solved** (`[x]`).
  - `src/formdiscovery/likelihood_feat.py` gains three functions, each with its source
    lines in the docstring:
    - `inv_covariance` (`inv_covariance.m:1-26`).
    - `gplike` (`gplike.m:1-26`).
    - `dataprobwsig` (`dataprobwsig.m:1-241`). It has both gradient branches: `nmiss == 0`
      (l.96-154) and `nmiss > 0` (l.155-236). The latter is the one the chunk path's
      recursive call uses, so item 17 only needs to add the chunk loop (l.24-60).
      `ps.missingdata` raises `NotImplementedError('... item 17')`.
    
    Matrix products keep MATLAB's left-to-right order. `_mm`/`_ew` raise
    `FormDiscoveryError` on nonconformant shapes where numpy would broadcast. `gplike`
    raises MATLAB's out-of-bound error when `size(X,1) > size(G,1)`. `inv_covariance`
    raises when `nobj > size(W,1)`. The NaN-gradient `keyboard` (patched to `error`) raises
    `FormDiscoveryError`.
  - Replicated behaviour:
    - l.179's `U` is computed and then overwritten.
    - The sigma gradient includes `trace(c3)`/`trace(c5)` only with `zglreg`.
    - `gplike` uses `nfeat*runps.SS` when `nobj == chunkcount && overrideSS == 0`, while the
      gradient always takes `SS` from `runps.SS` in that case (so `overrideSS=1` changes
      only the value; a test checks this).
    - The holes hack (new **KI-19**, replicate): `J(holes,holes) = 1` fills a block of ones,
      so two or more holes make `J` singular and `chol` fails. `test_known_issues.py` now
      expects KI-1..19 and pins `inv_covariance.m:26`.
  - `tests/helpers.py`: `checkgrad(f, X, e, *args) -> (d, dy, dh)`, a port of
    `checkgrad.m:18-42`.
  - `CONVENTIONS.md`: a bullet on the `nargout=` keyword and the log-weight `Wvec` layout.
  - Fixture `tests/octave/fx_dataprob.m` → `tests/fixtures/dataprob.mat` (Octave 10.3.0,
    generated this iteration, ~12 s). It has four parts:
    - **gr**: 29 graphs over 10 objects with random weights: 2 one-cluster graphs, seeded
      `split_node` sequences for 8 families (every step for partition and hierarchy), and 2
      graphs with unassigned objects.
    - **cs**: 609 cases. There are 7 data variants: feat (`d*d'`), featSS (chunkcount path
      with a random `runps.SS`), sim (`dim = 30`), featz (zglreg), and miss/simmiss/missz
      (7 of 10 rows, so `nmiss = 3`). All 7 run in mode none, and feat/miss run in the other
      7 tying modes. Each case records:
      - the three outputs, and the one-output value;
      - Octave's `checkgrad` value;
      - `inv_covariance` of the combined graph, and `gplike`;
      - or the error message.

      514 cases succeed. 83 fail with chol errors (two-hole partitions and the
      unassigned-object graphs), 11 are out of bound, and 1 is nonconformant.
    - **ic**: 24 `inv_covariance` calls on random `W` with holes, zglreg 0 and 1.
    - **bl**: a spy on `dataprobwsig` during the chain/ring/tree feature baselines (every
      97th call, 36 calls, 11 with gradients). Each run's final score equals the committed
      baseline.
  - `tests/test_dataprob.py` has 52 fixture tests and 2 live `octave` tests:
    - Every case and every spied call matches to rtol 1e-10: value, gradient, prior
      gradient, `J`, `L` and `gplike`. Every error case raises.
    - The Python `checkgrad` passes on every successful case in all 8 tying modes and both
      branches (worst d = 8e-10 against a tolerance of 1e-6), and Octave's values meet the
      same tolerance.
    - On the baseline calls, `d < 1e-6` or `‖dh-dy‖ < 1e-9·|ll|` must hold. Near the
      optimum, ‖dy‖ < 1 while ll ~ 1e4, and d reaches 2.8e-6 from finite-difference error
      alone: it shrinks as e² from e = 1e-3 to 1e-5 and grows again at 1e-6. The gradient
      itself is correct.
    - Other checks: the `featSS` path uses `runps.SS`; `hessiangrad` accepts
      `dataprobwsig`; a wrong gradient is detected; inputs are not mutated.
    - Live: the fixture regenerates identically, and fresh seeds (`seedoffset = 7919`)
      match and pass checkgrad.

    One live-test finding: graphs whose `objcount` is smaller than the number of data rows
    give `nmiss < 0`. Their `Y` (l.172) is singular (smallest eigenvalue ~4e-16), so
    Octave and numpy can fail at different points (a chol error or a nonconformant
    product). For those inputs only, the test accepts either error. No real caller passes
    such inputs.
  - A mutation check confirmed that the tests catch each of these deliberate breaks:
    dropping `trace(c3)`, skipping the l.180 `U`, the hole block written as its diagonal,
    the sign of `c2`, holes found by rows, a perturbed `X*X'`, and `trace(c5)` without
    zglreg.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 468 passed, 31 skipped.
    The fd env gives 499 passed, live Octave tests included.
  - Also fixed: item 15's live test `test_weights.py::test_live_fixture_regenerates`
    failed with `TypeError`. It called `assert_graph_equal` on the `cw = 0` placeholder
    that the fixture stores when `combineWs` errors. The test now compares `cwerr` and
    compares the graphs only when there was no error. The regression gate never ran this
    test, because it is marked `octave`.
  - `octave-workspace` (an Octave dump committed by accident last iteration) was deleted
    while this iteration's Octave runs were going. It was restored with `git checkout`,
    so the tree does not change it.
### Blockers
- None.
### Next
- Item 17 (L3-a2: the `dataprobwsig` missing-data chunk loop, l.24-60). `_grad_missing`
  (the `nmiss > 0` branch) is already ported and pinned, and `reordermissing` was done in
  item 14. What remains is the loop over `ps.runps.chunknum`, `obsind`/`missind` from
  `objind`, the `sind` gradient reassembly (skipped when `fixedexternal`), and the
  prior bookkeeping (`llc - wpriors`, `dWveccprior` subtracted for c > 1). Use the
  `judges` chunks. The spy pattern in `fx_dataprob.m` (`make_spy`) can capture real
  chunk calls, because the recursive call goes through the spy.

## Iteration 20 — 2026-09-29 14:01
### Completed
- Item 17 **solved** (`[x]`).
  - `src/formdiscovery/likelihood_feat.py`: `dataprobwsig` now runs the missing-data chunk
    loop (`dataprobwsig.m:24-60`) in `_dataprob_chunks`, with the source lines in its
    docstring. For each of `ps.runps.chunknum` chunks it does the following:
    - builds `obsind`/`missind` from `objind` and the assigned objects (`z >= 0`);
    - calls `reordermissing`;
    - takes the rows of `d` by rank (`tind[:nobs]`);
    - sets `runps.SS = chunkSS[c]` and `chunkcount = chunksize[c]`;
    - makes the recursive call through the module-level name, so a test can wrap it.

    It then reassembles the gradient via `sind` (skipped when `fixedexternal`) and does the
    prior bookkeeping as MATLAB does (`ll = wpriors + Σ(llc - wpriors)`, with
    `dWveccprior` subtracted for chunks after the first).

    `nargout=2` now returns `(ll, dWvec)` on both paths. This is what `fminunc` and
    `checkgrad` ask for.
  - Two new KIs, both replicated. `test_known_issues.py` now expects KI-1..21.
    - **KI-20**: with `fixedall` and without `fixedexternal`, `reordermissing.m:22` reads
      out of bound. `graph.reordermissing` now raises `FormDiscoveryError` instead of an
      `IndexError`. `runmodel.m:89` (`griddimsearch`, see KI-11) reaches this on judges.
    - **KI-21**: the chunk path never sets `dWvecprior`, so three outputs fail with 'element
      number 3 undefined in return list'. No caller asks for three outputs.
  - Fixture `tests/octave/fx_dpmiss.m` → `tests/fixtures/dpmiss.mat` (Octave 10.3.0,
    generated this iteration, ~68 s). It uses judges after `scaledata` (13 objects,
    38 chunks) and has these parts:
    - **gr**: 25 graphs with random weights: one cluster, seeded split sequences for chain,
      ring, tree, partition, connected, grid and cylinder, and 4 with unassigned objects.
      No hierarchy graph survived the split sequence; tree covers the hierarchy family's
      paths here.
    - **cs**: every graph × 8 tying modes (200 cases, 161 succeed), with
      `d = data(z > 0, :)` as `graph_like.m:7-10` passes it. The 39 errors: 25 KI-20 cases
      (fixedall), 7 chol failures (the partition:6 holes, KI-19), and 7 nonconformant (a
      tree graph with unassigned objects).
    - **ch**: a spy records all 228 recursive per-chunk calls of 6 cases, with inputs and
      outputs.
    - **bl**: a spy records 16 outer calls (8 value, 8 gradient) from a real
      partition × judges run with `run_baseline.m`'s settings. The final score is
      -16201.27918, the same as a separate `run_baseline('feat', 1, 13)` run (42 s).
    - **err3**: the KI-21 message.
  - `tests/test_dpmiss.py` has 26 fast tests, 7 `slow` tests (the full checkgrad) and 2
    live `octave` tests:
    - All cases in all modes match to rtol 1e-10 (value, gradient, one-output value), and
      every error case raises with the matching kind.
    - Each recursive chunk call matches Octave: reordered Wvec, data block, reordered
      graph, SS, chunkcount and the three outputs.
    - The spied-run calls match.
    - A one-chunk setup reduces to the direct path.
    - Python checkgrad (every 6th case per mode in the gate, all cases when slow) and
      Octave's checkgrad (92 values, max 4e-9) both pass FD_TOL 1e-6.
    - Inputs are not mutated.
    - Live: the fixture regenerates identically, and fresh seeds (`seedoffset = 7919`)
      match and pass checkgrad.

    The judges data from Python `scaledata` differ from Octave's by up to 1 ulp, so the
    chunk-data comparison uses rtol 1e-12.
  - A mutation check confirmed that the tests catch each of these deliberate breaks: the
    prior subtracted for every chunk, no `sind` reassembly, no `- wpriors`, rows taken by
    object id instead of rank, and `chunkcount` not set.
  - `test_dataprob.py::test_missingdata_path_not_ported` was replaced by `test_two_outputs`.
    `CONVENTIONS.md` now describes `nargout=2` and the chunk path's `d`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 496 passed, 33 skipped. The
    fd env gives 529 passed, live Octave tests included (8 min, most of it the live
    fresh-seed runs).
### Blockers
- None.
### Next
- Item 18 (L3-b1: `graph_like_conn` fast mode and the `graph_like` dispatcher).
  `graph_like` passes `data(z > 0, :)`, which the chunk path now expects. In the `dpmiss`
  fixture, every spied outer call from the judges run has `dsame = 1`, which confirms that
  subsetting. The fixture's `bl` calls with nargout 1 are probably fast-mode
  `graph_like_conn` calls (l.16) on judges, which item 18 could reuse. This is not checked:
  Octave's `fminunc` might also make one-output calls.

## Iteration 21 — 2026-09-29 14:24
### Completed
- Item 18 **solved** (`[x]`).
  - `src/formdiscovery/likelihood_feat.py` gains `graph_like_conn` (`graph_like_conn.m:1-110`),
    fast mode (l.6-32) only. It takes logs of `Wsym` (where `adjsym > 0`) and `sigma`, builds
    `Xinit = [log(sigma), mat2vec(...)]`, and returns `-dataprobwsig(Xinit, ..., nargout=1)`
    and the graph with `Wsym`/`sigma` sent through `exp(log(.))` as MATLAB does. Slow mode
    (`ps.fast` 0 or `None`) raises `NotImplementedError('... item 19')`.
  - New `src/formdiscovery/likelihood.py`: `graph_like` (`graph_like.m:1-22`). It keeps the
    assigned objects (`z >= 0`): rows for `feat`, rows and columns for `sim`; `rel` data
    are passed whole and raise `NotImplementedError('... item 20')`. It calls
    `graph_like_conn` through the module so tests can wrap it.
  - `CONVENTIONS.md`: a bullet on `graph_like`'s return value, data and fast/slow flag.
    No new KI.
  - Fixture `tests/octave/fx_graphlike.m` → `tests/fixtures/graphlike.mat` (Octave 10.3.0,
    generated this iteration, ~8 s). It has these parts:
    - **ds**: the 3 demo feature sets after runmodel's preprocessing.
    - **gh**: every `bestgraph` of the 19 feature baseline growth histories (47 graphs),
      scored in the file's own tying mode and, for tied files, also untied (82 records).
      Each stores `logI`, the returned graph, `graph_prior` and `bestgraphlls`.
    - **sy**: the 29 `dataprob.mat` graphs (some with unassigned objects) × random
      feature/similarity data × modes none, fixedexternal, fixedall, prodtied (232
      records, 24 chol errors from KI-19 graphs).
    - **jd**: the 25 `dpmiss.mat` graphs × judges (chunk path) × modes none and
      fixedexternal (50 records, 2 chol errors).
    - **bl**: a `graph_like` spy in chain × demo_chain_feat and tree × demo_tree_feat
      (run_baseline.m settings): 30 fast-mode calls with inputs and outputs. The final
      scores equal the committed baseline. The runs make 1065/2186 fast and 43/128 slow
      calls.
  - `tests/test_graphlike.py` has 371 fast tests (one per record) and 2 live `octave`
    tests:
    - Every record matches Octave: `logI` and the returned graph to rtol 1e-10, structure
      exact, and `graph_prior` of the returned graph. Every error case raises.
    - In the file's own tying mode, fast `logI + graph_prior` equals `bestgraphlls` for 36
      of 47 growth-history graphs. The exceptions are the 8 speed-4 noinit graphs
      (slow-mode scores) and depth 2 of the three demo_ring_feat alltie5 files. That
      score does not come from a fast call on the stored graph; it is probably a slow
      `gibbs_clean` pass (not checked). The test pins this split exactly.
    - Other checks: Python preprocessing reproduces the fixture data (rtol 1e-12); the
      data subsetting for feat/sim/rel; only `Wsym`/`sigma` change in the returned graph;
      slow mode raises; inputs are not mutated.
    - Live: the fixture regenerates identically, and fresh seeds (`seedoffset = 7919`)
      match.
  - A mutation check confirmed that the tests catch each of these deliberate breaks: no
    `exp` of sigma on return, no `exp` of `Wsym` on return, a perturbed `Xinit` sigma, and
    `z > 0` instead of `z >= 0` in `graph_like`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 869 passed, 35 skipped.
    (The fd-env gate result was never filled in here; iteration 22 ran it with item 19.)
### Blockers
- None.
### Next
- Item 19 (L3-b2: `graph_like_conn` slow mode, `graph_like_conn.m:35-110`). The spy in
  `fx_graphlike.m` (`make_spy`) counts slow calls (43 and 128 in the two runs). Change it
  to record slow calls and get `fminunc` optima and `logI` for the tolerance tests. The
  speed-4 noinit growth-history graphs are slow-mode inputs with known scores
  (`bestgraphlls`, which include `graph_prior`).

## Iteration 22 — 2026-09-29 15:36
### Completed
- Item 19 **solved** (`[x]`). The code, fixture and tests were written by an earlier session
  and committed by loop.py as `f07a438` ("iteration 22: item 19"). That session did not
  tick the checkbox or write this entry. This iteration checked the work, reran everything
  and recorded it.
  - `src/formdiscovery/likelihood_feat.py`: slow mode of `graph_like_conn`
    (`graph_like_conn.m:35-110`). It has three parts:
    - `_slow_minimize` replaces `fminunc` with `scipy.optimize.minimize`.
      `SLOW_METHOD = 'trust-exact'` uses the analytic gradient and a symmetrised
      finite-difference Hessian, with `gtol` 1e-8. Pass `method=` to choose another method.
    - `laplace_logI` (l.76-93) is an exact port. It uses the unsymmetrised `hessiangrad`
      H, truncates to `includeind` (`X < 195`), and warns 'sigma blows up'. It raises
      `FormDiscoveryError` when `includeind` is empty. When `logI` is complex it falls back
      to the `~isreal` formula from the positive eigenvalues.
    - `slow_graph` (l.95-101) builds the returned graph.

    The `'XXXHIDDENtree'` case can never match and is not ported. `info=` exposes the
    intermediate values. MATLAB's `disp('WARNING...')` lines become `warnings.warn`.
  - Fixture `tests/octave/fx_glslow.m` (+ `glc_quad.m`) → `tests/fixtures/glslow.mat`
    (Octave 10.3.0). It runs an instrumented shadow copy of `graph_like_conn.m` that
    records `Xinit`, X/fX, g, the full H, `includeind`, ll, `logI0` and `logI`. It has
    these parts:
    - **gh**: 82 growth-history records.
    - **sy**: 116 synthetic records (12 chol errors).
    - **jd**: 9 judges records (the chunk path).
    - **bl**: 75 slow calls spied in the chain and tree baseline runs. Their final scores
      equal the baseline.
    - **lp**: 80 Laplace-only records at non-optimal points (the fallback runs in 25).
    - **qd**: quadratic-objective records covering truncation, 'sigma blows up', the
      fallback and the empty-`includeind` error.

    **Regenerated this iteration** (38 s). The contents are identical to the committed
    copy; only the `.mat` header changed.
  - `tests/test_glslow.py` has 276 gate tests, 11 `slow` tests and 2 live `octave` tests:
    - At Octave's X, the Laplace step and the returned graph match to rtol 1e-10. H uses a
      documented FD tolerance.
    - On every record, Python's objective is ≤ Octave's fX + 1e-6 and its gradient norm is
      ≤ Octave's.
    - `logI` matches to rel **2e-4**, not the 1e-4 PLAN §4.1 started with. The worst gaps
      are 1.6e-4 (a tree-run call) and 1.06e-4 (gh 64). Octave causes the gap: `fminunc`
      (TolFun = TolX = 1e-6) stops early, with gradient norms up to ~15 and fX up to 0.08
      above the optimum. `test_worst_logI_gap_is_octaves` pins this. `KNOWN_ISSUES.md`
      KI-10 now points to this test file.
  - **Which scipy method tracks Octave best**: none follows `fminunc`'s early stop.
    `trust-exact`, `trust-ncg`, `BFGS` and `L-BFGS-B` all reach the same optimum
    (objectives within 1e-8), so they are all the same distance from Octave's `logI`.
    `L-BFGS-B` is ~3x faster on judges. `BFGS` fails on bl 43, where its line search
    probes a point that makes `chol` fail. `trust-exact` stays the default.
    `test_methods_agree` (slow) pins this.
  - `test_graphlike.py::test_slow_mode_not_ported` was removed; slow mode now dispatches
    (`test_graph_like_slow_dispatch`). `CONVENTIONS.md` describes slow mode.
  - This iteration: fixed the `fx_glslow.m` header comment ('8' → '9 (every 3rd)' judges
    graphs; comment only). Filled in the `FDGATE` placeholder that iteration 21 left.
  - Verified:
    - base `python -m pytest -q -m "not slow"`: 1142 passed, 37 skipped (68 s);
    - `-m slow tests/test_glslow.py`: 11 passed (2 min 46 s);
    - fd env `-m octave tests/test_glslow.py`: 2 passed (84 s; fixture regenerates
      identically, fresh seeds 7919 pass).
### Blockers
- None.
### Next
- Item 20 (L3-c: `countmatrix, rellikebin, rellikefreqs, graph_like_rel` →
  `likelihood_rel.py`). `graph_like` currently raises `NotImplementedError('... item 20')`
  for `runps.type == 'rel'`. `bbloglike`, `bblikesumhyps`, `dirmultloglike` and `makehyps`
  are already ported (item 08). `relgraphinit`/`filloutrelgraph` are done (item 14).

## Iteration 23 — 2026-09-29 15:46
### Completed
- Item 20 **solved** (`[x]`).
  - `src/formdiscovery/likelihood_rel.py` gains four functions, each with its source lines
    in the docstring:
    - `countmatrix` (`countmatrix.m:1-21`). Objects with `z == -1` are in no cluster. With
      no clusters it returns MATLAB's l.13 scalar as a 1 x 1 array.
    - `rellikebin` (`rellikebin.m:1-41`). It keeps the column-major hyperparameter grid and
      the `find(triu(ones))` pair order.
    - `rellikefreqs` (`rellikefreqs.m:1-27`).
    - `graph_like_rel` (`graph_like_rel.m:1-163`). It returns `(logI, graph)`, and the graph
      is the input object. It has three parts:
      - It fills out order/domtree/connected graphs first (`filloutrelgraph`, l.8-13).
      - relbin/relfreq (l.102-155) use the `_SELF` (links within classes) and `_UNDIR`
        (symmetrised) form lists. `hist_centres` counts the assigned objects per cluster.
      - The unused `'reldom'` branch (l.22-101) is ported in `_reldom`, including the
        `lowdiag` eps tricks and the 'data not lower diagonal!' error.

      An inf/NaN `logI` raises `FormDiscoveryError('graph_like_rel: logI is inf or NaN')`,
      and any other data type raises 'unknown relational type'.
  - `likelihood.graph_like` now passes rel data (the dict, whole) to
    `likelihood_rel.graph_like_rel` through the module.
    `test_graphlike.py::test_data_subsetting` now checks this dispatch instead of expecting
    `NotImplementedError`. `CONVENTIONS.md` is updated.
  - New **KI-22** (replicate): the `reldom` two-cluster edge-direction flip (l.93-100) only
    writes `graph.adj`, and l.162 then discards it, so it has no effect. It is not
    computed. `test_known_issues.py` now expects KI-1..22 and pins `graph_like_rel.m:96`.
  - Fixture `tests/octave/fx_rellike.m` → `tests/fixtures/rellike.mat` (Octave 10.3.0,
    generated this iteration, ~28 s). It has these parts:
    - **ri**: 980 records: the 24 `ps.structures` names + 4 domtree names × the 7
      relational data sets (relbin: demo_ring_rel_bin, demo_hierarchy_rel_bin, kularing,
      prisoners; relfreq: demo_order_rel_freq, mangabeys, bushcabinet) × 5 `z` kinds
      (1:n, one cluster, two seeded partitions, a partition with 2 unassigned objects).
      644 are scored. `relgraphinit` cannot build the feature forms, connected or
      domtree, so those records hold its 'init:' error.
    - **sq**: 455 graphs from seeded `split_node` sequences on all 7 data sets. They cover
      order, ordernoself, connected, connectednoself, the 4 domtree names, partition,
      undirchain, undirring, undirhierarchynoself and dirhierarchy. Together with ri,
      every relational form is scored on every data set.
    - **sy**: 1960 records: the ri recipe on 7 seeded random relations (binary, counts,
      two with self links, one with a NaN entry), each run as relbin and as relfreq.
      476 give the nanscore error. Examples: count data read as relbin (`ys > ns`), self
      links in a singleton cluster, and the NaN entry.
    - **pv**: 392 records: ri graphs under 4 non-default `edgesumsteps`/`edgeoffset`/
      `edgesumlambda` grids.
    - **gh**: 79 bestgraphs from the 54 relational baseline growth histories, with
      `graph_prior` and `bestgraphlls`.
    - **rb/rf**: 12 direct `rellikebin`/`rellikefreqs` calls each (all-zero and all-one
      adjacency included).
    - **rd**: 149 `reldom` records (`lowdiag` 0/1, two-cluster one-edge graphs) and the
      lowdiag error.
    - **bl**: 48 `graph_like_rel` calls spied in dirring × demo_ring_rel_bin,
      undirhierarchy × demo_hierarchy_rel_bin, order × demo_order_rel_freq and
      partitionnoself × demo_order_rel_freq (run_baseline.m settings). The final scores
      equal `test_baseline_rel.EXPECTED_LL` exactly.
  - `tests/test_rellike.py` has 77 gate tests and 2 live `octave` tests:
    - Every record matches Octave. `logI` matches to rtol 1e-10 (worst 4e-14). The
      returned graph is the input, exactly. `countmatrix` is exact, and `graph_like`'s
      `logI` also matches. Every Octave nanscore/lowdiag error raises.
    - On every gh graph, `logI + graph_prior` equals `bestgraphlls` to 1e-10 (relational
      runs score in fast mode only).
    - Other checks: coverage of every form × data set; `_SELF`/`_UNDIR` each change some
      scores; the KI-22 pin; inputs are not mutated; unassigned objects are excluded from
      `countmatrix`.
    - Live: the fixture regenerates identically, and fresh seeds (`seedoffset = 7919`)
      match.
  - A mutation check confirmed that the tests catch each of these deliberate breaks:
    - the diagonal size correction dropped;
    - `alphas` used for non-edges in `rellikefreqs`;
    - all theta pairs instead of `triu`;
    - no halving of reldom diagonal counts;
    - unassigned objects counted in the class sizes;
    - no `sizevec == 0 → 1`;
    - `countmatrix` transposed;
    - no `filloutrelgraph`.
  - Gate: base python `python -m pytest -q -m "not slow"` gives 1225 passed, 39 skipped
    (78 s). fd env `-m octave tests/test_rellike.py tests/test_graphlike.py` gives
    4 passed (88 s).
### Blockers
- None.
### Next
- Item 21 (M3 checkpoint: `tools/compare_runs.py --score-true-graphs`). Every likelihood
  path is now ported: feature fast/slow, the missing-data chunk path and relational.
  Relational scores have no slow mode (`graph_like_rel` has no optimiser), so for the rel
  demos "fast" and "slow" are the same number. Check how the `.mat` files store the true
  graphs before writing the script (the demo files are loaded by `io.load_dataset`, which
  currently keeps only `data`/`names`).

## Iteration 24 — 2026-09-29 15:57
### Completed
- Item 21 **solved** (`[x]`). This is the M3 checkpoint.
  - How the `.mat` files store the true graphs:
    - **Feature demos** have `adj`/`W` over the 8 objects plus the cluster nodes, `sigma`
      (2) and `structure`. `W` holds weights: 5 for leaves and 2 between clusters.
      `G = inv(diag(sum W) - W + diag(1/sigma^2 on objects))` to 1e-15, which is the
      model's own covariance.
    - The true tree is unrooted: its two internal nodes are joined directly. The model's
      trees have a degree-2 root.
    - **Relational demos** have a `graph` struct (`adjcluster`, `adj`, `objcount`, `z`)
      with no `type`.
  - New fixture script `tests/octave/fx_truegraphs.m` → `tests/fixtures/truegraphs.mat`
    (Octave 10.3.0, generated this iteration, 0.3 s).
    - **fe**: each feature demo's true graph, built with the model's own code. It starts
      from `makeemptygraph(ps)` and adds one component with these fields:
      - `z` = the cluster each object hangs from;
      - `adj` = triu of the cluster block (only `adjsym`/`Wsym` reach the feature
        likelihood);
      - `illegal` = the clusters that hold no object;
      - `leaflengths` = the leaf weights, and `extlen`/`intlen` = the unique leaf/cluster
        weight.

      Then `combinegraphs` runs. Each graph is scored in 3 tying modes (none, exttie,
      alltie), in fast mode and in slow mode. The record stores the returned graphs and
      `graph_prior`.
    - **re**: each relational demo's graph under every relational form of its generating
      family. Ring and hierarchy each get dir/undir × self/noself. Order gets order and
      ordernoself.
  - New `tools/compare_runs.py --score-true-graphs`:
    - `true_feat_graph`/`true_rel_graph` build the same graphs in Python.
    - `score_true_graphs` scores them and compares against the committed fixture, or
      against a fresh Octave run with `--live`.
    - `--method` picks the scipy method for slow mode.
    - It prints a Markdown table and exits with 1 on any failure.

    Checks per row:
    - the Python graph equals Octave's input graph (`graph_diff`);
    - fast `logI` and `graph_prior` match to rtol 1e-10;
    - feature slow `logI` matches to rel 2e-4 (`test_glslow.LOGI_RTOL`);
    - optimality: the fast score at Python's optimised weights is ≥ the fast score at
      Octave's, minus 1e-6;
    - relational slow is identical to fast (there is no optimiser).
  - `tests/test_truegraphs.py` has 27 gate tests and 2 live `octave` tests:
    - one test per row;
    - fast mode agrees to < 1e-14;
    - feature slow `logI` agrees to < 1e-5 on these graphs, and Python's optimum is always
      at least as good;
    - relational slow equals fast;
    - a baseline sanity check (below);
    - the checker catches perturbed Octave scores, priors and graphs;
    - `main` output and exit code.

    Live tests: the fixture regenerates identically, and `--live` passes.
  - **True graphs vs the baseline search** (pinned in `test_true_scores_vs_baseline_search`).
    Compare the true graph's untied slow `logI + graph_prior` with the final score the
    Octave search reached for the generating form:
    | form × data | true graph | baseline search |
    |---|---|---|
    | chain × demo_chain_feat | -8247.196 | -8247.205 |
    | ring × demo_ring_feat | -8500.517 | -8500.520 |
    | tree × demo_tree_feat | -8707.827 | -8707.814 |
    | dirring × demo_ring_rel_bin | -22.187 | same, exact |
    | order × demo_order_rel_freq | -3682.199 | same, exact |
    | dirhierarchy × demo_hierarchy_rel_bin | -81.05 | -70.25 |

    The first three agree within optimiser noise. For dirring and order the search
    recovered the true graph exactly. For dirhierarchy the search found a graph that
    scores better than the truth.
  - No new KI; no package code changed.
  - **M3 table** (`python tools/compare_runs.py --score-true-graphs`; "opt gain" is the
    Python optimum's fast score minus Octave's, so a positive value means Python's
    optimum is better):

    | data | form | tying | Octave fast | Python fast | rel diff | Octave slow | Python slow | rel diff | opt gain | prior | ok |
    |---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
    | demo_chain_feat | chain | none | -8223.958415 | -8223.958415 | 4.4e-16 | -8235.337295 | -8235.333485 | 4.6e-07 | 3.4e-03 | -11.858932 | yes |
    | demo_chain_feat | chain | exttie | -8215.606384 | -8215.606384 | 4.4e-16 | -8223.755961 | -8223.750087 | 7.1e-07 | 5.1e-03 | -11.858932 | yes |
    | demo_chain_feat | chain | alltie | -8213.552671 | -8213.552671 | 4.4e-16 | -8220.094005 | -8220.093830 | 2.1e-08 | 9.9e-04 | -11.858932 | yes |
    | demo_ring_feat | ring | none | -8542.135175 | -8542.135175 | 0.0e+00 | -8489.172608 | -8489.173582 | 1.1e-07 | 2.6e-03 | -11.344652 | yes |
    | demo_ring_feat | ring | exttie | -8533.783144 | -8533.783144 | 0.0e+00 | -8476.529255 | -8476.525548 | 4.4e-07 | 7.0e-03 | -11.344652 | yes |
    | demo_ring_feat | ring | alltie | -8530.702575 | -8530.702575 | 0.0e+00 | -8471.970942 | -8471.969387 | 1.8e-07 | 7.7e-04 | -11.344652 | yes |
    | demo_tree_feat | tree | none | -8686.976946 | -8686.976946 | 4.2e-16 | -8696.480260 | -8696.461848 | 2.1e-06 | 1.6e-02 | -11.346881 | yes |
    | demo_tree_feat | tree | exttie | -8678.624916 | -8678.624916 | 4.2e-16 | -8685.772557 | -8685.770600 | 2.3e-07 | 3.0e-03 | -11.346881 | yes |
    | demo_tree_feat | tree | alltie | -8674.517490 | -8674.517490 | 4.2e-16 | -8679.069206 | -8679.066800 | 2.8e-07 | 1.2e-03 | -11.346881 | yes |
    | demo_ring_rel_bin | dirring | - | -10.581857 | -10.581857 | 6.7e-16 | -10.581857 | -10.581857 | (= fast) | - | -11.605378 | yes |
    | demo_ring_rel_bin | dirringnoself | - | -4.966065 | -4.966065 | 2.1e-15 | -4.966065 | -4.966065 | (= fast) | - | -11.605378 | yes |
    | demo_ring_rel_bin | undirring | - | -12.622906 | -12.622906 | 2.8e-16 | -12.622906 | -12.622906 | (= fast) | - | -11.344652 | yes |
    | demo_ring_rel_bin | undirringnoself | - | -10.667355 | -10.667355 | 3.3e-16 | -10.667355 | -10.667355 | (= fast) | - | -11.344652 | yes |
    | demo_hierarchy_rel_bin | dirhierarchy | - | -18.765387 | -18.765387 | 1.9e-15 | -18.765387 | -18.765387 | (= fast) | - | -62.284607 | yes |
    | demo_hierarchy_rel_bin | dirhierarchynoself | - | -8.979946 | -8.979946 | 6.7e-15 | -8.979946 | -8.979946 | (= fast) | - | -62.284607 | yes |
    | demo_hierarchy_rel_bin | undirhierarchy | - | -21.904421 | -21.904421 | 1.1e-15 | -21.904421 | -21.904421 | (= fast) | - | -59.873732 | yes |
    | demo_hierarchy_rel_bin | undirhierarchynoself | - | -18.088085 | -18.088085 | 2.9e-15 | -18.088085 | -18.088085 | (= fast) | - | -59.873732 | yes |
    | demo_order_rel_freq | order | - | -3669.675536 | -3669.675536 | 1.2e-16 | -3669.675536 | -3669.675536 | (= fast) | - | -12.522996 | yes |
    | demo_order_rel_freq | ordernoself | - | -3651.093281 | -3651.093281 | 8.7e-16 | -3651.093281 | -3651.093281 | (= fast) | - | -12.522996 | yes |
    
    19/19 rows pass (fast rtol 1e-10, slow rel 0.0002, optimum tol 1e-06)
  - Gate results:
    - base `python -m pytest -q -m "not slow"`: 1252 passed, 41 skipped (81 s);
    - fd env `-m octave tests/test_truegraphs.py`: 2 passed.
### Blockers
- None.
### Next
- Item 22 (permutation replay: `rng.py` plus the `matlab/octave_shims/randperm.m` shim).
  L0–L3 are now all verified against Octave. M3 holds: every fast score is exact and every
  slow score is within tolerance.

## Iteration 25 — 2026-09-29 16:06
### Completed
- Item 22 **solved** (`[x]`).
  - New `src/formdiscovery/rng.py`. Each provider's `randperm(n)` returns a 0-based
    int64 permutation:
    - `PermutationProvider`, a runtime-checkable Protocol;
    - `NumpyPermutations(seed)`, the default;
    - `IdentityPermutations`;
    - `ReplayPermutations`, a queue. It raises `ReplayError` when the queue is exhausted
      or a length does not match, and `consumed`, `remaining()` and `assert_exhausted()`
      count the draws;
    - `RecordingPermutations`, a wrapper that logs what it returns;
    - helpers: `as_provider` (`None`/int/Generator → numpy), `check_perm`, and
      `write_queue`/`read_queue`/`parse_queue`. Files are 1-based, one `n p1 ... pn`
      line per draw, and `0` is the empty permutation.
  - New `matlab/octave_shims/randperm.m`. It shadows the built-in once the directory is
    first on the path, and `FD_RANDPERM` picks the source:
    - unset: `builtin('randperm', ...)`, so the stream is unchanged;
    - `identity`;
    - `<queue file>`: replay. It errors when the queue runs out, on a wrong length, on
      an entry that is not a permutation, and on a bad header.

    `FD_RANDPERM_LOG` appends every draw in the queue format, so an Octave log replays
    directly in Python. The queue is reloaded when the file name changes.
    `randperm_config(source, log)` sets the variables, truncates the log and rewinds.
    `randperm(n, m)` is passed through to the built-in, and is an error in the replay
    modes (the sources never call it).
  - `tests/conftest.py` has `SHIM_DIR` and a `replay` fixture, which returns a
    `ReplayControl`:
    - `queue(perms)` sets up the same queue on both sides;
    - `identity()`;
    - `record(seed)`, then `from_log()`: Octave's own seeded draws, replayed in Python;
    - `octave_log()`.

    On teardown the fixture restores the pass-through and removes the shim from the
    path. Checked: `which randperm` is the built-in again afterwards, and other live
    tests in the same session still pass.
  - Fixture `tests/octave/fx_rng.m` → `tests/fixtures/rng.mat` (Octave 10.3.0,
    regenerated this iteration, 0.1 s). It has these parts:
    - **bi**: pass-through equals the built-in for seeds 1–3;
    - **id**: identity;
    - **qu**: queue replay, rewind and reload on a new file;
    - **er**: all error messages;
    - **cs**: the real call site `choose_seedpairs.m:24`, with 7 draws of
      `randperm(6)`, under identity, recorded, and replayed from the log.
  - `tests/test_rng.py` has 19 gate tests and 5 live `octave` tests:
    - Every fixture part matches the Python providers exactly. The shim's log, its queue
      file and `write_queue` are byte-identical. The Python error messages match the
      shim's once file names are stripped.
    - A test-only mirror of the `choose_seedpairs` top-level branch (the port itself is
      item 23) gets Octave's seed pairs from the replayed log and uses up the queue
      exactly.
    - Live: the fixture regenerates identically. A fresh 40-entry numpy queue is
      consumed identically by Octave (read from its log) and by Python, and Octave then
      raises 'queue exhausted'. For seeds 1, 5 and 7919, Octave's seeded draws at
      `choose_seedpairs` are recorded and replayed to the same seed pairs; identity
      mode also agrees.
  - A mutation check confirmed that the tests catch each of these deliberate breaks:
    - `write_queue` writes 0-based values;
    - replay never advances;
    - the shim's cursor sticks at entry 1 (live);
    - pass-through consumes an extra `rand` (the fixture's `bi` then differs from the
      built-in).
  - Docs: `CONVENTIONS.md` (Randomness) describes the provider API, the `rng=None`
    argument for the L4 ports and the shim; `matlab/PATCHES.md` has a "Test shims"
    section, since the shims are not a source patch. No new KI.
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 1271 passed, 46 skipped (79 s);
    - fd env `-m octave tests/test_rng.py tests/test_split.py tests/test_patches.py`:
      10 passed.
### Blockers
- None.
### Next
- Item 23 (L4-a: `addnearmiss, choose_seedpairs, best_split, choose_node_split` →
  `search.py`). Give the functions an `rng=None` argument and draw with
  `as_provider(rng).randperm(n)`. For fixtures, have `fx_*.m` add `matlab/octave_shims`,
  record Octave's draws with `randperm_config('', logfile)` after `rand('state', s)`, and
  store the log text so Python can replay it with `parse_queue`. `test_rng.seedpairs_top`
  already mirrors the >5-members branch of `choose_seedpairs`; replace it with the real
  port.

## Iteration 26 — 2026-09-29 16:28
### Completed
- Item 23 **solved** (`[x]`).
  - New `src/formdiscovery/search.py`. Each function cites its source lines:
    - `addnearmiss` (`addnearmiss.m:1-16`) takes a 1-D score array and a list of graphs
      and returns new copies. When no stored score is below the new one, MATLAB fails at
      `lower(1)`; the port raises `FormDiscoveryError`.
    - `choose_seedpairs` (`choose_seedpairs.m:1-52`) covers the ≤5 branch (all pairs),
      the >5 branch (one `randperm` per member over its *combined* cluster, drawn even
      when empty, with the fallback to the node's other members), and the flip rules
      (high level; `partition` never; `tree` only for pind 2; otherwise not on the first
      split).
    - `best_split` (`best_split.m:1-165`):
      - greedy growth from each seed pair; ties go to `c1`;
      - the best-first `simplify_graph(cleanstrong=1)` pass that sets collapsing
        candidates to `-inf`;
      - speed 3 (slow rescoring), speeds 4 and 5, and other speeds raise (KI-1);
      - `ll = -inf` when the chosen candidate is `-inf`.

      For `compind < 0`, `pind` is the 0-based vacant neighbour node. `info=` exposes
      `gs`, `ls0`, `ls`, `mind`, `c1` and `c2`.
    - `choose_node_split` (`choose_node_split.m:1-23`) shares one provider between its
      two callees. A node with one member returns `(-inf, [node], [], None)`, and a NaN
      score raises.

    All of them take `rng=None` and draw with `as_provider(rng).randperm(n)`.
  - New **KI-23** (replicate): relational data are never masked in `best_split`. The
    code writes unused `d.ys`/`d.ns` fields. **KI-24** (replicate): high-level split
    parts are read from the input graph. **KI-25** (fix, unreachable): with one member,
    `nchoosek` returns a count, so the port raises. KI-1's pin now exists.
    `test_known_issues.py` expects KI-1..25 and pins the three new lines.
  - Fixture `tests/octave/fx_search.m` → `tests/fixtures/search.mat` (Octave 10.3.0,
    generated this iteration, 44 s). The shim runs in pass-through mode with a log, and
    each call's draws are stored as log text. Parts:
    - **an**: 60 `addnearmiss` cases, 14 of them errors.
    - **sq**: 219 `choose_node_split` records.
      - Sources: 19 seeded growth sequences (partition, chain, ring, tree, hierarchy,
        grid, cylinder, connected on the feature demos; dirring, undirringnoself,
        partitionnoself, dirhierarchy, undirhierarchynoself, order, dirchainnoself,
        connected on the relational demos), plus a crafted grid with 6 objects next to
        a vacant cell.
      - Coverage: 13 high-level splits, including the >5-member high-level case; 15
        one-member nodes; 18 productions that do not apply; 14 where every candidate
        collapses (`ll = -inf` with a graph).
      - Speeds: 189 at speed 5, 19 at speed 4, 11 at speed 3.
      - 204 records also have a separate `choose_seedpairs` call and its draws; 78 of
        them take the >5-members branch.
    - **er**: speeds 1, 2 and 54. Octave fails with "'mind' undefined near line 141".
    - **bl**: 24 calls spied in chain × demo_chain_feat, tree × demo_tree_feat,
      dirring × demo_ring_rel_bin and dirhierarchy × demo_hierarchy_rel_bin. Their final
      scores equal the committed baselines.
  - `tests/test_search.py` has 305 gate tests and 2 live `octave` tests:
    - Every sq/bl record replays Octave's draws. The queue is used up exactly.
    - Speeds 4/5: `ll` matches to rtol 1e-10, the parts exactly and `newgraph` to
      1e-10.
    - Speed 3: `ll` matches to rel 2e-4 (`LOGI_RTOL`); the graph is compared by
      structure only.
    - `choose_seedpairs` alone matches on all 204 calls. Every branch is exercised,
      including the singleton-cluster fallback on product graphs.
    - Property test (`test_best_split_maximises_candidates`, 46 records): the result is
      the first maximum of the candidate scores. Each candidate's score equals its
      graph's full-data `graph_like + graph_prior`. The `-inf` pass removes exactly a
      best-first prefix of candidates that collapse to one cluster.
    - Other checks: the KI-1/23/24/25 pins, NaN → raise, inputs not mutated, the default
      numpy rng, addnearmiss insertion positions, and that the sequences advance with
      the best speed-5 graph.
    - Live: the fixture regenerates identically; fresh seeds (`seedoffset = 7919`) replay.
  - **Float ties.** 136 records have several candidates tied at the maximum: mirror-image
    seed pairs give the same split with the children swapped. Python and Octave round
    differently, so `check_call` accepts any tied Python candidate (rtol 1e-10) whose
    graph and parts equal Octave's. In the committed fixture 3 records need this
    (sq 68, sq 212 and baseline call bl 0); the others pick the same candidate.
    The same can happen inside the greedy loop (`max([g1l, g2l])`). In the fd env,
    numpy 2.5 flips a 7e-15 tie on the fresh-seed relational run. So as a last rule the
    test accepts Octave's graph when Python scores it within 1e-10 of Python's own
    result; the base env never needs that rule. This is documented in `CONVENTIONS.md`
    (Randomness).
  - A mutation check confirmed that the tests catch each of these deliberate breaks:
    - always flip the seed pairs;
    - greedy ties go to `c2`;
    - no `-inf` pass;
    - membout not permuted (a draw is still made);
    - clustmembers taken from the node instead of the combined cluster;
    - high-level parts read from `newgraph`;
    - no `graph_prior` in the greedy step;
    - wrong addnearmiss shift.
  - `test_rng.seedpairs_top` now calls the real `search.choose_seedpairs`.
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 1579 passed, 48 skipped (95 s);
    - fd env `-m octave tests/test_search.py tests/test_rng.py`: 7 passed;
    - fd env non-live `test_search`/`test_rng`/`test_known_issues`: 354 passed.
### Blockers
- None.
### Next
- Item 24 (L4-b1: `swapobjclust` + subfunctions). Use the same recording pattern:
  truncate the log, call, and store `fileread(log)`. Before item 27 (reproducing
  structurefit growth histories), note that tied candidates **can** make Python and
  Octave diverge. It already happens once in a baseline call (bl 0: chain ×
  demo_chain_feat, 1st `choose_node_split`). The two choices are mirror images with
  equal scores, so later steps should be equivalent up to relabelling, but an exact
  growth-history comparison may need a tie-aware or relabelling-invariant check.

## Iteration 27 — 2026-09-29 16:53
### Completed
- Item 24 **solved** (`[x]`).
  - `src/formdiscovery/search.py` gains these functions, each citing its source lines:
    - `swapobjclust` (`swapobjclust.m:1-58`). `comp` is 0-based, or `None` for the whole
      graph. `objflag`/`fastflag`/`debug` are keywords, and it takes `rng=None`. It
      returns `(graph, currscore, overallchange, nearmscores, nearmgraphs)`, and the
      near-miss graphs are a list. Replicated quirks:
      - After an accepted change the candidates are listed again, but the pass goes on
        with the **old permutation**. Indices past the new list are skipped.
      - The accepted graph is the simplified candidate, not `graph_like`'s output.
      - The `disp` is dropped. `debug` raises.
    - `chooseswaps` (l.68-199). It covers all five kinds of change: object moves;
      cluster moves and swaps within a component; cluster moves and swaps across the
      whole graph. Each has a full mode and a fast mode (`dijkstra` neighbourhood of 3).
      Details:
      - The MATLAB row orders are kept. For whole-graph moves the source is the outer
        loop; within a component the source is the inner loop.
      - Self-moves are listed in full mode.
      - With one occupied node, the component swap list is the `[1 1]` pair (node 0 with
        itself).
      - Rows are float arrays holding 0-based indices, with NaN where MATLAB has NaN.
    - `doswap` (l.205-235).
    - `sourceobjs` (l.239-255) and `sourcecls` (l.259-272). Their type lists are
      replicated as they are, and they differ: `tree` is in neither list.
    - `cltypes` (l.277-283).
  - New **KI-26** (fix, unreachable): whole-graph full mode with one source cluster.
    `nchoosek(scalar, 2)` fails in MATLAB and in Octave; the port raises. On a one-node
    graph Octave's fast mode also fails (empty concatenation); the port returns an empty
    list. `gibbs_clean.m:101` never calls it on such graphs. `test_known_issues.py` now
    expects KI-1..26 and pins `swapobjclust.m:126`.
  - Fixture `tests/octave/fx_swap.m` → `tests/fixtures/swap.mat` (Octave 10.3.0,
    generated this iteration, 61 s, 633 KB).
    - It re-runs 11 runs with run_baseline.m's settings: chain, ring, tree, hierarchy,
      grid and cylinder on the feature demos; dirring, undirchain, order, dirhierarchy
      and undirhierarchy on the relational demos.
    - During these runs `swapobjclust` is replaced by a spy (new helper
      `tests/octave/swap_spy.m`). The original is copied to `swapobjclust_orig.m`, and
      its subfunctions to `swsub.m` behind a dispatcher, both in a temporary directory.
    - The runs' final scores equal the committed baselines for the 8 runs that have one.
    - Parts:
      - **sw**: 238 calls in two kinds.
        - `bl` (119): real `gibbs_clean` calls, the first 2 per mode and run plus up to
          2 more that changed the score. Each kept call is replayed in Octave with
          placeholder near-miss graphs `'in1'...`, so the output shows which entries
          are new.
        - `pt` (119): the same mode on a perturbed graph (random object moves plus one
          change of the call's own mode), with loopmax 1-3 and seeded draws.

        Every mode appears both with an accepted change and without one. The records
        include near-miss lists, product graphs (whole-graph moves and swaps on the
        cylinder) and loopmax 1, 2 and 3.
      - **sub**: 59 records, one per mode and run. Each has `chooseswaps` in every mode
        (Octave errors caught), `sourceobjs`, `sourcecls` (whole graph and per
        component), `cltypes`, and `doswap` on one random row per mode.
  - `tests/test_swap.py` has 250 gate tests and 2 live `octave` tests:
    - Every sw record replays Octave's draws, and the queue is used up exactly.
      `currscore` matches to rtol 1e-10. The graph and `overallchange` match exactly
      (graph weights to 1e-10). The near-miss scores match to 1e-10, and the near-miss
      graphs match, placeholders included.
    - Every sub output matches exactly, including the NaN pattern of the swap rows.
      KI-26 errors are handled as described above.
    - Other checks:
      - an accepted graph's score is its `currscore` and it is already simplified;
      - the stale-permutation quirk occurs (the list length changes after an accept);
      - inputs are not mutated;
      - `debug` raises;
      - the default numpy rng runs;
      - the one-node `[1 1]` swap;
      - the KI-26 pin.
    - **Near-miss ties.** Some candidates have equal scores. In the committed fixture 4
      near-miss entries sit at a different position among tied entries. On the live
      fresh-seed run, once, six or more candidates tied exactly (Python's set is 1e-13
      away from Octave's) and fewer fit in the list, so a different subset was kept.
      `check_nearmisses` accepts a tied permutation. If the tied group reaches the end
      of the list, it also accepts any Python graph that rescores to the tied value.
      This is documented in `CONVENTIONS.md`.
    - Live: the fixture regenerates identically, and fresh seeds (`seedoffset = 7918`,
      seed 7919) replay (fd env, 2 passed).
  - A mutation check confirmed that the tests catch 8 of 9 deliberate breaks:
    - no re-listing after an accept;
    - component moves with the source as the outer loop;
    - `undirhierarchy` dropped from `sourcecls`;
    - a whole-graph swap reading the new `z`;
    - the one-node swap using the occupied node;
    - no `simplify_graph`;
    - distance 0 included in fast mode;
    - `>=` in the near-miss test.

    The one missed break was keeping `graph_like`'s graph instead of the candidate.
    That change is equivalent here: in fast mode `graph_like` returns the graph
    unchanged, and `swapobjclust` always runs in fast mode.
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 1830 passed, 50 skipped (101 s);
    - fd env `tests/test_swap.py tests/test_known_issues.py` (live tests included):
      283 passed.
### Blockers
- None.
### Next
- Item 25 (L4-b2: `spr (+makerp, makers)`, `collapsedims (+getocc, get_occnodescomp,
  zassign)`). The `fx_swap.m` spy pattern should carry over:
  - copy the original to `<name>_orig.m` and write a forwarding spy;
  - copy the subfunctions into a dispatcher file;
  - record the draws per call;
  - replay kept calls with placeholder near-miss graphs.

  `spr` needs tree/hierarchy runs, and `collapsedims` needs grid/cylinder runs. In
  fx_swap only the cylinder run reached the whole-graph branch of `gibbs_clean` (the
  grid run on demo_chain_feat never grew in two dimensions), so for `collapsedims`
  consider cylinder on demo_ring_feat, grid on a larger data set, or crafted product
  graphs. Near-miss lists can hold tied candidates, so reuse `check_nearmisses`.

## Iteration 28 — 2026-09-29 17:20
### Completed
- Item 25 **solved** (`[x]`).
  - `src/formdiscovery/search.py` gains these functions, each citing its source lines.
    All take `rng=None` and draw with `as_provider(rng).randperm(n)`:
    - `spr` (`spr.m:1-50`), with `makerp` (l.53-60) and `makers` (l.63-99).
      - `makers` returns 0-based `(rs, cs)`: tree edges in column-major `find` order,
        with edges inside the subtree and edges touching the parent removed; for the
        hierarchy family, the sorted nodes.
      - Replicated quirk: after an accepted change `spr` draws a **new** permutation,
        re-reads `j` and the targets, but both loops keep their old lengths
        (break / skip past the end).
    - `collapsedims` (`collapsedims.m:1-58`), with `getocc` (l.63-69),
      `get_occnodescomp` (l.74-75) and `zassign` (l.80-85).
      - Replicated quirk: `dijkstra(Wclustersym)` is computed once per pass and is not
        recomputed after an accept.
      - One draw per slice that fits into the vacant clusters, none for the others.
      - The `disp` is dropped. `debug` raises in both functions.
  - New **KI-27** (fix, unreachable): `makers` has no case for `domtreenoself`, which
    `gibbs_clean.m:88-91` sends to `spr` ('rs' undefined). The port raises.
    `test_known_issues.py` expects KI-1..27 and pins `spr.m:75`.
  - Fixture `tests/octave/fx_spr.m` → `tests/fixtures/spr.mat` (Octave 10.3.0,
    generated this iteration, 203 s, 1.2 MB). New spy `tests/octave/l4b2_spy.m`.
    `fx_spr.m`'s `make_spy` generalises fx_swap's: `<name>_orig.m`, a forwarding stub,
    and subfunction dispatchers `sprsub.m`, `cdsub.m` and `swsub.m`.
    - 11 spied runs with run_baseline.m's settings:
      - for `spr`: tree and hierarchy × demo_tree_feat, tree × demo_chain_feat, and
        dir/undir hierarchy (self and noself) × demo_hierarchy_rel_bin;
      - for `collapsedims`: cylinder × demo_ring_feat, grid × demo_ring_feat,
        cylinder × demo_chain_feat and grid × synthgrid.

      The 6 runs that have a baseline reproduce it exactly.
    - **calls** (70 records, 317 draws in total):
      - `spr`: 16 `bl` (2 with an accepted change) and 16 `pt`. The `pt` records use a
        perturbed graph: random object moves plus one random regraft. All 16 accept a
        change.
      - `collapsedims`: 11 `bl` and 11 `pt`. None of them accepts: the real product
        graphs have little or no vacant room.
      - So 16 **crafted** `cr` calls were added: 2 × n zigzag (in order and in random
        order), 2 × n block, and random 3 × m placements, on each grid/cylinder context.
        Cases 2 and 4 get random edge weights so that the `dijkstra` distances do not
        tie. All 16 accept a change, with loopmax 1-3 and near-miss lists that fill.
    - **sub** (17 records): `makers` for every node and every object, and
      `getocc`/`get_occnodescomp` for every component and node. `zassign` is run on a
      random (occupied, vacant) pair.
  - `tests/test_spr.py` has 84 gate tests and 2 live `octave` tests:
    - Every call replays Octave's draws, and the queue is used up exactly.
      `currscore` matches to rtol 1e-10. The graph and `overallchange` match exactly
      (weights to 1e-10). Near-miss lists are checked with `test_swap.check_nearmisses`.
    - The subfunctions match exactly, and all `makers` branches are covered.
    - Other checks:
      - redraw-after-accept (draw count);
      - collapsedims draws only when there is room;
      - accepted graph = scored candidate;
      - inputs not mutated;
      - `debug` raises;
      - default rng;
      - `makerp` sizes;
      - KI-27 pin.
    - Live (fd env): the fixture regenerates identically, and fresh seeds
      (`seedoffset = 7918`) replay (2 passed, 8 min).
  - A mutation check confirmed that the tests catch 11 of 11 deliberate breaks:
    - no redraw after an accept;
    - no parent-edge filter;
    - the hierarchy parent kept as a target;
    - `unocc` not shrunk;
    - `<` instead of `<=` for room;
    - `getocc` keeping the own slice;
    - full `combinegraphs` instead of `zonly`;
    - no object pruning on trees;
    - last instead of first minimum;
    - `ds` recomputed after an accept. The first fixture missed this one: with equal
      weights the distances tie, which is why cases 2 and 4 now get random weights.
  - Docs: `CONVENTIONS.md` (Randomness: spr/collapsedims conventions, spy fixtures).
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 1915 passed, 52 skipped (106 s);
    - fd env non-live `test_spr`/`test_known_issues`: 116 passed.
### Blockers
- None.
### Next
- Item 26 (L4-c1: `gibbs_clean (+nearmissopts)`). All its callees are now ported:
  `swapobjclust`, `spr`, `collapsedims` and `addnearmiss`.
  - Use the same spy pattern on `gibbs_clean`, recording the draws per call.
  - The draw order across the callees must match exactly. Note that `spr` makes a
    variable number of draws, one extra per accepted change.
  - Real `collapsedims` calls rarely accept a change. For product-graph coverage of
    `gibbs_clean`, consider the crafted zigzag/block graphs of `fx_spr.m` as inputs.
  - Near-miss ties: reuse `check_nearmisses`. For `nearmissopts`, note that
    `cat(2, graph, nearmgraphs{:})` drops empty cells.

## Iteration 29 — 2026-09-29 17:51
### Completed
- Item 26 **solved** (`[x]`).
  - `src/formdiscovery/search.py` gains these functions, each citing its source lines:
    - `gibbs_clean` (`gibbs_clean.m:1-174`). MATLAB's options are keywords (`loopmax`,
      `nearmisses`, `loopeps`, `swaptypes`, `fast`, `debug`). `optlens` is accepted and
      ignored, because l.36 overwrites it. One `rng=None` is shared by all callees in
      MATLAB's call order. It returns `(ll, graph)`, and `ps` and the inputs are not
      modified. Replicated behaviour:
      - the gold-standard restore ("graph is getting worse");
      - the `ps.gibbsclean == 0` stop;
      - the three early returns at speed 5 without `fast`;
      - the extra slow score when the loop ran `loopmax` passes;
      - the near-miss rescoring loop.

      It uses the component count from the start of each pass. The near-miss list holds
      `4 * nearmisses` entries, with `None` for empty cells. `loopmax < 1` raises,
      because MATLAB leaves `ll` undefined. The `disp` calls and the dead `if 0` block
      are dropped.
    - `nearmissopts` (l.178-214). The current graph goes first and the empty cells are
      dropped (`cat(2, graph, nearmgraphs{:})`); scores get a leading 0.
    - A `graphsig` stub raises `NotImplementedError` (only reached with `ps.nauty = 1`).
  - New **KI-28** (replicate): without nauty, `nearmissopts` returns the current graph as
    entry 1, despite the l.185 comment, so every near-miss call scores it slowly again.
    `test_known_issues.py` expects KI-1..28 and pins `gibbs_clean.m:186`.
  - Fixture `tests/octave/fx_gibbs.m` → `tests/fixtures/gibbs.mat` (Octave 10.3.0,
    generated this iteration, 253 s, 2.0 MB). New helpers: `tests/octave/gibbs_spy.m` and
    `tests/octave/glc_spy.m`.
    - `gibbs_clean` is renamed to `gibbs_clean_orig` behind a forwarding spy.
    - `graph_like` is wrapped: while a spied call runs, every slow (`ps.fast == 0`) call
      is recorded (input graph, logI, output graph).
    - There are 7 speed-54 runs with run_baseline.m's settings: chain × demo_chain_feat,
      tree × demo_tree_feat, ring × demo_ring_feat, cylinder × demo_ring_feat,
      grid × synthgrid, dirring × demo_ring_rel_bin and
      undirhierarchy × demo_hierarchy_rel_bin. The 5 runs that have a baseline reproduce
      it exactly.
    - 127 records:
      - `bl` (61): real calls, the first 2 per mode and run plus up to 2 more that
        changed the graph;
      - `pt` (61): the same call on a graph with 1-3 random object moves, with seeded
        draws;
      - `g0` (5): speed 4 with `ps.gibbsclean = 0`.

      Modes: speed 5 with fast 1 and 0, the relational `swaptypes` `[1 0 0 0 0]` and
      `[0 1 0 0 0]`; speed 4 with fast 1, fast 0, and `'nearmisses', 10`. 77 records
      change the graph.
  - `tests/test_gibbs.py` has 126 gate tests, 16 `slow` tests (the synthgrid calls that
    take 2-29 s each in Python) and 2 live `octave` tests:
    - **Speed 5** (82 records): the draws are replayed and used up exactly, `ll` matches
      to rtol 1e-10 and the graph matches exactly.
    - **Speed 4, oracle** (45 records): `likelihood.graph_like` is monkeypatched so that
      each slow call returns Octave's recorded result, after checking that its input
      graph equals Octave's. Every record then matches exactly: the same slow calls in
      the same order, all of them used, the draws used up, `ll` and the graph.
    - **Speed 4, Python optimizer** (scipy): 33 of the 34 gate records replay. On call 12
      (chain) a slightly different optimum flips an accept decision, and the draws then
      differ. `ll` is within `LOGI_RTOL` (the largest difference is 9e-5 rel, and Python
      is usually higher). 29 of the 33 give Octave's graph; the other 4 are tree
      near-miss calls. On synthgrid (slow test), 1 of 7 fails to replay and 1 graph
      differs.
    - Other checks:
      - `nearmissopts`: empty cells dropped, current graph first, stops at the end of the
        list, cut to `nearmisses`;
      - `ps.nauty = 1` raises `NotImplementedError`;
      - slow-call counts, including the KI-28 re-score;
      - an unsimplified input (a dangling empty node) replays to Octave's result;
      - "graph is getting worse": pass 2's slow score is made worse on purpose, and the
        best graph is restored and scored once more;
      - speed-5 `ll` equals the fast score of the returned graph;
      - `optlens` is ignored;
      - `loopmax = 0` raises;
      - inputs not mutated;
      - default rng.
    - Live (fd env, 2 passed, 9.8 min): the fixture regenerates identically, and fresh
      seeds (`seedoffset = 7918`) replay on every record that is not heavy (speed 4
      through the oracle).
  - A mutation check confirmed that the tests catch 10 of 10 deliberate breaks:
    - no early return after the component swaps;
    - `spr` run in fast mode;
    - current graph left out of `nearmissopts`;
    - `collapsedims` skipped;
    - no final slow score after `loopmax` passes;
    - no gold restore;
    - `gibbsclean` ignored;
    - any near miss accepted;
    - no initial `simplify_graph`;
    - `loopmax` not passed to the callees.

    The first run missed two of them: the gold restore and the missing
    `simplify_graph`. The fixture never takes the restore branch, and the recorded
    inputs are already simplified. The last two targeted tests above were added for
    these.
  - Docs:
    - `CONVENTIONS.md` (Randomness): the gibbs_clean conventions, the speed-4 oracle
      pattern and the spy list;
    - `KNOWN_ISSUES.md`: KI-28.
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 2042 passed, 54 skipped (129 s);
    - base `-m slow tests/test_gibbs.py`: 16 passed (4 min).
### Blockers
- None.
### Next
- Item 27 (L4-c2: `structurefit (+bestsplit, graphscorenoopt, optimizebranches,
  optimizedepth)`).
  - All of `gibbs_clean`'s callees and `gibbs_clean` itself are now ported.
    `structurefit` itself calls slow `graph_like` (`optimizebranches`, `graphscorenoopt`,
    and `optimizedepth` at speeds 4/5), so the `glc_spy.m` oracle pattern (record the
    slow calls, inject them in Python) should carry over to exact growth-history parity.
    The Python optimizer can then be checked separately with tolerances.
  - Tied split candidates (item 23 note, bl 0) can still make the choices diverge:
    compare with the oracle and a tie-aware check.

## Iteration 30 — 2026-09-29 18:30
### Completed
- Item 27 **solved** (`[x]`).
  - `src/formdiscovery/search.py` gains these functions, each citing its source lines:
    - `structurefit` (`structurefit.m:1-213`):
      `structurefit(data, ps, graph=None, savefile=None, callback=None, rng=None)`
      returns `(ll, graph, bestgraphlls, bestgraph)`. One `rng` is shared by all callees
      in MATLAB's call order. It covers:
      - the speed-5 heuristics (optimise then fast-score at depth < 10, the
        current-graph and best-split fallbacks, the slow `gibbs_clean`,
        `optimizedepth`);
      - the speed 1-4 branch (`optimizedepth` at speed 4, slow `gibbs_clean`, 10 near
        misses);
      - the relational two-pass fast cleaning;
      - the product-graph vacant-neighbour moves (`hist` via `hist_centres`);
      - the `m == -inf` fallback.

      MATLAB's per-depth cell arrays become dicts keyed by `(i, c, pind)`.
    - `bestsplit` (l.216-242), which keeps KI-4 and raises if the stale `pind` is not 1.
    - `optimizedepth` (l.263-290).
    - `graphscorenoopt` (l.246-250) and `optimizebranches` (l.255-259).
  - **Deviation (planned):** `save(savefile, ...)` becomes optional. With `savefile`, a
    `.mat` file (`.mat` appended as MATLAB does; Octave does not append it) is written
    after each accepted depth, and `callback(bestgraphlls, bestgraph)` is called at the
    same points. The `disp` lines and the display blocks are dropped, and `part` is not
    kept (KI-3).
  - `KNOWN_ISSUES.md`: the KI-3 and KI-4 pins now exist (no new KI).
  - Fixture `tests/octave/fx_structurefit.m` → `tests/fixtures/structurefit.mat` (Octave
    10.3.0, generated this iteration, 19 s, 548 KB). New helpers:
    - `tests/octave/sf_spy.m` (structurefit spy);
    - `tests/octave/cns_spy.m` (records every `choose_node_split` call: arguments, `ll`
      and graph);
    - `glc_spy.m` (from item 26) records the slow `graph_like` calls.
    - Runs:
      - 5 runs with run_baseline.m's settings (speed 54): chain × demo_chain_feat,
        ring × demo_ring_feat, tree × demo_tree_feat (incl. the root-removal pass),
        cylinder × demo_ring_feat and dirring × demo_ring_rel_bin;
      - a speed-4 chain × demo_chain_feat run (growth from the empty graph through the
        speed 1-4 branch).

      The 4 runs that have a baseline reproduce it exactly.
    - 25 records: 21 real calls (`bl`, every call of the runs) and 4 crafted ones
      (`cr`). The real runs never try a vacant-neighbour move, so the crafted calls
      provide them:
      - a 2 × 3 cylinder with objects on two cells;
      - the grown cylinder with its chain dimension extended by a one-object node and a
        vacant node;

      each at speeds 5 and 4. The records hold 26 growth steps in total. The growth
      history saved by Octave equals the returned one.
  - `tests/test_structurefit.py` has 41 gate tests, 1 `slow` test and 2 live `octave`
    tests:
    - **Exact replay** (`test_growth_history_matches_octave`, all 25 records): the
      draws are replayed and used up exactly, and slow scores come from Octave
      (`test_gibbs.Oracle` checks each input graph). Every record matches: `ll` to
      rtol 1e-10, the final graph, `bestgraphlls` and every `bestgraph` entry. The
      target run, chain × demo_chain_feat (3 depths at speed 5), is also checked
      separately (`test_demo_chain_feat_chain`).
    - **Ties.** As item 23 predicted, the first split of chain × demo_chain_feat is a
      mirror-image tie, and Python picks the other child order. So is the first split
      of the cylinder run. There is also one pair of mirror-image near misses (slow
      scores equal to 2e-12) that `nearmissopts` passes to the slow scorer in the other
      order. The tests use two rules:
      - `SplitOracle` checks each `choose_node_split` call against Octave's (arguments,
        `ll`). If the graph differs, Octave's graph must be one of Python's `best_split`
        candidates tied to `TIE_RTOL`, and that candidate is used.
      - `TieOracle` lets a slow request take a later unused record whose slow score
        ties with the expected one.

      In the committed fixture the rules are needed 4 times (calls 0, 13 and 18 ×2).
      `test_ties_are_rare` bounds that.
    - **Python optimizer** (scipy): on the target run (speed 5 call 0 and speed 4
      call 18) the draws replay to the end, the score and growth history are within
      1e-6 rel of Octave's, and every graph has Octave's structure. On all 25 records
      (slow test), 14 replay to the end (all within 3e-6 rel, same structure). In the
      others a slightly different optimum changes a decision, and the draws differ.
    - Other checks:
      - `bestsplit`: first strict maximum, default `(0, 0, 1)`, product entries, and
        the KI-4 raise (and no raise when nothing reads the stale `pind`);
      - `optimizedepth` includes the product entries;
      - no splits possible (`-inf` everywhere): the current graph goes to the cleaning
        pass;
      - `savefile` and `callback`: the `.mat` file matches Octave's history when read
        back, and nothing is written without them;
      - inputs are not mutated;
      - the default rng runs;
      - `graphscorenoopt` does not modify `ps`.
    - Live (fd env): the fixture regenerates identically, and fresh seeds
      (`seedoffset = 7918`) replay exactly on every record (77 passed, with
      `test_known_issues`, 66 s).
  - A mutation check confirmed that the tests catch 12 of 13 deliberate breaks:
    - `>=` in `bestsplit`;
    - no initial fast score at speed 5;
    - `depth < 2`;
    - no current-graph heuristic;
    - no `optimizedepth` at speed 5;
    - relational data cleaned like feature data;
    - no speed-4 optimisation of the best split;
    - no near-miss pass;
    - vacant moves from one-object nodes;
    - fast cleaning with `loopmax 1`;
    - `loopeps = 1e-3`;
    - product entries skipped in `optimizedepth`.

    The first run missed the last two. The crafted records and
    `test_optimizedepth_includes_product_entries` were added for them. The missed break
    stores `-inf` instead of `currprob` in the `m == -inf` fallback. It is equivalent:
    that value is always overwritten (`gibbs_clean`, l.78) before it is compared.
  - Docs: `CONVENTIONS.md` (Randomness: the structurefit conventions, the two tie rules,
    the spy list).
  - Gate: base `python -m pytest -q -m "not slow"`: 2083 passed, 56 skipped (142 s).
### Blockers
- None.
### Next
- Item 28 (L5-a: `runmodel (+brlencases)` → `run.py`). `structurefit` takes
  `savefile=`, which replaces runmodel's `growthhistory<init><speed>` names under an
  explicit `outdir`.
  - To reproduce the baseline runs, the `fx_structurefit.m` pattern should carry over:
    record every slow call and every `choose_node_split` call for the whole run, then
    replay with `SplitOracle` and `TieOracle`.
  - Also port the speed-5 "true score" step (runmodel.m:174-179) and the tree
    root-removal pass.
  - Without the oracle, scipy's optimizer diverges on about 40% of the calls, so compare
    the end-to-end Python optimizer runs by score (item 29, PLAN §7.1).

## Iteration 31 — 2026-09-29 18:57
### Completed
- Item 28 **solved** (`[x]`).
  - New `src/formdiscovery/run.py`. Each function cites its source lines:
    - `runmodel` (`runmodel.m:1-193`):
      `runmodel(ps, sind, dind, rind, outdir=None, rng=None)` takes 0-based `sind`/`dind`
      and returns `(ll, graph, names, bestglls, bestgraph)`. One `rng` is shared by all
      callees, nested runs included. It covers:
      - data and names loading (missing names → `'1'..'n'`), `setrunps`, `scaledata`;
      - the `ps.outsideinit` start graph (only the `graph` variable is read);
      - relational `'overd'` init through `relgraphinit`. The `'external'` init (ASCII
        `_bestz` file) is ported but untested: the release has no such files;
      - `overrideSS`, `cleanstrong = 0`, `structcounts`;
      - `griddimsearch`/`cyldimsearchring`/`cyldimsearchchain` (a nested speed-5 run,
        then a one-node second dimension and `combinegraphs` with the nested `ps`);
      - speeds 1-5 and 54 (unknown → raises `'Unknown speed value'`);
      - the tree root-removal pass;
      - the speed-5 true score (`graph_like` slow + `graph_prior`).
    - `brlencases` (l.198-234): all four `init` schedules with MATLAB's file names. The
      returned `ps` keeps the untied flags. An unknown `init` raises (MATLAB leaves `ll`
      undefined). Replicated quirk: `'ext'` stores its first history in `bestgraph{1}`
      (linear index, l.208).
    - The `{stage, speed}` history cells are 2-D object arrays grown as MATLAB grows
      cells, with `None` for empty cells (`_cellset`, `_cellset_linear`).
  - **Deviation (planned):** an explicit `outdir` replaces `mkdir`/`cd`. With it the
    histories go to `<outdir>/results/<struct>out/<data><rind>/growthhistory<stage><speed>.mat`
    (`run_dir`), and the nested dimension-search runs use the run directory as their
    base, as MATLAB's relative `mkdir` does. Without it nothing is written. The
    `display`/`disp` lines and the figures are dropped.
  - New **KI-29** (replicate): `cyldimsearchring` runs `runmodel(ps, 3, ...)`, and
    `ps.structures{3}` is `order`, not `ring`. So the nested search grows an order
    (Octave saves it under `results/orderout/`), which is then relabelled `ring`.
    `test_known_issues.py` expects KI-1..29 and pins `runmodel.m:109`. The KI-11 pin now
    points to `test_runmodel.py`.
  - Fixture `tests/octave/fx_runmodel.m` → `tests/fixtures/runmodel.mat` (Octave 10.3.0,
    generated this iteration, 49 s, 1.1 MB).
    - `graph_like` (`glc_spy.m`) and `choose_node_split` (`cns_spy.m`) are wrapped for
      the whole run, and every draw of the run is logged.
    - 21 whole runs:
      - the 9 feature baselines (chain/ring/tree × demos 1-3, speed 54, intext);
      - 2 relational baselines (dirring × demo_ring_rel_bin with `relgraphinit`,
        partition × demo_hierarchy_rel_bin);
      - speed 5 on chain and tree (true score, root removal);
      - `init` `none`/`ext`/`int`;
      - `griddimsearch` at speeds 54 and 5, `cyldimsearchring` at 54,
        `cyldimsearchchain` at 5 (appended to `ps.structures`);
      - an `outsideinit` start graph.
    - The 11 runs that have a baseline reproduce it exactly. Each record also keeps the
      growth-history files written under the run directory and their contents.
  - `tests/test_runmodel.py` has 33 gate tests, 1 `slow` test and 2 live `octave` tests:
    - **Exact replay of all 21 runs**: the draws are replayed and used up. Octave's slow
      scores are injected (`TieOracle`), tied splits are accepted (`SplitOracle`), and
      Octave's scaled feature data are used. `ll` matches to rtol 1e-10, and the graph,
      names, both history cells (shape and every entry) and the set of growth-history
      files and their `bestgraphlls` all match.
    - The tie rules are needed 11 times in 8 runs (bounded by `test_ties_are_rare`).
    - Other checks:
      - the `ext` linear-index quirk;
      - `_cellset` growth;
      - KI-29 (the nested run is `order`, components `ring × chain`);
      - unknown speed/init raise;
      - no `outdir` → no files;
      - a preset `cleanstrong = 1` is reset;
      - `ps` not mutated;
      - `brlencases` stage names and flags;
      - the default rng.
    - Slow: scipy's optimizer on chain × demo_chain_feat at speed 5. It replays to the
      end, within `LOGI_RTOL`, with Octave's structure.
    - Live (fd env, 2 passed, 112 s): the fixture regenerates identically, and fresh
      seeds (`seedoffset = 7918`) replay exactly on all 21 runs.
  - A mutation check confirmed that the tests catch 13 of 13 deliberate breaks:
    - no true score;
    - true score without the prior;
    - `init` kept at speed 4;
    - no root removal;
    - `ext` quirk fixed;
    - `cyldimsearchring` using ring;
    - no `cleanstrong = 0`;
    - no `overd` init;
    - `intext` stage order swapped;
    - wrong type for the second dimension;
    - `outsideinit` ignored;
    - `griddimsearch` without `fixedall`;
    - 0-based default names.

    The first run missed the `cleanstrong` break (the default is `None`).
    `test_cleanstrong_reset` was added for it.
  - Docs:
    - `CONVENTIONS.md`: the runmodel conventions and the spy list;
    - `KNOWN_ISSUES.md`: KI-29 and the KI-11 pin.
  - Gate:
    - base `python -m pytest -q -m "not slow"`: 2117 passed, 58 skipped (175 s);
    - base `-m slow tests/test_runmodel.py`: 1 passed.
### Blockers
- None.
### Next
- Item 29 (L5-b: `masterrun` → CLI `formdiscovery run`).
  - `run.runmodel` is the per-run building block. masterrun seeds `rand('state', rind)`
    per run, stores `pss{sind,dind,rind} = ps` (the outer `ps`, not runmodel's), and
    stores `llhistory` = runmodel's `bestglls` cell.
  - End-to-end: without the oracle, compare by score, cluster count and ARI (PLAN §7.1).
    With replay, `tests/fixtures/runmodel.mat` already holds all 9 feature baseline
    runs with their draws.

## Iteration 32 — 2026-09-29 19:16
### Completed
- Item 29 **solved** (`[x]`).
  - `src/formdiscovery/run.py` gains the following, each citing its source lines:
    - `masterrun` (`masterrun.m:1-81`):
      `masterrun(ps=None, thisstruct=(1, 3, 5), thisdata=(0, 1, 2), repeats=1,
      extraspairs=(), extradpairs=(), outdir=None, masterfile='resultsdemo', rng=None,
      seed=1, log=None)` returns a `MasterResults`.
      - `modellike`, `structure`, `pss` and `llhistory` are 3-D `[sind, dind, rind - 1]`
        and grow as MATLAB grows them (0 fill / `None`). `names` is `1 x D`.
      - `pss` holds masterrun's own `ps`, not runmodel's.
    - `masterrun_ps` (l.12-25: `reloutsideinit = 'overd'`; the neato probe and the figures
      are dropped).
    - `masterrun_pairs` (l.52-56: the structures vary fastest, the extra pairs come first).
    - `graph_summary`: `nclusters` = distinct `z`, `nnodes`, `z`.
    - `save_results`/`load_results`: `<masterfile>.npz` holds `modellike` and, per run,
      `z`, `adj`, `W` and the history cells. `<masterfile>.json` holds the per-run summary
      (names, 0-based `sind`/`dind`, `rind`, `seed`, `ll`, cluster counts, `z`, `ps`
      scalars).
    - Seeding: `rand('state', rind)` becomes `NumpyPermutations(seed + rind - 1)`. A
      provider (or an int) passed as `rng` is one stream shared by all runs, which is what
      replay uses. A callable gets `rind`.
    - Replicated behaviour (l.62-65): an existing masterfile is loaded and merged before
      each store. The retry/`pause` loop and the `disp` are dropped (`log=` gets the text).
  - New CLI `src/formdiscovery/cli.py` + `__main__.py`, and `[project.scripts]
    formdiscovery` in `pyproject.toml`:
    `formdiscovery run --structures chain,ring,tree --datasets 1,2,3 --seed 1 --out results/`
    (plus `--repeats`, `--speed`, `--masterfile`, `-q`). The lists take names or MATLAB's
    1-based indices. It writes the `.npz` + `.json` pair and runmodel's growth histories
    under `<out>/results/`.
  - Fixture `tests/octave/fx_masterrun.m` → `tests/fixtures/masterrun.mat` (Octave 10.3.0,
    generated this iteration, 26 s, 556 KB). It runs the **unmodified** `masterrun.m` script
    in a temporary directory:
    - a verbatim copy is called by name. A first attempt with Octave's `run()` `cd`'d into
      the source directory and wrote `results/` and `resultsdemo.mat` there; both were
      deleted, and the source tree is clean;
    - a `system.m` shim answers `which neato` with "not found", which keeps it headless;
    - a `data` symlink serves setps's pwd-relative `dlocs`;
    - `glc_spy`/`cns_spy` and the randperm log run for the whole script (645 slow calls,
      400 splits).

    The 9 scores reproduce the feature baseline exactly. The fixture keeps the contents of
    masterrun's own `resultsdemo.mat` and the growth-history file list.
  - `tests/test_masterrun.py` has 19 gate tests, 1 `slow` test and 1 live `octave` test:
    - **Replay** (whole script, 6 s): one `ReplayPermutations` for all 9 runs, used up
      exactly, plus `SplitOracle`/`TieOracle` (4 ties) and Octave's scaled data. The
      following match: `modellike` (rtol 1e-10), every final graph, `names`, every
      `llhistory` cell, the empty cells, `pss` (masterrun's ps, input not mutated), and the
      growth-history file set. The §7.1 criteria (1e-3 rel, cluster count, ARI = 1) pass,
      and the saved `.npz`/`.json` read back identically.
    - Other checks: pair order and extras, per-run seeds (and shared/callable/int `rng`),
      the masterfile merge (including replacing a pair), no `outdir` → no files,
      `graph_summary`, empty results, ARI (vs sklearn), and the CLI (list parsing, a
      relational run with seed 3 equal to the API, errors, `python -m formdiscovery run
      --help`).
    - **Slow, no replay** (scipy optimizer, numpy permutations, seeds 1-3; 2.0 min): every
      pair and seed has Octave's cluster count and ARI = 1. The score is within 7.4e-6 rel
      of Octave's (worst: tree × demo_chain_feat), against the 1e-3 criterion.
    - Live (fd env, 28 s): the fixture regenerates identically (draws, `modellike`,
      graphs).
  - A mutation check confirmed that the tests catch 7 of 7 deliberate breaks: pair order,
    per-run seed, no merge, `pss` not copied, extras dropped, names not stored, and an int
    `rng` not shared. The first run missed the last one, and a check was added for it.
  - Docs: `CONVENTIONS.md` (the masterrun conventions, `fx_masterrun.m` in the spy list).
    No new KI.
  - Gate: base `python -m pytest -q -m "not slow"`: 2136 passed, 59 skipped (185 s).
### Blockers
- None.
### Next
- Item 30 (paper-level checks and property tests, all `slow`). `run.masterrun(ps,
  thisstruct, thisdata)` is the driver:
  - synthetic sets: structures `[0, 1, 3, 5, 6]` × data `7..11` (1-based; 0-based
    `6..10`);
  - animals/colors: data 12 and 14 (1-based).
  - Each Python feature run takes about 2-3 s on the demos; the synthetic sets
    (40 × 2000) will be much slower, so time one first.

## Iteration 33 — 2026-09-29 19:37
### Completed
- Item 30 **solved** (`[x]`).
  - New `tests/test_properties.py` (PLAN §7.3; 20 tests, all `slow`, 3 s). It uses
    hypothesis, 200 derandomized examples per property. `random_graph` builds a graph
    from `makeemptygraph`, random `split_node` calls, random weights and random object
    moves (average 12 cluster nodes; `simplify_graph` changes 241 of 300 samples).
    - `simplify_graph` is idempotent (`cleanstrong` 0/1, 9 feature forms).
    - `combinegraphs` (with and without `zonly`) keeps `objcount`, and each object has
      exactly one leaf edge, to its `z`; `compinds[z]` equals the component `z`.
    - The likelihood is invariant under relabelling (rtol 1e-9, fast mode). The objects
      are permuted in the raw data *before* `scaledata`, because `ps.runps.SS` is what the
      likelihood reads. Covered: feature (demo chain/tree, animals), similarity (colors)
      and relational (3 relational demos × 10 forms) data, plus one slow-mode case (rtol
      1e-6).
    - `graph_prior`:
      - for the 8 single-component families, `sum_k P(k) <= 1`, and they are normalised
        over all structures (the `structcounts.m` counts);
      - PLAN's weaker `sum_k P(k) <= 1` is **false for grid/cylinder** (nobj = 2:
        1.0024), because `gridpriors.m` gives weight to impossible node counts, as its own
        comment says. It is not a bug: grid/cylinder are checked for normalisation over
        k × l shapes instead.
    - Mutation check: 3 of 3 caught (a one-pass `simplify_graph`, a precision matrix that
      depends on object order, a relational `countmatrix` that drops object 0).
  - New `tests/test_paperlevel.py` (PLAN §7.2; 18 `slow` tests + 1 live `octave` test).
    - Fixture: `tests/octave/fx_paperlevel.m` → `tests/fixtures/paperlevel.mat` (Octave
      10.3.0, generated this iteration, 180 KB). New tool `tools/gen_paperlevel.py` runs
      the 45 jobs in parallel Octave processes (434 s on 32 cores) and merges them with
      `tests/octave/paperlevel_merge.m`. `tools/gen_fixtures.py paperlevel` also works,
      serially.
    - Jobs:
      - the 5 synthetic sets × {partition, chain, ring, tree, grid} at **speed 5**. The
        default 54 adds a speed-4 pass that is several times slower on 40 × 2000 data;
        speed 5 still ends with runmodel's slow true score;
      - animals and colors × the 8 feature forms at speed 54;
      - animals × {tree, hierarchy} with seeds 2 and 3.
    - Python runs all 45 in a spawn process pool (one BLAS thread each; about 10 min, the
      longest being grid × synthring).
    - Results:
      - every synthetic set recovers its true form, in Octave and in Python;
      - colors → ring in both.
    - **Finding, new KI-30 (paper vs code):** on animals the original code picks the
      **hierarchy**, not the paper's tree.
      - Octave's best hierarchy scores -3220.62; its best tree scores -3223.30.
      - With seed 1, Octave's tree search also stops early, at -3231.95.
      - Python's own searches end with tree -3223.33 against hierarchy -3223.49, so the
        tree wins there by 0.16.
      - Scoring is not the cause: Python scores each of Octave's final animals/colors
        graphs within 1.04e-4 rel (`test_python_rescores_octave_graphs`). With Octave's
        graphs, Python also ranks hierarchy first.
      - Tests pin: Octave picks hierarchy with tree second, less than 3 nats behind.
        Python has {tree, hierarchy} as its top two.
    - Score parity, no replay: 33 of 45 runs are within 1e-3 rel with the same cluster
      count (§7.1). The other 12 end in different local optima and are listed in
      `DIVERGENT`, which the test keeps exact: grid on synthchain/synthring/synthgrid/animals,
      cylinder on animals/colors, synthgrid ring/chain/tree, and animals tree (seeds 1-2) and hierarchy (seed 3). All
      are within 2e-2 rel; the worst is colors × cylinder (1.5e-2, Python better).
    - Live (fd env, 23 s): jobs 26, 34 and 35 regenerate in Octave identically (`ll` and
      graph).
  - `KNOWN_ISSUES.md`: KI-30. `test_known_issues.py` now expects KI-1..30.
  - Toolchain: `hypothesis==6.168.3` pip-installed into the base interpreter, as pinned
    in `environment.yml`. Both test files use `pytest.importorskip("hypothesis")`.
  - Gate: base `python -m pytest -q -m "not slow"`: 2136 passed, 59 skipped, 76
    deselected (187 s). Base `-m slow` on the two new files: 38 passed (621 s).
### Blockers
- None.
### Next
- Item 31 (Viz A1: `viz/dot.py`, `graph_to_dot` / `dot_to_graph`).
  `tests/fixtures/dot_to_graph*` already exists from item 03's `dot_to_graph.m` patch.

## Iteration 34 — 2026-09-29 20:41
### Completed
- Item 31 **solved** (`[x]`).
  - New package `src/formdiscovery/viz/` with `dot.py`. Each function cites its source
    lines:
    - `graph_to_dot(adj, node_label=None, arc_label=None, width=10, height=10,
      leftright=0, directed=1, filename=None) -> str` (`graph_to_dot.m:1-85`). It returns
      the text and writes it only when `filename` is given. `arc_label` is a 2-D sequence
      (`None` = empty cell) or a dict.
    - `dot_to_graph(text) -> (adj, labels, x, y)` (`dot_to_graph.m:1-114`, Octave-patched
      copy) and `dot_to_graph_file(path)`. It replicates `char` padding, the edge scan,
      the position carry-over (KI-7), substring label matching (KI-8), `sscanf`'s
      `' pos  = "%f,%f"'` and the normalisation. It warns when there are no coordinates,
      and raises as Octave does (no `graph ` → `ValueError`, short `pos` → `IndexError`,
      no edges → `ValueError`).
    - `adj_is_directed` (`draw_dot.m:35`).
  - Fixture `tests/octave/fx_viz_dot.m` → `tests/fixtures/viz_dot.mat` (Octave 10.3.0,
    generated this iteration, 5 s).
    - `bl_*`: the **unmodified `draw_dot(adj, names)`** runs on 74 graphs: the true `adj`
      of the 11 data sets that store one (runmodel.m:45), plus every final baseline graph
      (9 feature + 54 relational). A `graph_draw` shim (`tests/octave/drawdot_shim/`,
      added to the path only by this fixture) records the temporary `_GtDout.dot` and
      `_LAYout.dot` texts and the X/Y that draw_dot passes on. Octave's `dot_to_graph` of
      each layout is saved. neato is the fd env's Graphviz 14.1.2, put first on `PATH`.
    - `go_*`: 15 `graph_to_dot` option variants (node/arc labels, width/height including
      10.5 and 1/3, leftright, directed 0/1, no edges, weighted adj, and the undirected +
      arc_label error).
    - `cr_*`: 16 crafted DOT texts (chained and mixed `--`/`->` edges, no coordinates,
      substring labels in both orders, zero and signed/exponent coordinates, comments,
      CRLF, blank lines, a short `pos`, no `graph `, no edges).
  - `tests/test_viz_dot.py` has 200 gate tests and 1 live `octave` test:
    - byte parity of the DOT text on all 74 draw_dot graphs. It is exact, so the
      whitespace normalisation PLAN allows is not needed. The final `graph.adj` of the
      baselines is always directed, and 8 of the 11 true graphs give undirected text;
    - exact parse parity (adj, labels, x, y with `assert_array_equal`) on the 74 neato
      layouts, the 6 layouts of `dot_to_graph.mat` (item 03), and the crafted texts
      (errors and warnings included). draw_dot's `xret/yret` start with those `x/y`;
    - the option variants and their written files;
    - pins for KI-7, KI-8 and KI-31..34, plus `_sscanf_pos`, Octave's `%d`, and a round
      trip through graph_to_dot.
    - Live (fd env, 80 s): the fixture regenerates identically.
  - A mutation check confirmed that the tests catch 13 of 14 deliberate breaks: no
    padding, no `+1` in `x`, whole-name matching, no carry-over, undirected full row, no
    blank before `;`, `--` not symmetric, arrows before dashes, `+1` in `y`, no `x == 0`
    check, `left_bound` not advanced, no first-line check, comments kept.
    - The first run missed the arrows-first break; a mixed-line crafted case was added.
    - The one miss, `%g` for integer sizes, only differs at 10^6 or more; a check was
      added.
    - A stale `.pyc` (mutation and restore in the same second with the same size) gave a
      false result once. The loop was rerun with `PYTHONDONTWRITEBYTECODE` and a cleared
      `__pycache__`.
  - **Findings (new KI-31..34, ANOMALIES A9 and A10):**
    - **KI-31**: `graph_to_dot.m:50` has a `labeltext` typo, so an undirected graph with
      arc labels crashes. Replicated: `NameError`, after the partial file is written.
    - **KI-32**: `draw_dot.m:46-47` glue `-Gregular` and `-Gminlen=5` into one flag, and
      every layout carries `"regular-Gminlen"=5`. Neither `regular` nor `minlen` is ever
      applied, though PLAN §6 lists both. Item 32 must pass the same attributes to match
      the layouts.
    - **KI-33**: the right node keeps its `;` unless its line is the longest (`char`
      padding + `length(line)-1`). Not reached on neato output.
    - **KI-34**: `x` is divided by range + 1, `y` by range.
    - **A10**: Octave prints `%d` of 10.5 as `10.5`, MATLAB as `1.050000e+01`. Python
      follows Octave. draw_dot only uses 10,10, so drawn graphs are unaffected.
  - Docs:
    - `KNOWN_ISSUES.md`: KI-31..34, and the KI-7/KI-8 pins now exist.
      `test_known_issues.py` expects KI-1..34 and pins the new lines;
    - `ANOMALIES.md`: A9, A10;
    - `CONVENTIONS.md`: a new Display section.
  - Gate: base `python -m pytest -q -m "not slow"`: 2340 passed, 60 skipped, 76
    deselected (186 s).
### Blockers
- None.
### Next
- Item 32 (Viz A2: pygraphviz backend, `viz/draw.py` facade, CLI `formdiscovery draw`).
  - `viz_dot.mat` already holds, for all 74 graphs, draw_dot's `xret/yret` and the `X/Y`
    passed to `graph_draw`. These are the targets for porting draw_dot l.52-67:
    singletons at 0.05, the `sort(num_names)` reordering, and the `pos` override.
  - Decide KI-32 for the backend: replicate the glued `regular-Gminlen` attribute by
    default (layout parity with Octave's neato call), with an option for the intended
    flags.
  - `-x` applies for n > 100 (the largest graph in the fixture has 89 nodes).

## Iteration 35 — 2026-09-29 21:02
### Completed
- Item 32 **solved** (`[x]`).
  - New modules. Each function cites its source lines:
    - `viz/pygraphviz_backend.py`: `neato_attrs`/`neato_args` (draw_dot.m:44-50),
      `neato_layout`/`layout_text` (l.33-50), `find_neato` and `render` (Graphviz-only
      PNG/SVG/PDF, the PLAN's `.draw(path)`).
      - Engines: `'pygraphviz'`, `'cli'` (the neato executable, as draw_dot runs it) and
        `'auto'`.
      - `flags='matlab'` (default) passes draw_dot's glued attributes (KI-32, new KI-35).
        `flags='intended'` passes `regular`, `minlen=5` and `-x`.
    - `viz/graph_draw.py`: `graph_draw.m` with matplotlib. The pure geometry functions
      are `node_colors`, `oval_halfwidths`/`box_halfwidths`/`node_halfwidths`,
      `edge_segments` and `arrow_head`. `text_extents` measures the labels, and
      `graph_draw` draws 61-point ellipse patches, grey self-loop nodes and `my_arrow`
      heads (5 pt, 12°). `undirected='arrows'|'lines'`, and `wd=` overrides the
      half-widths.
    - `viz/draw.py`:
      - `draw_dot(adj, labels=None, backend='pygraphviz', *, pos, nodemult, fontsz, ax,
        flags, engine, undirected, wd)` returns MATLAB's `(xret, yret, labels)`;
      - `dot_positions` (l.52-72: singletons at 0.05, sorted by node number, `pos`);
      - `default_fontsize`, `pad_names`;
      - `ProgressFigures`, a show callback for figures 1/2/3, live and/or as numbered
        files, with `enable(ps)`;
      - `draw_results` (a results file, one panel per run).
  - Progress callbacks in the model code: `search.show_graph`, `sprintf_g` and `num2str`
    (Octave's rule). An optional `show(event, adj, names, title)` is called where MATLAB
    draws, gated by the `ps.show*` flags, with MATLAB's padding and titles:
    - `truegraph` and `inferredgraph` in `runmodel` (figures 1 and 3);
    - `preclean` and `postclean` in `structurefit` (figures 1 and 2);
    - `bestsplit` in `best_split` (figure 3).

    `show=` goes through `masterrun`, `runmodel`, `brlencases`, `structurefit`,
    `choose_node_split` and `best_split`. Existing calls are unchanged. The test fakes
    (`SplitOracle`, the `test_masterrun`/`test_runmodel` fakes and `replay`) accept
    `show`.
  - CLI:
    - `formdiscovery draw RESULTS --out fig.png [--runs 0,2] [--flags] [--undirected]
      [--graphviz]`;
    - `formdiscovery run ... --figures DIR` turns on masterrun's two figures
      (`showpostclean`, `showinferredgraph`, masterrun.m:17-21) and saves them.
  - Fixtures (Octave 10.3.0, generated this iteration):
    - `tests/octave/fx_viz_draw.m` → `tests/fixtures/viz_draw.mat` (12 s). **graph_draw.m
      cannot run in Octave** (new KI-36, A11): it uses `'VerticalAlign'` and reads
      `WarpToFill`/`Xform`. The fixture writes a temporary copy with three edits whose
      counts are asserted: the property name; the two `my_arrow` calls replaced by
      `tests/octave/graphdraw_shim/gd_arrow_rec.m`; and a recorder of
      x/y/labels/fontsize/nodemult/color/wd plus the `.dot` texts. The source is
      untouched.
      - The real `draw_dot` runs on 83 graphs: the 74 of `viz_dot.mat`, labelled as
        runmodel labels them, plus no labels, singletons, self-loops, `pos`, `nodemult`,
        `fontsz`, undirected, `' '` padding and a 105-node chain.
      - There are also 5 direct `graph_draw` calls: default labels, boxes, weights ≠ 1,
        vertical edges and coincident nodes.
    - `tests/octave/fx_viz_progress.m` → `tests/fixtures/viz_progress.mat` (2 s). It runs
      2 whole runmodel runs (chain × demo_chain_feat and dirring × demo_ring_rel_bin,
      speed 54) with every `ps.show*` flag on. `tests/octave/progress_shim/` shadows
      `figure`/`clf`/`title`/`drawnow`/`draw_dot` to log the display calls (34 and 9
      drawings). The draws and spies are recorded for replay, as in `fx_runmodel.m`.
  - `tests/test_viz_draw.py` has 230 tests, all passing in the fd env. In the base env
    224 pass and 6 skip: the 4 pygraphviz tests and the 2 live Octave tests.
    - **Exact parity on all 83 draw_dot cases.** The `graph_to_dot` text, xret/yret, the
      X/Y given to graph_draw, labels, font size, nodemult and the node colours match
      exactly. Every arrow end point matches to 1e-14 (0 in practice), given Octave's
      `wd`. The 5 direct graph_draw calls match too.
    - **Layout parity with live Graphviz 14.1.2.** pygraphviz reproduces Octave's neato
      layout text byte for byte on 83 + 74 graphs, and the neato executable does on 83.
      In the base env the tests use the fd env's neato, found next to Octave.
    - The intended flags give identical positions for n ≤ 100: `regular` and `minlen`
      are not neato layout attributes.
    - `draw_dot` end to end on 13 graphs: outputs as Octave's, and the drawn lines equal
      Octave's arrows when `wd` is Octave's.
    - **Progress replay.** Both runs replayed with every flag on give Octave's exact
      sequence of figures, titles (`%g`/`num2str`), padded names and graphs. The one
      exception is a bestsplit graph at a tied split, where Python shows the mirror
      candidate before `SplitOracle` swaps it. The count of these is bounded by the tie
      count (1 of 1).
    - Other checks: rendering smoke tests, `ProgressFigures` files and cleared figures,
      `enable`, `draw_results`, the CLI (`draw`, `--graphviz`, `run --figures`,
      `--help`), Graphviz `render`, `find_neato` skipping a neato without the plugin, and
      engine errors.
    - Image regression: `tests/viz_images.py` has 5 cases rendered at Octave's positions.
      The baselines in `tests/baseline_images/` are the port's own renders
      (`tools/gen_viz_baselines.py`, matplotlib 3.10.9). There are two tolerance tiers:
      the text-free render is compared at RMS 2 on any matplotlib (fd's 3.11.2 gives
      ≤ 1.3); the full render at RMS 2 on 3.10.9 and 15 otherwise, because text
      anti-aliasing changed.
    - Live (fd env): both fixtures regenerate identically.
  - A mutation check confirmed that the tests catch 16 of 17 deliberate breaks. The one
    miss (`<=` → `<` in the edge sign) is an equivalent mutant: equal `x` takes the
    vertical branch first. Two misses in the first run (the true-graph name padding and
    the binarised `adj` in `layout_text`) led to two new tests.
  - **Findings (new KI-35..39, ANOMALIES A11-A14; A9 updated with the decision):**
    - **KI-35 / A12**: for n > 100, `strcat` drops the trailing blank, so draw_dot passes
      `-Goverlap=false-x`. `-x` is never applied, and neato warns about an unknown overlap
      value. Replicated.
    - **KI-36 / A11**: graph_draw cannot run in Octave. Not ported (matplotlib port); the
      fixture uses an edited copy.
    - **KI-37 / A13**: `if 0 % ckemp` disables the plain-line branch, so every undirected
      edge is two opposite arrows. Replicated by default, with `undirected='lines'` as an
      option.
    - **KI-38 / A14**: the show blocks pad runmodel's *returned* `names`, and masterrun
      turns `showinferredgraph` on when `which neato` succeeds. So MATLAB's saved names
      depend on whether Graphviz is installed. Replicated (the padding follows the flags).
    - **KI-39**: textoval/textbox index the colour list locally, so mixed node shapes
      shift the colours. Unreachable from draw_dot. Replicated.
  - Docs:
    - `KNOWN_ISSUES.md`: KI-35..39 and the KI-32 decision. `test_known_issues.py`
      expects KI-1..39 and pins the new lines;
    - `ANOMALIES.md`: A11-A14 and the A9 update;
    - `CONVENTIONS.md`: the Display section for item 32 (layout, drawing, progress
      events, image regression).
  - Gate: base `python -m pytest -q -m "not slow"`: 2570 passed, 66 skipped, 76
    deselected (189 s).
### Blockers
- None.
### Next
- Item 33 (Viz B1: networkx backend).
  - Add `'networkx'` to `viz.draw.BACKENDS` behind the same `draw_dot` facade.
  - `ProgressFigures(**draw_kw)` and `draw_results(**draw_kw)` already forward
    `backend=`.
  - `tests/viz_images.py` can take a per-backend baseline set.
  - For layout parity, `nx.nx_agraph.graphviz_layout(prog='neato')` needs pygraphviz,
    which exists only in the fd env. Pass it the same neato attributes as
    `pygraphviz_backend.neato_attrs(n, 'matlab')`.

## Iteration 36 — 2026-09-30 11:38
### Completed
- Item 33 **solved** (`[x]`).
  - New `src/formdiscovery/viz/networkx_backend.py`. Each function cites its source lines:
    - `to_networkx(graph, names=None, directed=None)`. It takes a `Graph`, a MATLAB-style
      dict or a bare matrix.
      - Nodes are the 0-based indices of `graph.adj`. Each has `kind`
        (`object`/`cluster`), `label` and `cluster_id` (`z`, or `node - objcount` for a
        cluster node).
      - Each edge has `W` and `weight = 1/W` (`inf` where `W == 0`). The graph attributes
        are `type`, `objcount` and `sigma`.
      - `directed=None` follows draw_dot.m:35, so every stored `graph.adj` gives a
        `DiGraph`. `False` gives a `Graph` with each pair once.
    - `from_networkx`, `to_graphml`/`from_graphml`, and `to_dot`/`from_dot`. `to_dot` is a
      pure-text writer: floats use `repr`, and edges carry `len = 1/W` instead of Graphviz's
      integer `weight`. `from_dot` needs pygraphviz.
    - `nx_layout(adj, layout='auto'|'neato'|'kamada_kawai', flags)`:
      - `neato` is `nx.nx_agraph.graphviz_layout` on graph_to_dot's graph with draw_dot's
        neato attributes;
      - `kamada_kawai` is deterministic and scaled to 72-point edges (see below);
      - both are normalised as `dot_to_graph.m:103-110`.
    - `draw_networkx`: `nx.draw_networkx_*` on the unit square, with grey self-loop nodes,
      no self-loop edges, and `undirected='arrows'` (KI-37) or `'lines'`.
  - Facade: `viz.draw.BACKENDS` now includes `'networkx'`, and `draw_dot(...,
    backend='networkx', layout=, node_size=)` returns MATLAB's `(xret, yret, labels)`.
    `ProgressFigures` and `draw_results` forward it. CLI: `formdiscovery draw ...
    --backend networkx [--layout kamada_kawai]`.
  - Refactors (behaviour unchanged, all item 31/32 tests still green):
    - `viz.dot.normalise_xy` is factored out of `dot_to_graph`;
    - `viz.draw.order_positions` is factored out of `dot_positions`.
  - Fixture `tests/octave/fx_viz_networkx.m` → `tests/fixtures/viz_networkx.mat` (Octave
    10.3.0, generated this iteration, <1 s, 24 KB). It holds the 63 final baseline graphs,
    and for each: `find(graph.adj)` (column-major), `W` there, `1 ./ W`, the
    `tril(adjsym)` pairs with `Wsym`, `sum(adjsym, 2)`, and `inv_covariance`'s Laplacian
    `L`.
  - `tests/test_viz_networkx.py`. In the fd env, all 540 tests pass, the live Octave test
    included. In the base env, 381 pass and 159 skip (pygraphviz):
    - conversion against Octave on all 63 graphs:
      - edges, `W` and `1/W` are exact, in row-major order;
      - kinds, labels and cluster ids match, and every object hangs off its cluster node;
      - undirected: the networkx Laplacian over `W` equals `inv_covariance`'s `L`
        (rtol 1e-12), and the degrees match.
    - round trips (adj, W, labels, kind, cluster_id, type/objcount/sigma):
      - networkx and GraphML on all 63 graphs, directed and undirected;
      - DOT through pygraphviz on all 63 graphs.
      Also checked: the DOT text structure and escaping, and that Graphviz can lay out the
      export.
    - **Layout parity:** on all 83 `viz_draw.mat` graphs, `graphviz_layout` gives Octave's
      raw neato points exactly. The normalised positions equal Octave's draw_dot
      `xret/yret` and graph_draw `X/Y` exactly on 78 graphs. The other 5 are the KI-8
      cases below, where they equal a whole-name parse. The node order equals
      `dot_to_graph`'s. With pygraphviz available, the neato positions also equal the
      pygraphviz backend's.
    - Kamada-Kawai: deterministic, in draw_dot's order, within [0.05, 0.95], and the
      Spearman correlation of hop distance to drawn distance is > 0.8.
    - The facade on 10 draw_dot cases (labels, singletons, self-loops, `pos`, `nodemult`,
      `fontsz`, `' '` padding) returns Octave's outputs, and the drawn node offsets equal
      Octave's X/Y. Also covered: artists (grey nodes, arrow/line counts), errors,
      `ProgressFigures`, `draw_results` and the CLI.
    - Image regression per backend: `tests/viz_images.py` has `render_case(...,
      backend=)`, and the new baselines are in `tests/baseline_images/networkx/`
      (`tools/gen_viz_baselines.py` writes both sets; the item 32 baselines were rewritten
      byte-identical). Tolerances are as in item 32.
  - Mutation check: the tests catch 10 of 12 deliberate breaks. The first run missed a
    column-major edge scan, and a test was added for it (undirected W taken from the first
    row-major entry). The 2 remaining misses are equivalent mutants: dropping
    `center`/`size` does not change the `-Tdot` positions, and scanning full rows for an
    undirected graph only adds duplicate edges, which networkx merges.
  - **Finding (ANOMALIES A15, KI-8 updated with measurements):** KI-8 misplaces nodes in
    **every drawing of the synthetic true graphs** (46-89 nodes, 5 of 74 real graphs).
    - Node `41`'s line also matches `4`, so node `41` (and 6 nodes in synthgrid) keeps raw
      `(0, 0)`.
    - That zero enters the min/range normalisation, so every node moves. In synthgrid, 89
      nodes are drawn at 84 distinct points.
    - The demos and baselines (at most 35 nodes) and the crafted 105-node chain are not
      affected.
    - The pygraphviz backend replicates this (parity parser). The networkx backend reads
      whole names, as KI-8's decision said. No new KI.
  - Toolchain: the `kamada_kawai` layout needed a fix. networkx returns coordinates in
    [-1, 1], and at that scale KI-34's `range + 1` divisor squeezed x threefold (the first
    test run caught it). It is now scaled to neato's 72-point edge length.
  - Docs: `ANOMALIES.md` (A15), `KNOWN_ISSUES.md` (KI-8 measurements), `CONVENTIONS.md`
    (item 33 in the Display section), and the `viz` package docstring.
  - Gate: base `python -m pytest -q -m "not slow"`: 2951 passed, 225 skipped, 76
    deselected (195 s).
### Blockers
- None.
### Next
- Item 34 (Viz B2: optional `plotly`/`pyvis` backends behind extras, the
  `examples/formdiscovery_demo.ipynb` notebook, and the README usage section).
  - New backends plug into `viz.draw.BACKENDS`/`draw_dot`.
  - `networkx_backend.to_networkx` gives the node attributes for hover text.
  - `nx_layout(..., 'kamada_kawai')` works without Graphviz.

## Iteration 37 — 2026-09-30 11:58
### Completed
- Item 34 **solved** (`[x]`).
  - New modules. Each function cites its source lines:
    - `viz/interactive.py`:
      - `edge_sets(adj, undirected)` gives graph_draw's arrows in drawing order
        (`graph_draw.m:72-94`). With `'lines'`, each symmetric pair becomes one line
        instead (KI-37);
      - `hover_text(graph, names, sep)` is built from `to_networkx`: an object shows its
        name and `cluster c`, a cluster node its members;
      - also `default_hover`, `have_plotly` and `have_pyvis`.
    - `viz/plotly_backend.py`: `draw_plotly` returns a `go.Figure` on the unit square.
      It has a `'nodes'` trace (white or grey fill, labels at `fontsz * 4/3` px, hover
      text), a `'lines'` trace and one arrow annotation per edge (tail in data
      coordinates). It also works in `make_subplots` panels (`row`/`col`).
    - `viz/pyvis_backend.py`: `draw_pyvis` returns a pyvis `Network`. The nodes are
      pinned at `(600 x, -600 y)` with physics off, so the drawing is draw_dot's layout.
      The network must be **directed**: in an undirected one, pyvis drops the second
      arrow of a symmetric pair. A user `net` that is undirected raises.
  - Facade and CLI:
    - `viz.draw.BACKENDS` now also has `'plotly'` and `'pyvis'` (`INTERACTIVE`).
      `draw_dot(..., backend='plotly'|'pyvis', layout=, hover=)` uses the networkx
      backend's layout, so neato gives draw_dot's positions. `ax` is the figure or
      network to draw into, and a matplotlib axes raises. `return_figure=True` appends
      the figure for every backend;
    - new `draw_graph(graph, names, backend, title=)`: a model graph with hover text;
    - `draw_results(..., backend='plotly')`: all runs in one interactive HTML figure.
      pyvis raises (one graph per page), and `ProgressFigures` rejects the interactive
      backends;
    - CLI: `formdiscovery draw ... --backend plotly --out f.html` (all runs), and
      `--backend pyvis --runs k` (one run).
  - Extras: `pyproject.toml` has `interactive = [plotly, pyvis]` and `notebook`.
    `environment.yml` pins plotly 5.24.1 and pyvis 0.3.2 in a pip section. Both are
    pip-installed into the fd env; the base interpreter had plotly, and pyvis 0.3.2 was
    added.
  - `examples/formdiscovery_demo.ipynb` (458 KB, executed) is generated and run by the
    new `tools/gen_demo_notebook.py` (35 s). It covers:
    - the masterrun demo end to end (chain, ring, tree × the three feature demos);
    - a Python vs Octave score table: all 9 runs within 7.4e-6 rel, and every demo picks
      its true form in both;
    - `draw_results` (matplotlib), the progress figures 2/3 of one run
      (`ProgressFigures`), plotly `draw_results`, a pyvis tree, and the networkx/GraphML
      exports.
    - The layout is neato when pygraphviz is present, else Kamada-Kawai (the base
      kernel, as committed).
  - README: a new **Usage** section (running the model, a backend table, drawing,
    exports, progress figures and CLI examples, each snippet run once), an updated
    Status, and `viz/` and `examples/` rows in the Layout table.
  - Other docs: `CONVENTIONS.md` (item 34 in the Display section) and the `viz` package
    docstring.
  - Fixture: `tests/octave/fx_viz_draw.m` → `tests/fixtures/viz_draw.mat` was
    regenerated in Octave 10.3.0 (12 s). All 31 variables are identical to the committed
    ones. It is the parity target, together with `viz_networkx.mat` (hover) and
    `masterrun.mat` (notebook).
  - `tests/test_viz_interactive.py`: base env, 331 pass and 21 skip (pygraphviz). fd env,
    350 pass, the live Octave test included; 3 skip for nbformat/nbclient. There is also
    1 `slow` test that executes the notebook (37 s, passes). Checks:
    - on all 83 draw_dot cases, both backends are given Octave's X/Y. The nodes, labels,
      fills (grey self-loops) and font size are exact. There is one arrow per Octave
      arrow, in Octave's drawing order and pointing the same way. graph_draw offsets the
      ends by `wd_x cos`/`wd_y sin`, so the arrows are not exactly parallel to the centre
      line; the test checks which end is nearer which node;
    - hover on all 63 baseline graphs matches Octave's `z` and cluster edges;
    - facade: with neato (pygraphviz, 10 cases × 2 backends), Octave's xret/yret/labels,
      and the nodes drawn at Octave's X/Y. With Kamada-Kawai, the ordered layout;
    - `undirected='lines'`, subplots, `draw_graph`, `draw_results` (plotly), the errors
      and the CLI;
    - the notebook matches the generator's cells, ran without errors, and its printed
      scores are within 1e-3 rel of Octave's `modellike`, with each true form recovered;
    - live (fd env, 2 s): the real `draw_dot` on the 9 final graphs of Octave's
      masterrun demo. `draw_graph` places every node where Octave's draw_dot does, with
      plotly and with pyvis (9 of 9 compared).
  - Existing tests: two "unknown backend" checks used `'plotly'`, which is now valid.
    They use `'bokeh'` instead.
  - Mutation check: the tests catch 10 of 10 deliberate breaks: line pair order, hover
    cluster +1, column-major edge order, pyvis `y` sign, empty pyvis labels, swapped
    arrow ends, no grey fill, subplot `axref`, xret instead of the ordered positions, and
    the pyvis hover separator.
  - No new anomalies: the original has no interactive display, and the notebook's scores
    agree with Octave's. `ANOMALIES.md` and `KNOWN_ISSUES.md` are unchanged.
  - Gate: base `python -m pytest -q -m "not slow"`: 3282 passed, 246 skipped, 77
    deselected (272 s). fd env, the three viz test files: 1120 passed, 2 skipped.
### Blockers
- None.
### Next
- Item 35 (performance budget: Octave vs Python per `graph_like` call and per
  `structurefit` depth, profile `dataprobwsig`, safe optimisations with parity still
  green). Then verify every item, update the status header and add `LOOP_COMPLETE`.
- Housekeeping: `tests/baseline_images/networkx/feat_tree_demo_tree_feat_notext-failed-diff.png`
  is a matplotlib comparison artifact that was committed in item 33. Test runs rewrite it
  (it was restored this iteration). Remove it from git and add `*-failed-diff.png` to
  `.gitignore`.
