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

Work is driven by the Ralph loop in `RalphLoops/loop0001/` (`TASK.md`, `iterations.md`,
`PROGRESS.md`, `loop.py`); see `RalphLoops/ralph_loop_guide.md`.

Environment: conda env `fd` (`environment.yml`) has Python, numpy/scipy, Octave 10.3, oct2py
and pygraphviz. Regression gate: `~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow"`
(in the fd env, or with `RALPH_REQUIRE_OCTAVE=1`, a skipped `octave` test is a failure;
`RALPH_REQUIRE_OCTAVE=0` allows skips). Live Octave parity only: `-m octave` in the fd env. Fixtures are regenerated only through Octave
(`tools/gen_fixtures.py`).

Conventions: MATLAB names kept in snake_case, docstrings cite source lines, 0-based indices
converted only in `io.py`, quirks of the original replicated by default.
