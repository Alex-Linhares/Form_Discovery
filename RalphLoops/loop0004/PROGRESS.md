# Progress Log

## Ralph Loop 0004 Status
- **Started**: 2026-10-01
- **Target**: 6 items (see iterations.md)
- **Current**: 6/6 SOLVED

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

## Iteration 3 — 2026-10-01 18:20
### Completed
- Item 03 (Phase 2, tests). `git mv` to `legacy/tests/`: `test_patches.py`,
  `test_toolchain.py`, `test_gen_fixtures.py`, `test_gen_baselines.py`, `test_mat_compare.py`
  and also `test_compare_live.py` (it tests `legacy/tools/compare_live.py`; not in the item's
  list, found by the no-`legacy/` run). `test_known_issues.py` split: `QUIRKS` and
  `test_every_entry_documented` stay; `test_quirk_at_cited_line`,
  `test_zinit_rel_is_unreferenced`, `test_dijkstra_called_with_one_output` (all read `.m`
  files) are in `legacy/tests/test_known_issues_sources.py`, importing `QUIRKS`.
- Collection mechanism (documented in `pyproject.toml`, `legacy/tests/conftest.py`,
  `tests/conftest.py` docstrings, README Layout, CLAUDE.md): `testpaths = ["tests",
  "legacy/tests"]`; pytest drops a `testpaths` glob that matches nothing, so without
  `legacy/` only `tests/` is collected. `legacy/tests/` has no `__init__.py` (prepend mode
  would name it `tests`); its conftest puts the repo root on `sys.path` and re-exports
  `octave`, `replay`, `pytest_configure` and `pytest_runtest_makereport` (per-item hooks are
  path-scoped, so strict mode needs its own copy there) and runs the top conftest's
  `pytest_collection_modifyitems` only when `legacy/tests` is run alone.
- `tests/conftest.py`: `octave` tests are skipped at collection when
  `legacy/matlab/formdiscovery1.0` is absent (strict mode turns that into a failure, checked
  in a no-`legacy/` copy: `RALPH_REQUIRE_OCTAVE=1` -> errors with the reason,
  `=0` -> skips).
- A33 (ANOMALIES): `tests/test_gibbs.py` imported `legacy.tools.gen_fixtures` at module
  level, so it and the four modules that import from it (`test_runmodel`, `test_structurefit`,
  `test_masterrun`, `test_viz_draw`) failed to collect without `legacy/`. The import is now
  inside the live test.
- New tests in `tests/test_gate_env.py`: `test_legacy_tests_collected_only_when_present`
  (mini project, with and without `legacy/tests`), `test_octave_tests_skip_without_legacy`,
  `test_legacy_conftest_reexports` (skips without `legacy/`).
- Moved-test paths updated in ANOMALIES (A20, A21, A30, A32), KNOWN_ISSUES (intro, KI-5,
  KI-6, KI-15 pins), PATCHES.md, and the `legacy/tools` docstrings. README gains the
  fixture-only command `python -m pytest -q -m "not slow and not octave" -n 16`.
- Proof without `legacy/` (a copy of the working tree via `git ls-files -co`, `legacy/`
  deleted): `-m "not slow and not octave" -n 16` under the fd env: 3575 passed, 3 skipped,
  103 s; under the base interpreter (`~/anaconda3/bin/python`, no oct2py; pytest-xdist added
  in a throwaway `--system-site-packages` venv because the base env lacks it): 3305 passed,
  188 skipped (GUI modules without PySide6, etc.), 94 s. `legacy/tests` alone under the
  base interpreter: 93 passed (octave tests skip with `RALPH_REQUIRE_OCTAVE=0`).
- Strict gate (`RALPH_REQUIRE_OCTAVE=1`, `-n 16`): 3746 passed, 3 skipped (= 3743 + the 3
  new tests; collected count with `-m "not slow"` unchanged at 3746 before the new tests),
  522.5 s (the machine had another 6-worker job running, load ~25). No file under
  `tests/fixtures/` modified.
