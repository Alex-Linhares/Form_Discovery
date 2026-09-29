"""Graph structure (PLAN.md §5; L0-b item 08, L2-a1 item 11).

``expand_graph``, ``get_edgemap`` and ``find_descendants`` work on plain adjacency
matrices (pinned by ``tests/octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat``,
``tests/test_l0b.py``). The ``Graph``/``Component`` dataclasses mirror the MATLAB ``graph``
struct, and ``combinegraphs``/``makeemptygraph`` build graphs (pinned by
``tests/octave/fx_graph.m`` → ``tests/fixtures/graph.mat``, ``tests/test_graph.py``).
Indices are 0-based (``CONVENTIONS.md``); edge maps keep MATLAB's edge numbers.
"""

import copy
from dataclasses import dataclass, field, fields

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import find_F, median_matlab, union
from .util import subv2ind

__all__ = ["Component", "Graph", "expand_graph", "get_edgemap", "find_descendants",
           "combinegraphs", "makeemptygraph"]


@dataclass
class Component:
    """One entry of MATLAB ``graph.components{i}`` (fields as set by ``makeemptygraph.m:59-64``,
    ``split_node.m:167-185`` and ``combinegraphs.m:28-32``).

    ``adj``/``W``/``adjsym``/``Wsym`` are ``nodecount``-square float arrays over the
    component's cluster nodes. ``z`` (length ``graph.objcount``) is the 0-based node of each
    object, ``illegal`` a 1-D int array of 0-based nodes that may not hold objects (internal
    tree nodes), ``nodemap`` the 0-based component node of each node of the combined graph.
    ``edgemap``/``edgemapsym`` keep MATLAB edge numbers (``get_edgemap``). Unset fields are
    ``None``.
    """
    type: str | None = None
    prodcount: int | None = None
    adj: np.ndarray | None = None
    W: np.ndarray | None = None
    adjsym: np.ndarray | None = None
    Wsym: np.ndarray | None = None
    nodecount: int | None = None
    nodemap: np.ndarray | None = None
    edgecount: int | None = None
    edgemap: np.ndarray | None = None
    edgecountsym: int | None = None
    edgemapsym: np.ndarray | None = None
    z: np.ndarray | None = None
    illegal: np.ndarray | None = None

    def copy(self):
        """Deep copy (MATLAB structs are values)."""
        return copy.deepcopy(self)


@dataclass
class Graph:
    """MATLAB ``graph`` struct (``makeemptygraph.m``, ``combinegraphs.m``); field names as in
    MATLAB.

    Over clusters (``N = prod(compsizes)`` nodes of the product graph): ``adjcluster``,
    ``adjclustersym``, ``Wcluster``, ``Wclustersym`` (float). Over objects then clusters
    (``nobj + N`` square, ``nobj`` = observed objects): ``W``, ``Wsym`` (float) and ``adj``,
    ``adjsym`` (bool, MATLAB logical). ``z`` is the 0-based cluster of each object, **-1
    for a missing object** (MATLAB ``-1``; ``empty_graph.m:13``; observed is ``z >= 0``
    in both). ``compinds`` is ``N x ncomp`` (0-based component node of each cluster),
    ``globinds`` the inverse map (``combinegraphs.m:75-83``, 0-based, -1 where MATLAB has 0;
    ``N x N`` for one component, the ``zeros(compsizes)`` quirk). ``illegal`` is 1-D int.
    ``components`` is a list of :class:`Component`. Unset fields are ``None``.
    """
    type: str | None = None
    objcount: int | None = None
    sigma: float | None = None
    adjcluster: np.ndarray | None = None
    adjclustersym: np.ndarray | None = None
    adj: np.ndarray | None = None
    Wcluster: np.ndarray | None = None
    W: np.ndarray | None = None
    z: np.ndarray | None = None
    leaflengths: np.ndarray | None = None
    extlen: float | None = None
    intlen: float | None = None
    ncomp: int | None = None
    components: list = field(default_factory=list)
    compsizes: np.ndarray | None = None
    compinds: np.ndarray | None = None
    globinds: np.ndarray | None = None
    illegal: np.ndarray | None = None
    Wclustersym: np.ndarray | None = None
    adjsym: np.ndarray | None = None
    Wsym: np.ndarray | None = None

    def copy(self):
        """Deep copy (MATLAB structs are values)."""
        return copy.deepcopy(self)

    def replace(self, **changes):
        """Deep copy with some fields changed."""
        g = self.copy()
        for k, v in changes.items():
            if k not in GRAPH_FIELDS:
                raise AttributeError(f"Graph has no field {k!r}")
            setattr(g, k, v)
        return g


