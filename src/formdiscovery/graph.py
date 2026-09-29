"""Graph structure (PLAN.md §5; L0-b item 08, L2-a1 item 11, L2-a2 item 12, L2-a3 item 13).

``expand_graph``, ``get_edgemap`` and ``find_descendants`` work on plain adjacency
matrices (pinned by ``tests/octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat``,
``tests/test_l0b.py``). The ``Graph``/``Component`` dataclasses mirror the MATLAB ``graph``
struct, and ``combinegraphs``/``makeemptygraph`` build graphs (pinned by
``tests/octave/fx_graph.m`` → ``tests/fixtures/graph.mat``, ``tests/test_graph.py``).
``add_element``, ``empty_graph`` and ``split_node`` grow graphs (pinned by
``tests/octave/fx_split.m`` → ``tests/fixtures/split.mat``, ``tests/test_split.py``).
``simplify_graph`` and ``subtreeattach`` clean and regraft them (item 13, pinned by
``tests/octave/fx_simplify.m`` → ``tests/fixtures/simplify.mat``,
``tests/test_simplify.py``).
Indices are 0-based (``CONVENTIONS.md``); edge maps keep MATLAB's edge numbers.
"""

import copy
from dataclasses import dataclass, field, fields

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import (find_F, hist_centres, intersect, median_matlab, mysetdiff, setdiff,
                            stable_argsort, union)
from .util import subv2ind

__all__ = ["Component", "Graph", "expand_graph", "get_edgemap", "find_descendants",
           "combinegraphs", "makeemptygraph", "add_element", "empty_graph", "split_node",
           "split_production", "simplify_graph", "redundantinds", "subtreeattach"]


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


def add_element(g, compind, c, element, ps):
    """``add_element.m:1-19``: put object ``element`` (0-based) into cluster node ``c``
    (0-based) of component ``compind`` (0-based), then ``combinegraphs(..., zonly=1)``.

    ``compind < 0`` (MATLAB ``-1``, a split of the combined graph) sets every component's
    ``z`` from row ``c`` of ``g.compinds``. ``g.z[element]`` is set to ``0`` (MATLAB ``1``:
    "observed"; combinegraphs overwrites it) and ``objcount`` goes up by one. Returns a new
    :class:`Graph`.
    """
    g = g.copy()
    if compind < 0:
        for j in range(int(g.ncomp)):
            g.components[j].z[element] = g.compinds[c, j]
    else:
        g.components[compind].z[element] = c
    g.z[element] = 0
    g.objcount = g.objcount + 1
    # XXX: inefficient
    return combinegraphs(g, ps, zonly=1)


def empty_graph(graph, compind, c1, c2):
    """``empty_graph.m:1-18``: remove every member of cluster nodes ``c1``/``c2`` (0-based)
    of component ``compind`` (0-based; ``< 0`` uses the combined ``graph.z``).

    The members get ``z = -1`` (missing) and ``objcount`` drops by their number; component
    ``z`` is untouched. Replicated quirk: the rows/columns removed from ``graph.adj`` and
    ``graph.W`` are the members' *object indices*, which are the right rows only when no
    object was already missing (always the case in ``best_split.m:26``, the only caller).
    Returns a new :class:`Graph`.
    """
    graph = graph.copy()
    if compind < 0:
        z = np.asarray(graph.z)
    else:
        z = np.asarray(graph.components[compind].z)
    removeind = np.flatnonzero((z == c1) | (z == c2))
    graph.z = np.asarray(graph.z).copy()
    graph.z[removeind] = -1
    includeind = setdiff(np.arange(graph.adj.shape[0]), removeind).astype(np.int64)
    ix = np.ix_(includeind, includeind)
    graph.adj = graph.adj[ix]
    graph.W = graph.W[ix]
    graph.objcount = graph.objcount - len(removeind)
    return graph


