# Plan: `structure-discovery`, one JavaScript module for ARC-AGI

Status: plan only. Date: 2026-10-01.

## Goal

A single, dependency-free TypeScript module, **never published anywhere** (especially not npm) and usable from the browser or
Node, that takes a small set of entities (ARC objects, cells, colours, or game states) and
returns the structural form that best organises them, the graph of that form, and a score:

```ts
import { discoverStructure } from "structure-discovery";

const result = discoverStructure({
  entities: ["a", "b", "c", "d", "e", "f"],
  relations: { touches: [[0,1,0,0,0,1], ...] },      // and/or
  features:  [[x, y, w, h, colour, area], ...],      // and/or
  similarity: [[...]],
  forms: ["partition", "chain", "ring", "order", "tree", "hierarchy", "grid"],
});
// result.best      -> { form: "ring", score: -12.3, clusters: [["a","b"],["c"],...], graph: {nodes, edges} }
// result.ranking   -> all requested forms with scores and margins
```

That is the whole surface. No server, no Python, no Octave. Everything else in this repo is
background reading, not a dependency.

## What it is

The Kemp & Tenenbaum (2008) idea, reduced to what ARC needs:

- **Forms** are node-replacement grammars. Each form grows a cluster graph by splitting one
  node at a time: partition (split into two unconnected clusters), chain and order (insert a
  node in a line), ring (insert a node in a cycle), tree and hierarchy (add children),
  grid (chain × chain), plus a few ARC-specific ones: mirror pairs, star (one hub), periodic
  sequence (ring with period k).
- **Search** is the original greedy one: start with every entity in one cluster, try every
  legal split of every cluster, keep the best, clean up by moving entities between clusters,
  stop when the score stops improving. Entities are few (≤ 30), so the search is cheap.
- **Score** = log likelihood of the data given the graph + log prior of the graph. The prior
  penalises clusters (geometric in the number of nodes) and favours simpler forms. The
  likelihood has two cases:
  - *relations* (binary or count matrices): entities in cluster A relate to entities in
    cluster B with one probability per cluster pair, integrated out with a Beta or Dirichlet
    prior (closed form, no optimiser);
  - *features or similarity*: entities close in the graph have similar features, a Gaussian
    process over the graph with branch lengths fixed to one (closed form, no optimiser).
  Dropping the per-edge branch-length optimisation is the one deliberate simplification. It
  removes the only part of the original that is numerically delicate, and at ARC sizes the
  loss in discrimination is expected to be small. This is measured, not assumed (Phase 2).

Output per form: the cluster assignment, the cluster graph (nodes, edges, direction), the
score, and a margin to the runner-up. Deterministic for a given seed.

## What it is not

Not a grid parser, not a rule inducer, not an ARC solver. The caller segments the grid into
entities and computes relations and features; the module says what structure the entities
form. Keeping that line is what makes the module small and reusable: the same call describes
the objects in one grid, the colours across a task, or the states of an ARC-AGI-3 game.

## Design constraints

- TypeScript, zero runtime dependencies, one file per concern (`forms`, `search`, `score`,
  `index`), under 2,000 lines. ESM + CJS builds, type declarations, works in a Web Worker.
- Pure functions, seeded RNG, no global state. A fit of 12 entities over 7 forms completes
  in under 50 ms in Node; a 30-entity fit under 1 s.
- Inputs validated with clear errors (square matrices, matching lengths, known form names).
- Optional `onStep(frame)` callback that reports the graph after each accepted split, for
  UIs that want to watch the structure form.

## Phases

1. **Core (one loop, ~6 items).** Types and validation; the forms and their split
   productions; the relational likelihood; the feature/similarity likelihood; the prior;
   the greedy search with cleanup. Unit tests per piece on hand-built cases where the answer
   is known (a 6-cycle relation must come out a ring; two disconnected cliques a partition;
   a strict dominance matrix an order; a nested containment matrix a hierarchy).
2. **Calibration.** A labelled set of 100 ARC-AGI-1 grids and 50 ARC-AGI-3 frames with
   hand-labelled forms among their objects (entities by 4-connected same-colour flood fill,
   a few obvious relations). Tune the two prior parameters on half, report top-1 and top-3
   form accuracy on the other half, per form. Compare with the full model (the Python port
   in this repo, used only as an oracle here) on the same set to measure what the fixed
   branch lengths cost. Add branch lengths back only if the gap is material.
3. **Package.** npm package `structure-discovery`, README with the API and three examples
   (one grid's objects, colours across a task, states across ARC-AGI-3 frames), a 30-line
   browser demo page that draws the returned graph on a canvas, CI running the tests.
4. **ARC-specific forms** (mirror pairs, star, periodic sequence) added one at a time, each
   with its prior count and a labelled-set check that it is picked when it should be and
   not otherwise.

## Done when

- The API above works from a browser `<script type="module">` and from Node with no build
  step beyond `npm install`.
- Top-1 form accuracy on the held-out labelled set is reported, with the gap to the full
  model stated.
- The four hand-built unit cases and the labelled set are the regression suite.
