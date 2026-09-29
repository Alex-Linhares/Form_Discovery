"""Graph-structure helpers (PLAN.md §5; L0-b, item 08).

``expand_graph``, ``get_edgemap`` and ``find_descendants`` work on plain adjacency
matrices. The ``Graph``/``Component`` dataclasses and the functions that build graphs
(``combinegraphs``, ``makeemptygraph``, ...) are added here from item 11 on. Indices are
0-based (``CONVENTIONS.md``). Pinned against Octave by ``tests/octave/fx_l0b.m`` →
``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``).
"""

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import find_F, union

__all__ = ["expand_graph", "get_edgemap", "find_descendants"]


def expand_graph(adj, zs, type=None):
    """``expand_graph.m:9-31``: hang the objects off a graph over clusters.

    ``adj`` is ``nclust x nclust``; ``zs`` is a list of ``nclust`` arrays of 0-based object
    indices (MATLAB cell ``zs``). Returns ``(newadj, objcount)``: ``newadj`` is
    ``(objcount + nclust)`` square with the objects first, ``adj`` in the lower-right block
    and a directed edge from cluster node ``objcount + i`` to each object in ``zs[i]``.
    ``objcount`` is the total length of the ``zs`` (duplicates counted, as MATLAB).
    ``type`` is unused, as in MATLAB. Raises :class:`FormDiscoveryError` where MATLAB errors.
    """
    adj = np.atleast_2d(np.asarray(adj, dtype=float))
    if adj.shape[0] != adj.shape[1]:
        raise FormDiscoveryError("expand_graph: adj must be square")
    elif adj.shape[0] != len(zs):
        raise FormDiscoveryError("expand_graph: adj inconsistent with zs")
    nclust = adj.shape[0]
    zs = [np.asarray(z, dtype=np.int64).ravel() for z in zs]
    objcount = int(sum(len(z) for z in zs))
    newadj = np.zeros((objcount + nclust, objcount + nclust))
    newadj[objcount:, objcount:] = adj
    for i, z in enumerate(zs):
        newadj[objcount + i, z] = 1.0  # now directed
    return newadj, objcount


def get_edgemap(adj, sym=0):
    """``get_edgemap.m:6-24``: number the edges of ``adj``.

    Edges are numbered in MATLAB column-major ``find`` order. With ``sym`` true (MATLAB
    ``get_edgemap(adj, 'sym', 1)``, ``combinegraphs.m:31``) only the strict lower triangle
    is numbered and the map is symmetrised, so ``(i, j)`` and ``(j, i)`` share a number.

    **Edge numbers keep MATLAB's values** (``1..k``, ``0`` = no edge; ``CONVENTIONS.md``):
    callers test ``emap != 0`` (``find(emap)``) and ``kron`` the map with an identity
    (``combinegraphs.m:52,69``), which only works with 0 as the no-edge value. Subtract 1
    where an edge number indexes a weight vector (``combineWs.m:44``,
    ``extract_weights.m:64``). Returns a float array like MATLAB's ``zeros``.
    """
    adj = np.atleast_2d(np.asarray(adj))
    emap = np.zeros(adj.shape).ravel(order="F")
    if sym:
        es = find_F(np.tril(adj, -1))
        emap[es] = np.arange(1, len(es) + 1)
        emap = emap.reshape(adj.shape, order="F")
        emap = emap + emap.T
    else:
        es = find_F(adj)
        emap[es] = np.arange(1, len(es) + 1)
        emap = emap.reshape(adj.shape, order="F")
    return emap


def find_descendants(adj):
    """``find_descendants.m:5-39`` (with PATCH(octave) #16): the descendants of every node
    of the directed graph ``adj`` (``adj[i, j] != 0``: ``j`` is a child of ``i``).

    Returns a list of ``n`` sorted 1-D int arrays of 0-based node indices (MATLAB's
    ``union`` sorts); leaves (zero row sums, ``sum(adj, 2) == 0``) get an empty array. The
    queue order follows the MATLAB code exactly: a node whose children are not all done is
    moved to the back of the queue.

    Deviations (``KNOWN_ISSUES.md`` KI-15): MATLAB loops forever when a node in the queue
    sits above a cycle; this raises :class:`FormDiscoveryError` once a full pass over the
    queue makes no progress. Nodes that are never reached from a leaf get an empty array
    (MATLAB leaves them ``[]`` or, past the last assigned index, outside the cell). Callers
    pass trees and DAGs (``spr.m:86``, ``filloutrelgraph.m:10``), where neither happens.
    """
    adj = np.atleast_2d(np.asarray(adj))
    n = adj.shape[0]
    descendants = [np.empty(0, dtype=np.int64) for _ in range(n)]
    leaves = np.flatnonzero(np.sum(adj, axis=1) == 0)
    # nodes marked once they've been in queue
    marked = np.zeros(n, dtype=bool)
    processed = np.zeros(n, dtype=bool)
    queue = []
    for l in leaves:
        marked[l] = True
        processed[l] = True
        parents = np.flatnonzero(adj[:, l])
        new = parents[~marked[parents]]
        queue.extend(new.tolist())
        marked[new] = True

    stalled = 0  # consecutive requeues; len(queue) of them in a row = MATLAB never ends
    while queue:
        node = queue.pop(0)
        children = np.flatnonzero(adj[node, :])
        if np.sum(~processed[children]) >= 1:
            queue.append(node)
            stalled += 1
            if stalled >= len(queue):
                raise FormDiscoveryError(
                    "find_descendants: graph has a cycle above a queued node "
                    "(MATLAB loops forever)")
            continue
        stalled = 0
        ds = children.astype(np.int64)
        for c in children:
            ds = union(ds, descendants[c]).astype(np.int64)
        descendants[node] = ds
        parents = np.flatnonzero(adj[:, node])
        new = parents[~marked[parents]]
        queue.extend(new.tolist())
        marked[new] = True
        processed[node] = True
    return descendants