### Blockers
- None.
### Next
- Item 04: environment split (`environment.yml` Python-only, `legacy/environment-octave.yml`),
  `pyproject.toml` extras, README/CLAUDE.md/CONVENTIONS.md/`legacy/README.md`. Note: the base
  interpreter has no pytest-xdist, so the documented fixture-only `-n 16` command needs the
  `test` extra installed.

## Iteration 4 — 2026-10-01 18:27
### Completed
- Item 04 (Phase 2, env + docs). `environment.yml` is Python-only (octave and oct2py
  removed; PySide6, pytest-qt, pygraphviz, plotly/pyvis stay). New
  `legacy/environment-octave.yml` (`name: fd`, used as `conda env update -f
  legacy/environment-octave.yml`): octave=10.3.0, oct2py=6.1.1, and python, numpy, scipy,
  libopenblas=0.3.34 repeated so the update cannot move them (A19). Both verified with
  `conda env create --dry-run`: the Python-only file solves with no Octave package; the
  two merged solve to exactly the builds installed in the fd env (same octave, oct2py,
  numpy, scipy, python, libopenblas build strings).
- `pyproject.toml`: `octave` extra kept, commented as legacy (only for `legacy/`, removed
  in Phase 5). The `test` extra already includes pytest-xdist.
- New test `legacy/tests/test_toolchain.py::test_environment_split` (no Octave in
  `environment.yml`; octave/oct2py in the legacy file; shared pins agree).
