# Plan: move the MATLAB/Octave code to `legacy/`, then delete it

Status: Phases 1–3 done (loop0004, 2026-10-01; M1–M3 below); Phases 4–5 pending. Date: 2026-10-01.

## Goal

Make the Python package stand on its own. Today the repo still carries the original MATLAB
sources (`matlab/formdiscovery1.0/`, 4.2 MB with data), the Octave shims and baseline
scripts, 31 Octave fixture-generation scripts (`tests/octave/`), and 77 tests that drive
Octave live. That was the right scaffolding for the translation; it is not the shape of a
Python project. The end state is:

- the port, the GUI and the tests load data from a Python-owned folder;
- the committed fixtures (30 MB of Octave-produced reference answers) remain the oracle,
  frozen and checksummed, so the parity tests keep running with no Octave anywhere;
- everything Octave-specific lives under `legacy/`, runs only on request, and can be
  removed in one commit later with git history and a tag as the archival record.

Nothing numeric changes at any step: every phase ends with the same fixture-based parity
tests green.

## What depends on the MATLAB folder today

| Dependency | Where | What must change |
|---|---|---|
| **Data files** (`*.mat`, 20 sets) are inside the MATLAB tree | `io.DATA_DIR` (env `FORMDISCOVERY_DATA`), `params` (`ps.dlocs`), GUI default directory and demo, tools, ~20 test files | move the data out first; one constant |
| MATLAB sources as the live oracle | `tests/conftest.py` (`MATLAB_DIR`, `SHIM_DIR`, `OCTAVE_TESTS_DIR`, the `octave` and `replay` fixtures), 77 `octave`-marked tests in 39 files | optional, legacy-only |
| Fixture and baseline generation | `tools/gen_fixtures.py`, `gen_baselines.py`, `gen_paperlevel.py`, `compare_live.py`, `bench_perf.py --live`, `matlab/run_baseline.m`, `baseline_merge.m` | move to `legacy/tools/` |
| Tests that only make sense with the `.m` files present | `test_patches.py`, `test_toolchain.py`, `test_gen_baselines.py`, `test_gen_fixtures.py`, `test_known_issues.py::test_quirk_at_cited_line` | move to `legacy/tests/`, collected only when `legacy/` exists |
| Documentation | README, CLAUDE.md, PLAN.md, ANOMALIES.md, KNOWN_ISSUES.md (file:line citations), CONVENTIONS.md, `matlab/PATCHES.md` | paths updated; citations kept as history |
| Environment | `environment.yml` pins octave, oct2py | split into Python-only and legacy |

## Phases

### Phase 1 — Data out of the MATLAB tree
- Move `matlab/formdiscovery1.0/data/*.mat` (and its `README.txt`) to `data/` at the repo
  root; `io.DATA_DIR` points there; `FORMDISCOVERY_DATA` still overrides.
- Update every Python reference (the ~20 test files, tools, GUI default dir and `--demo`).
- Keep the MATLAB side working without editing `setps.m`: a relative symlink
  `matlab/formdiscovery1.0/data -> ../../data` (Octave follows it). Document it in
  `PATCHES.md` as an environment note, not a source patch.
- Gate: unchanged results, live Octave still on.

### Phase 2 — Everything Octave under `legacy/`
- `git mv matlab legacy/matlab`, `tests/octave legacy/tests_octave`, the Octave tools to
  `legacy/tools/`, the Octave-only tests to `legacy/tests/`.
- One constant `LEGACY_DIR` in `tests/conftest.py`; `MATLAB_DIR`, `SHIM_DIR`,
  `OCTAVE_TESTS_DIR` derive from it. If `legacy/` is absent, every `octave` test is skipped
  (or fails under `RALPH_REQUIRE_OCTAVE=1`, as now) and `legacy/tests/` is not collected.
- `environment.yml` becomes Python-only; `legacy/environment-octave.yml` adds octave,
  oct2py and pins. `pyproject.toml` loses the `octave` extra or marks it legacy.
