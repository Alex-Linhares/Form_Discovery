# TASK: Qt GUI for form discovery — pick a data file, watch the graph evolve, see statistics

## Philosophy
- **The GUI is a thin shell over the verified port.** No model logic in the GUI package.
  It calls `formdiscovery.run.runmodel` / `masterrun` and receives graphs through the
  existing `show(event, adj, names, title)` callback (`search.show_graph`,
  `viz.draw.ProgressFigures.enable`) and the per-depth `structurefit` callback. Drawing uses
  the existing `viz.draw.draw_dot` backends (pygraphviz/networkx on a matplotlib canvas).
- **Never block the UI thread.** The run executes in a worker thread; graphs cross to the
  GUI thread only via Qt signals carrying plain numpy/Python data. The window must stay
  responsive (file dialog, Stop button) during a run.
- **Testable headless.** Every item ships offscreen tests (`QT_QPA_PLATFORM=offscreen`,
  `pytest-qt`) that drive the real widgets on `demo_chain_feat × chain` (seconds). A
  screenshot per item goes to `examples/gui/` for the human to look at.
- **PySide6**, already installed in the fd env (6.10.1). Do not add PyQt.
- **One item per iteration**, foreground waiting, record anomalies.

## Current Focus
A desktop app, launched as `formdiscovery gui`, that lets the user choose a `.mat` data
file (the shipped ones or their own), choose forms and settings, run the search, watch the
graph redraw on a canvas each time the model transforms it (pre-clean / post-clean per
depth, optionally each best split), and when the run completes shows the statistics:
scores, cluster membership, per-depth score history, timing, and a ranked table of forms.

## Target Problems (in order)
See `iterations.md`. Work on the first unchecked item only.

## Acceptance Criteria (per item)
- [ ] Gate passes: `~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow" -n 16`
      (strict Octave live; `RALPH_REQUIRE_OCTAVE=1` is set by `loop.py`).
- [ ] New GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`) in the gate and finish in
      well under a minute each; nothing opens a window in tests.
- [ ] A PNG screenshot of the item's state is saved under `examples/gui/` (offscreen
      `grab()`), and referenced from PROGRESS.md.
- [ ] No change to `src/formdiscovery/` outside the new `gui/` package except small,
      documented hooks (e.g. a cancel check in the callback path, a `gui` CLI subcommand).
      loop0001/loop0002 parity results must not change.
- [ ] README gets a "GUI" section when the app first runs end to end (item 04);
      CLAUDE.md lists the gui package.
- [ ] Any anomaly found is added to `/ANOMALIES.md` and `KNOWN_ISSUES.md`.
- [ ] `iterations.md` checkbox updated and a PROGRESS.md section appended.

## Completion Conditions
Solved (all criteria) or Blocked (specific blocker, what was tried, smallest repro;
mark `[~]`).

## Context
- **Read first:** `/CLAUDE.md`; `src/formdiscovery/viz/draw.py` (`ProgressFigures`,
  `FIGURE`, `draw_dot`, `BACKENDS`); `src/formdiscovery/search.py` (`show_graph`,
  `structurefit(..., callback=)`); `src/formdiscovery/run.py` (`runmodel(..., show=)`,
  `masterrun`, `MasterResults`, `graph_summary`); `src/formdiscovery/io.py`
  (`load_dataset(name, with_names, data_dir)`, `load_mat`); `src/formdiscovery/cli.py`
  (subparsers `run`, `draw`); `tools/compare_live.py` for how runs are parameterised.
- **Show events** (`FIGURE` in draw.py): `truegraph`, `preclean`, `postclean`, `bestsplit`,
  `inferredgraph`. `ProgressFigures.enable(ps, events)` switches them on in `ps`.
- **Data files:** MATLAB v5 `.mat` with `data` (features n×m, similarity n×n, or a
  relational struct with `R`, `type`, `nobj`) and optional `names`; the shipped ones are in
  `matlab/formdiscovery1.0/data/`. `load_dataset(stem, data_dir=dir)` loads any such file.
- **Environment:** fd env (PySide6 6.10.1, matplotlib 3.11, pygraphviz, networkx). Add
  `pytest-qt` to `environment.yml`/`pyproject.toml[test]` in item 01. Use the fd env's
  `neato`. Headless tests: `QT_QPA_PLATFORM=offscreen`.
- **Machine:** 32 cores; BLAS is pinned to 1 thread by the drivers (`threads.py`).

## Important Notes
- The `show` callback runs in the worker thread. Emit a Qt signal with copies
  (`np.array(adj, copy=True)`, `list(names)`, `str(title)`); draw in the slot on the GUI
  thread. Coalesce bursts: if frames arrive faster than the canvas can draw, drop to the
  latest but never drop the final `inferredgraph`.
- Cancellation: the model has no stop hook. Add one documented hook: a `cancel` callable
  checked in `search.show_graph` (and once per depth in `structurefit`) that raises a
  `RunCancelled` exception; the worker catches it. Keep it off by default so parity is
  untouched.
- Layout stability: neato relayouts every frame, so nodes jump. Prefer passing the previous
  positions as the start (`draw_dot(..., pos=...)` if available, else `neato -Gstart`), and
  record what was possible in PROGRESS.md.
- Stats to show on completion: final ll, prior, likelihood, number of clusters, members per
  cluster (names), per-depth `bestgraphlls`, wall time, draws used; with several forms, a
  table ranked by ll with the winner highlighted (as in masterrun's `modellike`).
