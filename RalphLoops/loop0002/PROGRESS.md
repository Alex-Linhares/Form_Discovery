# Progress Log

## Ralph Loop 0002 Status
- **Started**: 2026-09-30
- **Target**: 7 items (see iterations.md)
- **Current**: 6/7 SOLVED

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

---

## Iteration 5 — 2026-09-30 23:43
### Completed
- Item 04, parallel baselines.
  - New `tools/gen_baselines.py --kind feat|rel --jobs N` (default cores/2; also
    `--struct`/`--data` sub-grids, `--outdir`, `--compare DIR`, `--logdir`). There is one
    task per (structure, dataset) pair: `run_baseline(kind, sind, dind, pairdir)` in its
    own `octave-cli` (`fixture_env('baseline')`, pinned), each into its own directory. It
    reuses `gen_fixtures.run_tasks`: longest pair first (expected times from the committed
    `timings.mat`), per-pair logs in `build/gen_baselines/<kind>/`, and the timing table.
  - Merge: the new `matlab/baseline_merge.m` replays `run_baseline`'s accumulation over the
    pairs in the serial run order (structure fastest, then dataset). `timings` is
    concatenated. `modellike`, `structure`, `names`, `pss` and `llhistory` at
    `(sind, dind, 1)` come from each pair's `resultsdemo.mat`, and a crashed pair adds only
    its timings entry, as in the serial run. Python then copies each pair's `results/`
    tree (it refuses a file written by two pairs). Everything is built in a staging
    directory next to `--outdir` and swapped in by rename. `--compare` checks the full
    file set (all files, not only `.mat`) and then `.mat` content to all digits
    (`mat_compare.compare_dirs`, skipping `timings.seconds` only).
  - Result: `--jobs 1`, `--jobs 16` and `--jobs 32` (and 9 for feat) all give **0
    differences** against the committed `tests/fixtures/baseline/feat` (21 files) and
    `rel` (56 files). They also give 0 differences against a fresh serial
    `run_baseline(kind)` in one pinned `octave-cli`, and `--jobs 1` vs `--jobs 16` has 0
    differences. So all ll values, graph structs, `pss`, `llhistory`, growth histories
    and timings (except seconds) match, with the same file sets.
  - Found and fixed a race, **ANOMALIES A20 (handled)**. Octave's `mkdir` of a nested path
    is check-then-create (`mkdir_recur`), so one of 9 simultaneous `run_baseline`s failed
    with "mkdir: operation failed: File exists" when a sibling created the shared
    `pairs/` parent first. The tool now creates each pair directory before starting
    Octave. No KI entry, because it is an environment issue (as for A18/A19).
  - New `tests/test_gen_baselines.py` (11 tests). The grids and pair order are checked
    against `run_baseline.m` and against the committed `timings.mat` order. Also task
    planning, the results-overlap guard, and file-set comparison. Live `octave` tests:
    all 9 feat pairs in parallel, merged, equal the committed baseline (≈8 s, in the gate;
    it failed before the A20 fix and passed 3 of 3 after), and merging with a synthetic
    crashed pair. A `slow` live test does the same for the 54 rel pairs with 16 processes
    (15 s).

  | run | wall clock | CPU (user+sys) | workers |
  |---|---|---|---|
  | loop0001: serial `run_baseline('feat'); run_baseline('rel')` | 2 min 45 s | – | 1 Octave |
  | serial `run_baseline('feat')`, pinned (this iteration, 2 runs) | 33.5–46.3 s | 33.5–46.3 s | 1 Octave |
  | serial `run_baseline('rel')`, pinned (2 runs) | 139.7–176.3 s | 139.7–176.0 s | 1 Octave |
  | `gen_baselines.py --kind feat --jobs 1` | 27.4 s | 29.3 s | 1 `octave-cli` at a time (9 + merge) |
  | `gen_baselines.py --kind feat --jobs 16` | **5.8 s** | 31.3 s | 9 `octave-cli` |
  | `gen_baselines.py --kind rel --jobs 1` | 145.7 s | 147.3 s | 1 at a time (54 + merge) |
  | `gen_baselines.py --kind rel --jobs 16` | **14.6 s** | 161.7 s | 16 `octave-cli` |
  | `gen_baselines.py --kind rel --jobs 32` | 15.3 s | 204.1 s | 32 `octave-cli` |

  Both grids together: about 20 s with `--jobs 16`, against 2 min 45 s serial (≈8×). The
  feat wall time is set by the three tree runs (5–10 s each). Other jobs shared the machine
  (load average 8–11), which is why the serial times vary between runs. The earlier
  pre-fix runs were slower for the same reason (feat 10.8 s, rel 30.8 s at 16 jobs).