# split_node.m:9-57: production names by pind
_PIND1 = {**dict.fromkeys(('dirchain', 'order', 'dirchainnoself', 'ordernoself',
                           'undirchain', 'undirchainnoself'), 'chain'),
          **dict.fromkeys(('dirring', 'dirringnoself', 'undirring', 'undirringnoself'), 'ring'),
          **dict.fromkeys(('dirhierarchy', 'domtree', 'dirhierarchynoself', 'undirhierarchy',
                           'undirhierarchynoself', 'dirdomtreenoself', 'undirdomtree',
                           'undirdomtreenoself'), 'hierarchy'),
          'partitionnoself': 'partition', 'connectednoself': 'connected'}
_PIND2_CHAIN = ('hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself', 'ordernoself',
                'undirhierarchy', 'undirhierarchynoself', 'dirdomtreenoself', 'undirdomtree',
                'undirdomtreenoself')
_PIND3 = ('hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself', 'undirhierarchy',
          'undirhierarchynoself', 'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself')


def split_production(graph, compind, c, pind):
    """``split_node.m:9-57``: the production name used to split node ``c`` (0-based) of
    component ``compind`` (0-based) with production ``pind`` (1, 2 or 3; a production
    *number*, not an index), or ``None`` where MATLAB returns ``-inf`` (the production does
    not apply: pind 2 on a one-node hierarchy or a tree with at most 3 nodes, pind 3 on a
    hierarchy node without parents)."""
    comp = graph.components[compind]
    structname = comp.type
    if pind == 1:
        structname = _PIND1.get(structname, structname)
    if pind == 2:
        if structname in _PIND2_CHAIN:
            structname = 'chain'
            if comp.nodecount == 1:  # all productions the same for a one node graph
                return None
            if np.sum(comp.adj[:, c]) == 0 and np.sum(comp.adj[c, :]) >= 2:
                structname = 'rootchain'
        elif structname == 'tree':
            structname = 'treever2'
            if comp.nodecount <= 3:  # all productions the same
                return None
    if pind == 3:
        if structname in _PIND3:
            structname = 'domtreeflat'
            if np.sum(comp.adj[:, c]) == 0:  # c has no parents
                return None
    return structname


