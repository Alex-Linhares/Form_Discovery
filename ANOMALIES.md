# Anomalies log

Things found during the translation that a reader of the results should know about: places
where the code disagrees with the paper, where Octave disagrees with MATLAB, where the search
gives a surprising answer, and bugs in the original that change behaviour. This is the
curated, high-level list. `KNOWN_ISSUES.md` (KI-n) holds the line-by-line entries with the
decision taken for each and the test that pins it; `matlab/PATCHES.md` holds the edits made
to the Octave copy of the sources.

Rule for the project: every new anomaly gets an entry here in the iteration that finds it,
with a status of **open** (needs a human look), **explained** (cause known, nothing to do), or
**handled** (code or test changed; say where).

| # | Anomaly | Category | Status | Details |
|---|---|---|---|---|
| A1 | On the `animals` feature data the code ranks a **hierarchy above the tree**; the paper (Fig. 3) reports the tree. Item 30 showed the two forms are nearly tied: Octave's best hierarchy −3220.6 vs best tree −3223.3 (under 3 nats), while Python's own searches end tree −3223.3 vs hierarchy −3223.5, i.e. the tree wins there by 0.16. Scoring is not the cause (Python ranks Octave's final graphs exactly as Octave does); the winner depends on how far the greedy search gets. | paper vs code | **open** | KI-30, `tests/test_paperlevel.py`. Still unexplained: the shipped data set has 33 animals × 102 features (the paper's had 60 × 106) and the released defaults may differ from those used for the figure. A multi-seed run at the paper's settings would settle whether the paper's clear tree preference is reproducible. |
| A2 | The relational demo `demo_hierarchy_rel_bin` is best fit by an **undirected ring without self-links** (−62.3), not by any hierarchy form (best −63.3). The "true" hierarchy stored in the `.mat` scores −81.1, well below what the search finds for a hierarchy (−70.2). | surprising result | **open** | Seen in the Octave baseline (PROGRESS.md iterations 7, 9) and confirmed by the M3 checkpoint (iteration 24). Pinned by `tests/test_baseline_rel.py::test_best_form`. Small data set (28 objects); may simply be what the model prefers at these hyperparameters. |
| A3 | Octave's `fminunc` (TolFun = TolX = 1e-6, `LargeScale` ignored) **stops early**: gradient norms up to ~15 and objectives up to 0.08 above the optimum. Log-evidence values therefore differ from Python's by up to 2e-4 relative; Python's optimum is never worse. All four scipy methods tried reach the same optimum. | Octave vs MATLAB / numerics | explained | KI-10, `tests/test_glslow.py::test_worst_logI_gap_is_octaves`. The baseline numbers committed under `tests/fixtures/baseline/` are therefore Octave's, not MATLAB's; final clusterings are unaffected on every data set tested (ARI = 1 across seeds). |
| A4 | Octave's `union(row, [])` returns a **column** where MATLAB returns a row. Every `tree` run and `undirhierarchy × demo_hierarchy_rel_bin` crashed in Octave (`spr.m:87`, `horizontal dimensions mismatch`). | Octave vs MATLAB | handled | Patch 16 in `matlab/PATCHES.md` (`find_descendants.m:29`), KI-9. All 37 set-operation call sites audited; this was the only one affected. |
| A5 | The released code contains bugs that were present when the paper was produced. Reachable ones: speeds 1 and 2 are dead (`case{'1,2'}` is a string, KI-1); `cyldimsearchring` grows an *order*, not a ring (KI-29); `find_descendants` loops forever on a cycle above a queued node (KI-15); `nchoosek` on a one-member node returns a count (KI-25). Unreachable or harmless ones are listed in `KNOWN_ISSUES.md`. | original bug | handled | Replicated in Python unless replication is impossible (endless loop) or the MATLAB code would itself error; each deviation is marked "fix" in its KI entry and raises `FormDiscoveryError`. |
| A6 | Current Graphviz writes **float node coordinates**; the original `dot_to_graph.m` parsed `%d,%d` and failed on every modern `neato` layout. Also, Ubuntu's `/usr/bin/neato` has no layout plugin; only the conda-forge `neato` works. | environment | handled | Patches 14 and "Environment note" in `matlab/PATCHES.md`. Display is off (`ps.show*=0`) in all baselines. |
| A7 | `structurefit` saves a growth-history file only for stages in which a depth improved, so a run leaves a **variable set of files** (`alltie5` always, others only if they improved). Not a bug, but easy to mistake for a missing output. | behaviour note | explained | PROGRESS.md iteration 4; `tests/test_baseline.py::test_growth_histories`. |
| A8 | The 2008 release directory contained an `octave-core` dump: someone tried it under Octave 3.x and it crashed, consistent with A4 and A6. | history | explained | The dump was not copied into the repo. |
| A9 | `draw_dot` **never applies `regular` or `minlen=5`**: `draw_dot.m:46-47` glue `-Gregular` and `-Gminlen=5` into one flag, and neato sets an attribute named `regular-Gminlen`. Only `maxiter=25000` and `overlap=false` take effect. Other display-code bugs: an undirected graph with arc labels crashes `graph_to_dot` (a `labeltext` typo); `dot_to_graph` keeps the `;` in a right-hand node name unless its line is the longest, gives a node the position of another whose name contains it, and divides `x` by its range + 1 but `y` by its range. | original bug | handled | KI-32, KI-31, KI-33, KI-8, KI-34; all replicated in `viz/dot.py` and pinned by `tests/test_viz_dot.py` (item 31). Display only. The figures the code draws differ from what the neato flags suggest; item 32 must decide whether to also offer the intended flags. |
| A10 | Octave's `sprintf('%d', 10.5)` prints `10.5` (like `%g`); MATLAB prints `1.050000e+01`. So `graph_to_dot`'s `size="%d,%d"` line differs between the two for a non-integer width or height. | Octave vs MATLAB | explained | `draw_dot` always uses the integer defaults (10, 10), so the drawn graphs are unaffected. `viz.dot.graph_to_dot` follows Octave (`_octave_d`), pinned by `test_graph_to_dot_options_match_octave` case 8 and `test_octave_d_format`. |

## Form definitions that matter for reading A1 and A2

In this code a **tree** is an *unrooted* tree whose objects sit only at leaves; the internal
nodes are latent cluster nodes that may not hold objects (`graph.illegal`). It grows by two
productions (`split_node.m`): a leaf splits into two new leaves and becomes internal, or two
sibling leaves are regrouped. The prior counts unrooted binary trees with labelled leaves
(`structcounts.m:33`). `runmodel` removes the tree root at the end and re-fits.

A **hierarchy** is a *rooted* tree in which objects may sit at **any** node, internal nodes
included, and edges are directed parent → child. It grows by three productions: add a child
under a node, insert a node into an edge (or a new root above a root with two or more
children), or add a sibling that shares the parents. The prior counts labelled rooted or
unrooted trees on the cluster nodes (`structcounts.m:36-37`). Relational data use the
`dirhierarchy`/`undirhierarchy` variants (with and without self-links).

So a hierarchy can put, say, "mammal" on an internal node with "dog" and "cat" below it,
whereas a tree must put every animal on a leaf and explain "mammal" with an unlabelled
internal node. On feature data the two forms score the same object arrangement differently
because of the branch-length priors and the number of cluster nodes each needs.
