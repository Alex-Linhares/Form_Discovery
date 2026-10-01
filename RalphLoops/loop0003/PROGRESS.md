# Progress Log

## Ralph Loop 0003 Status
- **Started**: 2026-10-01
- **Target**: 6 items (see iterations.md)
- **Current**: 1/6 SOLVED

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
