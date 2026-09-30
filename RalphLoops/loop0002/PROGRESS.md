# Progress Log

## Ralph Loop 0002 Status
- **Started**: 2026-09-30
- **Target**: 7 items (see iterations.md)
- **Current**: 1/7 SOLVED

---

## Iteration 1 — 2026-09-30 16:17
### Completed
- Item 01, strict Octave gate.
  - `tests/conftest.py` now has `is_fd_env()`, `octave_required()` and a
    `pytest_runtest_makereport` hookwrapper. In strict mode (`RALPH_REQUIRE_OCTAVE=1`, or
    the interpreter's `sys.prefix` is `.../envs/fd` when the variable is unset), any
    skipped `octave`-marked test, in setup or call, is reported as failed. The message
    gives the skip reason, the interpreter, and the fix ("use the fd env's Python, or set
    `RALPH_REQUIRE_OCTAVE=0`"). Non-Octave skips and xfails are left alone.
    `RALPH_REQUIRE_OCTAVE=0` turns strict mode off explicitly.
  - New `tests/test_gate_env.py`. Three `octave` tests: oct2py is importable, Octave is
    found, and one trivial live call works (`1+1`, `masterrun` on the path). Plus a
    two-case self-test that runs a small pytest subprocess with a copy of the conftest: under
    `=1` a skipped octave test makes the run fail with the strict message; under `=0`
    both tests skip.
  - Checked by hand. Base Python (no oct2py) with `RALPH_REQUIRE_OCTAVE=1`: the 3 octave
    tests fail with the message. Without the variable, or with `=0`: they skip.
  - Docs: `README.md` "How it was verified" and the commands block, `CLAUDE.md` gate
    command, and the `pyproject.toml` marker description.
- Gate in the fd env (`~/anaconda3/envs/fd/bin/python -m pytest -m "not slow"`, strict by
  env): **3614 passed, 3 skipped, 78 deselected, exit 0**. All 67 `octave` tests passed,
  **0 Octave tests skipped**. The 3 skips are not Octave tests: sklearn (1) and nbformat
  (2) are not in the fd env.

  | gate run | wall clock | CPU (user+sys) | workers |
  |---|---|---|---|
  | base Python, fixtures only (loop0001 it. 39) | 187–359 s | – | 1 |
  | fd env, strict, Octave live (this item) | 38 min 18 s | 4482 s (195 % CPU) | 1 (+1 Octave) |

  The first attempt was killed by the 30-min tool limit before it finished, so it has no
  result. The time goes to the live `fresh_seeds` and `fixture_regenerates` tests:
  gibbs 330+256 s, spr 281+209 s, dpmiss 161+69 s, swap 74+61 s, runmodel 60+50 s, and
  simplify, search and glslow about 40–58 s each. They are independent of each other,
  so they are the target for items 02 (BLAS pinning: 195 % CPU on a serial run points to
  extra BLAS threads) and 05 (xdist).
- Note: `loop.py`'s 240-min hang guard (`RALPH_TIMEOUT_MIN`) covers the 38-min gate.
### Blockers
- None for the item.
- **For a human:** during this iteration another process, loop0001's iteration 39, wrote
  to the same working tree. It edited `RalphLoops/loop0001/PROGRESS.md` (adding
  `LOOP_COMPLETE` there) and `tests/octave/fx_glslow.m` (it now clears the global `SPY`
  left by `fx_gibbs.m`, which had made `test_glslow::test_live_fixture_regenerates` fail
  after `test_gibbs` in a shared Octave session). It also regenerated
  `tests/fixtures/glslow.mat`; it reports all 17 variables unchanged. None of those were
  touched here. The fd-env gate above ran with its fix in place, and the glslow live tests
  passed after gibbs. That fix is needed for a strict gate, so it should be committed
  together with this item.
### Next
- Item 02: BLAS/OpenMP pinning for Octave and Python workers. Measure before and after
  using the durations above.

---

## Iteration 2 (gate fix) — 2026-09-30
### Context
- The item 02 work (BLAS/OpenMP pinning: `threads.PIN_ENV`/`pinned_env`/`pin_process_blas`,
  conftest pinning, pinned `gen_fixtures.py`/`gen_paperlevel.py`, `fx_perf.m`
  `nproc('current')`, A18, `tools/mat_compare.py`) was left uncommitted, with no PROGRESS
  entry and the item unchecked. The gate then failed:
  `tests/test_gibbs.py::test_live_fixture_regenerates` (`out_ll` −69392.59489410985 vs the
  fixture's −69392.59509400144). The other 3619 tests passed and the 3 skips are the known
  non-Octave ones.
### Investigation
- Regenerated `gibbs.mat` twice in parallel: pinned (`gen_fixtures.py`, 256 s wall, 255 s
  CPU) and unpinned (OpenBLAS default, 254 s wall, 661 s CPU). **The unpinned run matches
  the committed fixture exactly** (`tools/mat_compare.py`: 0 differences). The pinned run
  differs in calls 94-100, all run 5 (`grid x synthgrid`). `run_ll` is identical for all 7
  runs. So pinning Octave is **not** bit-neutral there, and item 02's "results are
  bit-identical" holds only for the cases that had been checked. Recorded as **ANOMALIES
  A19 (open)**.
- Regenerated every other fixture pinned (all `fx_*.m` except `paperlevel`, which
  `gen_paperlevel.py` already made pinned; 16 `octave-cli` side by side) and compared each
  with the committed one. Result: **29 identical**. `perf.mat` differs only in timing
  fields (`t_*`, the timeit counts `n_slow`, and `sf.ev`/`total`, which hold `toc` values).
  `rng.mat` differs only in two error messages that carry temp-directory names. `gibbs` is
  the only numeric difference.
- TASK.md forbids overwriting a committed fixture that regenerates differently, so
  `gibbs.mat` was **not** changed. For reference: all 126 non-live `test_gibbs.py` tests
  pass against the pinned regeneration (checked, then `gibbs.mat` restored from git).
### Fix
- `tests/conftest.py`: `BLAS_DEFAULT_FIXTURES = {"gibbs"}` and `fixture_env(name)`, which
  gives the pinned env except for those fixtures. For those it removes the pin
  (`threads.unpinned_env`), even inside the pinned test session.
- `tools/gen_fixtures.py`: `run_one` uses `fixture_env(name)`.
- `tests/test_gibbs.py::test_live_fixture_regenerates`: runs `gen_fixtures.run_one` (its own
  `octave-cli`, unpinned for gibbs) instead of the pinned Oct2Py session. It still compares
  logtext, `out_ll` and graphs exactly, and `run_ll`. Passed: 254 s wall, 646 s CPU. The
  gibbs `fresh_seeds` test still runs pinned (tolerance-based Python vs Octave comparison).
- `tests/test_gate_env.py`: new `test_fixture_env`. `test_octave_cli_pinned` now checks
  `env=fixture_env(name)` in `gen_fixtures.py`.
- Docs: A19 added, A18 narrowed ("that run only; see A19"), and the README pinning note
  names the exception. No KI entry: this is an environment issue, not a formdiscovery1.0
  one (as for A18).
