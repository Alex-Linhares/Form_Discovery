# TASK: Make the correctness gate Octave-backed and fast (parallel Octave + Python)

## Philosophy
- **The gate must prove parity, every iteration, without anyone choosing to.** In loop0001 the
  runner's gate ran under the base Python, where oct2py is missing, so every live Octave test
  was *skipped*; only committed fixtures were compared. From now on the gate runs in the `fd`
  env and a skipped Octave test is a failure.
- **Parallel, but bit-identical.** Speed comes from running independent Octave and Python
  jobs side by side on this 32-core / 121 GB machine, never from changing numerics. Every
  parallel path must produce output identical to the serial path it replaces, and a test
  must prove it.
- **Pin BLAS threads everywhere.** loop0001 item 35 found OpenBLAS waking 32 threads for
  40×40 matrices (15× slowdown, 244 CPU-min for 9 wall-min). Every Python worker and every
  Octave process must run with one BLAS/OpenMP thread; parallelism comes from processes.
- **One item per iteration**, foreground commands only, measure before and after.

## Current Focus
Turn the verification harness built in loop0001 into one that (a) always exercises Octave
live, (b) regenerates fixtures and baselines in minutes rather than tens of minutes, and
(c) runs the whole gate in a few minutes using all cores.

## Target Problems (in order)
See `iterations.md`. Work on the first unchecked item only.

## Acceptance Criteria (per item)
- [ ] The gate `~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow"` passes with
      **zero skipped Octave tests** (after item 01 this is enforced by the suite itself).
- [ ] Any new parallel path has a test showing its output is identical to the serial path
      (same `.mat` contents, same numbers to all digits, same file sets).
- [ ] Timings before and after are recorded in PROGRESS.md as a small table (wall clock,
      CPU time, worker count).
- [ ] `README.md` "How it was verified" and `CLAUDE.md` updated if commands change.
- [ ] Any anomaly found is added to `/ANOMALIES.md` (with status) and `KNOWN_ISSUES.md`.
- [ ] `iterations.md` checkbox updated and a PROGRESS.md section appended.
- [ ] No regressions: loop0001's parity results must not change.

## Completion Conditions
An item is DONE when either:
1. **Solved**: meets all criteria, OR
2. **Blocked**: PROGRESS.md records the specific blocker, what was tried, and the smallest
   reproduction. Mark the item `[~]` and move on.

## Context
- **Read first:** `/CLAUDE.md`, `/PLAN.md` §2 and §7.4, `/ANOMALIES.md` (A3, A16 in
  particular), `RalphLoops/loop0001/PROGRESS.md` iterations 30 and 38 (parallel Octave for
  the paper-level fixtures; the BLAS finding and `formdiscovery/threads.py`).
- **Existing pieces to build on:** `tools/gen_paperlevel.py` (already runs Octave in a
  `ThreadPoolExecutor`), `tools/gen_fixtures.py` (serial, one `octave-cli` per script),
  `matlab/run_baseline.m` (serial grid; takes `thisstruct`, `thisdata`, `outdir`),
  `tests/conftest.py` (`find_octave`, session-scoped `octave` fixture, `replay` fixture),
  `formdiscovery/threads.py` (`limit_blas_threads`).
- **Machine:** 32 cores, 121 GB RAM. Octave 10.3 (conda-forge, env `fd`), Graphviz 14.1.2
  (use the fd env's `neato`, the system one has no layout plugin).
- **Testing:** the gate above; `-m octave` for live-only; `-m slow` for long runs.
- **Constraints:** do not change numerics or any committed fixture value; if a regenerated
  fixture differs from the committed one, that is a finding to investigate, not a file to
  overwrite. Do not modify `matlab/formdiscovery1.0/` except via documented
  `PATCH(octave)` edits (none are expected here).

## Important Notes
- Octave's BLAS is also OpenBLAS: set `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` in
  the environment of every `octave-cli` and `Oct2Py` you start, and verify with a timing.
- With pytest-xdist each worker gets its own session-scoped `octave` fixture, i.e. its own
  Octave process: that is the intended design. Watch for shared temporary file names
  (`_GtDout.dot`, `_LAYout.dot`, `randperm_*` logs) and per-test `tmp_path` use.
- Image-regression tests and anything writing under `tests/` must be safe to run
  concurrently; use `tmp_path`.
- `loop.py` in this folder already defaults the gate to the fd env's Python
  (`RALPH_TEST_CMD` overrides it).