GRAPH_FIELDS = tuple(f.name for f in fields(Graph))
COMPONENT_FIELDS = tuple(f.name for f in fields(Component))


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


def _kron_eye(n, A):
    return np.kron(np.eye(n), A)


def combinegraphs(graph, ps, origgraph=None, compind=None, imap=None, zonly=0):
    """``combinegraphs.m:14-131``: the direct product of the components of ``graph``.

    Returns a new :class:`Graph` (``graph`` is not changed). The MATLAB name/value options
    are keywords: ``origgraph`` (a :class:`Graph`), ``compind`` (0-based component index),
    ``imap`` (0-based: node ``j`` of component ``compind`` in ``graph`` corresponds to node
    ``imap[j]`` of the same component in ``origgraph``) and ``zonly``. Always recomputes the
    component ``nodemap``/``edgemap``/``edgemapsym``, ``compsizes``, ``compinds``,
    ``globinds``, ``z`` (observed objects only), ``illegal``, ``W``, ``adj``, ``adjsym`` and
    ``Wsym``. Unless ``zonly``, also ``adjcluster``, ``adjclustersym``, ``Wcluster``
    (the product of the component ``W``) and ``Wclustersym``; if in addition
    ``ps.prodtied`` is 0, ``ncomp > 1`` and ``origgraph`` is given, ``Wcluster`` is
    replaced by the lengths copied from ``origgraph.Wcluster`` (l.99-117), with the
    median positive length of ``origgraph.Wcluster`` for edges it lacks (``1`` if it is
    1 x 1, NaN if it has no positive entry).

    Replicated quirks: ``Wclustersym`` is built from the product ``W`` *before* the copy
    from ``origgraph``; the leaf edges go to object columns ``0..nobj-1`` in order, not to
    ``obsind`` (l.119-121); ``globinds`` is ``N x N`` for a single component.

    Deviation (``KNOWN_ISSUES.md`` KI-2): with ``ncomp > 1`` and a non-empty ``illegal`` in
    any component, MATLAB's precedence bug (l.48, 66) silently drops the first component's
    list or errors on index 0; this raises :class:`NotImplementedError`. No reachable
    product graph has one.
    """
    graph = graph.copy()
    ncomp = int(graph.ncomp)
    comps = graph.components
    if ncomp > 1 and any(np.size(comps[i].illegal) for i in range(ncomp)):
        raise NotImplementedError(
            "combinegraphs: non-empty illegal in a product graph (KI-2: MATLAB's "
            "'na*0:(nb-1)+illegal' precedence bug)")

    compsizes = np.zeros(ncomp, dtype=np.int64)
    for i in range(ncomp):
        c = comps[i]
        n = np.atleast_2d(c.adj).shape[0]
        compsizes[i] = n
        c.nodemap = np.arange(n, dtype=np.int64)
        c.edgemap = get_edgemap(c.adj)
        c.edgemapsym = get_edgemap(c.adjsym, sym=1)

    graph.compsizes = compsizes
    W = np.atleast_2d(np.asarray(comps[0].W, dtype=float))
    adj = np.atleast_2d(np.asarray(comps[0].adj, dtype=float))
    z = np.asarray(comps[0].z, dtype=np.int64).ravel()
    illegal = np.asarray(comps[0].illegal if comps[0].illegal is not None else [],
                         dtype=np.int64).ravel()

    for i in range(1, ncomp):
        na = W.shape[0]
        Wb = np.atleast_2d(np.asarray(comps[i].W, dtype=float))
        adjb = np.atleast_2d(np.asarray(comps[i].adj, dtype=float))
        nb = Wb.shape[0]
        zb = np.asarray(comps[i].z, dtype=np.int64).ravel()
        Wnew = _kron_eye(nb, W)
        adjnew = _kron_eye(nb, adj)
        z = na * zb + z

        for j in range(i):
            comps[j].nodemap = np.tile(comps[j].nodemap, nb)
            comps[j].edgemap = _kron_eye(nb, comps[j].edgemap)
            comps[j].edgemapsym = _kron_eye(nb, comps[j].edgemapsym)

        Wnewbunscram = _kron_eye(na, Wb)
        adjnewbunscram = _kron_eye(na, adjb)
        # sind = reshape(1:na*nb, nb, na)'; sind = sind(:);
        sind = np.arange(na * nb).reshape(na, nb).ravel(order="F")
        ix = np.ix_(sind, sind)

        adj = adjnew + adjnewbunscram[ix]
        W = Wnew + Wnewbunscram[ix]

        comps[i].nodemap = np.tile(comps[i].nodemap, na)[sind]
        illegal = np.empty(0, dtype=np.int64)  # KI-2: all illegal lists are empty here

        comps[i].edgemap = _kron_eye(na, comps[i].edgemap)[ix]
        comps[i].edgemapsym = _kron_eye(na, comps[i].edgemapsym)[ix]

    # analysis: components of each node at highest level
    graph.compinds = np.column_stack([comps[i].nodemap for i in range(ncomp)])
    inds = subv2ind(compsizes, graph.compinds)
    # synthesis: map component nodes to combined node (zeros(compsizes): n x n if ncomp 1)
    shape = (int(compsizes[0]),) * 2 if ncomp == 1 else tuple(int(s) for s in compsizes)
    globflat = np.full(int(np.prod(shape)), -1, dtype=np.int64)
    globflat[inds] = np.arange(adj.shape[0])
    graph.globinds = globflat.reshape(shape, order="F")

    gz = np.asarray(graph.z, dtype=np.int64).ravel().copy()
    obsind = np.flatnonzero(gz >= 0)
    gz[obsind] = z[obsind]
    graph.z = gz
    graph.illegal = illegal
    nobj = len(obsind)
    if not zonly:
        graph.adjcluster = adj
        graph.adjclustersym = ((adj != 0) | (adj.T != 0)).astype(float)
        graph.Wcluster = W
        both = (adj != 0) & (adj.T != 0)
        doubleWcluster = np.zeros(W.shape)
        doubleWcluster[both] = W[both]
        graph.Wclustersym = W + W.T - doubleWcluster

    if not zonly and not ps.prodtied and ncomp > 1 and origgraph is not None:
        # copy across values from origgraph.Wcluster
        rind, cind, _ = find_F(graph.adjcluster, return_rc=True)
        oldcomps = graph.compinds.copy()
        imap = np.asarray(imap, dtype=np.int64).ravel()
        oldcomps[:, compind] = imap[oldcomps[:, compind]]
        oglob = np.asarray(origgraph.globinds).ravel(order="F")
        oldedgers = oglob[subv2ind(origgraph.compsizes, oldcomps[rind, :])]
        oldedgecs = oglob[subv2ind(origgraph.compsizes, oldcomps[cind, :])]
        oldW = np.atleast_2d(np.asarray(origgraph.Wcluster, dtype=float))
        oldedgelengths = oldW[oldedgers, oldedgecs]
        if oldW.shape[0] == 1:
            oldW = np.array([[1.0]])
        oldedgelengths[oldedgelengths == 0] = median_matlab(oldW[oldW > 0])
        newW = np.asarray(graph.adjcluster, dtype=float).copy()
        newW[rind, cind] = oldedgelengths  # newW(find(adj)): same column-major order
        graph.Wcluster = newW

    Wcl = np.atleast_2d(np.asarray(graph.Wcluster, dtype=float))
    if Wcl.shape != W.shape:
        raise FormDiscoveryError(
            f"combinegraphs: Wcluster is {Wcl.shape}, product graph is {W.shape} "
            "(MATLAB: nonconformant arguments)")
    fullW = np.zeros((W.shape[0] + nobj,) * 2)
    fullW[nobj + z[obsind], np.arange(nobj)] = \
        np.asarray(graph.leaflengths, dtype=float).ravel()[obsind]
    fullW[nobj:, nobj:] = Wcl
    graph.W = fullW
    graph.adj = fullW > 0
    graph.adjsym = graph.adj | graph.adj.T
    graph.Wsym = fullW.copy()
    Wtr = fullW.T
    graph.Wsym[graph.adj.T] = Wtr[graph.adj.T]
    return graph


