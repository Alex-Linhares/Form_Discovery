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

- Paper-level checks: every synthetic data set recovers its true form and `colors` gives a
  ring, in Octave and in Python.
- The display code (`draw_dot`, `graph_to_dot`, `dot_to_graph`, `graph_draw`) is ported
  with pygraphviz and matplotlib, and gives the same DOT text and node positions as the
  original. networkx, plotly and pyvis backends and GraphML/DOT exports are also
  available.

- Speed: per call, fast-mode scoring takes about half of Octave's time and relational
  scoring a fifth. Slow mode, with scipy's trust-exact optimiser, takes 1.4-3.6 times
  Octave's `fminunc`. Whole runs take 0.8-1.4 times Octave's, 0.25 on relational data.
  The model keeps BLAS to one thread, because OpenBLAS threads made it up to 20 times
  slower on these small matrices; the results do not change. Run
  `python tools/bench_perf.py` to measure it on your machine.

Progress is tracked in `RalphLoops/loop0001/PROGRESS.md` and `iterations.md`.

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

## Usage

The notebook [`examples/formdiscovery_demo.ipynb`](examples/formdiscovery_demo.ipynb) runs
the whole `masterrun` demo, compares it with Octave and draws the results with every
backend. `python tools/gen_demo_notebook.py` rebuilds and runs it.

### Running the model

```python
from formdiscovery.run import masterrun, masterrun_ps, runmodel, save_results

ps = masterrun_ps()                       # defaultps(setps()) with reloutsideinit = 'overd'
res = masterrun(ps, thisstruct=[1, 3, 5], thisdata=[0, 1, 2], seed=1, log=print)
res.modellike[:, :, 0]                    # log posterior per (structure, data set)
graph = res.structure[5, 2, 0]            # the tree fitted to demo_tree_feat
names = res.names[0, 2]
save_results(res, "results/resultsdemo", ps)   # .npz + .json, read back with load_results

ll, graph, names, bestglls, bestgraph = runmodel(ps, 5, 2, 1, rng=1)   # a single run
```

In Python, the structure and data set indices are 0-based (`ps.structures[5] == 'tree'`,
`ps.data[2] == 'demo_tree_feat'`). The CLI takes names or MATLAB's 1-based indices.
`rng` is a seed or a permutation provider (`formdiscovery.rng`).
`runmodel` and `structurefit` limit BLAS to one thread while they run
(`formdiscovery.threads`, needs `threadpoolctl`). Wrap your own loops over `graph_like` in
`with formdiscovery.threads.blas_threads():` for the same speed-up. On the command line
the option is `formdiscovery run --blas-threads N` (0 keeps the library's setting).

### Drawing graphs

`draw_dot(adj, labels, backend=...)` is `draw_dot.m`. It returns MATLAB's
`(xret, yret, labels)`, and `return_figure=True` also returns the figure.

| Backend | Needs | Layout | Output |
|---|---|---|---|
| `pygraphviz` (default) | pygraphviz or the `neato` executable | neato with draw_dot's flags (positions equal the original's) | matplotlib, the `graph_draw.m` ellipses and arrows |
| `networkx` | nothing extra | neato via pygraphviz, else Kamada-Kawai (`layout=`) | matplotlib, `nx.draw_networkx` |
| `plotly` | `pip install -e .[interactive]` | as `networkx` | interactive `plotly` figure with hover text |
| `pyvis` | `pip install -e .[interactive]` | as `networkx` | vis-network HTML page |

```python
from formdiscovery.viz.draw import draw_dot, draw_graph, draw_results, ProgressFigures
from formdiscovery.viz.networkx_backend import to_networkx, to_graphml, to_dot

draw_results(res, path="results.png", backend="networkx", layout="kamada_kawai")
draw_results(res, path="results.html", backend="plotly")    # all runs, interactive

fig = draw_graph(graph, names, backend="plotly")            # hover: object -> cluster,
fig.show()                                                  #        cluster -> members
draw_graph(graph, names, backend="pyvis").write_html("tree.html")

G = to_networkx(graph, names)          # DiGraph; node kind/label/cluster_id, edge W and 1/W
to_graphml(graph, "tree.graphml", names)                    # for Gephi / Cytoscape

# MATLAB's progress figures 1-3 (pre-clean, post-clean, best split / result)
show = ProgressFigures(outdir="figures", backend="networkx")
runmodel(ProgressFigures.enable(ps), 5, 2, 1, show=show)
```

