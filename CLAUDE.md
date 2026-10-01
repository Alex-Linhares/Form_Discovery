# Project notes for Claude sessions

This repo is a test-driven translation of Kemp & Tenenbaum's `formdiscovery1.0` (MATLAB) to
Python, verified against the original code running in GNU Octave.

Read first, in this order:
- `PLAN.md`: the plan (test architecture, dependency-ordered steps, hazards, milestones).
- `ANOMALIES.md`: the curated log of anomalies found (paper vs code, Octave vs MATLAB,
  surprising results, original bugs). **Every new anomaly must be added here** in the
  iteration that finds it, with a status of open / explained / handled.
- `KNOWN_ISSUES.md`: line-by-line entries (KI-n) with a decision (replicate / fix / not
  ported) and the test that pins each one.
- `matlab/PATCHES.md`: the only edits allowed to `matlab/formdiscovery1.0/`, each marked
  `PATCH(octave)` in the source.
- `src/formdiscovery/CONVENTIONS.md`: index, ordering and dtype rules for the port.

Work is driven by Ralph loops in `RalphLoops/loopNNNN/` (`TASK.md`, `iterations.md`,
`PROGRESS.md`, `loop.py`); see `RalphLoops/ralph_loop_guide.md`. `loop0001` did the port,
`loop0002` the Octave-backed parallel harness (before/after timings in README "How it was verified"),
`loop0003` the PySide6 GUI: package `src/formdiscovery/gui/` (`app.py` `main()`, `main_window.py`,
`dataset.py`, `worker.py` = `RunWorker` on a `QThread`, `canvas.py` = `GraphCanvas` (live frames, coalesced, stable neato positions), `stats.py` = `StatsPanel` (score + prior/likelihood parts, clusters, per-depth chart, export .npz/.json and PNG/SVG), `runs.py` = `RunQueue` (selected forms, N threads at once; `FormRun` + capped `FrameHistory` per form), `results.py` = `ResultsTable` (ranked by ll, winner, click a row; the window's frame slider scrubs a form's history); README "GUI" section; `formdiscovery gui [FILE]`; the only model hook is
`search.run_hooks` (per-thread cancel / on_depth, off by default)), a thin shell over the port with offscreen pytest-qt tests
(`tests/test_gui_*.py`, `QT_QPA_PLATFORM=offscreen` set in conftest) and screenshots in `examples/gui/`
(`tools/gui_screenshots.py`).

Environment: conda env `fd` (`environment.yml`) has Python, numpy/scipy, Octave 10.3, oct2py,
pygraphviz, pytest-xdist, PySide6 and pytest-qt. Regression gate: `~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow" -n 16`
(about 6 min, one Octave per xdist worker; about 40 min without `-n`; tests write only to `tmp_path`, and a
new file under `tests/` fails the run; in the fd env, or with `RALPH_REQUIRE_OCTAVE=1`, a skipped `octave` test is a failure;
`RALPH_REQUIRE_OCTAVE=0` allows skips). Live Octave parity only: `-m octave` in the fd env. Long runs: `-m slow -n 16` in the fd env (about 9 min; heavy module
fixtures shared across workers with `tests/helpers.xdist_shared`). Fixtures are regenerated only through Octave
(`tools/gen_fixtures.py`, `--jobs N` Octave processes at once, default cores/2; regenerate into
`--outdir` with `--compare tests/fixtures` rather than over the committed files). Baselines:
`tools/gen_baselines.py --kind feat|rel --jobs N --outdir D --compare tests/fixtures/baseline/<kind>`
(one Octave per pair, then a merge). Octave vs Python side by side:
`tools/compare_live.py [--pairs S:D[:SEED] ...] --jobs N` (default: the 63 baseline pairs).

Conventions: MATLAB names kept in snake_case, docstrings cite source lines, 0-based indices
converted only in `io.py`, quirks of the original replicated by default.
