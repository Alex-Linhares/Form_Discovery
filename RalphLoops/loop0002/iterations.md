# Iterations — loop0002

Legend: `[ ]` pending · `[x]` solved · `[~]` blocked (details in PROGRESS.md).
Work on the first `[ ]` item only.

- [x] 01. **Strict Octave gate.** Make the gate fail, not skip, when Octave or oct2py is
      missing: in `tests/conftest.py`, if `RALPH_REQUIRE_OCTAVE=1` (set by `loop.py`) or the
      running interpreter is the fd env's, turn the `octave`-marker skip into a hard failure
      with a clear message. Add `tests/test_gate_env.py` asserting the interpreter has oct2py,
      Octave is found, and one trivial live call works. Run the gate in the fd env, record the
      time, and confirm `0 skipped` among Octave tests. Update README/CLAUDE.md commands.
- [x] 02. **BLAS/OpenMP pinning for Octave and workers.** Set `OPENBLAS_NUM_THREADS=1`,
      `OMP_NUM_THREADS=1` (and `MKL_NUM_THREADS=1`) for every Octave started by
      `conftest.py`, `tools/gen_fixtures.py`, `tools/gen_paperlevel.py`, `tools/bench_perf.py`
      and any `run_baseline` driver; apply `limit_blas_threads` at pytest session start for
      the Python side. Measure Octave `run_baseline('feat', 2, 1)` and the live
      `test_glslow.py` tests before and after (wall and CPU). Prove results are bit-identical.
- [x] 03. **Parallel fixture generation.** `tools/gen_fixtures.py --jobs N` (default: cores/2):
      one `octave-cli` per `fx_*.m`, process pool, per-script logs, summary table of times.
      Regenerate all fixtures with `--jobs 16` and with `--jobs 1`; assert every `.mat` is
      content-identical (compare loaded arrays, not bytes; the header carries a timestamp).
      Table: serial vs parallel wall clock.
- [x] 04. **Parallel baselines.** `tools/gen_baselines.py --kind feat|rel --jobs N`: one
      Octave process per (structure, dataset) pair, each writing to its own directory, then a
      merge step that assembles `resultsdemo.mat`, `timings.mat` and the `results/` growth
      histories exactly as the serial `run_baseline` does. Verify the merged output is
      identical to the committed `tests/fixtures/baseline/{feat,rel}` (all `ll` values,
      graph structs, file sets). Table: serial 2 min 45 s vs parallel.
- [x] 05. **Parallel gate with pytest-xdist.** Add `pytest-xdist` to `environment.yml` and
      `pyproject.toml[test]`; make the gate `-n 16` (loop.py `TEST_CMD`), one Octave per
      worker. Fix any test that is not concurrency-safe (shared temp names, files written under
      `tests/`, image baselines). Run the gate 3× to check determinism (same pass set).
      Table: gate wall clock serial vs `-n 8` vs `-n 16`, and CPU time.
- [ ] 06. **Side-by-side live comparison tool.** `tools/compare_live.py --pairs ... --jobs N`:
      for a list of (structure, dataset, seed) triples, run Octave (`run_baseline` with the
      randperm-recording shim) and Python (`runmodel` replaying Octave's draws) concurrently in
      a process pool, then print one table: Octave ll, Python ll, rel diff, ARI, cluster
      counts, wall times of each side. Default set: the 9 feature demo pairs + the 54
      relational pairs. Add a `slow` test that runs the default set and asserts the loop0001
      criteria (§7.1) still hold. Record the full table in PROGRESS.md.
- [ ] 07. **Wrap-up.** Consolidated before/after table (fixtures, baselines, gate, live
      comparison) in README "How it was verified"; `CLAUDE.md` commands updated; confirm
      `loop0001`'s `-m slow` suite still passes in the fd env. Then verify every item above,
      update the status header and add the completion line.
