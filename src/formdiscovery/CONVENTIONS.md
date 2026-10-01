# Conventions for the Python port

These rules come from PLAN.md §2 and §4.3. Every module in `formdiscovery` follows them, so
that a line of Python can be matched to its `.m` source and compared with Octave.

## Names and structure
- Function names are the MATLAB names (already snake_case). Local variable names follow the
  `.m` source where that helps cross-referencing.
- `graph` becomes a `graph.Graph` dataclass whose fields have the MATLAB struct's names.
  `components` is a list of `graph.Component` dataclasses (item 11). Unset fields are
  `None`. Functions that change a graph return a changed deep copy (`Graph.copy()`), since
  MATLAB structs are values. `io.graph_from_mat` / `io.graph_to_mat` convert to and from
  MATLAB structs (fixtures, oct2py); `tests/helpers.py::graph_diff` compares two graphs and
  names the first differing field.
- Graph field types: `W`, `Wsym`, `Wcluster`, `Wclustersym`, `adjcluster`, `adjclustersym`
  and the component matrices are float; `graph.adj`/`graph.adjsym` are bool (MATLAB
  logical). `compinds` is always 2-D, `N x ncomp`. `globinds` keeps MATLAB's
  `zeros(compsizes)` shape, which is `N x N` for one component (only column 0 is used).
  MATLAB's unused 0 entries become -1. Counts (`objcount`, `ncomp`, `nodecount`, ...) are `int`.
- `ps` becomes a `params.Params` dataclass with a nested `params.RunPs` (item 09). A field
  that MATLAB has not set yet (`isfield` false) is `None`. `ps` is passed by value in MATLAB,
  so functions that change it return a changed copy (`Params.copy()`/`Params.replace()`,
  deep copies). `ps.logps` is a list of 10 1-D arrays, so `ps.logps{i}(n)` is
  `ps.logps[i-1][n-1]`. `setrunps` takes a 0-based `dind`. `setps` builds `dlocs` from
  `io.DATA_DIR` (the repo's `data/`), not from `pwd`.
- The chunk fields of `ps.runps` (`featind`, `objind`, `chunksize`, `chunkSS`; item 10,
  `preprocess.makechunks`) are Python lists with one entry per chunk, in the lexicographic
  order of `unique(~isinf(data)', 'rows')`. `featind`/`objind` entries are 0-based int
  arrays. They are set only when `ps.missingdata` is 1; `SS`/`chunkcount` only when it is 0
  (feature data).
- Each function's docstring cites its source file and line range, e.g. ``mysetdiff.m`` (whole
  file) or ``scaledata.m:45-63``.
- `keyboard` and `error` in the MATLAB code become `raise FormDiscoveryError(...)`
  (`formdiscovery.FormDiscoveryError`). `cd`/`mkdir` in `runmodel.m` become an explicit
  output directory. Any other difference from MATLAB is a deliberate deviation and goes in
  `KNOWN_ISSUES.md`.

## Indices
- Python indices are **0-based** everywhere inside the package. That covers `z`, `nodemap`,
  `illegal`, `objind`/`featind` chunk lists and permutations (edge maps: see below).
- Conversion happens only at the boundary: `formdiscovery.io.to0` / `to1` (fixtures, `.mat`
  results) and the parity helpers in `tests/`. Fixtures keep Octave's 1-based values.
- `graph.z` marks a missing object with **-1** (MATLAB `-1`, `empty_graph.m:13`). Observed
  is `z >= 0` in both languages, so the boundary maps MATLAB `z < 0` to -1 and every other
  value to `z - 1`. Component `z` values are always valid nodes.
- Values that are *labels*, not indices (e.g. the entries of `z` when they are compared as
  cluster ids), are shifted the same way. Otherwise `z` could not index `adj`.
