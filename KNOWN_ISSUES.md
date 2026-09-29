# Known issues in formdiscovery1.0 and how the Python port handles them

This file lists bugs and quirks in the original MATLAB code (`matlab/formdiscovery1.0/`)
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
`matlab/PATCHES.md`. KI-9 and KI-10 are listed here as well because the port also has to
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
- **Pin:** `tests/test_search.py::test_best_split_speed_1_2_raises` *(item 23)*.

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
- **Pin:** `tests/test_graph.py::test_combinegraphs_illegal_empty` and
  `::test_combinegraphs_nonempty_illegal_raises` *(item 11)*.

### KI-3 `structurefit.m:38,59`: `part{depth,c,pind,2}` misses the component index `i`
- **Code:** the second partition output of `choose_node_split` is stored as
  `part{depth,c,pind,2}` (l.38) and `part{depth,c,1,2}` (l.59), not
  `part{depth,i,c,pind,2}`. Different components can overwrite each other's entries.
- **Reachable:** yes, but the effect is invisible. `part` is written and never read anywhere
  in `structurefit.m`.
- **Decision:** fix by omission. The Python `structurefit` does not keep `part`, because
  nothing reads it. Results are the same.
- **Pin:** `tests/test_structurefit.py::test_growth_history_matches_octave` *(item 27)*
  (identical outputs show the dropped variable does not matter).

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
- **Pin:** `tests/test_structurefit.py::test_product_graph_vacant_move_uses_pind_1`
  *(item 27)*.

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
- **Pin:** `tests/test_util.py::test_dijkstra_matches_octave` *(item 08)* and
  `tests/test_known_issues.py::test_dijkstra_called_with_one_output` (exists).

## Other issues found during Phase 0

### KI-7 `dot_to_graph.m:81–101`: node positions found only by line carry-over
- **Code:** `lst_node` is set on a line that holds `label [` and is used on the first later line
  that holds `pos`. Current Graphviz writes attributes over several lines, so the position is
  found only because `lst_node` carries over from one line to the next.
- **Reachable:** yes (display only, items 31–32).
- **Decision:** replicate in the parity parser `viz/dot.py::dot_to_graph`. The
  pygraphviz backend reads positions from the layout directly and does not have this quirk.
- **Pin:** `tests/test_viz_dot.py::test_dot_to_graph_matches_octave` *(item 31)*, run on
  `tests/fixtures/dot_to_graph/`.

### KI-8 `dot_to_graph.m:88–89`: labels that are substrings of other labels
- **Code:** `strfind(line, labels{node})` for every node, and the last match wins
  (the source says "we assume no label is substring of any other label"). With labels
  `1` and `10`, a line for node `10` also matches `1`. Which node gets the position then
  depends on label order and on which nodes already have `x(node) ~= 0`.
- **Reachable:** yes, for any graph with 10 or more numbered nodes (e.g. the `ring12`
  fixture).
- **Decision:** replicate in the parity parser. The pygraphviz/networkx backends match whole
  node names.
- **Pin:** `tests/test_viz_dot.py::test_dot_to_graph_ring12_substring_labels` *(item 31)*.

### KI-9 Octave `union(row, [])` returns a column (`find_descendants.m:29`)
- **Code:** this is an Octave-vs-MATLAB difference, not a bug in the original. Octave returns
  a column for `union([1 2], [])`, where MATLAB returns a row. After the leaves' `[]` is merged
  in, `descendants{j}` becomes a column, and `spr.m:87` `[j, descendants{j}]` crashes.
- **Reachable:** yes. It crashes every feature `tree` run (item 04) and the
  `undirhierarchy × demo_hierarchy_rel_bin` relational run (item 05).
- **Decision:** fixed in the Octave copy with `PATCH(octave)` #16 (`ds = ds(:)';` after the
  `union`, item 03b). In MATLAB the result was already a row, so the patch changes nothing
  there. The other 36 set-operation call sites were audited (`matlab/PATCHES.md`, "Set-operation
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
- **Pin:** `tests/test_likelihood_feat.py` slow-mode tests *(item 19)*.

### KI-11 `runmodel.m:89`: `ps.fixedall` is set twice
- **Code:** `ps.speed = 5; ps.fixedall= 1; ps.fixedall= 1; ...`. The duplicate is harmless.
  The analogous lines 107 and 126 set `fixedinternal` and `fixedexternal`, so the author may
  have meant to set a second flag here.
- **Reachable:** yes (the `alltie` stage). It has no effect.
- **Decision:** replicate (set `fixedall` once).
- **Pin:** `tests/test_run.py::test_runmodel_matches_baseline` *(item 28)*.

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
