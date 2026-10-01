# TASK: Move the MATLAB/Octave oracle under `legacy/` (PLAN_LEGACY.md, phases 1–3)

## Philosophy
- **Nothing numeric changes.** This loop moves files and rewires paths. Every iteration ends
  with the strict live-Octave gate green and every committed fixture byte-identical.
- **The Python package must stand on its own.** After this loop, data lives in a
  Python-owned folder, the default test gate needs no Octave, and everything Octave-specific
  is under `legacy/` where a later loop can delete it in one commit.
- **Keep the oracle usable until the freeze.** The live Octave suite keeps running from
  `legacy/` on request; the strict gate in this loop still runs it, so a path mistake cannot
  slip through.
- One item per iteration; foreground waiting; anomalies into `ANOMALIES.md`.

## Current Focus
Phases 1–3 of `/PLAN_LEGACY.md`: data out of the MATLAB tree; all Octave material under
`legacy/`; a fixture-only default gate protected by checksums, with the live suite as an
explicit job. Phases 4–5 (freeze and delete) are a later loop.

## Target Problems (in order)
See `iterations.md`. Work on the first unchecked item only.

## Acceptance Criteria (per item)
- [ ] Strict gate green: `~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow" -n 16`
      with `RALPH_REQUIRE_OCTAVE=1` (set by `loop.py`): same pass count as before the item
      (minus tests deliberately moved, which must pass from their new location).
- [ ] `git mv` for moves (history preserved); no fixture under `tests/fixtures/` changes
      (`git status` shows none modified; `tests/fixtures/SHA256SUMS` once it exists).
- [ ] Every reference to a moved path is updated (grep the repo for the old path; zero
      hits outside `RalphLoops/*/PROGRESS.md`, `PLAN*.md` history and `KNOWN_ISSUES.md`
      citations, which are historical by design).
- [ ] README, CLAUDE.md and CONVENTIONS.md updated where commands or paths changed.
- [ ] `iterations.md` checkbox updated and a PROGRESS.md section appended.

## Completion Conditions
Solved (all criteria) or Blocked (specific blocker, what was tried, smallest repro;
mark `[~]`).

## Context
- **Read first:** `/PLAN_LEGACY.md` (the dependency table is the checklist), `/CLAUDE.md`,
  `tests/conftest.py` (`MATLAB_DIR`, `SHIM_DIR`, `OCTAVE_TESTS_DIR`, `find_octave`, the
  `octave` and `replay` fixtures, `RALPH_REQUIRE_OCTAVE` handling from loop0002 item 01),
  `src/formdiscovery/io.py` (`DATA_DIR`, env `FORMDISCOVERY_DATA`),
  `src/formdiscovery/params.py` (`ps.dlocs`), `src/formdiscovery/gui/` (default data dir,
  `--demo`), `tools/` (which scripts start Octave), `matlab/PATCHES.md`.
- **Reference counts** (from `grep` on 2026-10-01): ~25 Python files reference the MATLAB
  data path or the MATLAB dir; 77 `octave`-marked tests in 39 files; docs: README,
  CLAUDE.md, PLAN.md, ANOMALIES.md, KNOWN_ISSUES.md, CONVENTIONS.md.
- **Machine / env:** fd env (Octave 10.3, oct2py, PySide6); 32 cores; gate ≈ 6 min with
  `-n 16`.
- **Constraints:** do not edit `.m` sources except the documented `PATCHES.md` edits (none
  expected; the data path is handled by a symlink, not by editing `setps.m`). Do not
  regenerate or overwrite fixtures. Keep `FORMDISCOVERY_DATA` as an override.

## Important Notes
- `setps.m` builds data paths from `pwd/data/`; `run_baseline.m` and the fixture scripts
  `cd` into the sources. A relative symlink `legacy/matlab/formdiscovery1.0/data ->
  ../../../data` (Phase 1: `matlab/formdiscovery1.0/data -> ../../data`) keeps them working.
  Octave follows symlinks. Commit the symlink; note it in `PATCHES.md` as an environment
  note.
- When Octave-only tests move to `legacy/tests/`, pytest must still find `tests/conftest.py`
  fixtures: either make `legacy/tests/` a `testpaths` entry guarded by existence in
  `conftest.py`'s `pytest_ignore_collect`, or keep a tiny `legacy/tests/conftest.py` that
  imports from `tests.conftest`. Decide, document, test both presence and absence of
  `legacy/` (absence can be simulated in a temporary clone with `legacy/` deleted).
- The fixture-only gate must be genuinely Octave-free: run it once under the base
  interpreter (no oct2py) and once in the fd env with `legacy/` absent; both green.
- `loop.py` in this folder keeps the strict live gate for the whole loop. The fixture-only
  command becomes the documented default for future loops (update
  `RalphLoops/ralph_loop_guide.md` and the `TEST_CMD` default in a new `loop.py` template),
  not for this one.