def split_node(graph, compind, c, pind, part1, part2, ps):
    """``split_node.m:1-191``: split cluster node ``c`` of component ``compind`` with
    production ``pind`` and put objects ``part1``/``part2`` in the two children.

    Indices are 0-based (``compind``, ``c``, ``part1``, ``part2``, the returned ``c1``,
    ``c2``); ``pind`` is MATLAB's production number 1-3 (:func:`split_production`).
    Returns ``(graph, c1, c2)``, or ``(None, None, None)`` where MATLAB returns
    ``-inf, -inf, -inf`` (the production does not apply). The component gets the new
    ``adj`` (0/1 float), ``W``, ``Wsym``, ``adjsym``, counts, ``z`` and ``illegal``, and
    the graph is recombined with ``combinegraphs(..., origgraph=, compind=, imap=)``.
    ``disp(structname)`` is dropped. An unknown production raises
    :class:`FormDiscoveryError` (MATLAB ``error('Unknown structure')``).

    Replicated quirks (``KNOWN_ISSUES.md`` KI-17): old edges are marked ``1..nold`` in
    column-major order, the markers are copied with the row/column of ``c``, and the old
    weights go to the first ``nold`` positions of a stable sort of the markers. Where the
    copies leave a marker twice (``connected``, ``domtreeflat``: the new node keeps the
    parents of ``c``) or ``treever2`` deletes one, later weights shift by one and the left
    over positions keep their marker value (or the median weight, if an ``inf``) as weight.
    """
    comp = graph.components[compind]
    structname = split_production(graph, compind, c, pind)
    if structname is None:
        return None, None, None
    origgraph = graph
    graph = graph.copy()
    comp = graph.components[compind]

    ntot = int(comp.nodecount)
    origadj = np.atleast_2d(np.asarray(comp.adj, dtype=float)).copy()
    origW = np.atleast_2d(np.asarray(comp.W, dtype=float))
    # make markers for original edges
    origind = find_F(origadj)
    nold = len(origind)
    oa = origadj.ravel(order="F")
    oa[origind] = np.arange(1, nold + 1)
    origadj = oa.reshape(origadj.shape, order="F")
    newinternal = np.empty(0, dtype=np.int64)

    if structname in ('partition', 'chain', 'ring', 'hierarchy', 'domtreeflat',
                      'connected', 'rootchain'):
        newadj = np.zeros((ntot + 1, ntot + 1))
        minusnew = setdiff(np.arange(ntot + 1), [c + 1]).astype(np.int64)
        newadj[np.ix_(minusnew, minusnew)] = origadj
        # give the new node all the connections of the previous nodes
        newadj[c + 1, :] = newadj[c, :]
        newadj[:, c + 1] = newadj[:, c]
        # c, c+1 are the new clusters
        c1, c2 = c, c + 1
        newnodes = [c1, c2]
        oldps = np.flatnonzero(newadj[:, c])
        oldchild = np.flatnonzero(newadj[c, :])
        if structname == 'connected':
            newadj[c, c + 1] = np.inf
        elif structname in ('chain', 'ring'):
            newadj[c, c + 1] = np.inf
            newadj[c + 1, c] = 0
            newadj[oldps, c + 1] = 0
            newadj[c, oldchild] = 0
            if structname == 'ring' and len(oldps) == 0 and len(oldchild) == 0:
                newadj[c + 1, c] = np.inf
        elif structname == 'hierarchy':
            newadj[c, c + 1] = np.inf
            newadj[c + 1, c] = 0
            newadj[oldps, c + 1] = 0
            newadj[c + 1, oldchild] = 0
        elif structname == 'domtreeflat':
            newadj[c, c + 1] = 0
            newadj[c + 1, c] = 0
            newadj[c + 1, oldchild] = 0
        elif structname == 'rootchain':
            newadj[c, c + 1] = np.inf
            newadj[c + 1, c] = 0
            newadj[c + 1, oldchild[0]] = 0
            newadj[c, oldchild[1:]] = 0
    elif structname == 'tree':
        newadj = np.zeros((ntot + 2, ntot + 2))
        minusnew = setdiff(np.arange(ntot + 2), [c + 1, c + 2]).astype(np.int64)
        newadj[np.ix_(minusnew, minusnew)] = origadj
        # c+1, c+2 new leaf nodes
        c1, c2 = c + 1, c + 2
        newnodes = [c, c1, c2]
        newadj[c + 1, c] = 0
        newadj[c, c + 1] = np.inf
        newadj[c + 2, c] = 0
        newadj[c, c + 2] = np.inf
        newinternal = np.array([c], dtype=np.int64)
    elif structname == 'treever2':
        newadj = np.zeros((ntot + 2, ntot + 2))
        cpar = np.flatnonzero(origadj[:, c])
        # find(origadj(cpar,:)): linear indices, = column indices for one parent
        csibs = find_F(origadj[cpar, :])
        csib = csibs[csibs != c]
        origadj[np.ix_(cpar, csib)] = 0
        minusnew = setdiff(np.arange(ntot + 2), [c + 1, c + 2]).astype(np.int64)
        newadj[np.ix_(minusnew, minusnew)] = origadj
        # c+1, c+2 new leaf nodes
        c1, c2 = c + 1, c + 2
        newnodes = [c, c1, c2]
        newadj[c, c + 2] = np.inf
        newadj[c, minusnew[csib]] = np.inf
        newadj[minusnew[cpar], c + 1] = np.inf
        newinternal = np.array([c], dtype=np.int64)
    else:
        raise FormDiscoveryError("Unknown structure")

    n = newadj.shape[0]
    newind = find_F(newadj)
    sind = stable_argsort(newadj.ravel(order="F")[newind])
    newW = newadj.copy()

    # replace markers with weights
    if nold > 0:
        newW[np.isinf(newW)] = median_matlab(origW.ravel(order="F")[origind])
        nw = newW.ravel(order="F")
        nw[newind[sind[:nold]]] = origW.ravel(order="F")[origind]
        newW = nw.reshape(newW.shape, order="F")
    else:
        newW[np.isinf(newW)] = 1

    newadj[newadj > 0] = 1

    # map[i]: what node i in old graph is now labelled
    # imap[j]: what node j in new graph corresponds to
    brandnew = setdiff(newnodes, [c]).astype(np.int64)
    oldind = setdiff(np.arange(n), brandnew).astype(np.int64)
    map_ = np.zeros(n, dtype=np.int64)
    map_[:len(oldind)] = oldind
    imap = np.zeros(n, dtype=np.int64)
    imap[oldind] = np.arange(len(oldind))
    imap[brandnew] = c

    newz = map_[np.asarray(comp.z, dtype=np.int64)]
    illegal = np.asarray(comp.illegal if comp.illegal is not None else [],
                         dtype=np.int64).ravel()
    comp.illegal = np.concatenate([map_[illegal], newinternal]).astype(np.int64)

    comp.adj = newadj
    comp.W = newW
    both = (newadj != 0) & (newadj.T != 0)
    doubleW = np.zeros(newW.shape)
    doubleW[both] = newW[both]
    comp.Wsym = newW + newW.T - doubleW
    comp.adjsym = newadj + newadj.T - both
    comp.nodecount = n
    comp.edgecount = int(np.sum(newadj))
    ecs = np.sum(comp.adjsym) / 2
    comp.edgecountsym = int(ecs) if ecs == int(ecs) else float(ecs)

    # new cluster nodes appear in order at the end of newnodes
    newz[np.asarray(part1, dtype=np.int64)] = newnodes[-2]
    newz[np.asarray(part2, dtype=np.int64)] = newnodes[-1]
    comp.z = newz

    graph = combinegraphs(graph, ps, origgraph=origgraph, compind=compind, imap=imap)
    return graph, c1, c2


