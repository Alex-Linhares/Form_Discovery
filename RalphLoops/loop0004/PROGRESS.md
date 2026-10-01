# Progress Log

## Ralph Loop 0004 Status
- **Started**: 2026-10-01
- **Target**: 6 items (see iterations.md)
- **Current**: 2/6 SOLVED

---

## Iteration 1 — 2026-10-01 17:09
### Completed
- Item 01 (Phase 1, data out). `git mv matlab/formdiscovery1.0/data data` (20 `.mat`,
  `README.txt`, `faces.tar.gz`, `.svnignore`; history kept). Committed relative symlink
  `matlab/formdiscovery1.0/data -> ../../data` (mode 120000, staged); no `.m` source edited.
- `io.DATA_DIR = REPO_ROOT / "data"` (`$FORMDISCOVERY_DATA` still overrides). `params.setps`
  (`ps.dlocs`), the GUI default directory and `--demo`, `tools/gui_screenshots.py`,
  `tools/compare_runs.py` and every Python test already went through `io.DATA_DIR`, so they
  follow with no edit. Spelled-out old paths fixed: `cli.py` docstring, README (GUI command,
  Layout gains a `data/` row), `tests/octave/fx_l0b.m`, `fx_viz_dot.m`, `fx_matlab_compat.m`
  (now `root/data`), `fx_masterrun.m` (its temp `data` symlink points at `root/data`). The
  `mdir/data` loads in other fixture scripts and `setps.m`'s `pwd/data` go through the symlink.
- Docs: `matlab/PATCHES.md` "Data symlink (not a source patch)"; CLAUDE.md "Data:" line;
  CONVENTIONS.md (`setps`/`DATA_DIR`).
- New test `tests/test_io.py::test_data_dir_is_repo_data_and_matlab_side_links_to_it`
  (default dir, symlink target, env override in a subprocess).
- Live verification: `gen_baselines.py --kind feat --struct 2 --data 1` (= `run_baseline('feat',
  2, 1)`, chain × demo_chain_feat) into `build/`: growth history identical (`compare_mat`),
  `modellike` −8247.20481344 and `llhistory` equal to the committed pair. Fixture
  regeneration of `params preprocess matlab_compat l0b viz_dot masterrun` (`-j 6`, into
  `build/`, `--compare tests/fixtures`): 6 identical, 0 differ.
- Found and fixed A30: `gen_fixtures._publish` used `os.replace` from `/tmp` and failed
  with EXDEV when `--outdir` is on another file system; now copies to `<out>.part` and
  renames. Test `test_gen_fixtures.py::test_publish_across_file_systems`. ANOMALIES.md A30.
- Strict gate (`RALPH_REQUIRE_OCTAVE=1`, `-n 16`): 3742 passed, 3 skipped, 373.7 s. No file
  under `tests/fixtures/` modified.
- Grep: `formdiscovery1.0/data` now appears only in PLAN_LEGACY.md, loop0004 TASK/iterations,
  older RalphLoops logs, PATCHES.md (the symlink note) and CLAUDE.md (same).
### Blockers
- None.
### Next
- Item 02: `git mv matlab legacy/matlab` etc.; re-point the symlink to `../../../data`
  (and update `test_io.py`'s symlink check, which expects `matlab/formdiscovery1.0/data` →
  `../../data` and is skipped only if that directory is absent).

## Iteration 2 — 2026-10-01 17:25
### Completed
- Item 02 (Phase 2, moves). `git mv matlab legacy/matlab`, `git mv tests/octave
  legacy/tests_octave`, and `gen_fixtures.py`, `gen_baselines.py`, `gen_paperlevel.py`,
  `compare_live.py`, `mat_compare.py` to `legacy/tools/` (history kept, all `R`). Symlink
  re-pointed: `legacy/matlab/formdiscovery1.0/data -> ../../../data` (mode 120000, staged).
  `bench_perf.py` stays in `tools/`: only `--live` needs Octave (it imports
  `legacy.tools.gen_fixtures.run_one` lazily); `compare_runs.py` likewise
  (`live_fixture`).
