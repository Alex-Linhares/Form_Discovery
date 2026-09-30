# Progress Log

## Ralph Loop 0002 Status
- **Started**: 2026-09-30
- **Target**: 7 items (see iterations.md)
- **Current**: 3/7 SOLVED

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

---

## Iteration 3 — 2026-09-30 20:16
### Completed
- Item 02, BLAS/OpenMP pinning. Iteration 2 committed the pinning and the A19 gate fix but
  did not check the item. This iteration finished it: the remaining measurements, proof
  of bit-identical results, and coverage of the last driver.
  - Checked every place that starts Octave. `tests/conftest.py`: `pytest_configure` calls
    `pin_blas_env()` before oct2py starts, and `pytest_sessionstart` calls
    `pin_process_blas(1)` for the Python side. `tools/gen_fixtures.py` uses
    `fixture_env(name)`. `tools/gen_paperlevel.py` uses `pinned_env()`.
    `tools/bench_perf.py --live` goes through `_configure_octave_env` and
    `gen_fixtures.run_one` (perf is pinned). There is no Python `run_baseline` driver
    except the tests' `octave` fixture, which is pinned.
  - `tests/test_gate_env.py::test_octave_cli_pinned` now also asserts that
    `bench_perf.py --live` uses `run_one` and that `perf` is not in
    `BLAS_DEFAULT_FIXTURES`.
  - Bit-identical: `run_baseline('feat', 2, 1)` pinned and unpinned, each to its own
    directory. `tools/mat_compare.py` finds 0 differences over the 3 `.mat` files. The
    pinned run also matches the committed `tests/fixtures/baseline/feat`:
    `modellike(2,1)` = −8247.204813441429 exactly, and
    `results/chainout/demo_chain_feat1/growthhistoryalltie5.mat` has 0 differences. The
    live glslow tests pass pinned and unpinned (both compare exactly with `glslow.mat`).
    The fixture-wide check from iteration 2 still holds: 29 of 32 fixtures regenerate
    identical when pinned, perf and rng differ only in non-numeric fields, and gibbs is
    A19 (still open, left for a human to decide).

  | run | wall | CPU (user+sys) | processes |
  |---|---|---|---|
  | `run_baseline('feat',2,1)`, unpinned | 1.71 s | 3.64 s | 1 Octave |
  | `run_baseline('feat',2,1)`, pinned | 1.68 s | 1.67 s | 1 Octave |
  | live `test_glslow.py` (2 tests), before (item 01 tree, unpinned) | 82.6 s | 90.5 s | 1 Python + 1 Octave |
  | live `test_glslow.py` (2 tests), after (pinned) | 82.8 s | 82.5 s | 1 Python + 1 Octave |
  | full gate, item 01 (unpinned) | 38 min 18 s | 4482 s (195 % CPU) | 1 (+1 Octave) |
  | full gate, this item (pinned; gibbs regen unpinned per A19) | 38 min 03 s | 2714 s (119 % CPU) | 1 (+1 Octave) |

  Pinning saves CPU (40 % of the gate's CPU time) but not wall clock, because a serial
  run on small matrices does not benefit from extra BLAS threads. Wall-clock gains come
  from items 03–05 (processes side by side), and pinning is what makes those safe to run
  in parallel.
- Gate (fd env, strict): **3621 passed, 3 skipped (sklearn 1, nbformat 2; no Octave
  skips), 78 deselected, exit 0.**
### Blockers
- None for this item. A19 (whether to keep `gibbs.mat` unpinned) is still open for a
  human.
### Next
- Item 03: `tools/gen_fixtures.py --jobs N` (parallel fixture generation, compared with
  the serial run).

---

## Iteration 4 — 2026-09-30 21:39
### Completed
- Item 03, parallel fixture generation.
  - `tools/gen_fixtures.py --jobs N` (default `os.cpu_count() // 2`). Each task is one
    `octave-cli` (with `fixture_env(name)`, so everything is pinned except gibbs, A19).
    Up to N run at once from a thread pool, each thread waiting on its own Octave
    process, longest expected task first. `paperlevel` becomes its 45 `fx_paperlevel(part, j)` runs plus
    a `paperlevel_merge` task, as in `gen_paperlevel.py`. The per-job expected times come
    from the committed fixture's `secs`.
  - Dependencies: `fx_perf.m` loads `paperlevel.mat`, and `fx_glslow.m`/`fx_graphlike.m`
    load `dataprob.mat`/`dpmiss.mat`, always from `tests/fixtures`. In the old serial
    alphabetical order the dependency ran first, so `DEPENDS` makes the dependent task
    wait when both are regenerated. `tests/test_gen_fixtures.py` checks `DEPENDS` against
    the scripts' `load(fullfile(fxdir, ...))` calls. Each output is written to a staging
    directory and moved into `--outdir` with `os.replace`, so a reader of
    `tests/fixtures` never sees a half-written file.
  - Per-task logs go to `<logdir>/<task>.log` (default `build/gen_fixtures/`, which is
    gitignored). Each log holds the command, the Octave output, and the exit code with
    wall and CPU seconds (`os.wait4`). At the end the tool prints a summary table: wall
    and CPU per task, then the totals.
  - `--compare DIR`: `compare_fixture` compares loaded arrays to all digits
    (`tools/mat_compare.py`, which gains a `normalize` hook for strings). It skips
    `DEFAULT_IGNORE` (`seconds`) plus the `VOLATILE` timing fields (perf `t_*`/`n_*`/
    `total`/`ev`, keeping `ev`'s count columns; paperlevel `secs`) and masks
    `/tmp/oct-XXXXXX` in strings (rng's error messages). `run_one` keeps its signature
    for `test_gibbs`, `bench_perf` and `compare_runs`.
  - New `tests/test_gen_fixtures.py` (7 tests). `DEPENDS` vs the scripts; task planning;
    the scheduler with a stand-in Octave (dependency order, longest first, job limit,
    a failed paperlevel job skips the merge and perf); the volatile-field comparison; and
    a live `octave` test showing that `--jobs 1` and `--jobs 4` give the same content for
    7 quick fixtures, equal to the committed ones.
- Full regeneration, all 31 fixtures (76 tasks), into `/tmp`:
  - `--jobs 16` vs committed `tests/fixtures`: **31 identical**. That includes `gibbs`
    (regenerated unpinned) and `paperlevel`.
  - `--jobs 1` vs `--jobs 16`: **31 identical**. `--jobs 1` vs committed: 31 identical.
  - A raw `mat_compare.compare_dirs` with no masking finds differences only in
    `paperlevel.mat` (`secs`), `perf.mat` (timings) and `rng.mat` (temp dir names), which
    are the known volatile fields.

  | run | wall clock | CPU (user+sys) | workers |
  |---|---|---|---|
  | `gen_fixtures.py --jobs 1` (all 31, paperlevel as 45 tasks) | 68 min 49 s | 4530 s | 1 `octave-cli` |
  | `gen_fixtures.py --jobs 16` | **7 min 56 s** (8.7×) | 5310 s | 16 `octave-cli` |
  | before this item: serial `gen_fixtures.py`, `paperlevel` alone (one process, 45 runs) | ≈ 81 min (sum of `secs`) | – | 1 |

  The `--jobs 16` wall time is set by the longest task (`paperlevel_job15`: 414 s,
  348 s in the serial run). Per-task times are 15–30 % longer with 16 running side by
  side. gibbs uses 673–840 CPU-s for 265–348 wall-s because it runs unpinned (A19). The
  gate below ran at the same time as the `--jobs 1` run, so the serial times may be
  slightly high.
- Docs: `README.md` (bullet in "How it was verified" and the commands block),
  `CLAUDE.md`, `PLAN.md` tree, and the `gen_paperlevel.py`/`test_paperlevel.py` docstrings.
  No new anomaly: every regeneration matched.
- Gate (fd env, strict): **3627 passed, 3 skipped (the known sklearn/nbformat, no Octave
  skips), 78 deselected, exit 0**, in 39 min 19 s wall, 2970 s CPU.
### Blockers
- None. A19 (gibbs kept unpinned) is still open for a human.
### Next
- Item 04: `tools/gen_baselines.py --kind feat|rel --jobs N` with a merge step, compared
  with the committed `tests/fixtures/baseline/{feat,rel}`.
