# Progress Log

## Ralph Loop 0003 Status
- **Started**: 2026-10-01
- **Target**: 6 items (see iterations.md)
- **Current**: 4/6 SOLVED

---

## Iteration 1 — 2026-10-01 12:32
### Completed
- Item 01 (skeleton and data picker) solved.
- New package `src/formdiscovery/gui/` (PySide6; importing the package does not import Qt):
  - `dataset.py`: `dataset_info(path)` loads any `.mat` with `io.load_dataset(stem, with_names=True,
    data_dir=parent)` and classifies it with `params.setrunps` (the model's own feat/sim/rel rule);
    `DatasetInfo.summary()` gives the info panel text (type, objects, features / similarity size /
    relation type and count, first 8 names + "(+k more)", the speed-5 note for relational data).
  - `main_window.py`: `MainWindow` has an "Open data file…" button (`QFileDialog`, `*.mat`, starting in
    `io.DATA_DIR`, then in the last file's directory), a path label, a "Data set" info panel, a form list
    (the 24 `ps.structures`, MultiSelection, chain/ring/tree preselected = masterrun's `thisstruct`),
    seed (default 1) and speed spin boxes, Run (enabled once a file and at least one form are chosen;
    emits `run_requested(dict)` with path/info/forms/seed/speed) and Stop (disabled until item 02).
    Unreadable or unsuitable files (not a .mat, no `data`, truncated) put the error in the info panel
    and disable Run. `SpeedSpinBox` steps through the working speed codes only (3, 4, 5, 54; default 54):
    `ps.speed` is a mode code, 1/2 crash (KI-1) and 23 is runmodel's "Unknown speed value".
  - `app.py`: `main(argv=None, args=None)` (reuses or creates the QApplication, opens the window with
    FILE, runs the loop), `build_parser`, `screenshot(widget, path)` (offscreen `grab()`).
- CLI: `formdiscovery gui [FILE] [--data-dir D]` (subparser in `cli.py`, Qt imported only for `gui`).
- Packaging: extra `gui = ["PySide6>=6.6"]`, `pytest-qt>=4.4` in the `test` extra, `qt_api = "pyside6"`
  in `[tool.pytest.ini_options]`; `environment.yml` lists `pyside6=6.10.1` and `pytest-qt=4.5.0`
  (installed into fd from conda-forge; nothing else changed in the env).
- `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` in `pytest_configure`, so no test opens a window.
- `tests/test_gui_picker.py` (17 tests, 0.5 s total): each of the 6 shipped demo files opened via
  `load_file` (signal, kind/objects/features/relation type, info text, path label, title, button
  states); colors (sim, names line with "+6 more") and animals; initial state (24 forms in order,
  chain/ring/tree, seed 1, speed 54); form selection by API and by mouse click; Run emits the settings;
  the speed codes; bad/missing/no-`data` files; a user's file outside the data dir with names; the file
  dialog (monkeypatched `getOpenFileName`, start dir and filter, cancel keeps the data set); screenshot;
  `cli.main(["gui", FILE])` reaches `gui.app.main`; `app.main` runs the event loop with FILE loaded.
- Screenshot: `examples/gui/01_picker.png` (demo_chain_feat loaded, defaults), made with
  `tools/gui_screenshots.py` (offscreen).
- Anomalies: A22 (PyQt5/Qt5 installed next to PySide6 in the fd env; handled by `qt_api = "pyside6"`).
  KI-1 notes the GUI's speed restriction and its pin. CLAUDE.md lists the gui package.
- Gate: `pytest -q -m "not slow" -n 16` with `RALPH_REQUIRE_OCTAVE=1`: 3666 passed, 3 skipped (the
  existing non-Octave skips), 358 s, exit 0. No model code changed, so parity is untouched.
### Blockers
- None.
### Next
- Item 02: `gui/worker.py` (`RunWorker` on a `QThread`, `ProgressFigures.enable` events, signals) and
  the documented cancel hook (`RunCancelled`) in `search.show_graph` / `structurefit`. Wire
  `MainWindow.run_requested` and enable Stop while a run is going.

## Iteration 2 — 2026-10-01 12:50
### Completed
- Item 02 (worker thread and cancel hook) solved.
- Model hook (the only change outside `gui/`), `search.py`: `run_hooks(cancel=None, on_depth=None)`, a
  context manager installing per-thread (`threading.local`) hooks; `RunCancelled` (an `Exception`, not a
  `FormDiscoveryError`); `check_cancel()`; `current_depth()`. `cancel()` is checked at the top of every
  `show_graph` call (whatever the `ps.show*` flags, so a run is stoppable without frames) and at the start
  of each `structurefit` depth (`_hook_depth`, which also records the depth); `on_depth(bestgraphlls,
  bestgraph)` is called after each accepted depth, next to `callback`. Without `run_hooks` nothing is
  checked or called: results and draws unchanged (the gate's parity tests; the worker's ll equals
  masterrun's bit for bit). Documented in the search module docstring and `structurefit`'s.
- `gui/worker.py`: `RunWorker(QObject)` with signals `frame(event, adj, names, title, depth)`,
  `depth_done(lls)`, `finished(result dict: ll, graph, names, bestglls, bestgraph, form, sind, dind, path,
  seed, speed, frames, wall)`, `failed(traceback)`, `cancelled()`, then `done()`. `run()` builds `ps`
  with `run_ps(path, form, speed)` (masterrun_ps; a shipped file keeps its `ps.data` index, any other file
  is appended to `ps.data`/`dlocs`/`simdim`), `ProgressFigures.enable(ps, preclean/postclean/
  inferredgraph [+bestsplit])`, `NumpyPermutations(seed)` (masterrun's repeat-1 seed) and runs
  `runmodel(..., show=)` inside `run_hooks`. Frames are copies (`np.array(adj, copy=True)`, str names and
  title). `start_worker(worker, parent, start=True)` moves it to a `QThread`; `done` → `thread.quit`
  (direct connection).
- `MainWindow`: `run_requested` → `start_run` (first selected form; the queue is item 05), `run_started(
  worker)` for item 03's canvas, `run_ended(outcome)`, Stop → `stop_run` (`worker.cancel()`), Run disabled
  while running, a status line (frame/depth during the run; `chain: ll = -8247.1924 (11 frames, 1.3 s)` at
  the end), `wait_run(ms)`, and `closeEvent` cancels and joins the thread.
- `tests/test_gui_worker.py` (13 tests, ~6 s): `run_ps` for shipped/user files; the demo run in a worker
  (ll == masterrun's `modellike[1,0,0]`, slots run in the GUI thread, last frame `inferredgraph` with the
  final adj, postclean count == accepted depths, frames ≥ depths, `depth_done` histories grow by one per
  stage, frame depth == accepted depth); bestsplit frames; cancel after the first frame (`cancelled`, no
  `finished`, thread finished); cancel before start; failure traceback; `run_hooks` unit (flags off still
  checked, nesting, per-thread); `structurefit` with hooks gives the same result, `on_depth` == `callback`,
  per-depth cancel at depth 2 without any `show`; window Run → finished, Stop → cancelled, close joins.
- Screenshot: `examples/gui/02_run.png` (window after a chain run on demo_chain_feat, status line with
  the score, 11 frames, 1.3 s), from `tools/gui_screenshots.py` (01_picker.png regenerates unchanged).
- Anomalies: A23 (PySide6 calls a plain function/lambda connected to a cross-thread signal in the emitting
  thread; only `QObject` methods get queued; documented in `worker.py`), A24 (`QApplication.quit()` in item
  01's `test_app_main_runs_event_loop` posted a deferred Quit event that pytest-qt's teardown delivered after
  `exec()` returned, leaving every later `QEventLoop.exec()` in that process returning -1 at once; in the
  first gate run the worker tests on that xdist worker timed out instantly, their orphan thread ran into
  `test_structurefit`'s monkeypatched oracle and the worker aborted. Fixed in the test with `qapp.exit(0)`
  + `qtbot.wait(1)`; `run_worker` in the tests now cancels and joins on any timeout). Both are
  environment/test issues, not original-code lines, so no KI entry (as A22).
- `test_gui_picker.py::test_run_emits_settings` now stops and joins the run its Run click starts.
- CLAUDE.md lists `worker.py` and the `search.run_hooks` hook.

- Gate: `pytest -q -m "not slow" -n 16` with `RALPH_REQUIRE_OCTAVE=1`: 3678 passed, 3 skipped (the existing
  non-Octave skips), 365 s, exit 0 (the first run, before the A24 fix, had 3 failures on one xdist worker).
### Blockers
- None.
### Next
- Item 03: `gui/canvas.py` `GraphCanvas(FigureCanvasQTAgg)` fed by `MainWindow.run_started` → the worker's
  `frame` signal (connect a `QObject` method, A23), coalescing with a timer (latest wins, never drop
  `inferredgraph`), status line from `frame`'s `depth` and the title's score; stable positions (`draw_dot
  pos=`). Stop already works through `MainWindow.stop_run`.

## Iteration 3 — 2026-10-01 13:19
### Completed
- Item 03 (live canvas) solved.
- `gui/canvas.py`: `GraphCanvas(FigureCanvasQTAgg)`. `push_frame(event, adj, names, title, depth)` (a `Slot`
  on a GUI-thread `QObject`, so the worker's `frame` connection is queued, A23) stores the frame; a
  single-shot timer (100 ms) draws the latest stored one (older ones counted in `dropped`); an
  `inferredgraph` frame is drawn at once and never dropped; `flush()` draws a pending frame now. Each frame
  is drawn with `viz.draw.draw_dot(adj, names, backend, pos=..., ax=...)`, backend `pygraphviz` (default) or
  `networkx` (`CANVAS_BACKENDS`), titled with the model's title, and a status line under the graph:
  `event · depth d · score S (the title's last word) · elapsed s · frame k`. `frame_drawn(event, title)` is
  emitted after each drawing. A frame draw_dot cannot draw (no edges) shows the error in the axes.
  `begin_run`/`clear`/`set_status` reset or annotate it.
- Layout stability (what was possible): neato honours a node's `pos` attribute as its *initial* position.
  With `stable=True` (default, needs pygraphviz) the canvas lays each frame out with draw_dot's neato
  attributes, giving every node `k` of the previous frame that frame's point as start (not pinned), and
  passes the result (normalised by `dot_positions`) to `draw_dot(pos=)`, for both backends. The first frame
  of a run is exactly draw_dot's layout (tested). Object nodes `1..nobj` are matched exactly; cluster nodes
  by index (a split/clean may reassign them; neato then moves them). On the recorded demo run the object
  nodes move 2.3 (sum of |Δ| in normalised units over the post-clean/inferred frames) vs 7.5 with fresh
  layouts (`test_stable_positions`). Cost: draw_dot still runs its own neato when given `pos`, so two neato
  runs per frame (milliseconds here). `stable=False` gives draw_dot's fresh layout each frame. No change to
  `viz/`.
- `MainWindow`: the canvas fills the right half ("Graph"), the left column has data set, settings (new:
  "Drawing" backend combo, "Draw best splits" check box → the worker's `bestsplit`) and forms;
  `run_settings()` adds `backend`/`bestsplit`. `start_run` calls `canvas.begin_run` and connects
  `worker.frame` → `canvas.push_frame`. Stop: the canvas flushes and its status becomes `stopped · last:
  <last status>`; a failed run says `Run failed.`. Window 1100×720.
- `tests/test_gui_canvas.py` (13 tests, ~5 s): frames recorded from a `RunWorker` run (chain ×
  demo_chain_feat, best splits, 33 frames) fed to the canvas: one frame (title, status text, frame_drawn,
  positions == draw_dot's layout); a burst is coalesced to 1 drawing (the `inferredgraph`, last title ==
  inferred title, `dropped == received - 1`); the timer draws the latest; `inferredgraph` is never dropped;
  with event processing between frames >1 drawings and the inferred title last; stable vs fresh positions;
  both backends unstable, networkx stable; bad backend raises; undrawable frame; set_status/clear; window
  Run (networkx, best splits) → canvas got every frame, last title the inferred graph's, ll equal; window
  Stop on the first frame → cancelled, canvas status `stopped · last: …`.
- Screenshots (`tools/gui_screenshots.py`, offscreen): `examples/gui/03_live_mid.png` (first frame the
  canvas drew during the run: pre-clean, depth 4, frame 17 — the first 17 frames came within 0.1 s and
  were coalesced) and `examples/gui/03_live_end.png` (inferred graph, ll -8247.19, 33 frames, 1.6 s; nodes
  in the same places as mid-run). `01_picker.png`/`02_run.png` regenerated with the new layout.
- Anomaly A25 (explained): cluster nodes are small ovals in pre/post-clean frames (names padded `' '`,
  structurefit.m:89-91) but bare points in the inferred graph (padded `''`, runmodel.m:184-186; an empty
  label measures `[0 0]`), as in MATLAB's figures; no KI entry (KI-38 covers the padding).
- CLAUDE.md lists `canvas.py`.
- Gate: `pytest -q -m "not slow" -n 16` with `RALPH_REQUIRE_OCTAVE=1`: 3691 passed, 3 skipped (the existing
  non-Octave skips), 367 s, exit 0. No model or viz code changed, so parity is untouched.
### Blockers
- None.
### Next
- Item 04: `gui/stats.py` statistics panel on `finished` (ll, prior/likelihood via `graph_prior` +
  `graph_like`, clusters and members, per-depth `bestgraphlls` chart, wall time, frames), export
  (`.npz`/`.json`, PNG/SVG of the canvas figure), README "GUI" section.

## Iteration 4 — 2026-10-01 13:38
### Completed
- Item 04 (statistics on completion) solved.
- `gui/stats.py`: `score_parts(path, form, graph, speed)` rebuilds runmodel's `ps` (`run_ps`, `setrunps`,
  `scaledata`, `structcounts`) and returns `(graph_prior, graph_like)` of the final graph in slow mode
  (`ps.fast = 0`, as runmodel.m:178-180); prior + likelihood == runmodel's ll exactly for chain, ring and tree
  on demo_chain_feat (the fast score is ~20 nats higher, see A26). `history_stages(bestglls)` (the cell in run
  order: speed 5 before 4, stages in order, empty ones kept), `clusters(graph, names)` (names grouped by `z`,
  unassigned last), `run_stats(result)`, `stats_text(st)`; `export_results(result, path)` stores the run in a
  `MasterResults` as masterrun does (repeat 1) and writes `.npz` + `.json` with `save_results` (same keys and
  run record as `formdiscovery run`, loads back with `load_results`); `export_figure(fig, path)` (PNG/SVG).
  `StatsPanel`: monospaced text, a matplotlib "Score per depth" chart (one line per stage, fixed categorical
  order, final ll dashed), live stages from `depth_done` (`push_depth`), `show_result` on `finished`,
  "Export results…" / "Save figure…" (the graph canvas's figure) with save dialogs, `exported` signal.
- `worker.py`: the `finished` dict now also has `prior` and `likelihood` (computed in the worker thread,
  NaN if that fails). `main_window.py`: a third "Statistics" column (window 1440×800); `start_run` clears the
  panel and connects `depth_done` → `push_depth`, `finished` → `show_result`.
- `tests/test_gui_stats.py` (17 tests, ~22 s alone, mostly the module fixtures: masterrun chain+tree and the
  worker runs): parts add up and equal a fresh `score_parts`; `run_stats` vs `MasterResults` (ll, cluster
  counts, members from `structure.z`/`names`, history == `llhistory`); the panel text (ll from
  `modellike`, prior, likelihood, clusters, history, wall/frames); missing parts recomputed; clusters with
  unassigned and padded names; history order; export results (3 suffixes) loads back equal to masterrun's
  graph/names/llhistory and matches the CLI's file layout; a user file outside the data dir; figure PNG/SVG
  (magic bytes, default suffix, bad suffix); panel fill/clear, live depths, dialogs (monkeypatched); the window
  fills the panel after a run.
- Screenshot: `examples/gui/04_stats.png` (chain × demo_chain_feat: ll -8247.1924 = prior -11.8589 +
  likelihood -8235.3335, 4 clusters of 2, history chart, 11 frames). `tools/gui_screenshots.py` makes it;
  01-03 regenerated with the new column.
- README: new "GUI" section (launch, what each column shows, exports, screenshot). CLAUDE.md lists `stats.py`.
- Anomaly A26 (explained): the per-depth chart's speed-5 history ends above the final ll (fast vs slow
  score on one axis); the panel notes it. No KI entry (no new code line).
- Gate: `pytest -q -m "not slow" -n 16` with `RALPH_REQUIRE_OCTAVE=1`: 3708 passed, 3 skipped (the existing
  non-Octave skips), 367 s, exit 0. No model or viz code changed, so parity is untouched.
### Blockers
- None.
### Next
- Item 05: queue the selected forms (one or N workers), a results table ranked by ll with the winner
  highlighted (could sit in the Statistics column; `run_stats` per form), click a row to show its graph and
  stats, and a frame-history slider (capped).