- `tests/conftest.py`: one `LEGACY_DIR = REPO_ROOT / "legacy"`; `MATLAB_DIR`, `SHIM_DIR`,
  `OCTAVE_TESTS_DIR` derive from it. Tests use `LEGACY_DIR / "matlab"` (test_baseline,
  test_baseline_rel, test_gen_baselines, test_patches, test_gate_env) and
  `OCTAVE_TESTS_DIR / "drawdot_shim"` (test_viz_interactive); `test_io.py` checks the new
  symlink. Tools and tests import `legacy.tools.<name>` (namespace package, no
  `__init__.py`); moved tools use `REPO_ROOT = parents[2]`; `gen_baselines` and
  `compare_live` add `LEGACY_DIR / 'matlab'` to the Octave path.
- `.m` scripts: `fullfile(root, 'legacy', 'matlab', ...)` (root = `here/../..` is still the
  repo root); `fx_util.m`, `fx_matlab_compat.m`, `fx_dot_to_graph.m` and `run_baseline.m`
  (output dir `here/../../tests/fixtures/baseline`) fixed. No `formdiscovery1.0/*.m` edited;
  `dot_to_graph.m`'s comment `see matlab/PATCHES.md` is left (noted in PATCHES.md).
- Paths rewritten repo-wide by one script (`tests/octave` -> `legacy/tests_octave`,
  `matlab/` -> `legacy/matlab/`, `tools/<moved>` -> `legacy/tools/<moved>`, module
  imports): README (Layout gains `legacy/tests_octave/` and `legacy/tools/` rows; `tools/`
  row now lists the Python-side tools), CLAUDE.md (new "Legacy:" paragraph, symlink
  target), CONVENTIONS.md, PATCHES.md, ANOMALIES.md, KNOWN_ISSUES.md headers, module
  docstrings, the demo notebook and its generator (same text, so they stay in sync).
- A31 (ANOMALIES): built paths the rewrite missed (`REPO_ROOT / 'matlab'` in two
  f-strings, `fullfile(root, 'matlab', ...)` in the `.m` scripts); found by the live check.
- A32 (ANOMALIES): the committed baselines' `pss{}.dlocs{}` are absolute checkout paths
  (`.../matlab/formdiscovery1.0/data/<name>`); a fresh run now writes `.../legacy/...`,
  so `test_parallel_feat_equals_serial_baseline` failed on 180 strings (numbers equal).
  `gen_baselines.compare_baselines` compares strings after `source_relative` (prefix before
  `formdiscovery1.0/data/` dropped; `mat_compare.compare_dirs` got `normalize`). New test
  `test_gen_baselines.py::test_compare_baselines_masks_data_dir_prefix`. No fixture edited.
- Live verification: `legacy/tools/gen_fixtures.py -j 8 --outdir build/... --compare
  tests/fixtures dot_to_graph util matlab_compat rng params l0b viz_dot masterrun`: 8
  identical, 0 differ. `legacy/tools/gen_baselines.py --kind feat --struct 2 --data 1`:
  growth history identical, modellike −8247.20481344. `--help`/`--list` of every moved
  tool and `tools/bench_perf.py` run.
- Strict gate (`RALPH_REQUIRE_OCTAVE=1`, `-n 16`): 3743 passed, 3 skipped, 373.7 s
  (= 3742 before + the new test). Slow suite (`-m slow -n 16`, strict): 78 passed,
  1 skipped, 1 failed: `test_perf.py::test_fast_mode_within_octave_budget` (wall-clock
  budget, 0.63 ms vs 1.5 × 0.41 ms under 16-worker load, the load sensitivity loop0002
  recorded); it passes alone. No file under `tests/fixtures/` modified.
- Grep for `tests/octave`, unprefixed `matlab/`, `tools/<moved>` and `tools.<moved>`
  outside RalphLoops history, PLAN*.md and loop0004 TASK/iterations: only the
  `dot_to_graph.m` comment and PATCHES.md's sentence about it.
### Blockers
- None.
### Next
- Item 03: move the Octave-only tests to `legacy/tests/` and make their collection
  conditional on `legacy/` existing. Note: `test_gen_baselines.py` now also has an
  Octave-free test (`test_compare_baselines_masks_data_dir_prefix`) that moves with it.