def _sym_count(adjsym):
    """``sum(sum(adjsym))/2`` as an ``int`` when it is whole (a self-loop counts half)."""
    ecs = np.sum(adjsym) / 2
    return int(ecs) if ecs == int(ecs) else float(ecs)


def simplify_graph(graph, ps):
    """``simplify_graph.m:1-60``: remove unnecessary cluster nodes from every component.

    For each component, :func:`redundantinds` cases 1-3 are applied in turn until one full
    pass removes nothing (l.22-40): case 1 drops dangling unoccupied nodes, case 2 an
    unoccupied node with two neighbours (joining them), case 3 merges split singleton pairs
    (trees) or moves a lone object up/down to its only neighbour (other single-component
    feature graphs). A changed component gets the new ``adj``, ``W``, ``adjsym`` (bool),
    ``Wsym``, ``z``, counts and ``illegal`` (removed nodes dropped), and the graph is
    recombined with ``combinegraphs(..., origgraph=<input graph>, compind=i, imap=)``,
    where ``imap`` maps the kept nodes to their original numbers. Every component uses the
    *input* graph as ``origgraph``, also after an earlier component was changed
    (l.14, 54). The trailing ``if graph.objcount < 30 return`` (l.59) does nothing.
    Returns a new :class:`Graph`.
    """
    origgraph = graph
    graph = graph.copy()
    overallchange = False
    for i in range(int(graph.ncomp)):
        comp = graph.components[i]
        adj = np.atleast_2d(np.asarray(comp.adj, dtype=float)).copy()
        W = np.atleast_2d(np.asarray(comp.W, dtype=float)).copy()
        imap = np.arange(adj.shape[0], dtype=np.int64)
        z = np.asarray(comp.z, dtype=np.int64).ravel().copy()
        illegal = np.asarray(comp.illegal if comp.illegal is not None else [],
                             dtype=np.int64).ravel()
        cont = [1, 1, 1]
        while sum(cont):
            for caseind in (1, 2, 3):
                ntot = adj.shape[0]
                occ = np.zeros(ntot)
                occ[z] = 1
                adj, W, z, includeind = redundantinds(caseind, graph, i, adj, W, z, occ, ps)
                if len(includeind) == ntot:
                    cont[caseind - 1] = 0
                else:
                    cont[caseind - 1] = 1
                    overallchange = True
                    map_ = np.full(ntot, -1, dtype=np.int64)
                    map_[includeind] = np.arange(len(includeind))
                    z = map_[z]
                    illegal = map_[illegal]
                    illegal = illegal[illegal >= 0]
                    imap = imap[includeind]

        if overallchange:
            adjsym = (adj != 0) | (adj.T != 0)
            comp.adj = adj
            comp.W = W
            comp.adjsym = adjsym
            Wsym = W.copy()
            mask = adj.T != 0
            Wsym[mask] = W.T[mask]
            comp.Wsym = Wsym
            comp.z = z
            comp.edgecount = int(np.sum(adj))
            comp.edgecountsym = _sym_count(adjsym)
            comp.illegal = illegal
            comp.nodecount = adj.shape[0]
            graph = combinegraphs(graph, ps, origgraph=origgraph, compind=i, imap=imap)
            overallchange = False
    return graph


