# Known issues in formdiscovery1.0 and how the Python port handles them

This file lists bugs and quirks in the original MATLAB code (`legacy/matlab/formdiscovery1.0/`)
and records one decision for each:

- **replicate**: the Python port behaves like the MATLAB code on every path the code can reach.
- **fix**: the port deliberately behaves differently. The reason is given in the entry.
- **not ported**: the code is outside the pipeline, so nothing in Python depends on it.

The default is *replicate* (PLAN.md §3.5, TASK.md "Faithful first").
Each entry gives the source location, what goes wrong, whether any run can reach it,
the decision, and the test that pins it. Tests marked *(item NN)* do not exist yet; the item
that ports the function must add them under that name. Right now,
`tests/test_known_issues.py` checks that every quirk is still at the cited line and that
every entry below is present.

Octave-vs-MATLAB compatibility edits to the sources are documented separately in
`legacy/matlab/PATCHES.md`. KI-9 and KI-10 are listed here as well because the port also has to
deal with them.

## Bugs listed in PLAN.md §3.5

### KI-1 `best_split.m:120`: speeds 1 and 2 match no `case`
- **Code:** `switch ps.speed ... case{'1,2'}`. The case label is the *string* `'1,2'`, so
  the numeric speeds 1 and 2 never match it. `runmodel.m:147` accepts
  `case{1,2,3,4,5}`, so a run with `ps.speed = 1` or `2` gets as far as `best_split`. There
  no branch assigns `ll`/`mind`, and `if ls(mind) == -inf` (l.141) fails with an
  undefined-variable error.
- **Reachable:** only if a user sets `ps.speed` to 1 or 2. The default is 54 (5 then 4).
  Only speeds 3, 4, 5 and 54 work.
- **Decision:** replicate. For speed 1 or 2, Python `best_split` raises `FormDiscoveryError`
  (the MATLAB run crashes too). The code of the intended branch (`graph_like` for every
  candidate split) is not ported.
