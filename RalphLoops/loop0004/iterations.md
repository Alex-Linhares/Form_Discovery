# Iterations — loop0004

Legend: `[ ]` pending · `[x]` solved · `[~]` blocked (details in PROGRESS.md).
Work on the first `[ ]` item only. Phase numbers refer to `/PLAN_LEGACY.md`.

- [x] 01. **Data out (Phase 1).** `git mv matlab/formdiscovery1.0/data data` (the 20 `.mat`
      files and `data/README.txt`); `io.DATA_DIR = REPO_ROOT/"data"` (env override kept);
      update `params` (`ps.dlocs`), the GUI default directory and `--demo`, every tool and
      test that spelled the old path. Add the relative symlink
      `matlab/formdiscovery1.0/data -> ../../data` so `setps.m`, `run_baseline.m` and the
      fixture scripts keep working unchanged; verify with a live `run_baseline('feat', 2, 1)`
      and one fixture regeneration compared to the committed file. Note the symlink in
      `matlab/PATCHES.md`. Strict gate green.
- [x] 02. **`legacy/` (Phase 2, moves).** `git mv matlab legacy/matlab`,
      `tests/octave legacy/tests_octave`, and the Octave tools (`gen_fixtures.py`,
      `gen_baselines.py`, `gen_paperlevel.py`, `compare_live.py`, `mat_compare.py`,
      `bench_perf.py` if it needs Octave) to `legacy/tools/`. Re-point the symlink
      (`legacy/matlab/formdiscovery1.0/data -> ../../../data`). One constant `LEGACY_DIR` in
      `tests/conftest.py`; `MATLAB_DIR`, `SHIM_DIR`, `OCTAVE_TESTS_DIR` derive from it. Fix
      every import and path (tools import each other; tests import tools). Strict gate green
      with the same counts.
- [x] 03. **Octave-only tests to `legacy/tests/` (Phase 2, tests).** Move `test_patches.py`,
      `test_toolchain.py`, `test_gen_fixtures.py`, `test_gen_baselines.py`,
      `test_mat_compare.py`, and split `test_known_issues.py` so the `.m` line-pin test lives
      in `legacy/tests/` while the decision/pin checks stay. Collection rule: `legacy/tests/`
      is collected only when `legacy/` exists (document the mechanism). Behaviour when
      `legacy/` is absent: `octave` tests skip (or fail under `RALPH_REQUIRE_OCTAVE=1`).
      Prove both: strict gate green with `legacy/`; in a temporary clone without `legacy/`,
      `pytest -q -m "not slow and not octave" -n 16` green under the fd env **and** under
      the base interpreter.
- [x] 04. **Environment split (Phase 2, env + docs).** `environment.yml` Python-only
      (PySide6 and the GUI extras stay); `legacy/environment-octave.yml` adds octave, oct2py
      and the pins; `pyproject.toml` extras adjusted (`octave` extra marked legacy or
      removed). README ("How it was verified", "Layout", a new "Legacy: the Octave oracle"
      section), CLAUDE.md, CONVENTIONS.md, `legacy/README.md` (what is there, how to run the
      live suite, how to regenerate fixtures and baselines). Strict gate green.
- [ ] 05. **Fixture-only default gate + integrity (Phase 3).** `tests/fixtures/SHA256SUMS`
      committed and a test that verifies every fixture's hash (fails on any edit, no Octave
      needed). `tools/legacy_check.sh` (or a `Makefile` target `legacy-check`) = the strict
      live gate. Document the default gate as `pytest -q -m "not slow and not octave" -n 16`
      and time it (target < 2 min); time the live job too. Update
      `RalphLoops/ralph_loop_guide.md` and add `RalphLoops/loop_template/loop.py` with the
      fixture-only default (`loop0004/loop.py` itself stays strict). Add the post-freeze
      policy line to CLAUDE.md ("a change that alters a fixture value needs the oracle rerun
      from the tag first").
- [ ] 06. **Wrap-up.** Grep audit for stale paths; run the strict gate, the fixture-only gate
      (fd env and base interpreter), and the `slow` suite; `legacy/README.md` final;
      PLAN_LEGACY.md M1–M3 ticked with the numbers; then verify every item above, update the
      status header and add the completion line.
