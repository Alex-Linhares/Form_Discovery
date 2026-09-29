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

## Tests and tolerances (PLAN §2)
- Integers and structure (adjacency, `z`, maps, indices): exact, after `to0`.
- Deterministic floats: `assert_allclose(rtol=1e-10, atol=1e-12)`.
- Anything downstream of `fminunc`: compared by optimality within a documented tolerance.
- Every fixture comes from a `tests/octave/fx_<name>.m` function `fx_<name>(outfile)` that
  writes `tests/fixtures/<name>.mat` with `save -v7`. Regenerate with
  `python tools/gen_fixtures.py [name]`. Load with `io.load_fixture(name)`.