- **Pin:** `tests/test_search.py::test_best_split_speed_1_2_raises` and `::test_speed_errors`
  (Octave fails with "'mind' undefined near line 141" for speeds 1, 2 and 54).
  The GUI (loop0003 item 01) offers only the working speeds 3, 4, 5 and 54
  (`gui.main_window.SpeedSpinBox`; 23 is runmodel's "Unknown speed value"), pinned by
  `tests/test_gui_picker.py::test_speed_codes`.

### KI-2 `combinegraphs.m:48,66`: operator precedence in the product-graph `illegal` indices
- **Code:** `illegal = na*0:(nb-1)+illegal;` and `illind(nb*0:(na-1)+newillegal) = 1;`.
  In MATLAB `:` binds more loosely than `+` and `*`, so these are
  `0:((nb-1)+illegal)` and `0:((na-1)+newillegal)`. The intended value was probably
  `na*(0:nb-1) + illegal` (an outer sum). With empty `illegal` the range is `0:[]`, which is
  empty, so the result is correct. With a non-empty list, index 0 either causes an error
  (l.66) or lands in the illegal set (l.48).
- **Reachable:** no. Product graphs (`grid`, `cylinder`) are built only from
  chain/ring components, and `makeemptygraph.m:63` gives every component `illegal = []`.
- **Decision:** replicate the reachable behaviour: empty `illegal` in every component gives an
  empty combined `illegal`. When a component of a product graph has a non-empty `illegal`,
  Python raises `NotImplementedError` instead of guessing the intended formula.
- **Pin:** `tests/test_graph.py::test_combinegraphs_illegal_empty` (every captured product-graph
  call in `tests/fixtures/graph.mat` has empty lists) and
  `::test_combinegraphs_nonempty_illegal_raises` (the fixture records Octave dropping a
  first-component list silently and failing with `illind(0): subscripts must be ...` on a
  second-component one; Python raises in both cases).

### KI-3 `structurefit.m:38,59`: `part{depth,c,pind,2}` misses the component index `i`
- **Code:** the second partition output of `choose_node_split` is stored as
  `part{depth,c,pind,2}` (l.38) and `part{depth,c,1,2}` (l.59), not
  `part{depth,i,c,pind,2}`. Different components can overwrite each other's entries.
- **Reachable:** yes, but the effect is invisible. `part` is written and never read anywhere
  in `structurefit.m`.
- **Decision:** fix by omission. The Python `structurefit` does not keep `part`, because
  nothing reads it. Results are the same.
- **Pin:** `tests/test_structurefit.py::test_growth_history_matches_octave`. Every
  structurefit call in `tests/fixtures/structurefit.mat` replays to Octave's outputs,
  which shows that the dropped variable does not matter.

### KI-4 `structurefit.m:239`: stale `pind` in the product-graph branch
- **Code:** in the "move objects to vacant neighbours" block (`graph.ncomp > 1`) the test
  reads `lls{depth,i,c,1}`, but the assignment reads
  `m = lls{depth,i,c,pind}; ... mpind = pind;`. `pind` still holds the value from
  the previous loop (the last component's `prodcount`).
- **Reachable:** yes, for every `grid`/`cylinder` run. It does no harm there because every
  component of a product graph is a chain or a ring with `prodcount = 1`
  (`makeemptygraph.m`), so `pind == 1`.
- **Decision:** replicate. Python uses the leftover `pind` in the same way, with a comment
  citing this entry, and asserts `pind == 1` there so that a future structure with
  `prodcount > 1` fails loudly.
- **Pin:** `tests/test_structurefit.py::test_product_graph_vacant_move_uses_pind_1`. The
  real grid/cylinder runs never try a vacant-neighbour move, so the fixture adds crafted
  cylinder calls (`cr`) that do; they replay exactly.

### KI-5 `zinit_rel.m:14`: undefined `irmdatadir`, discarded `defaultps`
- **Code:** a script, not a function. It calls `cd(irmdatadir)`, but `irmdatadir` is never
  defined. At l.7 it calls `defaultps(ps);` and throws away the result.
- **Reachable:** no. Nothing calls it. It is a helper for building
  `ps.reloutsideinit = 'external'` initialisations by hand (`runmodel.m:54–62` reads their
  output from `ps.relinitdir`).
- **Decision:** not ported. The `'external'` branch of `runmodel` is ported, and
  users supply the `*_bestz` files themselves.
- **Pin:** `tests/test_known_issues.py::test_zinit_rel_is_unreferenced` (exists).

### KI-6 `dijkstra.m:111`: call to a missing `pred2path`
- **Code:** `if nargout > 1 & length(s) == 1 & length(t) == 1, P = pred2path(P,s,t);`.
  `pred2path.m` is not part of the package.
- **Reachable:** no. The package calls `dijkstra` only with one output
  (`swapobjclust.m:79,105,144` and `collapsedims.m:24`).
- **Decision:** replicate the single-output behaviour. The Python `dijkstra` returns only the
  distance matrix and raises `NotImplementedError` when paths are requested.
- **Pin:** `tests/test_l0b.py::test_dijkstra_matches_octave`, `::test_dijkstra_errors_and_paths` and
  `tests/test_known_issues.py::test_dijkstra_called_with_one_output` (exists).

## Other issues found during Phase 0

### KI-7 `dot_to_graph.m:81–101`: node positions found only by line carry-over
- **Code:** `lst_node` is set on a line that holds `label [` and is used on the first later line
  that holds `pos`. Current Graphviz writes attributes over several lines, so the position is
  found only because `lst_node` carries over from one line to the next.
- **Reachable:** yes (display only, items 31–32).
- **Decision:** replicate in the parity parser `viz/dot.py::dot_to_graph`. The
  pygraphviz backend reads positions from the layout directly and does not have this quirk.
- **Pin:** `tests/test_viz_dot.py::test_dot_to_graph_matches_octave` (run on
  `tests/fixtures/dot_to_graph/`), `test_ki7_positions_come_from_the_next_line` and
  `test_dot_to_graph_baseline_layout_matches_octave` (74 neato layouts, item 31).

### KI-8 `dot_to_graph.m:88–89`: labels that are substrings of other labels
- **Code:** `strfind(line, labels{node})` for every node, and the last match wins
  (the source says "we assume no label is substring of any other label"). With labels
  `1` and `10`, a line for node `10` also matches `1`. Which node gets the position then
  depends on label order and on which nodes already have `x(node) ~= 0`.
- **Reachable:** yes, for any graph with 10 or more numbered nodes (e.g. the `ring12`
  fixture).
- **Decision:** replicate in the parity parser. The pygraphviz/networkx backends match whole
  node names.
- **Pin:** `tests/test_viz_dot.py::test_dot_to_graph_ring12_substring_labels` (item 31).
  Crafted case 5 of `viz_dot.mat` shows it: node `1` takes the position of node `10`.
- **Measured (item 33, ANOMALIES A15):** on the 74 real graphs draw_dot was run on, it
  hits exactly the 5 synthetic true graphs (46-89 nodes). Node `41` (and 6 nodes in
  `synthgrid`) is left at raw `(0, 0)`, which shifts the normalisation of every node.
  The networkx backend (`viz/networkx_backend.py`, `graphviz_layout`) matches whole
  names: its positions equal Octave's on the other 78 `viz_draw.mat` graphs. Pinned by
  `tests/test_viz_networkx.py::test_ki8_in_draw_dot_layouts` and
  `::test_neato_layout_parity`.

### KI-9 Octave `union(row, [])` returns a column (`find_descendants.m:29`)
- **Code:** this is an Octave-vs-MATLAB difference, not a bug in the original. Octave returns
  a column for `union([1 2], [])`, where MATLAB returns a row. After the leaves' `[]` is merged
  in, `descendants{j}` becomes a column, and `spr.m:87` `[j, descendants{j}]` crashes.
- **Reachable:** yes. It crashes every feature `tree` run (item 04) and the
  `undirhierarchy × demo_hierarchy_rel_bin` relational run (item 05).
- **Decision:** fixed in the Octave copy with `PATCH(octave)` #16 (`ds = ds(:)';` after the
  `union`, item 03b). In MATLAB the result was already a row, so the patch changes nothing
  there. The other 36 set-operation call sites were audited (`legacy/matlab/PATCHES.md`, "Set-operation
  orientation audit"): none receives a 0×0 operand whose result shape is later relied on.
  Python returns 1-D arrays, so the port does not have the problem.
- **Pin:** `tests/test_patches.py::test_find_descendants_returns_rows` (live Octave) and
  `::test_find_descendants_patch_present`; the tree entries in `tests/test_baseline.py` and the
  `undirhierarchy × demo_hierarchy_rel_bin` entry in `tests/test_baseline_rel.py`, regenerated
  with the patch applied.

### KI-10 `graph_like_conn.m:50`: `optimset('LargeScale','on',...)`
- **Code:** Octave warns `optimset: unrecognized option: 'LargeScale'` and ignores the
  option. MATLAB's trust-region `fminunc` is replaced by Octave's own `fminunc`.
- **Reachable:** yes, on every slow-mode `graph_like_conn` call.
- **Decision:** the Octave baseline stands in for MATLAB (PLAN §4.1). The Python port uses
  `scipy.optimize.minimize` and is compared by optimality within a tolerance.
- **Pin:** `tests/test_glslow.py` (item 19): the Laplace step and the returned graph at
  Octave's optimum match to rtol 1e-10; the Python optimum is at least as good as
  Octave's (objective ≤ `fX + 1e-6`, smaller gradient norm) and `logI` agrees to rel 2e-4.
  Octave's `fminunc` (TolFun = TolX = 1e-6) stops early, with gradient norms up to ~15,
  which accounts for the whole `logI` gap.

### KI-11 `runmodel.m:89`: `ps.fixedall` is set twice
- **Code:** `ps.speed = 5; ps.fixedall= 1; ps.fixedall= 1; ...`. The duplicate is harmless.
  The analogous lines 107 and 126 set `fixedinternal` and `fixedexternal`, so the author may
  have meant to set a second flag here.
- **Reachable:** yes (the `alltie` stage). It has no effect.
- **Decision:** replicate (set `fixedall` once).
- **Pin:** `tests/test_runmodel.py::test_runmodel_matches_octave` (the two `griddimsearch`
  runs replay Octave exactly; a mutation check confirmed that dropping `fixedall = 1`
  breaks them).

### KI-12 `mylogdet.m` / `logdet.m`: behaviour on non-positive-definite input
- **Code:** `logdet.m:7` calls `U = chol(A)` with one output, so it errors on non-PD input.
  `mylogdet.m:7-12` (whose `function` line says `logdet`; the file name wins) calls
  `[U p] = chol(A)` and on `p ~= 0` returns `log(det(A))` of the *full* matrix. That value is
  complex (`log|det| + i*pi`) when `det(A) < 0`, real when `det(A) > 0` (an even number of
  negative eigenvalues), and `-Inf` when `det(A) == 0`. Both functions read only the upper
  triangle of `A` on the `chol` path.
- **Reachable:** `mylogdet` only at `graph_like_conn.m:90`, `mylogdet(inv(-H))` on the Laplace
  Hessian, which is followed by `if ~isreal(logI)` → recompute from the positive eigenvalues of
  `inv(-H)`. The complex value is therefore part of the control flow. `logdet` is called by
  `gplike.m:11` on a covariance built by `inv_posdef`, so non-PD input would already have
  failed there.
- **Decision:** replicate. `util.mylogdet` returns a Python `complex` when `det < 0` and a
  `float` otherwise (`-inf` for `det == 0`), so the item-19 port of `graph_like_conn` tests
  `isinstance(logI, complex)` as the analogue of `~isreal`. The indefinite-with-`det > 0` case
  stays real and silently wrong, exactly as in MATLAB. `util.logdet` and `util.inv_posdef`
  raise `FormDiscoveryError` where MATLAB's `chol` errors.
- **Pin:** `tests/test_util.py::test_mylogdet_fallback_replicates_complex_log_det` (the five
  non-PD fixture cases: det < 0, det > 0, singular, non-symmetric, negative definite),
  `::test_logdet_and_inv_posdef_raise_on_non_pd`, and the live
  `::test_live_random_parity`.

## Octave-vs-MATLAB built-in differences found while writing `matlab_compat.py` (item 06)

### KI-13 `hist`: values on a bin edge, and `hist(x, n)` on constant `x`
- **Code:** MATLAB's `hist(x, centres)` counts with `histc` on the midpoints between centres,
  so a value exactly on a midpoint goes to the *upper* bin. Octave 10.3 puts it in the
  *lower* bin: `hist([1 2 2.5 3], 1:3)` is `[1 1 2]` in MATLAB and `[1 2 1]` in Octave.
  For the scalar `hist(x, n)` on constant `x`, MATLAB centres the bins on
  `x - floor(n/2) - 0.5 .. x + ceil(n/2) - 0.5` and Octave on
  `x + (-floor((n-1)/2):ceil((n-1)/2))`; they agree for odd `n` and differ for even `n`.
- **Reachable:** no, in practice. The call sites (`graph_like_rel.m:105`,
  `relgraphinit.m:18`, `simplify_graph.m:110,128`, `structurefit.m:49`) count integer
  cluster labels against integer centres (`1:n` or `unique(z)`), so no label lies on a
  midpoint. The scalar form happens only when `unique(z)` has one element `v`, i.e.
  `relgraphinit` with a single cluster. `v = 1` gives the same answer in both.
- **Decision:** replicate MATLAB. `matlab_compat.hist_centres` uses MATLAB's rules; the
  Octave fixture leaves out the two disagreeing cases.
- **Pin:** `tests/test_matlab_compat.py::test_hist_centres_edge_goes_up_as_in_matlab`,
  `::test_hist_nbins_constant_even_follows_matlab`.

### KI-14 `[b, i, j] = unique(...)`: first or last occurrence
- **Code:** MATLAB 7 (the version the code was written for) returned the *last* occurrence in
  `i`. MATLAB R2013a+ and Octave 10.3 return the *first*.
- **Reachable:** no. The only three-output call, `scaledata.m:51`
  (`[b i j]=unique(datamask', 'rows')`), uses `b` and `j` only. Those are the same either way.
- **Decision:** `matlab_compat.unique_rows` / `unique_matlab` default to `'first'` and take
  `occurrence='last'`. Both are tested against Octave's explicit `'first'`/`'last'`.
- **Pin:** `tests/test_matlab_compat.py::test_unique_rows`, `::test_unique_matlab`.

## Issues found while porting L0-b (item 08)

### KI-15 `find_descendants.m:22-25`: endless loop on a cycle above a queued node
- **Code:** a node whose children are not all processed goes to the back of the queue
  (`queue = [queue, node]; continue;`). If a queued node lies on or above a directed cycle,
  its children are never processed and the `while` loop never ends. Nodes never reached from
  a leaf keep no entry: they are `[]`, or outside the cell if their index is past the last
  assigned one.
- **Reachable:** no. The callers pass trees and DAGs: the tree/hierarchy component `adj` in
  `spr.m:86` and the transitive-backbone `adjcluster` in `filloutrelgraph.m:10`. Every such
  graph in the Octave baselines ends (72 inputs in `tests/fixtures/l0b.mat`).
- **Decision:** fix (the only way out of the endless loop). `graph.find_descendants` raises
  `FormDiscoveryError` once `len(queue)` consecutive requeues make no progress, which is the
  point at which the MATLAB queue repeats itself. It always returns `n` entries, with empty
  arrays for unreached nodes. Every input where MATLAB ends gives the same result.
- **Pin:** `tests/test_l0b.py::test_find_descendants_repro_and_cycle`, `::test_find_descendants`.

## Issues found while porting L1 params (item 09)

### KI-16 `structcounts.m:31`: `nobjects = 1` grows `counts` to two columns
- **Code:** `counts(3, 1:2) = [0,0];` writes column 2 even when `maxn = 1`, so the 8×1
  `counts` becomes 8×2. Rows 4-8 are then 1×1 values assigned to both columns, and
  `logcounts + repmat(logclustercounts, 8, 1)` adds an 8×2 matrix to an 8×1 one. MATLAB 7
  (no implicit expansion) stops with a dimension error. Octave 10.3.0 broadcasts: every
  `totsums(i)` gets a phantom second term, so `logps{i}(1)` is `log(1/2)` instead of 0, and
  the tree row is complex (`gammaln(-0.5)` is complex in Octave; the result is
  `36.64 + 1.57i`). For `maxn >= 2` the overwrite on line 31 stays inside the matrix, and
  `gammaln(-0.5)` at `counts(4,1)` is overwritten on line 35, so the output is real.
- **Reachable:** no. It needs a data set with a single object, and none of the 20 has fewer
  than 8.
- **Decision:** follow MATLAB 7: `params.structcounts` raises `FormDiscoveryError` for
  `nobjects < 2`. The Octave result for n = 1 stays in the fixture as evidence.
- **Pin:** `tests/test_params.py::test_structcounts` (case n = 1).

## Issues found while porting L2-a2 (item 12)

### KI-17 `split_node.m:66-149`: edge weights misplaced when a split duplicates or deletes an edge marker
- **Code:** the old edges of the component get the markers `1..nold` in column-major order
  (l.70: `origadj(origind)=1:nold`). The new node copies the row and column of `c`, and the
  old weights are then written to the first `nold` entries of a stable sort of the markers
  (l.141-148: `newW(newind(sind(1:nold)))=origW(origind)`). This is correct only when every
  marker survives exactly once. Two productions break that:
  - `connected` keeps every copied edge, and `domtreeflat` keeps the parents of `c` on the
    new node. Markers then appear twice. The duplicates take later weights, so the weights
    shift. The positions past `nold` keep the raw marker value (an integer such as `3`)
    as their weight.
  - `treever2` deletes the marker of the edge from the parent to the sibling (l.127). The
    weights after it shift by one, and the first new `inf` edge (column-major) gets the last
    old weight instead of the median.
- **Reachable:** yes. It happens in every `connected*` split of a component with edges and in
  every hierarchy pind-3 (`domtreeflat`) split of a node with parents, and the baseline
  relational runs do both (`tests/fixtures/split.mat`, `bl_sp`). The weights of those
  components are placeholders: with `ps.fast` or tied weights `graph_like` re-derives them,
  and otherwise the optimiser moves them.
- **Decision:** replicate. `graph.split_node` uses the same markers and
  `matlab_compat.stable_argsort`.
- **Pin:** `tests/test_split.py::test_marker_weight_quirk` and every `split_node` parity test.

## Issues found while porting L2-b2 (item 15)

### KI-18 `mat2vec.m:21-28`: with `ps.prodtied`, the internal weights are not log weights
- **Code:** `graph_like_conn.m:7` takes the log of `graph.Wsym` only, then calls
  `mat2vec(graph.Wsym, graph, ps)`. With `ps.prodtied` the internal part of the vector
  comes from `graph.components{i}.Wsym` (l.23), which still holds raw weights. The start
  vector therefore mixes log leaf weights (or `log(extlen)`) with raw internal weights.
  `dataprobwsig` takes `exp` of all of them, so every tied internal weight `w` is read as
  `exp(w)`. The round trip `exp(mat2vec(log-Wsym of combineWs(g, Wvec)))` returns `Wvec`
  in every other mode, but with `prodtied` its internal entries are `log(w)` instead of `w`
  whenever the graph has internal edges. The fixture shows this for 94 of 110 graphs in
  both `prodtied` modes; the other 16 have no internal edges. Also, l.25 skips a component
  whose `Wsym` sums to 0, but `combineWs.m:41-42` still takes its `edgecountsym` entries.
- **Reachable:** no. `ps.prodtied` is 0 in `defaultps.m:57` and no source file sets it.
  With `prodtied = 1`, fast mode would score the wrong weights, and slow mode would start
  `fminunc` from a different point.
- **Decision:** replicate. `weights.mat2vec` reads `comp.Wsym` as MATLAB does.
- **Pin:** `tests/test_weights.py::test_round_trip` (the `prodtied` cases) and every
  `mat2vec` parity test.

## Issues found while porting L3-a1 (item 16)

### KI-19 `inv_covariance.m:24-26`: the 'holes' hack makes `J` singular when there are two or more holes
- **Code:** nodes whose column of `W` has no nonzero entry ("orphaned cluster nodes") get
  `J(holes, holes) = 1`. This sets the whole `holes × holes` block to 1, not just its
  diagonal. With one hole, `J` stays positive definite. With two or more, the block is a
  rank-1 matrix of ones, so `J` is singular, and `inv_posdef(J)` in `dataprobwsig.m:83`
  fails in `chol` ('input matrix must be positive definite').
- **Reachable:** only when a scored graph has two or more cluster nodes that have no
  members and no cluster edges. A partition split with an empty part creates such a node:
  `tests/fixtures/dataprob.mat` has `partition:4-6`, all 63 of whose cases error, while
  `partition:3` (one hole) scores normally. None of the 36 `dataprobwsig` calls spied from
  the chain, ring and tree feature baselines has a hole.
- **Decision:** replicate. `likelihood_feat.inv_covariance` sets the same block, and
  `dataprobwsig` raises `FormDiscoveryError`.
- **Pin:** `tests/test_dataprob.py::test_hole_hack_is_exercised`,
  `::test_inv_covariance_holes_block` and the `chol` error cases in `::test_cases`.

### KI-20 `reordermissing.m:22`: `ps.fixedall` without `ps.fixedexternal` fails on missing data
- **Code:** unless `ps.fixedexternal`, `Wvec(2:nobj+1) = Wvec(tind+1)` permutes one leaf
  weight per object. With `ps.fixedall`, `mat2vec` returns a single weight, so `Wvec` has
  two entries and the read fails ('Wvec(14): out of bound 2' for judges' 13 objects). Only
  the missing-data chunk path (`dataprobwsig.m:39`) calls `reordermissing`.
- **Reachable:** `runmodel.m:89` (`griddimsearch`) sets `ps.fixedall = 1` twice and leaves
  `fixedexternal` at 0 (KI-11), so `griddimsearch` on a data set with missing values
  (judges) would stop here. The default `masterrun` grid does not run `griddimsearch`.
- **Decision:** replicate. `graph.reordermissing` raises `FormDiscoveryError`.
- **Pin:** `tests/test_dpmiss.py::test_fixedall_errors` (every `fixedall` case of
  `tests/fixtures/dpmiss.mat`).

### KI-21 `dataprobwsig.m:24-60`: the chunk path never sets `dWvecprior`
- **Code:** the missing-data branch returns after the loop without assigning the third
  output, so `[ll dW dWp] = dataprobwsig(...)` with `ps.missingdata = 1` fails in Octave
  with 'element number 3 undefined in return list'. The recursive per-chunk calls use `ps.missingdata = 0` and are not
  affected.
- **Reachable:** no. `graph_like_conn.m` asks for one output (fast mode, l.16) or two
  (`fminunc`, l.55); `checkgrad` asks for two.
- **Decision:** replicate. `dataprobwsig(..., nargout=3)` raises `FormDiscoveryError` on the
  chunk path; `nargout=2` returns `(ll, dWvec)`.
- **Pin:** `tests/test_dpmiss.py::test_three_outputs_error`.

### KI-22 `graph_like_rel.m:93-100`: the `reldom` edge-direction flip is discarded
- **Code:** for a two-cluster graph with one cluster edge, the `'reldom'` branch flips the
  edge (`graph.adj(nobj+1:end, nobj+1:end) = clustgraph'`) when the data favour the other
  direction. l.162 then sets `graph = origgraph`, so the flip never reaches the caller and
  has no effect on `logI`.
- **Reachable:** no. The branch is marked "Not currently used", and no data set has type
  `'reldom'`.
- **Decision:** replicate (the result is the input graph). `likelihood_rel._reldom` does not
  compute the flip.
- **Pin:** `tests/test_rellike.py::test_reldom_direction_flip_discarded`.

## Issues found while porting L4-a (item 23)

### KI-23 `best_split.m:57-58`: relational data are never masked
- **Code:** feature data hide the unplaced objects with `d(membout, :) = inf`. For
  relational data the code writes `d.ys(:, membout) = inf` etc. into new fields `ys`/`ns`
  of the data struct, and before the loop (l.38-42) it does not mask at all.
  `graph_like_rel` reads only `data.R` and `data.type`, so every call sees the full data.
  (The feature masking has no effect on the score either: the unplaced objects have
  `z = -1` after `empty_graph`, and `graph_like` drops their rows.)
- **Reachable:** yes, on every relational split.
- **Decision:** replicate. `search.best_split` passes relational data unchanged.
- **Pin:** `tests/test_search.py::test_rel_data_not_masked` (plus exact parity of every
  relational `sq`/`bl` record).

### KI-24 `best_split.m:142-145`: high-level split parts come from the input graph
- **Code:** for `compind < 0` (`structurefit.m:60`, moving objects of a product graph
  into a vacant neighbour cell) `part1 = find(graph.z == c1)` and
  `part2 = find(graph.z == c2)` read the *input* graph, not `newgraph`. So `part1` is
  every member of the split cell and `part2` (the vacant cell) is empty, whatever the
  split did.
- **Reachable:** yes, on grid and cylinder runs. The effect is invisible: `structurefit`
  stores the parts in `part`, which it never reads (KI-3).
- **Decision:** replicate.
- **Pin:** `tests/test_search.py::test_high_level_parts_from_input_graph`.

### KI-25 `choose_seedpairs.m:19`: `nchoosek` of a one-member node is a count
- **Code:** `seedpairs = nchoosek(partmembers, 2)`. With one member, `partmembers` is a
  scalar and `nchoosek(n, 2)` returns the number `n*(n-1)/2`, not pairs. With none,
  `best_split` then fails at `partmembers(1)`.
- **Reachable:** no. `choose_node_split.m:13` handles one member itself, and
  `structurefit` only splits occupied nodes.
- **Decision:** fix (deviation). `search.choose_seedpairs` raises `FormDiscoveryError`
  for fewer than two members.
- **Pin:** `tests/test_search.py::test_seedpairs_too_few_members`.

### KI-26 `swapobjclust.m:104-130`: whole-graph swaps with one source cluster
- **Code:** in the full whole-graph mode `pairs = nchoosek(csource, 2)` (l.126). With a
  single source cluster, `csource` is a scalar. MATLAB's `nchoosek(n, 2)` then returns a
  count, and `pairs(:,2)` fails. Octave errors in `nchoosek` itself when `n < 2`. The fast
  mode (l.104-118) has no `nchoosek`. On a one-node product graph, though, Octave fails
  there too, when it concatenates the empty blocks at l.117-118 ('vertical dimensions
  mismatch (0x4 vs 0x2)'). The list would have been empty anyway.
- **Reachable:** no. `gibbs_clean.m:101` calls the whole-graph mode only when
  `ncomp > 1` and at least two components have more than one node. The graph then has
  at least four clusters. The error needs all objects in one of them, which did not
  happen in the fixture's spied grid and cylinder runs. Only the direct `chooseswaps`
  calls on one-cluster graphs in `tests/fixtures/swap.mat` (sub) reach it.
- **Decision:** fix (deviation). `search.chooseswaps` raises `FormDiscoveryError` in
  full mode when there are fewer than two source clusters. In fast mode it returns the
  empty candidate list instead of replicating Octave's concatenation error.
- **Pin:** `tests/test_swap.py::test_ki26_single_source_cluster` and
  `::test_chooseswaps_and_doswap` (the Octave errors in the sub records).

### KI-27 `spr.m:72-98`: `makers` has no case for `domtreenoself`
- **Code:** `gibbs_clean.m:88-91` sends `tree`, the hierarchy family, `domtree` and
  `domtreenoself` components to `spr`. The two `switch` statements in `spr>makers`
  (l.72-77 for objects, l.90-98 for cluster nodes) list `tree`, `hierarchy`,
  `dirhierarchy`, `domtree`, `dirhierarchynoself`, `undirhierarchy` and
  `undirhierarchynoself`, but not `domtreenoself`. For that type `rs` is never assigned,
  and `isempty(rs)` at `spr.m:25` fails with "'rs' undefined". A parentless cluster node
  returns early (l.83-85), before the switch, so it does not fail.
- **Reachable:** no. `domtreenoself` is not in `setps.m`'s structure list, and
  `relgraphinit.m:126-128` refuses to initialise any domtree.
- **Decision:** fix (deviation). `search.makers` raises `FormDiscoveryError` (message
  mentions KI-27) for any type outside the two lists, instead of failing later.
- **Pin:** `tests/test_spr.py::test_ki27_makers_unknown_type`.

### KI-28 `gibbs_clean.m:185-212`: `nearmissopts` rescores the current graph
- **Code:** the comment at l.185 says "so that we don't optimize the current best graph
  again", and l.186 puts the current graph first in the list
  (`cat(2, graph, nearmgraphs{:})`, score 0). Only the nauty branch skips it
  (`j > 1`, l.204). Without nauty (l.209-212, the default `ps.nauty = 0`), the first
  `nearmisses` entries are returned, so entry 1 is the current graph. `gibbs_clean`
  (l.162-170) then scores it slowly once more and could accept it as a "good near-miss"
  if the new optimum beats `ll` by more than `loopeps`. Only `nearmisses - 1` real near
  misses are tried.
- **Reachable:** yes. It happens in every `'nearmisses', 10` call (`structurefit.m:178`,
  speeds 1-4).
- **Decision:** replicate. `search.nearmissopts` returns the current graph first.
- **Pin:** `tests/test_gibbs.py::test_nearmissopts_drops_empties_and_puts_graph_first` and
  `test_speed4_slow_call_counts`; the speed-4 oracle replay checks the order of the slow
  calls.

### KI-29 `runmodel.m:109`: `cyldimsearchring` grows an `order`, not a `ring`
- **Code:** the `cyldimsearchring` branch runs `runmodel(ps, 3, dind, rind)` to grow the
  first dimension, and then sets `graph.components{1}.type = 'ring'` (l.110). In
  `setps.m:3`, `ps.structures{3}` is `'order'` (`{'partition', 'chain', 'order', 'ring',
  ...}`); the ring is `{4}`. The index was probably written for an older structure list.
  So the nested search grows an order (saved under `results/orderout/`), and that
  component, relabelled, becomes the "ring" dimension of the cylinder. The `griddimsearch` and `cyldimsearchchain` branches use `{2}` (`'chain'`),
  which is correct.
- **Reachable:** only when a user appends `'cyldimsearchring'` to `ps.structures`. It is not
  in `setps.m`, and the default `masterrun` grid does not use it.
- **Decision:** replicate. `run.runmodel` runs the nested search on `ps.structures[2]`.
- **Pin:** `tests/test_runmodel.py::test_cyldimsearchring_grows_an_order` and the exact
  replay of the `cyldimsearchring` run in `test_runmodel_matches_octave`.

### KI-30 Paper vs code: on `animals` the hierarchy beats the tree
- **Code:** the PNAS paper (Fig. 3) reports the tree as the best form for the animals data.
  The released code and `data/animals.mat` (33 animals, 102 features; the data README says
  4 all-zero features were dropped from the paper's set) give the unrooted hierarchy the
  best score in Octave: masterrun.m's option b settings (default speed 54),
  `rand('state', s)` for s = 1, 2, 3: hierarchy -3223.66, -3220.63, -3220.62; tree
  -3231.95, -3223.30, -3223.31. The tree is the runner-up, 2.7 nats behind. With seed 1 the
  tree search also stops in a worse local optimum (19 clusters). A hierarchy may put
  objects at internal nodes, so it contains the tree up to the prior, and the two forms
  are close on 33 objects. The other paper-level results hold: every synthetic set
  recovers its form (at speed 5) and `colors` gives the ring.
- **Reachable:** yes, in the default real-world feature analysis (masterrun.m option b).
- **Decision:** replicate (the code wins, TASK.md); nothing is changed. The Python port
  scores Octave's graphs the same (within 1.04e-4 rel), so it too ranks Octave's
  hierarchy first. Its own searches, with numpy permutations seeded 1-3, do not find the
  -3220.6 hierarchy: they end with tree -3223.33 against hierarchy -3223.49. With either
  port, tree and hierarchy are the top two forms and the winner depends on which local
  optimum the search reaches.
- **Pin:** `tests/test_paperlevel.py::test_octave_recovers_form`,
  `test_octave_animals_tree_runner_up`, `test_python_recovers_form` and
  `test_python_rescores_octave_graphs` (all `slow`; fixture `paperlevel.mat`).

### KI-31 `graph_to_dot.m:50`: undirected graphs with arc labels crash
- **Code:** the undirected branch assigns `labeltext = '[label="%s",dir=none]'`, but l.66
  builds the edge format from `labeltxt`, which is then undefined. Octave:
  `'labeltxt' undefined`, after the header and node lines are already in the file.
- **Reachable:** no. `draw_dot` never passes `arc_label`.
- **Decision:** replicate. `viz.dot.graph_to_dot` raises `NameError` and, when given a
  `filename`, writes the same partial text first.
- **Pin:** `tests/test_viz_dot.py::test_graph_to_dot_options_match_octave` (case 10) and
  `test_graph_to_dot_ki31_undirected_arc_label`.

### KI-32 `draw_dot.m:46-47`: `-Gregular` and `-Gminlen=5` are glued together
- **Code:** l.46 ends the string with `-Gregular` and l.47 appends `'-Gminlen=5 ...'` with
  no blank. neato receives `-Gregular-Gminlen=5` and sets a graph attribute named
  `regular-Gminlen` to 5 (it shows in every layout as `"regular-Gminlen"=5`). So neither
  `regular` nor `minlen=5` is applied; only `maxiter=25000` and `overlap=false` are. PLAN §6
  lists all four as the attributes to use.
- **Reachable:** yes, whenever a graph is drawn (`ps.show*`), display only.
- **Decision:** replicate for layout parity. The item 32 backend
  (`viz.pygraphviz_backend`, `flags='matlab'`, the default) passes the same attributes and
  reproduces Octave's layout text byte for byte; `flags='intended'` passes `regular` and
  `minlen=5`. Neither is a neato layout attribute, so the positions do not change
  (`tests/test_viz_draw.py::test_intended_flags_same_positions`).
- **Pin:** `tests/test_viz_dot.py::test_baseline_neato_attributes_ki32` (on the 74
  layouts that Octave's `draw_dot` produced).

### KI-33 `dot_to_graph.m:57`: the right node keeps its `;` unless its line is the longest
- **Code:** `char(lines)` pads every line with blanks to the longest one, and the right node
  is read from `line(dash_pos+3 : length(line)-1)`. The character dropped is meant to be
  the final `;`, but it is a pad blank except on the longest line. So `1 -- 2;` gives the
  node `2;` (a new label), unless that line is the longest in the file.
- **Reachable:** no, for neato output. neato writes every edge with a `[pos=...]` list after
  the right node, so the first token is the plain name. Hand-written DOT files hit it.
- **Decision:** replicate (the parser pads as `char` does).
- **Pin:** `tests/test_viz_dot.py::test_ki33_right_node_keeps_semicolon_unless_longest_line`
  and the crafted cases of `test_dot_to_graph_crafted_matches_octave`.

### KI-34 `dot_to_graph.m:108`: `x` is divided by its range plus one
- **Code:** `x = .9*(x-min(x))/((max(x)-min(x))+1)+.05`, but
  `y = .9*(y-min(y))/(max(y)-min(y))+.05` (l.109). The `+1` guards against a zero range
  but also keeps `x` just below 0.95 (on neato layouts of hundreds of points the effect
  is < 0.5 %; on small coordinates it is large).
- **Reachable:** yes, whenever a graph is drawn, display only.
- **Decision:** replicate.
- **Pin:** `tests/test_viz_dot.py::test_ki34_x_divided_by_range_plus_one`.

### KI-35 `draw_dot.m:47-49`: `-x` is glued onto the overlap value for n > 100
- **Code:** l.47 builds `neato = strcat([neato '-Gminlen=5 -Goverlap=false '])`. `strcat`
  drops trailing blanks from a char argument (MATLAB and Octave), so the string ends in
  `-Goverlap=false` with no blank. For `n > 100`, l.49 appends `-x` the same way, giving
  `-Goverlap=false-x`. neato warns `Unrecognized overlap value "false-x" - using false`
  and sets the attribute `overlap="false-x"`; the `-x` (reduce) flag is never applied.
- **Reachable:** yes, when a graph with more than 100 nodes is drawn (display only). No
  demo graph is that large; the fixture adds a 105-node chain.
- **Decision:** replicate. `viz.pygraphviz_backend.neato_attrs(n, 'matlab')` passes
  `overlap=false-x` for `n > 100`; `flags='intended'` passes `-x` (command-line engine
  only).
- **Pin:** `tests/test_viz_draw.py::test_neato_args`,
  `test_octave_layouts_carry_the_glued_flags` (Octave's layout of the 105-node chain) and
  `test_pygraphviz_layout_is_octaves`/`test_cli_layout_is_octaves`.

### KI-36 `graph_draw.m:115, 125, 158, 166, 557`: graph_draw cannot run in Octave
- **Code:** the four `text(...)` calls abbreviate `'VerticalAlignment'` to
  `'VerticalAlign'`, which Octave rejects as ambiguous (`verticalalignment` /
  `verticalalignmentmode`); MATLAB accepts it. `my_arrow` then reads the undocumented
  MATLAB axes properties `'WarpToFill'` (l.557) and `'Xform'` (l.274), which Octave does
  not have. So no graph can be drawn in Octave with the released code.
- **Reachable:** only with a `ps.show*` flag set (display only; all baselines run with
  them off).
- **Decision:** not ported: the drawing is `viz.graph_draw` (matplotlib). The source is
  not patched. `legacy/tests_octave/fx_viz_draw.m` runs a temporary copy with three recorded
  edits (`'VerticalAlignment'`, the two `my_arrow` calls replaced by a recorder, and a
  recorder of `wd`/`color` before `if nargout > 2`), so the node geometry and arrow end
  points are still compared with the original code.
- **Pin:** `tests/test_viz_draw.py::test_fixture_contents` (the edit counts) and
  `test_graph_draw_geometry_matches_octave`.

### KI-37 `graph_draw.m:82-92`: an undirected edge is drawn as two opposite arrows
- **Code:** both branches of `if (adj(node2,node) == 0)` call `my_arrow`; the plain
  `line(...)` and `adj(node2,node) = -1` of the symmetric branch are disabled by
  `if 0 % ckemp`. So each direction of a symmetric pair gets its own arrow, and an
  undirected edge shows a head at both ends. PLAN §6 says "arrows for directed".
- **Reachable:** yes, whenever a symmetric graph is drawn (8 of the 11 true graphs).
- **Decision:** replicate by default (`undirected='arrows'`); `undirected='lines'` draws
  the disabled branch (one plain line per symmetric pair).
- **Pin:** `tests/test_viz_draw.py::test_undirected_edges_get_two_arrows` and
  `test_graph_draw_octave_wd_and_lines_mode`.

### KI-38 `runmodel.m:42-44, 184-186`: the returned `names` are padded when a figure is on
- **Code:** the `showtruegraph` and `showinferredgraph` blocks pad `names` itself with
  `''` up to the node count of the drawn graph before `draw_dot`. `names` is runmodel's
  output, so with either flag set runmodel returns the padded list, and `masterrun.m`
  stores it in `names{dind}`. `masterrun.m:17-21` sets `showinferredgraph = 1` whenever
  `which neato` succeeds, so in MATLAB the saved names depend on whether Graphviz is
  installed. (`ps.runps.names` is set before and is not affected.)
- **Reachable:** yes, with the flags on (masterrun with neato installed).
- **Decision:** replicate: `run.runmodel` pads the returned names when the flag is set,
  whether or not a `show` callback is given. `masterrun_ps` drops the neato probe (item
  29), so by default the flags are off and the names are not padded.
- **Pin:** `tests/test_viz_draw.py::test_progress_events_match_octave` (Octave's
  `out_names`) and `test_names_padded_without_callback`.

### KI-39 `graph_draw.m:60, 65`: mixed node shapes shift the fill colours
- **Code:** `textoval(x(idx1), ..., color, ...)` and `textbox(x(idx2), ..., color)` pass
  the whole colour list, and both index it with their local loop counter (`c(i,:)`). With
  mixed `node_shapes`, the k-th oval (or box) gets the colour of node k, not its own.
- **Reachable:** no. `draw_dot` always passes `node_shapes = zeros`.
- **Decision:** replicate in `viz.graph_draw.graph_draw`.
- **Pin:** `tests/test_viz_draw.py::test_graph_draw_mixed_shapes_colour_quirk`.
