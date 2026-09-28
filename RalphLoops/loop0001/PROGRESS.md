# Progress Log

## Ralph Loop 0001 Status
- **Started**: 2026-09-28
- **Target**: 35 items (see iterations.md)
- **Current**: 3/35 SOLVED

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
