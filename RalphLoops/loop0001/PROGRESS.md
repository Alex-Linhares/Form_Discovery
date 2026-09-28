# Progress Log

## Ralph Loop 0001 Status
- **Started**: 2026-09-28
- **Target**: 35 items (see iterations.md)
- **Current**: 2/35 SOLVED

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
