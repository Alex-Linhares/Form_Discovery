# Progress Log

## Ralph Loop 0001 Status
- **Started**: 2026-09-28
- **Target**: 36 items (see iterations.md)
- **Current**: 3/36 SOLVED

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