def redundantinds(caseind, graph, i, adj, W, z, occ, ps):
    """``simplify_graph.m:62-148`` (subfunction): one cleaning case on component ``i``.

    ``adj``/``W`` are the component's current matrices, ``z`` its current 0-based node of
    each object and ``occ`` the 0/1 occupancy of each node. Returns
    ``(adj, W, z, includeind)`` with the removed node's rows/columns already dropped and
    ``includeind`` the kept (old, 0-based) nodes in order; ``len(includeind) == len(adj)``
    before the call means nothing changed. The inputs are not modified.

    - Case 1: every unoccupied node with at most one neighbour.
    - Case 2: the first unoccupied node with exactly two neighbours (for a ``tree``
      without ``ps.cleanstrong``, only if it also has one parent, so the root stays).
      Its neighbours are joined by an edge from the parent-side one (both neighbours
      children: first to second) of weight ``1/sum(1./w)`` over the positive weights of
      the four possible edges between it and them (``inf`` if there are none). A 2-node
      cycle or self-loop (both neighbours the same node) just drops the node.
    - Case 3, ``tree``: unless a ``ps.fixed*`` flag is set, the first node with exactly
      two singleton neighbours has them merged into the lower-numbered one.
    - Case 3, other types (feature data, one component): the first occupied node holding
      one object, with one parent and no children (else one child and no parents), gives
      its object to that neighbour and is removed.
    """
    adj = adj.copy()
    W = W.copy()
    z = z.copy()
    n = adj.shape[0]
    colsum = adj.sum(axis=0)
    rowsum = adj.sum(axis=1)
    ctype = graph.components[i].type
    removeind = np.empty(0, dtype=np.int64)
    if caseind == 1:
        # dangling cluster nodes: unoccupied, zero or one cluster neighbour
        removeind = np.flatnonzero((colsum + rowsum <= 1) & (occ == 0))
    elif caseind == 2:
        # unoccupied node with exactly two neighbours (keep the root of a tree)
        if ctype == 'tree' and not ps.cleanstrong:
            cand = np.flatnonzero((colsum + rowsum == 2) & (colsum == 1) & (occ == 0))
        else:
            cand = np.flatnonzero((colsum + rowsum == 2) & (occ == 0))
        if len(cand) == 0:
            return adj, W, z, np.arange(n, dtype=np.int64)
        r = int(cand[0])
        removeind = np.array([r])
        nbs = np.concatenate([np.flatnonzero(adj[:, r]), np.flatnonzero(adj[r, :])])
        if adj[nbs[1], r]:  # nbs(2) is a parent
            nbs = nbs[::-1]
        if nbs[0] != nbs[1]:  # special case when we simplify a 2 cluster ring
            adj[nbs[0], nbs[1]] = 1
            oldWs = W[[nbs[0], nbs[1], r, r], [r, r, nbs[0], nbs[1]]]
            oldWs = oldWs[oldWs > 0]
            with np.errstate(divide='ignore'):
                W[nbs[0], nbs[1]] = 1 / np.sum(1 / oldWs)
    else:
        if ctype == 'tree':
            if not (ps.fixedall or ps.fixedinternal or ps.fixedexternal):
                # join pairs that have been split
                zcnts = hist_centres(z + 1, np.arange(1, n + 1))
                singletons = np.flatnonzero(zcnts == 1)
                cnt = adj[singletons, :].sum(axis=0) + adj[:, singletons].sum(axis=1)
                twosingleneighbors = np.flatnonzero(cnt == 2)
                if len(twosingleneighbors):
                    parent = twosingleneighbors[0]
                    children = intersect(
                        singletons, np.flatnonzero((adj[parent, :] != 0) | (adj[:, parent] != 0)))
                    if len(children) < 2:
                        raise FormDiscoveryError(
                            "simplify_graph: index (2): out of bound (children, l.117)")
                    z[z == children[1]] = children[0]
                    removeind = np.array([children[1]])
        elif ps.runps.type != 'rel' and int(graph.ncomp) == 1:
            zcnts = hist_centres(z + 1, np.arange(1, n + 1))
            # occupied node with one cluster parent and no cluster children
            removeindpar = np.flatnonzero((colsum == 1) & (rowsum == 0) & (zcnts == 1))
            # occupied node with one cluster child and no cluster parents
            removeindch = np.flatnonzero((rowsum == 1) & (colsum == 0) & (zcnts == 1))
            if len(removeindpar) == 0 and len(removeindch) == 0:
                return adj, W, z, np.arange(n, dtype=np.int64)
            if len(removeindpar):
                r = removeindpar[0]
                newz = np.flatnonzero(adj[:, r])
            else:
                r = removeindch[0]
                newz = np.flatnonzero(adj[r, :])
            z[z == r] = newz[0]
            removeind = np.array([r])

    includeind = np.asarray(mysetdiff(np.arange(n), removeind), dtype=np.int64)
    ix = np.ix_(includeind, includeind)
    return adj[ix], W[ix], z, includeind