From the shell:

```bash
formdiscovery run --structures chain,ring,tree --datasets 1,2,3 --out results/ --figures figs/
formdiscovery draw results/resultsdemo.npz --out results.png                 # neato + matplotlib
formdiscovery draw results/resultsdemo.npz --out results.png --backend networkx --layout kamada_kawai
formdiscovery draw results/resultsdemo.npz --out results.html --backend plotly
formdiscovery draw results/resultsdemo.npz --out tree.html --backend pyvis --runs 8
formdiscovery draw results/resultsdemo.npz --out tree.svg --graphviz --runs 8  # Graphviz renders (pygraphviz)
```

Display quirks of the original are kept by default. Each undirected edge is drawn as two
arrows (KI-37); use `undirected='lines'` for plain lines. draw_dot's neato flags are
malformed (KI-32/35); use `flags='intended'` for the documented ones. See
`KNOWN_ISSUES.md`.

## How it was verified

- Every MATLAB function has an Octave fixture script in `tests/octave/` that runs the original
  code on real inputs and saves inputs and outputs to `tests/fixtures/*.mat`. The pytest
  suite compares the Python translation against those fixtures, so the tests run without
  Octave. Tests marked `octave` additionally drive Octave live through oct2py. They are
  skipped when it is not installed, except in strict mode (the `fd` env's Python, or
  `RALPH_REQUIRE_OCTAVE=1`), where a skipped Octave test fails the run;
  `tests/test_gate_env.py` checks the toolchain itself.
- Structural outputs are compared exactly; deterministic floats at `rtol=1e-10`;
  optimiser-dependent values by optimality (objective and gradient norm no worse than
  Octave's) plus a documented tolerance.
- Randomness enters only through `randperm`. An Octave shim (`matlab/octave_shims/`) records
  or replays permutations, and `formdiscovery.rng` provides matching Python providers, so the
  search heuristics are compared with identical random choices.
- The Octave baseline runs (`matlab/run_baseline.m`) for the feature and relational demo grids
  are committed under `tests/fixtures/baseline/`.

```bash
~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow"   # regression gate, Octave live (strict)
python -m pytest -q -m "not slow"     # fixture-only run under another Python (~1 min)
python -m pytest -q -m octave         # live Octave parity (needs the fd env)
python -m pytest -q -m slow           # long runs
python tools/gen_fixtures.py          # regenerate all fixtures through Octave
```

## Layout

| Path | Contents |
|---|---|
| `src/formdiscovery/` | The port. `graph.py` (graph structure and grammars), `likelihood_feat.py` / `likelihood_rel.py` (scores), `search.py` (split, swap, prune-and-regraft, `gibbs_clean`, `structurefit`), `run.py` (`runmodel`, `masterrun`), `cli.py`, `rng.py`, `params.py`, `preprocess.py`, `weights.py`, `matlab_compat.py`, `io.py` |
| `src/formdiscovery/viz/` | Display: `dot.py` (DOT text), `pygraphviz_backend.py` + `graph_draw.py` (draw_dot's layout and drawing), `draw.py` (the `draw_dot` facade, progress figures, results), `networkx_backend.py` (conversion, exports), `plotly_backend.py`, `pyvis_backend.py`, `interactive.py` |
| `examples/` | `formdiscovery_demo.ipynb`: the masterrun demo end to end, with figures |
| `src/formdiscovery/CONVENTIONS.md` | Index, ordering and dtype rules used throughout the port |
| `matlab/formdiscovery1.0/` | Verbatim copy of the original MATLAB sources and data, plus 16 documented Octave-compatibility edits (`matlab/PATCHES.md`) |
| `matlab/run_baseline.m` | Headless Octave reproduction of `masterrun` used to produce the baseline fixtures |
| `ANOMALIES.md` | Curated log of anomalies found: paper vs code, Octave vs MATLAB, surprising results, original bugs, each with a status |
| `KNOWN_ISSUES.md` | Bugs and quirks of the original and how the port treats each one (replicate, fix, or not ported) |
| `tests/` | Fixture scripts (`tests/octave/`), fixtures, pytest parity tests, Octave baselines |
| `tools/` | Fixture generation, Octave/Python run comparison, benchmark (`bench_perf.py`) |
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