- Docs: `README.md` (bullet in "How it was verified", the commands block, the layout row),
  `CLAUDE.md` (the baseline command), the `PLAN.md` tree, and ANOMALIES A20.
- Gate (fd env, strict): **3637 passed, 3 skipped (the known sklearn/nbformat, no Octave
  skips), 79 deselected, exit 0**, in 40 min 37 s wall, 2892 s CPU. A first attempt was
  stopped at 10 min by a tool time limit I set too low; it is not a test result.
### Blockers
- None. A19 (gibbs kept unpinned) is still open for a human.
### Next
- Item 05: parallel gate with pytest-xdist (`-n 16`, one Octave per worker).

---

## Iteration 6 — 2026-10-01 01:45
### Completed
- Item 05, parallel gate with pytest-xdist.
  - Installed `pytest-xdist=3.8.0` (and `execnet` 2.1.2) from conda-forge in the fd env.
    Added it to `environment.yml` and to `pyproject.toml` `[test]` (`pytest-xdist>=3`).
    `loop.py`'s default `TEST_CMD` is now `<fd python> -m pytest -q -m "not slow" -n 16`.
  - One Octave per worker: each xdist worker is its own pytest session, so the
    session-scoped `octave` fixture starts one Oct2Py per worker. New live
    `test_gate_env.py::test_xdist_one_octave_per_worker` runs an inner `-n 2` session and
    checks two workers with two distinct Octave PIDs, one PID per worker.
  - Concurrency check. The first `-n 16` run passed, but
    `test_viz_networkx.py::test_networkx_differs_from_graph_draw_render` left
    `tests/baseline_images/networkx/feat_tree_demo_tree_feat_notext-failed-diff.png`.
    matplotlib's `compare_images` writes `<actual>-failed-diff.png` next to its second
    argument, which there was a committed baseline (gitignored, so `git status` did not
    show it). Fixed: the test compares a copy in `tmp_path`. To keep this from coming
    back, `conftest.py` records the files under `tests/` at session start (controller or
    serial session only) and fails the run if a new one appears
    (`test_new_file_under_tests_fails`). There are no other shared names: `_GtDout.dot`/
    `_LAYout.dot` are not written by the Python side, and the live Octave `draw_dot` test
    `cd`s to `tmp_path`. The `randperm` logs are in `tmp_path`, and the tools' Octave runs
    use temporary directories or the test's `tmp_path` for logs and outputs. The Oct2Py
    cwd is the repo root, and `git status --ignored` shows nothing new after the runs.
    No anomaly: this was a test-hygiene bug, not a formdiscovery1.0 or Octave issue.
  - Scheduling. xdist's `load` hands out contiguous chunks, so the first run put both
    gibbs live tests (≈300 s each) on one worker: 10:22 wall at 533 % CPU. Under xdist,
    `conftest.long_first` now puts the `LONG_TESTS` (19 tests ≥ 30 s, timings from
    `--durations`) first, longest first, each followed by one short test. `pytest_configure`
    defaults `--maxschedchunk` to 1 on the controller, so every worker starts with one
    long test. A serial run keeps pytest's order. Tests: `test_long_first`,
    `test_long_tests_exist`, `test_maxschedchunk_default`. The wall clock is now the
    longest single test (gibbs `test_live_fresh_seeds`, 358 s at `-n 16`).
  - Determinism: three `-n 16` runs, one `-n 8` run and one serial run (JUnit XML,
    `build/xdist/`) have **identical (nodeid, outcome) sets**: 3642 passed, 3 skipped
    (sklearn 1, nbformat 2; no Octave skips) each. All exit 0.

  | gate run (fd env, strict, this tree) | wall clock | CPU (user+sys) | workers |
  |---|---|---|---|
  | serial (no `-n`) | 38 min 16 s | 2754 s (119 %) | 1 (+1 Octave) |
  | `-n 16`, before scheduling fix | 10 min 22 s | 3319 s (533 %) | 16 (+16 Octave) |
  | `-n 8` | **6 min 03 s** | 3255 s (895 %) | 8 (+8 Octave) |
  | `-n 16`, run a | 6 min 12 s | 3604 s (969 %) | 16 (+16 Octave) |
  | `-n 16`, run b | 6 min 05 s | 3560 s (975 %) | 16 (+16 Octave) |
  | `-n 16`, run c | **6 min 01 s** | 3572 s (989 %) | 16 (+16 Octave) |

  6.3× faster than serial. `-n 8` is as fast as `-n 16` because both are limited by the
  358 s gibbs test. `-n 16` keeps the requested setting and leaves headroom. The parallel
  runs use about 30 % more CPU than serial: 16 Octave startups, contention for memory
  bandwidth, and the unpinned gibbs regeneration (A19) running 32 BLAS threads beside 15
  other workers. Going below about 6 min would mean splitting the gibbs and spr live
  tests (per-run parametrisation), which this item did not do.
