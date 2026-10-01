# Progress Log

## Ralph Loop 0004 Status
- **Started**: 2026-10-01
- **Target**: 6 items (see iterations.md)
- **Current**: 1/6 SOLVED

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
