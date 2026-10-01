# Project notes for Claude sessions

This repo is a test-driven translation of Kemp & Tenenbaum's `formdiscovery1.0` (MATLAB) to
Python, verified against the original code running in GNU Octave. The Octave oracle has
been **frozen and removed**: it exists only at the git tag `octave-oracle-final`
(`legacy/FREEZE.md` there records versions and the final identical regeneration).

Read first, in this order:
- `PLAN.md`: the plan (test architecture, dependency-ordered steps, hazards, milestones).
- `ANOMALIES.md`: the curated log of anomalies found (paper vs code, Octave vs MATLAB,
  surprising results, original bugs). **Every new anomaly must be added here** with a
  status of open / explained / handled.
- `KNOWN_ISSUES.md`: line-by-line entries (KI-n) with a decision (replicate / fix / not
  ported) and the test that pins each one. Its `file:line` citations refer to the MATLAB
  sources at the tag.
- `src/formdiscovery/CONVENTIONS.md`: index, ordering and dtype rules for the port.
- `PLAN_LEGACY.md` (done), `PLAN_ARC_AGI_JS.md` (plan only).

Layout: `src/formdiscovery/` (the port, CLI, `gui/` PySide6 app, `viz/`), `data/` (the 20
data sets, MATLAB v5 `.mat`), `tests/` (fixture-based parity tests; `tests/fixtures/` holds
the Octave-produced reference answers, hashed in `tests/fixtures/SHA256SUMS`), `tools/`
(Python-side tools), `examples/` (notebook, GUI screenshots), `RalphLoops/` (the iteration
loops that built all of this; `ralph_loop_guide.md`, `loop_template/loop.py`).

Environment: conda env `fd` from `environment.yml` (Python-only: numpy/scipy, networkx,
matplotlib, pygraphviz, PySide6, pytest-xdist, pytest-qt). No Octave is needed.

Gate: `make test` = `pytest -q -m "not slow and not octave" -n 16` (~1 min; the `octave`
marker still exists and those tests skip). `make slow` for the long runs. `make
fixture-sums` verifies every fixture hash; `tests/test_fixture_integrity.py` does the same
inside the gate.

**Fixture policy:** the committed fixtures are the oracle. A change that alters any fixture
value must first be checked against the original code: check out `octave-oracle-final`,
build its environment (`environment.yml` + `legacy/environment-octave.yml`), run
`make legacy-check` and `legacy/tools/gen_fixtures.py --compare`, and only then update the
fixture and `SHA256SUMS` on `main`, recording why in `ANOMALIES.md`.

Conventions: MATLAB names kept in snake_case, docstrings cite source lines, 0-based indices
converted only in `io.py`, quirks of the original replicated by default. Thread pinning:
drivers limit BLAS to one thread (`threads.py`, ANOMALIES A16/A19).
