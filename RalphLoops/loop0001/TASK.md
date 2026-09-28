# TASK: Test-driven translation of formdiscovery1.0 (Kemp & Tenenbaum 2008) from MATLAB to Python

## Philosophy
- **Octave is the oracle.** Every translated function is tested against the original MATLAB
  code running in GNU Octave on identical inputs. A Python function is not done until its
  parity test is green. Write the Octave fixture script and the failing pytest first, then
  translate.
- **Faithful first, pretty later.** Keep MATLAB function names (snake_case), field names and
  algorithmic structure so any line of Python can be matched to its `.m` source. Replicate
  the original's quirks and bugs by default; record every deliberate deviation in
  `KNOWN_ISSUES.md`.
- **One item per iteration.** Finish it fully (fixture, test, code, docs, green run) or
  document exactly why it is blocked. Do not start the next item.
- **Bottom-up.** Translate leaves before callers. The order in `iterations.md` respects the
  verified call graph; do not reorder without a reason recorded in PROGRESS.md.
- **Deterministic before stochastic.** Layers L0–L3 must match Octave to near machine
  precision. Search code (L4+) is compared with replayed permutations. Anything downstream of
  `fminunc` is compared by optimality within a tolerance, never bit-for-bit.

## Current Focus
Produce a Python package `formdiscovery` (in `src/formdiscovery/`) that reproduces the
MATLAB pipeline `masterrun -> runmodel -> structurefit -> gibbs_clean/graph_like`, verified
layer by layer against Octave, and then port the Graphviz display code (`draw_dot` and
friends), first to pygraphviz, then to networkx/matplotlib.

## Target Problems (in order)
See `iterations.md` in this folder. Work on the first unchecked item only.
The full rationale, layer table, hazards and milestones are in `/PLAN.md` at the repo root;
read the relevant section of PLAN.md before starting an item.

## Acceptance Criteria (per item)
- [ ] An Octave fixture script exists in `tests/octave/` for every MATLAB function touched,
      and its committed fixture in `tests/fixtures/` was regenerated in this iteration.
- [ ] A pytest exists that loads the fixture and compares; where the item involves graph
      structs or randomness, a live parity test (`@pytest.mark.octave`) also exists.
- [ ] Comparison tolerances follow PLAN.md §2 (exact for integers/structure, `rtol=1e-10`
      for deterministic floats, documented tolerance for optimizer-dependent values).
- [ ] Each Python function has a docstring citing the source file and line range.
- [ ] `python -m pytest -q -m "not slow"` passes (all previously green tests still green).
- [ ] `iterations.md` checkbox updated and a PROGRESS.md section appended.
- [ ] No regressions.

## Completion Conditions
An item is DONE when either:
1. **Solved**: meets all criteria, OR
2. **Blocked**: PROGRESS.md records the specific blocker (missing tool, Octave crash, ambiguous
   MATLAB semantics, etc.), what was tried, and the smallest input that reproduces it. Mark
   the item `[~]` in `iterations.md` and move on.

## Context
- **Original sources**: `/home/al/Dropbox/AL Cognitive Model Course/MathModels/formdiscovery1.0/`
  (74 `.m` files, `data/*.mat`). Iteration 01 copies them to `matlab/formdiscovery1.0/`.
  After that, only use the in-repo copy.
- **Key docs**: `/PLAN.md` (the plan), `src/formdiscovery/CONVENTIONS.md` (index/ordering
  rules, created in iteration 06), `matlab/PATCHES.md` (Octave compatibility edits),
  `KNOWN_ISSUES.md` (bugs replicated or fixed).
- **Testing**: `python -m pytest -q -m "not slow"` is the regression gate.
  `python -m pytest -q -m octave` runs live Octave parity tests (needs Octave + oct2py).
  `python tools/gen_fixtures.py [name]` regenerates fixtures through Octave.
- **Toolchain**: Python 3.12 (anaconda), numpy 1.26, scipy 1.17, networkx 3.3, Graphviz 14.1
  (`dot`, `neato`). Octave, oct2py and pygraphviz are NOT installed at loop start; iteration 02
  installs them via conda-forge (no sudo). Prefer a dedicated conda env named `fd`.
- **Constraints**: never modify files under `matlab/formdiscovery1.0/` except the documented
  compatibility patches in iteration 03. Never delete or rewrite committed fixtures without
  regenerating them from Octave in the same iteration. Do not run the big synthetic or
  real-world data sets in the regression gate (mark them `slow`).

## Important Notes
- Three hazards are known up front (PLAN.md §4): (1) `fminunc` + Laplace approximation in
  `graph_like_conn.m` cannot match bit-for-bit; (2) randomness enters only via `randperm` at
  five call sites and is handled by an injectable permutation provider plus an Octave
  `randperm.m` shim; (3) MATLAB column-major `find`, `hist` with bin centres, sorted set ops,
  upper-triangular `chol`, and `sparse` accumulation all differ silently in numpy.
- Indices are 0-based in Python; convert only in `io.py` and parity helpers.
- `keyboard` calls in the MATLAB code become raised exceptions; `cd`/`mkdir` side effects in
  `runmodel.m` become an explicit output directory. These are the only planned deviations.
- Load `.mat` files with `scipy.io.loadmat(path, mat_dtype=True)`; data are stored as
  uint8/uint16 but are doubles in MATLAB.
- Load all functions' behaviour from the real code, not from memory of the paper. When the
  code and the README/paper disagree, the code wins and the disagreement goes in
  `KNOWN_ISSUES.md`.
- Keep iterations short. If an item is clearly too big once you start, finish a coherent
  sub-part, mark the item still `[ ]`, and split the remainder into a new item inserted
  directly after it in `iterations.md`, explaining the split in PROGRESS.md.