- Docs: README (Quick start env line and a note; "How it was verified" names the env
  file and versions; new section "Legacy: the Octave oracle"; Layout rows for
  `legacy/environment-octave.yml`, `legacy/README.md`, `environment.yml`/`pyproject.toml`;
  command comment for `-m octave`), CLAUDE.md Environment line, CONVENTIONS.md intro
  (package never needs Octave), new `legacy/README.md` (contents table, environment, the
  live suite with counts: 74 `octave` tests in the default gate + 3 slow, 38 files;
  regeneration commands checked against each tool's `--help`).
- A34 (ANOMALIES, explained): an `fd` env built from the Python-only file is strict by
  default (`octave_required` keys on the env name), so octave tests fail rather than skip
  until the legacy env file is applied; documented, kept for this loop's strict gate.
- Strict gate (`RALPH_REQUIRE_OCTAVE=1`, `-n 16`): 3747 passed, 3 skipped, 402 s
  (= 3746 + the new test). No file under `tests/` modified.
### Blockers
- None.
### Next
- Item 05: `tests/fixtures/SHA256SUMS` + hash test, `tools/legacy_check.sh` (or Makefile
  `legacy-check`), time the fixture-only gate, `RalphLoops/loop_template/loop.py`,
  ralph_loop_guide.md, CLAUDE.md post-freeze policy line. Consider whether the fixture-only
  default should also relax the fd-env strict default (A34).

## Iteration 5 — 2026-10-01 18:43
### Completed
- Item 05 (Phase 3). `tests/fixtures/SHA256SUMS` (115 files, `sha256sum` format, paths
  relative to `tests/fixtures`, C-sorted, the list itself excluded). New
  `tests/test_fixture_integrity.py` (118 tests: every file listed and every listed file
  present, list sorted/well formed, one hash test per fixture, a tmp_path check that an
  edit and an extra file are caught). Verified by appending a byte to `graph.mat`: exactly
  `test_fixture_hash[graph.mat]` failed; file restored. Rewrite command documented in the
  test docstring and `legacy/README.md`
  (`git ls-files ':!SHA256SUMS' | LC_ALL=C sort | xargs sha256sum > SHA256SUMS`).
- `Makefile` (chose it over `tools/legacy_check.sh`): `make test` = default gate
  `-m "not slow and not octave" -n $(JOBS)`; `make legacy-check` =
  `RALPH_REQUIRE_OCTAVE=1 ... -m "not slow" -n $(JOBS)` (the strict live gate);
  `make slow`; `make fixture-sums` (`sha256sum -c`). `PY` defaults to the fd env.
- `RalphLoops/loop_template/loop.py`: copy of loop0004's runner with
  `TEST_CMD` default `-m "not slow and not octave" -n 16` and docstring on when to set
  `RALPH_TEST_CMD='make legacy-check'`. `loop0004/loop.py` unchanged (strict).
  New `tests/test_gate_env.py::test_gate_commands` pins the template, loop0004 and Makefile
  commands. `ralph_loop_guide.md`: "The regression gate (this repo)" section, template in
  the folder tree.
- A34 follow-up: no change needed. The fixture-only gate deselects `octave` tests, so the
  fd env's strict default never sees one; the template still sets
  `RALPH_REQUIRE_OCTAVE=1` so an overridden live command stays strict.
- Docs: CLAUDE.md (default gate, strict live gate, post-freeze policy line: a change that
  alters a fixture value needs the oracle rerun first, from the `octave-oracle-final` tag
  after the freeze, and updates fixture + hash line in one commit), README (command block,
  verification table row, Legacy section policy, Layout rows `Makefile`, `tests/`,
  `RalphLoops/`), `legacy/README.md`, CONVENTIONS.md intro.
- Timings (machine shared with another 6-worker job, load ~10–15):
  `make test` 52 s, 3792 passed, 3 skipped (target < 2 min met);
  `make legacy-check` 382 s, 3866 passed, 3 skipped (= 3747 + 119 new tests). No file
  under `tests/fixtures/` modified (only the new `SHA256SUMS`). No new anomaly.
### Blockers
- None.
### Next
- Item 06: wrap-up (grep audit, strict + fixture-only gates in fd env and base interpreter
  and without `legacy/`, slow suite, `legacy/README.md` final, PLAN_LEGACY.md M1–M3 with
  numbers: M3 = 52 s fixture-only, `make legacy-check` green 3866 passed).

## Iteration 6 — 2026-10-01 18:59
### Completed
- Item 06 (wrap-up). Grep audit (outside RalphLoops history, PLAN*.md, KNOWN_ISSUES.md):
  `tests/octave`, unprefixed `matlab/`, the old data path, `tools/<moved tool>` /
  `tools.<moved tool>`, and the moved test files without `legacy/` turned up no stale
  references. The only hits are historical by design: the ANOMALIES A31/A33 text, the
  PATCHES.md diff headers and its note on the `dot_to_graph.m` comment (not editable),
  the A32 docstrings in `gen_baselines`, and `legacy/README.md` paths, which are relative
  to `legacy/`.
- Gates (fd env unless noted, logs in `build/loop0004_it6/`):
  - strict live gate (`RALPH_REQUIRE_OCTAVE=1 -m "not slow" -n 16`): 3866 passed,
    3 skipped, 379 s;
  - fixture-only `make test`: 3792 passed, 3 skipped, 50 s;
  - fixture-only under the base interpreter (`~/anaconda3/bin/python`, no oct2py;
    pytest-xdist from a throwaway `--system-site-packages` venv): 3521 passed,
    189 skipped, 40 s;
  - copy of the tree with `legacy/` deleted: fd env 3696 passed, 4 skipped, 50 s; base
    interpreter 3426 passed, 189 skipped, 45 s; `-m octave` errors under
    `RALPH_REQUIRE_OCTAVE=1` and skips 65 under `=0`;
  - slow suite (`-m slow -n 16`, strict): 79 passed, 1 skipped, 562 s. This time the
    perf budget test passed too.
- Counts in `legacy/README.md` checked by collection: 74 `octave` tests in the default gate,
  3 under `slow`, 38 files. `legacy/README.md` is final: it now also records the
  no-`legacy/` results.
- `PLAN_LEGACY.md`: the status line says Phases 1–3 are done; the milestones table has a
  Status column, with M1–M3 ticked and their numbers, and M4–M5 open.
- Items 01–05 re-checked in the tree: the `data/` symlink (mode 120000, `../../../data`);
  `io.DATA_DIR` with the env override; the `legacy/` layout; `environment.yml` (Octave
  only in comments); `make fixture-sums` clean; `loop_template/loop.py`; the CLAUDE.md
  policy line. No file under `tests/fixtures/` modified. No new anomaly.
### Blockers
- None.
### Next
- Loop complete. Phases 4–5 (freeze, tag `octave-oracle-final`, delete `legacy/`) are a
  later loop.

LOOP_COMPLETE