- Docs: `README.md` ("How it was verified" bullet and the commands block) and `CLAUDE.md`
  (the gate command, pytest-xdist in the env).
### Blockers
- None. A19 (gibbs kept unpinned) is still open for a human.
### Next
- Item 06: `tools/compare_live.py --pairs ... --jobs N` (Octave and Python side by side).

---

## Iteration 7 — 2026-10-01 03:48
### Completed
- Item 06, the side-by-side live comparison tool.
  - New `tools/compare_live.py [--pairs S:D[:SEED] ...] [--set all|feat|rel] [--seed N]
    --jobs N [--logdir D] [--json F]`. A pair is `structure:dataset[:seed]`, as names or
    1-based `ps` indices. The default set is run_baseline's two grids in run order, 9
    feature and then 54 relational pairs, all with seed 1. Each triple is one task in a
    `ProcessPoolExecutor` (spawn context, workers pinned with `pin_blas_env` and
    `pin_process_blas(1)`). A task does two things:
    1. Octave: `run_baseline(kind, sind, dind, dir, seed)` in its own pinned `octave-cli`
       (`gen_fixtures._run_octave`, per-triple log in `build/compare_live/<key>.log`). The
       `randperm` shim runs in pass-through mode and logs every draw
       (`randperm_config('', log)`). `kind` is `rel` (`reloutsideinit = 'overd'`) for
       relational data.
    2. Python: `runmodel` on the same pair and the same `ps`, replaying Octave's log with the
       new `ReplayThenNumpy` provider. There are no oracles: Python uses its own scaled
       data, scipy's optimizer and its own tie breaking. Once a draw no longer fits (wrong
       length or queue exhausted), the provider goes on with `NumpyPermutations(seed)`, and
       the row records `full` or `diverged@k`.

    Octave and Python runs of different triples overlap. The table gives Octave and Python
    ll, relative difference, ARI, clusters and nodes on each side, the draws, the replay
    status, each side's wall time, and a §7.1 verdict: within 1e-3 rel, same cluster count,
    ARI = 1 on a full replay and ≥ 0.9 on a diverged one. With seed 1, Octave's ll must also
    equal the committed baseline exactly.
  - `matlab/run_baseline.m` gets an optional 5th argument `seed`:
    `rand('state', seed + rind - 1)`. The default of 1 gives the old `rand('state', rind)`.
    The committed baselines are unchanged: the gate's live baseline tests pass, and all 63
    Octave scores here equal the committed ones exactly.
  - New `tests/test_compare_live.py` (7 tests). The unit tests cover `parse_pair`, the
    default triples (against `gen_baselines.GRIDS` and the `EXPECTED_LL` keys),
    `data_kind`, `ReplayThenNumpy` and the table. A live `octave` test in the gate (≈3 s)
    runs 4 cheap relational triples, one of them seed 2: `--jobs 1` and `--jobs 4` give
    identical rows, and all meet §7.1. A `slow` live test runs the 63 default triples with 16
    workers. It checks §7.1 on every row, Octave = committed baseline, relational scores
    exact to 1e-12, and at least 50 of 54 relational replays complete. It passes in 30 s.
  - **Result: 63/63 rows pass §7.1.** Every Octave ll equals the committed baseline. All
    54 relational pairs agree to ≤ 1.0e-15 rel with ARI 1. The 9 feature pairs agree to
    ≤ 7.4e-6 rel with ARI 1 and Octave's cluster and node counts. All 9 feature replays
    diverge (draws 20–201) where scipy's optimum differs from fminunc's (A3). 53 of 54
    relational replays run to the end. The exception is `partitionnoself x
    demo_hierarchy_rel_bin`, which diverges at draw 58 on a mirror-image tied split: after
    the first split Python's clusters come out 19 | 7 against Octave's 7 | 19, and Python
    then asks for `randperm(19)` where Octave drew `randperm(7)`. Python still reaches the
    same partition and score. Logged as **ANOMALIES A21 (explained)**: these are the same
    ties that `SplitOracle` absorbs in loop0001's exact replays. No KI entry, because the
    scores are equal and either order is correct.
  - Determinism: the `--jobs 1`, `--jobs 16` and `--jobs 32` JSON rows are identical apart
    from the times (all numbers, replay status and verdicts).

  | run (63 triples) | wall clock | CPU (user+sys) | workers |
  |---|---|---|---|
  | `compare_live.py --jobs 1` | 3 min 35 s | 216.6 s | 1 (Octave then Python, in turn) |
  | `compare_live.py --jobs 16` | **25.7 s** (8.3×) | 257.4 s | 16 workers + their `octave-cli` |
  | `compare_live.py --jobs 32` | 21.8 s | 375.7 s | 32 workers + their `octave-cli` |

  Summed per-side wall times at `--jobs 1`: Octave 162.3 s, Python 51.7 s. Per run (`--jobs 1`,
  Octave startup included), Python is 1.2–6.9× faster than Octave, except on
  `tree x demo_tree_feat`, where it is 10 % slower. At `--jobs 16` the wall time is
  set by the longest tasks (`dirhierarchy x demo_hierarchy_rel_bin`: 13.4 s Octave +
  2.9 s Python). `--jobs 32` gains only 4 s for 46 % more CPU.

  Full table (`--jobs 16`):

  | structure | data | seed | Octave ll | Python ll | rel diff | ARI | clusters O/P | nodes O/P | draws | replay | Octave s | Python s | ok |
  |---|---|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|---|
  | chain | demo_chain_feat | 1 | -8247.204813 | -8247.192418 | 1.5e-06 | 1.000 | 4/4 | 4/4 | 121 | diverged@44 | 2.0 | 1.5 | yes |
  | ring | demo_chain_feat | 1 | -8264.200371 | -8264.196320 | 4.9e-07 | 1.000 | 4/4 | 4/4 | 134 | diverged@44 | 2.2 | 1.6 | yes |
  | tree | demo_chain_feat | 1 | -8252.886501 | -8252.947688 | 7.4e-06 | 1.000 | 4/4 | 6/6 | 255 | diverged@201 | 5.8 | 4.9 | yes |
  | chain | demo_ring_feat | 1 | -8566.636517 | -8566.635937 | 6.8e-08 | 1.000 | 4/4 | 4/4 | 160 | diverged@20 | 2.6 | 1.4 | yes |
  | ring | demo_ring_feat | 1 | -8500.520170 | -8500.518235 | 2.3e-07 | 1.000 | 4/4 | 4/4 | 160 | diverged@20 | 2.4 | 1.6 | yes |
  | tree | demo_ring_feat | 1 | -8512.873765 | -8512.860034 | 1.6e-06 | 1.000 | 4/4 | 6/6 | 268 | diverged@28 | 5.8 | 3.7 | yes |
  | chain | demo_tree_feat | 1 | -8764.165562 | -8764.171835 | 7.2e-07 | 1.000 | 4/4 | 4/4 | 134 | diverged@105 | 2.4 | 1.7 | yes |
  | ring | demo_tree_feat | 1 | -8722.589004 | -8722.608739 | 2.3e-06 | 1.000 | 4/4 | 4/4 | 161 | diverged@90 | 2.9 | 1.7 | yes |
  | tree | demo_tree_feat | 1 | -8707.813669 | -8707.808730 | 5.7e-07 | 1.000 | 4/4 | 6/6 | 239 | diverged@163 | 6.5 | 7.0 | yes |
  | partition | demo_ring_rel_bin | 1 | -33.900480 | -33.900480 | 2.1e-16 | 1.000 | 2/2 | 2/2 | 34 | full | 0.6 | 0.1 | yes |
  | partitionnoself | demo_ring_rel_bin | 1 | -34.770934 | -34.770934 | 0.0e+00 | 1.000 | 2/2 | 2/2 | 46 | full | 0.7 | 0.1 | yes |
  | dirchain | demo_ring_rel_bin | 1 | -25.243492 | -25.243492 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 18 | full | 0.9 | 0.2 | yes |
  | dirchainnoself | demo_ring_rel_bin | 1 | -20.509796 | -20.509796 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 18 | full | 0.9 | 0.2 | yes |
  | undirchain | demo_ring_rel_bin | 1 | -36.180524 | -36.180524 | 0.0e+00 | 1.000 | 2/2 | 2/2 | 36 | full | 0.7 | 0.1 | yes |
  | undirchainnoself | demo_ring_rel_bin | 1 | -24.108644 | -24.108644 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 19 | full | 0.7 | 0.1 | yes |
  | order | demo_ring_rel_bin | 1 | -36.834862 | -36.834862 | 0.0e+00 | 1.000 | 2/2 | 2/2 | 48 | full | 0.8 | 0.1 | yes |
  | ordernoself | demo_ring_rel_bin | 1 | -35.268000 | -35.268000 | 0.0e+00 | 1.000 | 2/2 | 2/2 | 48 | full | 0.8 | 0.1 | yes |
  | connected | demo_ring_rel_bin | 1 | -35.617544 | -35.617544 | 0.0e+00 | 1.000 | 2/2 | 2/2 | 48 | full | 0.7 | 0.1 | yes |
  | connectednoself | demo_ring_rel_bin | 1 | -31.710242 | -31.710242 | 1.1e-16 | 1.000 | 2/2 | 2/2 | 48 | full | 0.7 | 0.1 | yes |
  | dirring | demo_ring_rel_bin | 1 | -22.187235 | -22.187235 | 3.2e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 1.0 | 0.2 | yes |
  | dirringnoself | demo_ring_rel_bin | 1 | -16.571443 | -16.571443 | 6.4e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 0.9 | 0.2 | yes |
  | undirring | demo_ring_rel_bin | 1 | -23.967559 | -23.967559 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 18 | full | 0.7 | 0.1 | yes |
  | undirringnoself | demo_ring_rel_bin | 1 | -22.012007 | -22.012007 | 3.2e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 0.7 | 0.1 | yes |
  | dirhierarchy | demo_ring_rel_bin | 1 | -25.697328 | -25.697328 | 1.4e-16 | 1.000 | 4/4 | 4/4 | 57 | full | 1.4 | 0.3 | yes |
  | dirhierarchynoself | demo_ring_rel_bin | 1 | -20.963631 | -20.963631 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 57 | full | 1.3 | 0.3 | yes |
  | undirhierarchy | demo_ring_rel_bin | 1 | -25.866105 | -25.866105 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 33 | full | 0.8 | 0.2 | yes |
  | undirhierarchynoself | demo_ring_rel_bin | 1 | -24.182736 | -24.182736 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 81 | full | 1.2 | 0.3 | yes |
  | partition | demo_hierarchy_rel_bin | 1 | -137.839985 | -137.839985 | 8.2e-16 | 1.000 | 3/3 | 3/3 | 174 | full | 5.8 | 1.0 | yes |
  | partitionnoself | demo_hierarchy_rel_bin | 1 | -135.483933 | -135.483933 | 1.0e-15 | 1.000 | 3/3 | 3/3 | 232 | diverged@58 | 8.7 | 1.5 | yes |
  | dirchain | demo_hierarchy_rel_bin | 1 | -67.166824 | -67.166824 | 4.2e-16 | 1.000 | 5/5 | 5/5 | 97 | full | 5.1 | 1.4 | yes |
  | dirchainnoself | demo_hierarchy_rel_bin | 1 | -63.026923 | -63.026923 | 1.1e-16 | 1.000 | 5/5 | 5/5 | 182 | full | 6.9 | 1.8 | yes |
  | undirchain | demo_hierarchy_rel_bin | 1 | -65.795092 | -65.795092 | 4.3e-16 | 1.000 | 5/5 | 5/5 | 97 | full | 5.6 | 1.4 | yes |
  | undirchainnoself | demo_hierarchy_rel_bin | 1 | -63.046911 | -63.046911 | 2.3e-16 | 1.000 | 5/5 | 5/5 | 97 | full | 5.4 | 1.5 | yes |
  | order | demo_hierarchy_rel_bin | 1 | -145.764105 | -145.764105 | 7.8e-16 | 1.000 | 3/3 | 3/3 | 236 | full | 10.9 | 1.7 | yes |
  | ordernoself | demo_hierarchy_rel_bin | 1 | -145.270424 | -145.270424 | 9.8e-16 | 1.000 | 3/3 | 3/3 | 236 | full | 10.2 | 1.8 | yes |
  | connected | demo_hierarchy_rel_bin | 1 | -136.720410 | -136.720410 | 1.0e-15 | 1.000 | 3/3 | 3/3 | 234 | full | 9.4 | 1.6 | yes |
  | connectednoself | demo_hierarchy_rel_bin | 1 | -136.709061 | -136.709061 | 8.3e-16 | 1.000 | 3/3 | 3/3 | 234 | full | 9.4 | 1.7 | yes |
  | dirring | demo_hierarchy_rel_bin | 1 | -66.900334 | -66.900334 | 2.1e-16 | 1.000 | 5/5 | 5/5 | 94 | full | 4.0 | 1.0 | yes |
  | dirringnoself | demo_hierarchy_rel_bin | 1 | -65.153688 | -65.153688 | 0.0e+00 | 1.000 | 5/5 | 5/5 | 94 | full | 4.0 | 1.1 | yes |
  | undirring | demo_hierarchy_rel_bin | 1 | -64.292369 | -64.292369 | 8.8e-16 | 1.000 | 5/5 | 5/5 | 94 | full | 4.2 | 1.0 | yes |
  | undirringnoself | demo_hierarchy_rel_bin | 1 | -62.286278 | -62.286278 | 3.4e-16 | 1.000 | 5/5 | 5/5 | 94 | full | 4.3 | 0.9 | yes |
  | dirhierarchy | demo_hierarchy_rel_bin | 1 | -70.246660 | -70.246660 | 2.0e-16 | 1.000 | 5/5 | 5/5 | 501 | full | 13.4 | 2.9 | yes |
  | dirhierarchynoself | demo_hierarchy_rel_bin | 1 | -63.332757 | -63.332757 | 0.0e+00 | 1.000 | 5/5 | 5/5 | 253 | full | 7.8 | 1.7 | yes |
  | undirhierarchy | demo_hierarchy_rel_bin | 1 | -71.815458 | -71.815458 | 4.0e-16 | 1.000 | 5/5 | 5/5 | 254 | full | 9.1 | 2.1 | yes |
  | undirhierarchynoself | demo_hierarchy_rel_bin | 1 | -67.098305 | -67.098305 | 2.1e-16 | 1.000 | 5/5 | 5/5 | 254 | full | 8.5 | 1.9 | yes |
  | partition | demo_order_rel_freq | 1 | -3685.662207 | -3685.662207 | 2.5e-16 | 1.000 | 4/4 | 4/4 | 50 | full | 0.4 | 0.1 | yes |
  | partitionnoself | demo_order_rel_freq | 1 | -3683.781001 | -3683.781001 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 74 | full | 0.5 | 0.1 | yes |
  | dirchain | demo_order_rel_freq | 1 | -3685.466330 | -3685.466330 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 19 | full | 0.4 | 0.1 | yes |
  | dirchainnoself | demo_order_rel_freq | 1 | -3682.323096 | -3682.323096 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 19 | full | 0.4 | 0.1 | yes |
  | undirchain | demo_order_rel_freq | 1 | -3685.851609 | -3685.851609 | 3.7e-16 | 1.000 | 4/4 | 4/4 | 19 | full | 0.5 | 0.1 | yes |
  | undirchainnoself | demo_order_rel_freq | 1 | -3685.337243 | -3685.337243 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 19 | full | 0.5 | 0.1 | yes |
  | order | demo_order_rel_freq | 1 | -3682.198532 | -3682.198532 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 76 | full | 0.9 | 0.2 | yes |
  | ordernoself | demo_order_rel_freq | 1 | -3663.616277 | -3663.616277 | 8.7e-16 | 1.000 | 4/4 | 4/4 | 76 | full | 0.8 | 0.2 | yes |
  | connected | demo_order_rel_freq | 1 | -3683.780622 | -3683.780622 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 76 | full | 0.7 | 0.2 | yes |
  | connectednoself | demo_order_rel_freq | 1 | -3684.141544 | -3684.141544 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 76 | full | 0.8 | 0.2 | yes |
  | dirring | demo_order_rel_freq | 1 | -3684.938153 | -3684.938153 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 18 | full | 0.4 | 0.1 | yes |
  | dirringnoself | demo_order_rel_freq | 1 | -3683.447012 | -3683.447012 | 2.5e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 0.5 | 0.1 | yes |
  | undirring | demo_order_rel_freq | 1 | -3685.126414 | -3685.126414 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 0.4 | 0.1 | yes |
  | undirringnoself | demo_order_rel_freq | 1 | -3684.717571 | -3684.717571 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 18 | full | 0.4 | 0.1 | yes |
  | dirhierarchy | demo_order_rel_freq | 1 | -3685.920165 | -3685.920165 | 1.2e-16 | 1.000 | 4/4 | 4/4 | 57 | full | 0.7 | 0.2 | yes |
  | dirhierarchynoself | demo_order_rel_freq | 1 | -3682.776931 | -3682.776931 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 57 | full | 0.7 | 0.2 | yes |
  | undirhierarchy | demo_order_rel_freq | 1 | -3685.925701 | -3685.925701 | 0.0e+00 | 1.000 | 4/4 | 4/4 | 35 | full | 0.5 | 0.1 | yes |
  | undirhierarchynoself | demo_order_rel_freq | 1 | -3685.411335 | -3685.411335 | 2.5e-16 | 1.000 | 4/4 | 4/4 | 35 | full | 0.5 | 0.1 | yes |

- Docs: `README.md` (bullet in "How it was verified" and the commands block), `CLAUDE.md`
  (the command), the `PLAN.md` tree, and ANOMALIES A21.
- Gate (fd env, strict, `-n 16`): **3648 passed, 3 skipped (the known sklearn/nbformat, no
  Octave skips), exit 0**, in 6 min 07 s wall, 3596 s CPU.
### Blockers
- None. A19 (gibbs kept unpinned) is still open for a human.
### Next
- Item 07: wrap-up (consolidated before/after table in README, CLAUDE.md commands, the
  loop0001 `-m slow` suite in the fd env, then verify every item and complete the loop).
