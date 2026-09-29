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
  `io.DATA_DIR`, not from `pwd`.
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
  and call `randperm_config()` before they save.

## Tests and tolerances (PLAN §2)
- Integers and structure (adjacency, `z`, maps, indices): exact, after `to0`.
- Deterministic floats: `assert_allclose(rtol=1e-10, atol=1e-12)`.
- Anything downstream of `fminunc`: compared by optimality within a documented tolerance.
- Every fixture comes from a `tests/octave/fx_<name>.m` function `fx_<name>(outfile)` that
  writes `tests/fixtures/<name>.mat` with `save -v7`. Regenerate with
  `python tools/gen_fixtures.py [name]`. Load with `io.load_fixture(name)`.
