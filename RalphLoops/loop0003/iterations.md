# Iterations — loop0003

Legend: `[ ]` pending · `[x]` solved · `[~]` blocked (details in PROGRESS.md).
Work on the first `[ ]` item only.

- [x] 01. **Skeleton and data picker.** New package `src/formdiscovery/gui/` (PySide6):
      `app.py` (`main()`), `main_window.py`. Window: a "Open data file…" button + path
      label (QFileDialog, `*.mat`, default dir `matlab/formdiscovery1.0/data`), a dataset
      info panel (type feat/sim/rel, objects, features or relation type, first names),
      a form list (24 names, multi-select, chain/ring/tree preselected), seed and speed
      spin boxes, Run and Stop buttons (Stop disabled). CLI: `formdiscovery gui [FILE]`.
      Add `pytest-qt` to env/pyproject. Tests (offscreen): open each shipped demo file via
      the model (no dialog), info panel text, form selection. Screenshot
      `examples/gui/01_picker.png`.
- [x] 02. **Worker thread and cancel hook.** `gui/worker.py`: `RunWorker(QObject)` on a
      `QThread` running `runmodel` for one (form, file) with `ps` from `ProgressFigures.enable`
      (`preclean`, `postclean`, `inferredgraph`, optional `bestsplit`); signals
      `frame(event, adj, names, title, depth)`, `depth_done(lls)`, `finished(result)`,
      `failed(traceback)`. Documented cancel hook in `search.show_graph` / `structurefit`
      raising `RunCancelled`; worker catches it and emits `cancelled`. Tests: run
      `demo_chain_feat × chain` in a worker under pytest-qt (`qtbot.waitSignal`), count
      frames ≥ depths, cancel after the first frame and assert the thread ends cleanly;
      parity tests untouched (gate).
- [ ] 03. **Live canvas.** `gui/canvas.py`: `GraphCanvas(FigureCanvasQTAgg)` drawing a frame
      with `viz.draw.draw_dot` (backend selectable: pygraphviz default, networkx), title
      and a status line (event, depth, score, elapsed). Coalesce frames (timer, latest
      wins, never drop `inferredgraph`). Keep positions stable between frames where the
      backend allows (record in PROGRESS.md). Wire picker → worker → canvas; Stop works.
      Tests: feed recorded frames from a worker run, assert the canvas redraws and the last
      title is the inferred graph's. Screenshot `examples/gui/03_live.png` mid-run and
      at the end.
- [ ] 04. **Statistics on completion.** `gui/stats.py`: a panel that fills when
      `finished` arrives: final ll (and its prior / likelihood parts via `graph_prior` +
      `graph_like`), clusters and members (names grouped by `z`), per-depth score chart
      (`bestgraphlls`, matplotlib), wall time and frame count; buttons to export results
      (`.npz`/`.json` as the CLI writes) and the final figure (PNG/SVG). README "GUI"
      section; CLAUDE.md. Tests: stats text for the demo run matches `MasterResults`
      numbers; export files load back. Screenshot `examples/gui/04_stats.png`.
- [ ] 05. **Several forms and history scrubbing.** Queue the selected forms (one worker at a
      time, or N in parallel with a spin box, each on its own thread; BLAS already pinned),
      a results table ranked by ll with the winner highlighted, click a row to show that
      form's final graph; a slider to scrub back through the frames recorded during a run
      (frames kept in memory with a cap, oldest dropped). Tests offscreen on chain+ring+tree
      × demo_chain_feat. Screenshot `examples/gui/05_forms.png`.
- [ ] 06. **Polish and wrap-up.** Error dialogs (bad file, Octave-free: the GUI needs no
      Octave), remember last directory (QSettings), window title with file name, keyboard
      shortcuts, a `--demo` flag that opens `demo_chain_feat` and starts chain; a short
      `examples/gui/README.md` with the screenshots; verify the gate and the `slow` suite;
      then verify every item above, update the status header and add the completion line.
