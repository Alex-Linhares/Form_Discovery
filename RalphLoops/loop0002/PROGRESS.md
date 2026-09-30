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