- `compind` is a 0-based component index; a negative value keeps MATLAB's meaning `-1`
  (split of the combined graph: `add_element`, `empty_graph`, `best_split.m:12`). A
  production number `pind` (1-3, `split_node.m`, `structurefit.m`) is a label, not an index,
  and is **not** shifted. Where MATLAB returns `-inf` as "production does not apply"
  (`split_node` → `graph = c1 = c2 = -inf`), the port returns `None`s.
- MATLAB name/value options become keywords (`combinegraphs(..., origgraph=, compind=,
  imap=, zonly=)`, `subtreeattach(..., objflag=)`). In `subtreeattach`, `j` is a 0-based
  component node when `objflag` is 0 and a 0-based object when it is 1, as in MATLAB.
  MATLAB subfunctions that tests need to observe are module-level functions
  (`graph.redundantinds`, called through the module so a test can wrap it).
- Cluster *labels* passed in as `z` (`relgraphinit`, `makelcfreq`; item 14) are 0-based
  and must be contiguous (`0..k-1`), as MATLAB needs `1..k`; other labels raise
  `FormDiscoveryError` where MATLAB errors. `reordermissing` takes 0-based `obsind`/
  `missind` and a 1-D `Wvec` (entry 0 = sigma, then the leaf weights). `filloutrelgraph`
  returns a float `adjcluster` also where MATLAB's `A | A'` makes it logical.
- Where a MATLAB function does extra work depending on `nargout`, the port takes a
  `nargout=` keyword with the MATLAB default. `likelihood_feat.dataprobwsig(Wvec, d,
  graph, ps, nargout=3)` returns `(ll, dWvec, dWvecprior)`, `(ll, dWvec)` for
  `nargout=2`, or just `ll` for `nargout=1`, which skips the gradient. With
  `ps.missingdata` (the chunk path, item 17) `d` holds the rows of the assigned objects
  (`z >= 0`, as `graph_like` passes them), and only `nargout` 1 and 2 work (KI-21). Objective callbacks for `hessiangrad`/`checkgrad`
  wrap it as `lambda x: dataprobwsig(x, ...)[:2]`. Weight vectors passed to
  `dataprobwsig` are log weights: entry 0 is `log(sigma)`, then `mat2vec` order.
- `likelihood.graph_like(data, graph, ps)` and `likelihood_feat.graph_like_conn` return
  `(logI, graph)` (item 18). `graph_like` takes the full data set and keeps the assigned
  objects (`z >= 0`). Fast mode is `ps.fast == 1`; `None`/0 means slow mode (item 19):
  `scipy.optimize.minimize` (`likelihood_feat.SLOW_METHOD`, default `trust-exact` with a
  symmetrised finite-difference Hessian; `graph_like_conn(..., method=)` overrides it)
  replaces `fminunc`, then `laplace_logI` and `slow_graph` port l.76-101 exactly. Its
  results are compared with Octave by optimality, not bit for bit (`tests/test_glslow.py`).
  MATLAB's `disp('WARNING: ...')` lines become `warnings.warn`. For `runps.type == 'rel'`
  `graph_like` passes the data dict (`R`, `type`; `lowdiag` for `'reldom'`) whole to
  `likelihood_rel.graph_like_rel` (item 20), which returns the input graph unchanged.
- Weight vectors (`weights.mat2vec`, `combineWs`, `extract_weights`; item 15) are 1-D and
  keep MATLAB's entry order, which is column-major: leaf weights in object order, then
  cluster edges on the strict lower triangle of `adjclustersym` (or of each component's
  `adjsym` with `prodtied`). They hold no indices, so nothing is shifted. `combineWs`
  returns only the graph (MATLAB's second output `ps` is unchanged). Where MATLAB `v(1:n)`
  or `A(idx) = v` would error, the port raises `FormDiscoveryError` instead of truncating;
  a scalar right-hand side is broadcast as in MATLAB.
- Exception: `matlab_compat.chol_upper` returns MATLAB's 1-based failure column `p`, because
  callers only test `p == 0`.
- Exception: **edge maps** (`graph.get_edgemap`, the `edgemap`/`edgemapsym` fields) keep
  MATLAB's edge *numbers* `1..k` with `0` = no edge. Callers test `emap != 0` and `kron` the
  map with an identity (`combinegraphs.m:52,69`), which needs 0 as the empty value. Subtract 1
  where an edge number indexes a weight vector (`combineWs.m:44`, `extract_weights.m:64`).

## Data types
- `.mat` data are uint8/uint16 on disk but double in MATLAB: read them with
  `scipy.io.loadmat(..., mat_dtype=True)` (`io.load_dataset`, `io.load_mat`).
- Relational data sets are dicts `{'R', 'type', 'nobj', 'names'}`. Feature and similarity data
  sets are float ndarrays (`io.load_dataset`).
- MATLAB vectors become 1-D arrays. Row/column orientation is not carried, so Octave's
  set-op orientation problem (KI-9) cannot happen.

## MATLAB semantics that differ silently (use `matlab_compat`)
| MATLAB | Python | Note |
|---|---|---|
| `find(A)`, `[i,j,v] = find(A)` | `find_F(A)`, `find_F(A, return_rc=True)` | column-major order |
| `A(:)`, `reshape`, `A(find(M))` | `order='F'` explicitly | `mat2vec`, `combineWs`, `get_edgemap`, `extract_weights`, `relgraphinit` |
| `hist(x, centres)` | `hist_centres(x, centres)` | end bins open, edge values go up (KI-13); length-1 centres = nbins. Never `np.bincount` directly |
| `unique(v)`, `unique(A,'rows')` with `[b,i,j]` | `unique_matlab`, `unique_rows` | sorted / lexicographic; `occurrence` first/last (KI-14) |
| `setdiff`, `intersect`, `union` | `matlab_compat.setdiff/intersect/union` | sorted unique; never rely on insertion order |
| `mysetdiff(A,B)` | `mysetdiff(A,B)` | the one order-preserving set op; keeps duplicates of `A` |
| `[U,p] = chol(A)` | `chol_upper(A)` | upper-triangular, reads only the upper triangle |
| `sum(X)`, `mean(X)` on vector-or-matrix input | `util.matlab_reduce(np.sum, X)` | a vector of either orientation → float; a matrix → per-column 1-D array |
| `~isreal(y)` after `mylogdet` | `isinstance(y, complex)` | `util.mylogdet` returns `complex` only when `det < 0` (KI-12) |
| `sparse(i,j,v,m,n)` | `sparse_accum(i,j,v,shape)` | duplicates are summed |
| `median([])` | `median_matlab(x)` | NaN for empty input or any NaN |
| `[s,i] = sort(x)`, `sort(x,'descend')` | `stable_argsort(x, descending=)` | stable in both directions; NaN last (asc) / first (desc) |
| `[m,i] = max(x)` | `max_first(x)` | first index on ties; NaN skipped unless all NaN |
| `nchoosek(v,2)` | `itertools.combinations(v, 2)` | same lexicographic order; guard the scalar-`v` case (`nchoosek(n,2)` is a count) |
| `for c = unique(...)` | iterate over the 1-D array | a column would iterate once in MATLAB; the sources always use rows |
| `cat(2, graph, nearmgraphs{:})` | list concatenation, dropping `None` | `gibbs_clean.m:186` |

## Randomness
- Randomness enters only through `randperm` (PLAN §4.2). Python code takes an injectable
  permutation provider (`rng.py`, item 22). Parity tests replay the same permutations on both
  sides.
- Where the MATLAB code calls `randperm(n)`, the Python code calls `rng.randperm(n)` on a
  `PermutationProvider`, which returns a 0-based int64 permutation. A search function
  takes an `rng=None` argument and normalises it with `as_provider`. `None` or an int
  seed gives `NumpyPermutations`; `IdentityPermutations` and `ReplayPermutations` serve
  tests. Draw exactly as often, and in the same order, as the MATLAB code, including
  `randperm(0)`. Replay counts the draws, and `assert_exhausted()` checks them.
- The Octave side is `matlab/octave_shims/randperm.m`. It takes these settings:
  - `FD_RANDPERM` unset: the built-in;
  - `FD_RANDPERM=identity`: `1:n`;
  - `FD_RANDPERM=<file>`: replay the file;
  - `FD_RANDPERM_LOG=<file>`: log every draw.

  `randperm_config(source, log)` sets these and rewinds the queue. Queue and log files
  share one format: a 1-based `n p1 ... pn` line per draw (`write_queue`/`read_queue`).
  In live tests, the `replay` fixture offers `queue(perms)`, `identity()` and
  `record(seed)` + `from_log()`. Fixture scripts `addpath` the shim directory themselves
  and call `randperm_config()` before they save. To record the draws of one call, a
  fixture truncates the log, calls the function in pass-through mode and stores the log
  text; the test replays it with `ReplayPermutations(parse_queue(text))`
  (`fx_search.m`, item 23).
- `search.py` (item 23): `choose_seedpairs`, `best_split` and `choose_node_split` take
  0-based `compind`/`c`/object indices and `rng=None`; `choose_node_split` passes one
  provider to both of its callees. For a high-level split (`compind < 0`,
  `structurefit.m:60`) the `pind` argument of `best_split`/`choose_node_split` is the
  vacant neighbour's 0-based node index, not a production number. A node that cannot be
  split returns `(-inf, parts, None)` instead of MATLAB's `newgraph = []`.
  `addnearmiss` works on a 1-D score array and a list of graphs and returns new copies.
- Ties: when two `best_split` candidates are mirror images (the same split with the
  children swapped) their scores are equal in exact arithmetic, and rounding decides
  which one `max` sees first. Python and Octave round differently, so the parity tests
  accept any Python candidate within rtol 1e-10 of the best whose graph and parts equal
  Octave's (`tests/test_search.py::check_call`). Growth histories (item 27) can diverge at
  such a tie; see `structurefit` below.
- `search.swapobjclust` (item 24) takes `comp` as a 0-based component or `None`
  (MATLAB `[]`, the whole graph), the MATLAB options as keywords (`objflag`, `fastflag`,
  `debug`) and `rng=None`. The near-miss graphs are a list. `chooseswaps` returns float
  `(sw1, sw2)` arrays that hold 0-based indices, with NaN where MATLAB has NaN. After an
  accepted change the pass goes on with the old permutation, as in MATLAB.
  Ties in the near-miss list: equal-scoring candidates can be stored in a different order,
  and when more of them tie than fit, a different subset can be kept.
  `tests/test_swap.py::check_nearmisses` accepts both, but only among entries that tie
  to rtol 1e-10.
- `search.spr` and `search.collapsedims` (item 25) have the same return tuple and
  near-miss handling. `spr` takes a 0-based component `i`; `makers` returns 0-based
  `(rs, cs)` int arrays (`tree` edges in column-major `find` order). Replicated quirks:
  after an accept, `spr` draws a **new** permutation and keeps the loops' old lengths,
  and `collapsedims` keeps the pass's `dijkstra` distances. `collapsedims` makes one draw
  per slice that fits into the vacant clusters, and none for the others.
- `search.gibbs_clean` (item 26) takes MATLAB's options as keywords (`loopmax`,
  `nearmisses`, `loopeps`, `swaptypes`, `fast`, `debug`; `optlens` is ignored, as l.36
  overwrites it) and one `rng`, which all its callees share in MATLAB's call order. It
  returns `(ll, graph)`. The near-miss list is a list with `None` for MATLAB's empty cells,
  and `nearmissopts` drops them (`cat(2, graph, nearmgraphs{:})`). `graphsig` (nauty)
  raises `NotImplementedError`. Speed 5 is compared exactly. At speed 4 the slow score
  (`fminunc`) cannot match bit for bit, so `tests/test_gibbs.py` has two tests.
  **Oracle replay:** `likelihood.graph_like` is monkeypatched so that every slow call
  (`ps.fast == 0`) returns Octave's recorded result, after checking that its input graph
  is Octave's; the replay must then match exactly. **Python optimizer:** `ll` must lie
  within `LOGI_RTOL`, and most graphs must match; an accept decision can flip, and then
  the draws differ.
- Fixtures that spy on a function during real runs (`fx_search.m`, `fx_swap.m`,
  `fx_spr.m`, `fx_gibbs.m`, `fx_structurefit.m`, `fx_runmodel.m`, `fx_masterrun.m`) copy the
  original to `<name>_orig.m` in a temporary directory placed first on the path. A
  forwarding `<name>.m` records the calls. `fx_swap.m` also copies the subfunctions into
  `swsub.m` behind a dispatcher so they can be called directly; `fx_spr.m` does the same
  for `spr` and `collapsedims` (`sprsub.m`, `cdsub.m`, one spy `l4b2_spy.m`).
  `fx_gibbs.m` spies on `gibbs_clean` (`gibbs_spy.m`). While a spied call runs,
  it also wraps `graph_like` (`glc_spy.m`) to record the slow calls. `fx_structurefit.m`
  spies on `structurefit` (`sf_spy.m`), with `glc_spy.m` and a `choose_node_split`
  wrapper (`cns_spy.m`).
- `search.structurefit(data, ps, graph=None, savefile=None, callback=None, rng=None)`
  (item 27) returns `(ll, graph, bestgraphlls, bestgraph)`: a 1-D array and a list of
  graphs. `graph=None` is MATLAB's `[]`. `save(savefile, ...)` becomes optional: with
  `savefile` a `.mat` file is written after each accepted depth (`.mat` is appended, as
  MATLAB does; Octave's `save` does not append it), and `callback(bestgraphlls,
  bestgraph)` is called at the same points. The per-depth `lls`/`newgraph` cell arrays
  become dicts keyed by `(i, c, pind)`: `i` is a 0-based component, or `ncomp` for the
  product-graph moves; `c` is a 0-based node (for `i = ncomp`, the 0-based move number);
  `pind` is the production label. `bestsplit` returns `(m, key)`, and `(0, 0, 1)` when
  nothing beats `-inf`. `tests/test_structurefit.py` replays with Octave's slow results
  (the speed-4 oracle pattern, used at both speeds since `structurefit` itself scores
  slowly). It also uses two tie rules:
  - **split ties:** when Python's `choose_node_split` graph is not Octave's, Octave's
    graph must be one of Python's `best_split` candidates tied with the best to
    `TIE_RTOL`, and that candidate is used instead (`SplitOracle`);
  - **near-miss ties:** mirror-image near misses can reach their slow scores in the
    other order. A request may then take a later unused Octave record whose slow score
    ties with the expected one (`TieOracle`).

  The committed fixture needs these 4 times: the first split of both
  `chain:demo_chain_feat` runs and of the cylinder run, and one near-miss pair.
- `run.runmodel(ps, sind, dind, rind, outdir=None, rng=None)` (item 28) takes 0-based
  `sind`/`dind` into `ps.structures`/`ps.data` and returns `(ll, graph, names, bestglls,
  bestgraph)`. One `rng` is shared by every callee, nested dimension searches included.
  `bestglls`/`bestgraph` are MATLAB's cells `{stage, speed}` as 2-D object arrays, grown as
  MATLAB grows cells, with `None` for empty cells: entry `[k, speed - 1]` holds stage `k`'s
  1-D history array or list of graphs. `outdir` replaces `mkdir`/`cd`: with it the growth
  histories go to `<outdir>/results/<struct>out/<data><rind>/growthhistory<stage><speed>.mat`
  (`run.run_dir`), and without it nothing is written. The `griddimsearch`/`cyldimsearch*`
  names are not in `setps.structures`; append them to use them. Their nested run uses the
  run directory as its base, as MATLAB's relative `mkdir` does. `tests/test_runmodel.py`
  replays whole runs from `fx_runmodel.m`, which wraps `graph_like` (`glc_spy.m`) and
  `choose_node_split` (`cns_spy.m`) for the whole run. It uses the `SplitOracle`/`TieOracle`
  rules above and substitutes Octave's scaled feature data for Python's `scaledata` output
  (they agree to about 1 ulp, which can flip ties).
- `run.masterrun(ps=None, thisstruct=(1, 3, 5), thisdata=(0, 1, 2), repeats=1, ...,
  outdir=None, masterfile='resultsdemo', rng=None, seed=1)` (item 29) returns a
  `run.MasterResults`. Its `modellike`/`structure`/`pss`/`llhistory` are 3-D
  (`[sind, dind, rind - 1]`, 0-based, `rind` from 1; MATLAB drops the trailing singleton
  when `repeats = 1`) and `names` is `1 x D`. Seeding: MATLAB's `rand('state', rind)`
  before each run becomes `NumpyPermutations(seed + rind - 1)`. A provider passed as `rng`
  is shared by every run in order (whole-script replay); a callable gets `rind`. With
  `outdir`, `<outdir>/<masterfile>.npz` (arrays) and `.json` (summary) replace
  `resultsdemo.mat`, and an existing pair is merged in before each store, as
  masterrun's `load(masterfile)` does. The CLI `formdiscovery run` (`cli.py`,
  `python -m formdiscovery`) takes names or MATLAB's 1-based indices. `fx_masterrun.m`
  runs the unmodified `masterrun.m` script. A verbatim copy is called by name, because
  Octave's `run()` would `cd` into the source directory. A `system.m` shim answers the
  `which neato` probe with "not found", and a `data` symlink serves `setps`'s pwd-relative
  `dlocs`. `tests/test_masterrun.py` replays the whole script with one provider and the
  oracles above.

## Display (`viz/`, PLAN §6)
- `viz/dot.py` (item 31) is a pure-text port: `graph_to_dot(adj, ...)` returns the DOT
  string (nodes numbered `1..n`, MATLAB's numbers, as in the file Octave writes) and
  writes it only when `filename=` is given. `dot_to_graph(text)` returns `(adj, labels, x,
  y)` with `labels` in order of first appearance and `adj` holding 1-based edge numbers;
  `dot_to_graph_file(path)` reads a file first. `adj_is_directed` is `draw_dot.m:35`.
- The parsers replicate the original's quirks (KI-7, KI-8, KI-31..34); a real DOT parser
  (pygraphviz) belongs to the backends of items 32-33.
- Layouts are compared on the same neato text, so parses are exact (`assert_array_equal`).
  `fx_viz_dot.m` runs the unmodified `draw_dot` with a `graph_draw` shim
  (`tests/octave/drawdot_shim/`, added to the path only by that fixture) that records the
  temporary `_GtDout.dot`/`_LAYout.dot` texts. neato comes from the Octave prefix's `bin/`
  (the fd env), put first on `PATH`.
- Item 32: `viz/draw.py` `draw_dot(adj, labels=None, backend='pygraphviz', *, pos,
  nodemult, fontsz, ax, flags, engine, undirected, wd)` returns MATLAB's `(xret, yret,
  labels)` and draws on matplotlib axes (`ax=None`: pyplot's current axes; tests always
  pass a `Figure` axes). No temporary `.dot` files are written.
  - Layout (`viz/pygraphviz_backend.py`): `graph_to_dot` of `adj > 0`, then neato through
    pygraphviz (`engine='pygraphviz'`) or the executable (`'cli'`, found by `find_neato`:
    `$FORMDISCOVERY_NEATO`, `PATH`, next to Python, each probed). `flags='matlab'` (default)
    passes draw_dot's glued attributes (KI-32, KI-35), so the layout text equals Octave's
    with the same Graphviz (14.1.2); `flags='intended'` the documented ones.
  - Positions: `dot_positions(lay, n, pos)` is `draw_dot.m:52-72` (singletons at 0.05,
    sorted by node number).
  - Drawing (`viz/graph_draw.py`): the geometry is in pure functions (`node_colors`,
    `node_halfwidths`, `edge_segments`); the half-widths come from matplotlib text
    extents, so parity tests pass Octave's `wd`. KI-37 (two arrows per undirected edge) is
    the default, `undirected='lines'` the alternative.
  - `graph_draw.m` cannot run in Octave (KI-36): `fx_viz_draw.m` runs an edited temporary
    copy and records its geometry; `tests/octave/graphdraw_shim/` holds the arrow recorder.
- Progress figures: the model code calls an optional `show(event, adj, names, title)`
  (`search.show_graph`) where MATLAB draws, gated by the `ps.show*` flags, with MATLAB's
  padding (`''`, or `' '` for pre/post-clean) and titles (`sprintf_g`, `num2str`). Events
  and MATLAB figures: `truegraph` 1, `preclean` 1, `postclean` 2, `bestsplit` 3,
  `inferredgraph` 3. `runmodel`, `brlencases`, `structurefit`, `choose_node_split`,
  `best_split` and `masterrun` take `show=`. `viz.draw.ProgressFigures` is the drawing
  callback. `fx_viz_progress.m` records Octave's `figure`/`clf`/`title`/`drawnow`/
  `draw_dot` calls with the shims in `tests/octave/progress_shim/`.
- Image regression: `tests/viz_images.py` renders fixture graphs at Octave's positions
  (DejaVu Sans, 560 x 420 px); baselines in `tests/baseline_images/` (the port's own
  renders, `python tools/gen_viz_baselines.py`). The text-free variant is compared at
  RMS 2 on any matplotlib; the full one at 2 on the baselines' version, else 15.

- Item 33, networkx backend (`viz/networkx_backend.py`):
  - `to_networkx(graph, names, directed=None)`: nodes are the 0-based indices of
    `graph.adj`. Each node has `kind` (`object`/`cluster`), `label` and `cluster_id`
    (`z`, or `node - objcount` for a cluster node). Each edge has `W` and
    `weight = 1/W` (a length, as networkx layouts read it). `directed=None` follows
    draw_dot.m:35, which makes every stored `graph.adj` a `DiGraph`.
  - `from_networkx` is the inverse. `to_graphml`/`from_graphml` and `to_dot`/`from_dot`
    are the exports. The DOT writer is pure text and writes `len = 1/W` instead of
    `weight`; the reader needs pygraphviz.
  - `draw_dot(..., backend='networkx', layout='auto'|'neato'|'kamada_kawai')`.
    - `neato` is `graphviz_layout` with draw_dot's attributes. It reads positions by
      whole node name, so it equals Octave's draw_dot except where KI-8 fires
      (ANOMALIES A15).
    - `kamada_kawai` is scaled to 72-point edges before the `dot_to_graph`
      normalisation.
  - `tests/viz_images.py` takes `backend=`. The networkx baselines are in
    `tests/baseline_images/networkx/`.

- Item 34, interactive backends (optional extra `interactive`: plotly, pyvis):
  - `draw_dot(..., backend='plotly'|'pyvis')` uses the networkx backend's layout
    (`layout`, `flags`) and draws with `viz/plotly_backend.draw_plotly` (a `go.Figure`:
    a `'nodes'` trace, a `'lines'` trace, one arrow annotation per edge) or
    `viz/pyvis_backend.draw_pyvis` (a *directed* `Network`, nodes pinned at
    `(600 x, -600 y)`, physics off; pyvis drops the second edge of a pair in an
    undirected network). `ax` is then the figure/network to draw into.
    `return_figure=True` appends the figure (matplotlib, plotly or pyvis) to the return.
  - `viz/interactive.py`: `edge_sets` (graph_draw's arrows in drawing order, or lines for
    symmetric pairs) and `hover_text` (object → `cluster c` = `cluster_id`, 0-based;
    cluster → members), built from `to_networkx`. `sep='<br>'` for plotly, `'\n'` for
    pyvis (vis-network shows titles as plain text).
  - `viz.draw.draw_graph(graph, names, backend)` draws a model graph with hover text;
    `draw_results(..., backend='plotly')` makes one `make_subplots` figure (HTML);
    `ProgressFigures` stays matplotlib-only. CLI: `draw --backend plotly|pyvis`.
  - Tests feed Octave's `X/Y` to both backends and compare nodes, fills and arrows with
    Octave's (`viz_draw.mat`); graph_draw's arrow ends are offset by `wd_x cos`/`wd_y
    sin`, so they are not exactly parallel to the centre line.
  - `examples/formdiscovery_demo.ipynb` is generated and executed by
    `tools/gen_demo_notebook.py`; the gate checks that it matches the generator's cells
    and that its outputs reproduce Octave's masterrun scores, and a `slow` test runs it.

## Performance (item 35, PLAN §7.4)
- Optimisations must leave every result bit for bit unchanged. `tests/test_perf.py`
  compares each one with the code it replaces. Changes that only agree within a
  tolerance (a different optimiser, reusing `inv(J)` blocks) are not made.
- **BLAS threads**: `runmodel` and `structurefit` run under
  `threads.blas_threads()` (1 thread, `threadpoolctl`). On these small matrices a
  multithreaded OpenBLAS is up to 200 times slower (ANOMALIES A16), and one thread
  gives the same bits. Code that calls `graph_like` in a loop outside the drivers should
  use `with threads.blas_threads():` too. `threads.BLAS_THREADS = None` or
  `formdiscovery run --blas-threads 0` keeps the library's setting.
- `Graph.copy`/`Component.copy` copy field by field (`graph._copy_struct`), not through
  `copy.deepcopy`. Arrays keep their memory layout. Two fields that share one array get
  separate copies, so do not rely on aliasing between fields.
- `graph_like_conn`'s slow mode keeps the optimiser's last 8 finite-difference Hessians
  (`hcache`, keyed by the point's bytes). `laplace_logI` reuses the one taken at the
  optimum instead of calling `hessiangrad` again. `gplike` takes `inv_posdef` and
  `logdet` from one `chol` (`util.inv_posdef_logdet`).
- Where the time goes (PROGRESS.md iteration 38): fast mode and `dataprobwsig` take 0.5-0.7
  of Octave's time per call, and relational scoring 0.2. Slow mode takes 1.4-3.6 times
  Octave's, because trust-exact (item 19) computes a finite-difference Hessian, `2n`
  gradient calls, at every iteration. BFGS and L-BFGS-B reach the same optimum at
  Octave's speed, but they are not the default because they change scores within the
  optimiser tolerance.
- Benchmark: `python tools/bench_perf.py [--sections gl,sf] [--live] [--profile]`
  against `tests/fixtures/perf.mat` (`tests/octave/fx_perf.m`).

## Tests and tolerances (PLAN §2)
- Integers and structure (adjacency, `z`, maps, indices): exact, after `to0`.
- Deterministic floats: `assert_allclose(rtol=1e-10, atol=1e-12)`.
- Anything downstream of `fminunc`: compared by optimality within a documented tolerance.
- Every fixture comes from a `tests/octave/fx_<name>.m` function `fx_<name>(outfile)` that
  writes `tests/fixtures/<name>.mat` with `save -v7`. Regenerate with
  `python tools/gen_fixtures.py [name]`. Load with `io.load_fixture(name)`.