- Docs: paths updated; `README` gets a short "Legacy: the Octave oracle" section.

### Phase 3 — The default gate needs no Octave
- Default gate: `pytest -q -m "not slow and not octave" -n 16` (fixture-only, strict about
  nothing external; expected 1–2 minutes). The Octave-live suite becomes an explicit job:
  `make legacy-check` = the current strict gate, run before any fixture is touched and in
  the Phase 4 freeze. `loop.py` for future loops defaults to the fixture-only gate.
- A fixture-integrity test: `tests/fixtures/SHA256SUMS` committed; the gate verifies every
  fixture's hash so a silently edited fixture fails even without Octave.

### Phase 4 — Freeze
- Regenerate every fixture and both baselines one last time through `legacy/` with the
  pinned Octave (16 jobs; ~8 minutes), confirm identical to the committed files
  (`mat_compare`), and write `legacy/FREEZE.md`: Octave, OpenBLAS, numpy/scipy versions,
  the BLAS-pinning policy (A19), dates, and the fixture hashes.
- Tag `octave-oracle-final`; attach `legacy-octave-oracle.tar.gz` (the `legacy/` tree) to
  a GitHub release so the oracle can be reconstructed without digging through history.

### Phase 5 — Delete
- Remove `legacy/` from `main` in one commit that references the tag. Remove oct2py and
  Octave from all environment files and CI. `KNOWN_ISSUES.md` keeps its `file:line`
  citations as historical pointers into the tag; `test_known_issues.py` keeps the
  decision/pin checks and drops the line-pin test. README "How it was verified" explains
  that the fixtures were produced by Octave at the tag and how to rerun that check.
- Keep the attribution: the README credits for Charles Kemp and the contributors stay.

## Order of risk

1. **Data move breaks loading.** Mitigated by doing it first, alone, with the full live gate
   still on; `FORMDISCOVERY_DATA` lets anything pinned to the old path keep working.
2. **Fixtures become unregenerable.** Only after Phase 5, and only without the tag; the
   freeze records enough to rebuild the environment, and the hashes catch tampering.
3. **Octave-only tests silently vanish.** Phase 2 moves them, Phase 3 lists them in
   `legacy/README.md` with the command that still runs them.
4. **A future numerics change with no oracle.** The policy after Phase 5: a change that
   alters any fixture value needs the oracle rerun from the tag before the fixture is
   updated. Written into CLAUDE.md.

## Milestones

| # | Done when | Status |
|---|---|---|
| M1 | Data in `data/`; live gate green; MATLAB side runs through the symlink | [x] loop0004 item 01: live `run_baseline('feat', 2, 1)` and a fixture regeneration identical through `legacy/matlab/formdiscovery1.0/data -> ../../../data` |
| M2 | `legacy/` holds all Octave material; gate green with and without `RALPH_REQUIRE_OCTAVE` | [x] items 02–04: strict gate 3866 passed, 3 skipped; without `legacy/`: `RALPH_REQUIRE_OCTAVE=0` skips the 65 remaining `octave` tests, `=1` fails them |
| M3 | Default gate is fixture-only and under 2 minutes; fixture hashes verified; `make legacy-check` green | [x] items 05–06: `make test` 3792 passed, 3 skipped, 50 s (fd env); base interpreter (no oct2py) 3521 passed, 189 skipped, 40 s; without `legacy/` 3696 passed (fd) and 3426 passed (base); `tests/fixtures/SHA256SUMS` (115 files) checked by `tests/test_fixture_integrity.py`; `make legacy-check` 3866 passed, 3 skipped, 379 s; `-m slow -n 16` (strict) 79 passed, 1 skipped, 562 s |
| M4 | `legacy/FREEZE.md`, tag and release tarball exist; final regeneration identical | [ ] |
| M5 | `legacy/` removed from `main`; docs and env updated; gate green | [ ] |

Phases 1–3 are one Ralph loop (about five items). Phases 4–5 are a second, short loop to be
run when the decision to delete is final.