# makeemptygraph.m:15-56
_SINGLE = ('partition', 'chain', 'ring', 'tree', 'hierarchy', 'order',
           'dirchain', 'dirring', 'dirhierarchy', 'domtree',
           'connected', 'partitionnoself', 'dirringnoself', 'dirchainnoself',
           'ordernoself', 'dirhierarchynoself', 'dirdomtreenoself',
           'undirchain', 'undirchainnoself', 'undirring', 'undirringnoself',
           'undirhierarchy', 'undirhierarchynoself', 'undirdomtree',
           'undirdomtreenoself', 'connectednoself')
_PRODCOUNT1 = ('partition', 'chain', 'ring', 'order',
               'dirchain', 'dirring', 'connected', 'partitionnoself',
               'dirchainnoself', 'dirringnoself', 'ordernoself',
               'undirchain', 'undirchainnoself', 'undirring',
               'undirringnoself', 'connectednoself')
_PRODCOUNT3 = ('hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself',
               'dirdomtreenoself', 'undirhierarchy', 'undirhierarchynoself',
               'undirdomtree', 'undirdomtreenoself')
_PRODUCTS = {'grid': ('chain', 'chain'), 'cylinder': ('ring', 'chain')}


def makeemptygraph(ps):
    """``makeemptygraph.m:5-65``: a graph with one cluster holding every object
    (``ps.runps.nobjects``) for structure ``ps.runps.structname``.

    One component of that type for the 26 single-component names; two components
    (chain x chain, ring x chain) for ``grid``/``cylinder``. ``prodcount`` is 1, 2 (tree)
    or 3 (hierarchy family). An unknown name raises :class:`FormDiscoveryError` (MATLAB
    fails on the undefined ``graph.ncomp``).
    """
    name = ps.runps.structname
    n = int(ps.runps.nobjects)
    graph = Graph()
    graph.type = name
    graph.objcount = n
    graph.sigma = ps.sigmainit
    graph.adjcluster = np.zeros((1, 1))
    graph.adjclustersym = np.zeros((1, 1))
    graph.adj = expand_graph(np.zeros((1, 1)), [np.arange(n)], ps.runps.type)[0]
    graph.Wcluster = np.zeros((1, 1))
    graph.W = graph.adj
    graph.z = np.zeros(n, dtype=np.int64)
    graph.leaflengths = np.ones(n)
    graph.extlen = 1
    graph.intlen = 1
    if name in _SINGLE:
        graph.ncomp = 1
        prodcount = 1 if name in _PRODCOUNT1 else 2 if name == 'tree' else 3
        graph.components = [Component(type=name, prodcount=prodcount)]
    elif name in _PRODUCTS:
        graph.ncomp = 2
        graph.components = [Component(type=t, prodcount=1) for t in _PRODUCTS[name]]
    else:
        raise FormDiscoveryError(f"makeemptygraph: unknown structure {name!r}")

    for c in graph.components:
        c.adj = np.zeros((1, 1))
        c.W = np.zeros((1, 1))
        c.adjsym = np.zeros((1, 1))
        c.Wsym = np.zeros((1, 1))
        c.nodecount = 1
        c.nodemap = np.zeros(1, dtype=np.int64)
        c.edgecount = 0
        c.edgemap = np.zeros((1, 1))
        c.edgecountsym = 0
        c.edgemapsym = np.zeros((1, 1))
        c.z = np.zeros(n, dtype=np.int64)
        c.illegal = np.empty(0, dtype=np.int64)
    return combinegraphs(graph, ps)
