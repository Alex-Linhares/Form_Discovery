# Kemp-Tenenbaum form discovery: MATLAB to Python

A test-driven translation of Charles Kemp's `formdiscovery1.0` MATLAB code, which implements
the structural form discovery model from:

> Kemp, C., & Tenenbaum, J. B. (2008). The discovery of structural form. *PNAS*, 105(31), 10687–10692.

The model fits graph structures (partitions, chains, orders, rings, hierarchies, trees, grids,
cylinders) to feature, similarity, or relational data and returns the best structure of each
form together with its posterior probability.

## Status

The model is fully translated and verified against the original code running in GNU Octave.
The Python port runs the original `masterrun` demo end to end:

- With Octave's random permutations replayed, all nine demo runs (chain, ring, tree × three
  feature data sets) reproduce the Octave baseline: final scores to ten significant digits,
  and identical final graphs and growth histories.
- Without replay (numpy permutations, scipy optimiser, three seeds), every run finds the
  same clustering as Octave (adjusted Rand index 1, same cluster count) with scores within
  about 1e-5 relative.
- Deterministic code (utilities, priors, graph construction, likelihoods, relational model)
  matches Octave to near machine precision. The one irreducible gap is the branch-length
  optimiser: Octave's `fminunc` stops early, so log-evidence values agree to about 2e-4
  relative, and Python's optimum is never worse than Octave's.

Anomalies found along the way (for example, on the `animals` data the code prefers a hierarchy
where the paper reports a tree) are logged in `ANOMALIES.md`.

Remaining work: paper-level checks on the real data sets, the Graphviz display port
(pygraphviz, then networkx/matplotlib), and a performance pass. Progress is tracked in
`RalphLoops/loop0001/PROGRESS.md` and `iterations.md`.

## Quick start

```bash
conda env create -f environment.yml      # env "fd": Python, numpy/scipy, Octave, oct2py, pygraphviz
conda activate fd
pip install -e .

formdiscovery run                                            # masterrun demo: chain,ring,tree × datasets 1-3
formdiscovery run --structures dirringnoself --datasets 4 --seed 3 --out results/
formdiscovery run --help
```

From Python:

```python
from formdiscovery.run import masterrun
res = masterrun()            # MasterResults: names, ll, cluster counts, z, graphs, ps per run
```

Data sets and structure names follow the original `setps.m` (20 data sets, 24 forms); both
can be given by name or 1-based index.

## How it was verified

- Every MATLAB function has an Octave fixture script in `tests/octave/` that runs the original
  code on real inputs and saves inputs and outputs to `tests/fixtures/*.mat`. The pytest
  suite compares the Python translation against those fixtures, so the tests run without
  Octave. Tests marked `octave` additionally drive Octave live through oct2py and are
  skipped when it is not installed.
- Structural outputs are compared exactly; deterministic floats at `rtol=1e-10`;
  optimiser-dependent values by optimality (objective and gradient norm no worse than
  Octave's) plus a documented tolerance.
- Randomness enters only through `randperm`. An Octave shim (`matlab/octave_shims/`) records
  or replays permutations, and `formdiscovery.rng` provides matching Python providers, so the
  search heuristics are compared with identical random choices.
- The Octave baseline runs (`matlab/run_baseline.m`) for the feature and relational demo grids
  are committed under `tests/fixtures/baseline/`.

```bash
python -m pytest -q -m "not slow"     # regression gate (~1 min)
python -m pytest -q -m octave         # live Octave parity (needs the fd env)
python -m pytest -q -m slow           # long runs
python tools/gen_fixtures.py          # regenerate all fixtures through Octave
```

## Layout

| Path | Contents |
|---|---|
| `src/formdiscovery/` | The port. `graph.py` (graph structure and grammars), `likelihood_feat.py` / `likelihood_rel.py` (scores), `search.py` (split, swap, prune-and-regraft, `gibbs_clean`, `structurefit`), `run.py` (`runmodel`, `masterrun`), `cli.py`, `rng.py`, `params.py`, `preprocess.py`, `weights.py`, `matlab_compat.py`, `io.py` |
| `src/formdiscovery/CONVENTIONS.md` | Index, ordering and dtype rules used throughout the port |
| `matlab/formdiscovery1.0/` | Verbatim copy of the original MATLAB sources and data, plus 16 documented Octave-compatibility edits (`matlab/PATCHES.md`) |
| `matlab/run_baseline.m` | Headless Octave reproduction of `masterrun` used to produce the baseline fixtures |
| `ANOMALIES.md` | Curated log of anomalies found: paper vs code, Octave vs MATLAB, surprising results, original bugs, each with a status |
| `KNOWN_ISSUES.md` | Bugs and quirks of the original and how the port treats each one (replicate, fix, or not ported) |
| `tests/` | Fixture scripts (`tests/octave/`), fixtures, pytest parity tests, Octave baselines |
| `tools/` | Fixture generation and Octave/Python run comparison |
| `PLAN.md` | The translation plan: test architecture, dependency-ordered steps, hazards, milestones |
| `RalphLoops/` | The fresh-context iteration loop that carried out the plan |

## Conventions

Python function names match the MATLAB file names (`graph_like_conn`, `gibbs_clean`, ...),
and each docstring cites the source lines it translates. Indices are 0-based in Python and
converted only at the I/O boundary. Quirks of the original are replicated by default; the
only deliberate deviations are that `keyboard` debug stops become exceptions and `runmodel`
writes to an explicit output directory instead of changing the working directory.

## Credits

Original MATLAB code: Charles Kemp (2008), with contributions from Kevin Murphy (BNT),
Thomas Minka (lightspeed), Leon Peshkin (Graphviz interface), Carl Rasmussen, John Burkardt,
and Michael Kay, as listed in the original `README.txt`.
