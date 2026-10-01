# Plan: an ARC-AGI structure discovery model, callable from JavaScript

Status: plan only, nothing implemented. Date: 2026-10-01.
Builds on the verified Python port in this repo (`PLAN.md`, loops 0001–0003) and on the
ARC work already in `~/dev`: ConForm Level 1 entities for ARC-AGI-3 frames
(`ConFormJS/ARC3`, `library/ConForm_Level1_ARC-AGI-3_Entities`), the ConForm-applied-to-ARC
book, and the Deep_Vision `arc-agi` solver (codelets, slipnet of 1946 audited relations,
pixel- and object-level QAP matching).

## 0. What form discovery can and cannot do for ARC

The model answers one question: **given a set of entities and what is known about them
(features, similarities, or relations), which structural form organises them, and what is the
best graph of that form?** It returns a form label (partition, chain, order, ring, hierarchy,
tree, grid, cylinder, and their directed / self-link variants), a cluster assignment, the
cluster graph with edge lengths, and a Bayesian score that trades fit against complexity.

It does **not** parse grids, infer transformations, or produce output grids. For ARC it is a
**structure descriptor**: a component that turns a bag of objects into a small symbolic
summary ("six objects arranged in a ring", "three colour classes in a strict order", "a
containment hierarchy three deep"), with a principled score for how clearly the structure is
there. The value for ARC comes from using that summary in three places:

1. **Per grid**: a compact, discrete description of an input or output grid's organisation,
   invariant to pixel position and scale. Useful as a feature for the existing solvers, as a
   slipnet relation (`arranged_in_ring`, `ordered_by_size`, `nested_in_hierarchy`), and for
   choosing which codelets to run.
2. **Across the demonstration pairs**: the structure of the inputs versus the structure of the
   outputs is often the whole rule ("the chain is reversed", "each cluster of the partition is
   collapsed to one object", "the ring is rotated one step"). A rule expressed at the level of
   forms transfers to the test input even when object counts and sizes differ.
3. **Over time (ARC-AGI-3)**: entities across frames, and game states as entities with
   transitions as relations, give the topology of a level (a chain of rooms, a ring of states,
   a grid of positions) and which entities move together (a partition). That is world-model
   material for an agent.

Honest expectations: on ARC-AGI-1/2 this is a contributor to a solver, not a solver. The plan
therefore measures it first as a descriptor (does it recover hand-labelled structure?) and
only then as part of a solving pipeline against the existing baselines.

## 1. Target architecture

```
JavaScript (browser / Node)                     Python (this repo)
────────────────────────────                    ───────────────────────────────────────────
ConFormJS entities, ARC task JSON  ──HTTP/SSE──▶ formdiscovery-server (FastAPI)
@rootai/formdiscovery-client (TS)  ◀──frames───  ├─ formdiscovery.arc    (grid → entities → relations)
                                                 ├─ formdiscovery.run    (fit, replay, cancel, frames)
Node-only: child_process JSONL     ──stdio────▶  └─ formdiscovery.cli    (fit --json, serve)
Browser-only (optional): Pyodide bundle of the numeric core
```

Three ways to call from JavaScript, in order of delivery:

- **A. HTTP service + TypeScript client (first).** One process serves fits; the browser or
  Node calls `fit`, streams progress frames (the same `preclean` / `postclean` /
  `inferredgraph` events the Qt GUI draws), and fetches results. Works for both ConFormJS in
  the browser and Node pipelines. No change to the numerics.
- **B. Node direct (cheap, second).** `formdiscovery fit --json` reads a request on stdin and
  writes JSON lines (frames, then the result) on stdout, so a Node script can spawn it with
  `child_process` and no server. Same request/response schema as A.
- **C. In-browser (optional, later).** A Pyodide build of the numeric core (numpy + scipy are
  available in Pyodide; pygraphviz, threadpoolctl and Qt are not and must become optional
  imports). Lets ConFormJS run fits with no backend. Expected to be 5–20× slower than native;
  fine for ARC-sized problems (≤ 30 entities) if measured so.
- **D. TypeScript port (optional, last).** Only if latency or offline use demands it. The same
  test-driven method as loop0001 applies, with the Python port and its 25 committed fixtures
  as the oracle (export them to JSON). ~6k lines; the optimiser and Laplace step would be
  compared by optimality, as in PLAN.md §4.1.

## 2. The request/response contract (shared by A, B, C)

Request (`FitRequest`), JSON:

```json
{
  "entities": [{"id": "obj3", "label": "red L", "features": [..]}],   // or
  "similarity": [[...]],                                                // n×n, or
  "relations": [{"name": "touches", "type": "binary|frequency", "matrix": [[...]]}],
  "forms": ["chain", "ring", "tree", "partition", "grid", "order", "hierarchy"],
  "settings": {"seed": 1, "speed": 5, "theta": null, "lbeta": null, "sigbeta": null,
               "repeats": 1, "frames": true, "timeout_s": 30}
}
```

Response (`FitResult`): per form, `ll`, `prior`, `likelihood`, `z` (cluster of each entity),
`clusters` (lists of ids), `cluster_graph` (`adj`, `W`, `type`), `object_graph`, `nframes`,
`elapsed_s`; plus `ranking` (forms by `ll`) and `winner`. Frames (`Frame`): `event`, `adj`,
`names`, `title`, `ll`, `depth`, `t`. Errors carry the model's `FormDiscoveryError` message.
The schema is published as JSON Schema and as TypeScript types generated from the Python
dataclasses, and a contract test runs the same request through A and B and asserts identical
results.

ARC-specific endpoint (`/arc/describe`): input an ARC task JSON (train/test pairs) or an
ARC-AGI-3 frame CSV; output, per grid, the entities found, the relations computed, and the
`FitResult` for each requested form. The grid-to-entities step is pluggable: 4-connected
same-colour components (the ARC convention), ConForm Level 1 clusters (imported from the
ARC3 study's space files), or caller-supplied entities.

## 3. Model extensions needed for ARC

Each is a separate, Octave-free item; parity tests from loop0001 stay green since the
original forms and code paths are untouched.

1. **Multiple relations at once.** The original takes one relation matrix. ARC grids yield
   several (touches, same colour, same shape, aligned horizontally, aligned vertically,
   contains, larger than). Treat them as independent relational data sets sharing the
   structure (the likelihood is a sum over relations), or stack them as a binary feature
   matrix. Decide by Phase 0 experiments.
2. **Features from geometry.** Entities' bounding boxes, centroids, colour histograms, shape
   signatures (normalised masks), areas; and scaling that suits a dozen 20-dimensional
   objects rather than 8 objects with 1000 features (the shipped `simpleshiftscale` and
   `sigbeta`/`lbeta` defaults assume the latter).
3. **Forms that ARC needs and the grammar lacks.** Torus (ring × ring) and cylinder already
   follow from the product machinery; add explicit "mirror pair" (partition into pairs with a
   reflection relation), "star" (one hub, the `hierarchy` of depth 1), and "sequence with
   period k" (a `ring` with k clusters), each as a named form with its prior count, so the
   ranking can say "this is a mirror arrangement" instead of a generic partition.
4. **Hyperparameters for small n.** With 3–12 entities the prior dominates. Make `theta`,
   `lbeta`, `sigbeta` request parameters, and calibrate defaults on the labelled set from
   Phase 0 (maximise agreement with hand labels), reporting the sensitivity.
5. **Speed.** Fast mode (speed 5) for ranking many forms, slow mode only on the winner; a
   wall-clock budget per request; parallel forms across processes (BLAS already pinned);
   cache `structcounts` per n. Target: ≤ 2 s per grid for all forms on a laptop core.
6. **Relabelling-invariant comparison of two structures** (input vs output grid): canonical
   forms of the cluster graph (the original's `graphsig` used nauty; use networkx's
   Weisfeiler–Lehman hash plus explicit isomorphism for ≤ 12 nodes) so "same form, same
   graph, clusters permuted" is detectable. This is the hook Phase 4 builds on.

## 4. Phases

Each phase is a Ralph loop with the strict, parallel gate from loop0002, one item per
iteration, anomalies logged in `ANOMALIES.md`.

### Phase 0 — Feasibility study (no new code paths in the model)
- Build a **labelled structure set**: 100 ARC-AGI-1 grids (train split) and 50 ARC-AGI-3
  frames, each hand-labelled with the form(s) a person sees among its objects (chain, ring,
  grid, partition, order, hierarchy, none). Store as JSON with the entity segmentation used.
- Run the existing port on them with flood-fill entities and simple relations/features.
  Report: top-1 and top-3 form accuracy versus the labels, per form; failure modes; timing.
- Survey 200 ARC-AGI-1 tasks and tag which have a rule expressible as a structure-level
  transformation. This number decides how much of Phase 4 is worth doing.
- Deliverable: `docs/arc/phase0_report.md` with the tables, and a go/no-go per extension in §3.

### Phase 1 — Model extensions (§3, items 1–5)
- Multi-relation likelihood, geometric features and scaling, the new forms, request-level
  hyperparameters, fast-mode ranking with a budget, calibration on the Phase 0 set.
- Gate: all loop0001 parity tests unchanged; new tests against hand-built small cases and
  the labelled set (accuracy must not drop below Phase 0 numbers).

### Phase 2 — ARC adapters (`formdiscovery.arc`)
- `grid_to_entities` (flood fill; ConForm Level 1 import from the ARC3 study space files;
  caller-supplied), `entities_to_relations` (the relation list above, each a documented
  function), `describe_grid`, `describe_task`, `describe_frames` (ARC-AGI-3 sequences:
  entities tracked across frames, states as entities).
- Fixtures: the Phase 0 labelled set becomes the regression set; outputs pinned.

### Phase 3 — JavaScript access (A and B)
- `formdiscovery serve` (FastAPI + uvicorn): `/fit`, `/jobs/{id}/frames` (SSE),
  `/jobs/{id}`, `/score`, `/arc/describe`, `/health`; cancellation via the loop0003 hook;
  one worker process per job from a pool; CORS; OpenAPI.
- `formdiscovery fit --json` (JSON lines on stdio) for Node.
- `js/formdiscovery-client/`: TypeScript package with generated types, `fit()`,
  `fitStream()` (async iterator of frames), `describeArcTask()`; tests with a mocked server
  and one live test against `serve`; a 40-line example that feeds ConFormJS clusters in and
  draws the returned cluster graph with the explorer's existing canvas.
- Contract test: identical results through HTTP, stdio, and the Python API for the same
  request and seed.

### Phase 4 — Structure-level rule inference on ARC-AGI-1/2
- For each task: describe every input and output grid; find the per-pair structural change
  (same form / different form; cluster mapping via §3.6; chain reversal, ring rotation,
  cluster collapse or expansion, hierarchy level change); express it in a small DSL; verify
  the DSL program reproduces every demonstration output from its input description; apply to
  the test input; render via the existing object-level reconstruction in Deep_Vision
  (same-shape tasks first, as `ARC_OBJECT_QAP_PLAN.md` does).
- Integration, additive only (the Deep_Vision `INTEGRATION_PLAN.md` rule): expose the
  descriptors as slipnet relations and as codelets; never remove an existing solver path.
- Evaluation: exact-match on the ARC-AGI-1 public evaluation set, reported alongside the
  pixel-QAP and object-QAP baselines, plus the subset the Phase 0 survey tagged as
  structure-level; latency per task.

### Phase 5 — ARC-AGI-3 temporal structure
- Entities across frames (track by shape and colour), relations "moves with", "precedes",
  "blocks"; states as entities with action-transition relations; forms over both. Output: a
  level map (form + graph) and entity groups, streamed as frames so an agent UI can watch it
  form. Evaluate on the 25 games × 10 steps of the ARC3 sample frames against hand labels.

### Phase 6 — In-browser and native JS (C, then D if justified)
- Pyodide build: optional imports, a wheel, a benchmark page; if ≤ 5 s per grid, publish.
- TypeScript port only if Phase 3–5 usage shows the service is the bottleneck; use the
  Python fixtures as oracle, exactly as loop0001 used Octave.

## 5. Milestones and exit criteria

| # | Milestone | Done when |
|---|---|---|
| M0 | Phase 0 report | labelled set committed; accuracy table; go/no-go per extension |
| M1 | Extended model | top-1 form accuracy on the labelled set ≥ 0.8 (or the Phase 0 ceiling), parity tests green |
| M2 | ARC adapters | `describe_task` runs on all 400 ARC-AGI-1 training tasks in < 10 min total |
| M3 | JS access | ConFormJS example fits and draws through the TS client; contract test green |
| M4 | Solver contribution | exact-match on the structure-level subset reported; no regression on existing baselines |
| M5 | ARC-AGI-3 | level maps for the 25 sample games with labelled agreement reported |
| M6 | In-browser | Pyodide fit of a demo grid in the browser within budget |

## 6. Risks and how the plan handles them

- **Descriptor, not solver.** Phase 0 quantifies the ceiling before anything is built, and
  Phase 4 measures contribution against existing baselines rather than in isolation.
- **Tiny n.** The prior over forms dominates with 3–12 objects; calibration (§3.4) and
  reporting the ranking with scores, not just the winner, keep this visible.
- **Segmentation errors propagate.** Entities are pluggable; ConForm Level 1 and flood fill
  can both be run and their descriptions compared; the raw grid is always available to the
  caller.
- **Grammar gaps.** Symmetry, counting and arithmetic relations are not forms; the plan adds
  only forms that are, and leaves the rest to the codelet solver.
- **Service dependency for JS.** Tier B removes the server for Node; Tier C removes it for
  the browser; Tier D is the escape hatch, costed as a loop like 0001.
- **Known model anomalies** (`ANOMALIES.md` A1, A19): near-ties between forms and search
  sensitivity to summation order. Report full rankings with margins, and run a few seeds
  when margins are small.

## 7. Open decisions (defaults chosen)

- Server stack: FastAPI + uvicorn, SSE for frames (WebSocket only if bidirectional control
  beyond cancel is needed).
- Entity default for ARC-AGI-1/2: 4-connected same-colour components; ConForm Level 1 as the
  alternative, imported from the ARC3 study format.
- Package layout: `src/formdiscovery/arc/`, `src/formdiscovery/server/`,
  `js/formdiscovery-client/`; all behind extras (`arc`, `server`) so the core stays light.
- Datasets: ARC-AGI-1 public train/eval JSON and the ARC3 sample frames already on disk;
  nothing is downloaded at test time.