_SUBTREE_HIER = ('hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself',
                 'domtreenoself', 'undirhierarchy', 'undirhierarchynoself',
                 'undirdomtree', 'undirdomtreenoself')


def subtreeattach(graph, j, edgep, edgec, comp, ps, objflag=0):
    """``subtreeattach.m:1-82``: regraft node ``j`` (or object ``j`` if ``objflag``) in
    component ``comp`` (all 0-based), as ``spr.m:28`` does.

    ``tree``: a new internal node ``n`` (the old node count) is put on the edge
    ``edgep -> edgec``, both halves getting twice the old weight, and is added to
    ``illegal``. With ``objflag`` 0 the subtree rooted at ``j`` moves from its parent to
    the new node (keeping its edge weight); with ``objflag`` 1 object ``j`` moves to a new
    leaf ``n + 1`` under it, with twice its leaf length (``leaflengths[j]`` is doubled).
    Hierarchy family (``edgec`` is ignored): with ``objflag`` 0 node ``j`` moves from its
    parent to ``edgep``; with ``objflag`` 1 object ``j`` moves to a new leaf ``n`` under
    ``edgep``. ``adjsym``/``Wsym`` are rebuilt; ``edgecount``/``edgecountsym`` are left
    stale, as in MATLAB. The graph is recombined with ``imap`` sending each new node to the
    first node adjacent to neither ``edgep`` nor ``edgec`` in the old ``adj`` (node 0 if
    there is none, l.76-78).

    With ``objflag`` 0 and ``j`` parentless the input is returned unchanged (a copy), before
    the type check. Any other type (e.g. ``dirdomtreenoself``, missing from MATLAB's list)
    raises :class:`FormDiscoveryError` ('unexpected structure'), and so does a ``j`` with
    several parents (MATLAB: nonconformant assignment).
    """
    origgraph = graph
    c = graph.components[comp]
    adj = np.atleast_2d(np.asarray(c.adj, dtype=float))
    W = np.atleast_2d(np.asarray(c.W, dtype=float))
    n = adj.shape[0]
    oldp = None
    if objflag == 0:
        oldp = np.flatnonzero(adj[:, j])
        if len(oldp) == 0:  # j is a cluster node with no parent
            return graph.copy()

    def _single_parent():
        if len(oldp) != 1:
            raise FormDiscoveryError(
                f"subtreeattach: node {j} has {len(oldp)} parents (MATLAB: =: nonconformant)")
        return int(oldp[0])

    graph = graph.copy()
    c = graph.components[comp]
    if c.type == 'tree':
        size = n + 2 if objflag else n + 1
    elif c.type in _SUBTREE_HIER:
        size = n + 1 if objflag else n
    else:
        raise FormDiscoveryError("unexpected structure")
    newadj = np.zeros((size, size))
    newadj[:n, :n] = adj
    newW = np.zeros((size, size))
    newW[:n, :n] = W
    leaflengths = np.asarray(graph.leaflengths, dtype=float).ravel().copy()

    if c.type == 'tree':
        # attach subtree rooted at j to edge between edgep and edgec
        newweight = 2 * W[edgep, edgec]
        newp = n
        newadj[edgep, newp] = 1
        newadj[newp, edgec] = 1
        newadj[edgep, edgec] = 0
        newW[edgep, newp] = newweight
        newW[newp, edgec] = newweight
        newW[edgep, edgec] = 0
        illegal = np.asarray(c.illegal if c.illegal is not None else [],
                             dtype=np.int64).ravel()
        c.illegal = np.concatenate([illegal, [newp]]).astype(np.int64)
        if objflag:
            newpc = n + 1
            newadj[newp, newpc] = 1
            newW[newp, newpc] = 2 * leaflengths[j]
            newadj[newpc, :] = 0
            newW[newpc, :] = 0
            leaflengths[j] = 2 * leaflengths[j]
            c.z = np.asarray(c.z, dtype=np.int64).copy()
            c.z[j] = newpc
            c.nodecount = c.nodecount + 2
        else:
            p = _single_parent()
            newadj[newp, j] = 1
            newW[newp, j] = W[p, j]
            newadj[p, j] = 0
            newW[p, j] = 0
            c.nodecount = c.nodecount + 1
    else:
        if objflag:  # attach object j to edgep
            newp = n
            newadj[edgep, newp] = 1
            newadj[newp, :] = 0
            newW[edgep, newp] = 2 * leaflengths[j]
            newW[newp, :] = 0
            leaflengths[j] = 2 * leaflengths[j]
            c.z = np.asarray(c.z, dtype=np.int64).copy()
            c.z[j] = newp
            c.nodecount = c.nodecount + 1
        else:  # attach subtree rooted at j to edgep
            p = _single_parent()
            newadj[oldp, j] = 0
            newW[oldp, j] = 0
            newadj[edgep, j] = 1
            newW[edgep, j] = W[p, j]
    graph.leaflengths = leaflengths

    both = (newadj != 0) & (newadj.T != 0)
    c.adj = newadj
    c.W = newW
    c.adjsym = newadj + newadj.T - both
    c.Wsym = newW + newW.T - newW * both

    # make sure new node doesn't map to a neighbour of edgep or edgec
    empties = np.concatenate([np.flatnonzero((adj[edgep, :] == 0) & (adj[edgec, :] == 0)),
                              [0, 0, 0]]).astype(np.int64)
    imap = np.concatenate([np.arange(n), empties[:size - n]]).astype(np.int64)
    return combinegraphs(graph, ps, origgraph=origgraph, compind=comp, imap=imap)
