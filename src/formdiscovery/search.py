"""Search heuristics (PLAN.md §5). Part a (item 23, L4-a): ``addnearmiss``,
``choose_seedpairs``, ``best_split`` and ``choose_node_split``. Part b1 (item 24, L4-b1):
``swapobjclust`` and its subfunctions ``chooseswaps``, ``doswap``, ``sourceobjs``,
``sourcecls`` and ``cltypes``. Part b2 (item 25, L4-b2): ``spr`` (with ``makerp`` and
``makers``) and ``collapsedims`` (with ``getocc``, ``get_occnodescomp`` and ``zassign``).

Randomness enters through ``randperm`` at ``choose_seedpairs.m:24``,
``best_split.m:35``, ``swapobjclust.m:33``, ``spr.m:57/59`` and ``collapsedims.m:35``. The ports take ``rng=None`` and draw with
``as_provider(rng).randperm(n)`` exactly as often, and in the same order, as the MATLAB
code (``rng.py``, item 22).

Pinned by ``tests/octave/fx_search.m`` → ``tests/fixtures/search.mat``
(``tests/test_search.py``) and ``tests/octave/fx_swap.m`` → ``tests/fixtures/swap.mat``
(``tests/test_swap.py``) and ``tests/octave/fx_spr.m`` → ``tests/fixtures/spr.mat``
(``tests/test_spr.py``), which replay Octave's recorded draws.
"""

import numpy as np

from . import FormDiscoveryError, likelihood
from .graph import (add_element, combinegraphs, empty_graph, find_descendants, simplify_graph,
                    split_node, subtreeattach)
from .matlab_compat import intersect, max_first, setdiff, stable_argsort, unique_matlab
from .util import dijkstra
from .params import graph_prior
from .rng import as_provider

__all__ = ["addnearmiss", "choose_seedpairs", "best_split", "choose_node_split",
           "swapobjclust", "chooseswaps", "doswap", "sourceobjs", "sourcecls", "cltypes",
           "spr", "makerp", "makers", "collapsedims", "getocc", "get_occnodescomp", "zassign"]

_EMPTY = np.empty(0, dtype=np.int64)


def addnearmiss(nearmscores, nearmgraphs, graph, score, currgraph, currscore, epsilon):
    """``addnearmiss.m:1-16``: insert ``graph``/``score`` into the near-miss list.

    ``nearmscores`` is sorted in descending order and ``nearmgraphs`` (a list, MATLAB's
    cell) holds the matching graphs. If ``|currscore - score| < epsilon`` the lists are
    returned unchanged (l.6-8). Otherwise ``graph`` goes in at the first position whose
    score is ``< score`` (l.11) and the last entry drops out (l.12-15). Returns new
    ``(nearmscores, nearmgraphs)``; the inputs are not modified. ``currgraph`` is unused,
    as in MATLAB.

    MATLAB fails at ``lower(1)`` when no stored score is below ``score``; the port
    raises :class:`FormDiscoveryError`. The callers (``swapobjclust.m:51``, ``spr.m:43``,
    ``collapsedims.m:52``) only call it when ``score > nearmscores(end)``.
    """
    scores = np.asarray(nearmscores, dtype=float).ravel()
    graphs = list(nearmgraphs)
    if abs(currscore - score) < epsilon:
        return scores.copy(), graphs
    if len(graphs) != scores.size:
        raise FormDiscoveryError("addnearmiss: nearmscores and nearmgraphs differ in length")
    lower = np.flatnonzero(scores < score)
    if lower.size == 0:
        raise FormDiscoveryError("addnearmiss: lower(1): out of bound; no score below "
                                 "the new one")
    l = int(lower[0])
    scores = np.concatenate([scores[:l], [score], scores[l:-1]])
    graphs = graphs[:l] + [graph] + graphs[l:-1]
    return scores, graphs


def choose_seedpairs(graph, compind, c, pind, ps, rng=None):
    """``choose_seedpairs.m:1-52``: pairs of objects that seed the two children when
    cluster node ``c`` of component ``compind`` is split with production ``pind``.

    Indices are 0-based; ``compind < 0`` is MATLAB's ``-1`` (a split of the combined
    graph, where ``c`` is a combined cluster). Returns an ``(k, 2)`` int64 array of
    object indices.

    - At most 5 members (l.18-19): every pair, ``nchoosek`` order.
    - More (l.20-35, pc = 1): each member is paired with a random other object of its
      *combined* cluster (``graph.z``, also when ``compind >= 0``), one
      ``randperm`` per member (drawn even when there is no other object). If there is
      none, it is paired with the first other member of ``c``.
    - The reversed pairs are appended (l.37-51) for a high-level split, and for a
      component whose ``adj`` has more than one row, except for ``ps.runps.structname``
      ``'partition'`` (never) and ``'tree'`` (only with ``pind == 2``).

    Deviation: with fewer than two members MATLAB's ``nchoosek`` returns a count (one
    member) or fails (none); the port raises :class:`FormDiscoveryError`
    (``KNOWN_ISSUES.md`` KI-25). ``choose_node_split`` never calls it with one member.
    """
    rng = as_provider(rng)
    pc = 1
    z = np.asarray(graph.z).ravel()
    if compind < 0:  # high level split
        partmembers = np.flatnonzero(z == c)
    else:
        partmembers = np.flatnonzero(np.asarray(graph.components[compind].z).ravel() == c)
    if partmembers.size < 2:
        raise FormDiscoveryError(
            f"choose_seedpairs: node has {partmembers.size} member(s), need 2 (KI-25)")

    if partmembers.size <= 5:  # consider all possible seedsplits
        i, j = np.triu_indices(partmembers.size, 1)
        seedpairs = np.column_stack([partmembers[i], partmembers[j]])
    else:
        pair2 = np.zeros((partmembers.size, pc), dtype=np.int64)
        for i, m in enumerate(partmembers):
            clustmembers = np.flatnonzero(z == z[m])
            clustmembers = clustmembers[clustmembers != m]
            clustmembers = clustmembers[rng.randperm(clustmembers.size)]
            if clustmembers.size == 0:
                clustmembers = partmembers[partmembers != m]
            if clustmembers.size < pc:
                clustmembers = np.tile(clustmembers, pc)
            pair2[i, :] = clustmembers[:pc]
        pair1 = np.tile(partmembers, pc)
        seedpairs = np.column_stack([pair1, pair2.ravel(order="F")])
    seedpairs = seedpairs.astype(np.int64)

    if compind < 0:  # high level split
        flip = True
    else:
        nrows = np.atleast_2d(graph.components[compind].adj).shape[0]
        structname = ps.runps.structname
        if structname == "partition":  # children are symmetric
            flip = False
        elif structname == "tree":
            flip = pind == 2 and nrows > 1
        else:  # unless this is first split
            flip = nrows > 1
    if flip:
        seedpairs = np.vstack([seedpairs, seedpairs[:, ::-1]])
    return seedpairs


def _mask(data, membout, ps):
    """``best_split.m:38-42,56-62``: hide the objects not yet placed. Feature and
    similarity data get ``inf`` rows. For relational data MATLAB writes ``inf`` into new
    fields ``d.ys``/``d.ns`` that ``graph_like_rel`` never reads (and the first call
    does not mask at all), so the data go unchanged (``KNOWN_ISSUES.md`` KI-23)."""
    if ps.runps.type == "rel":
        return data
    d = np.array(data, dtype=float)
    d[membout, :] = np.inf
    return d


def best_split(graph, compind, c, pind, data, seedpairs, ps, rng=None, info=None):
    """``best_split.m:1-165``: the best split of cluster node ``c`` found by growing the
    two children greedily from each seed pair.

    Indices are 0-based (``compind``, ``c``, ``seedpairs``, the returned parts). For
    ``compind >= 0``, ``pind`` is the production number (1-3) and the node is split with
    ``split_node``. For ``compind < 0`` (``structurefit.m:60``) the split moves members
    of combined cluster ``c`` into the vacant neighbour cluster, and ``pind`` is that
    neighbour's 0-based node index. Returns ``(ll, part1, part2, newgraph)``, or
    ``(-inf, [], [], None)`` when the production does not apply (l.23-25).

    For each seed pair (l.28-102): add the seeds, draw one ``randperm`` over the other
    members, and score the partial graph on data with the unplaced objects' rows set to
    ``inf``. Then each unplaced object joins whichever child scores higher
    (``graph_like + graph_prior``; ties go to ``c1``). The candidates are then visited
    best first (a stable descending sort); any whose members all end up in one cluster
    after ``simplify_graph`` with ``cleanstrong = 1`` is set to ``-inf``, up to the first
    that does not (l.105-116).

    ``ps.speed > 1`` sets ``ps.fast = 1`` (l.10). Speeds 4 and 5 return the best
    candidate as it is. Speed 3 rescores it in slow mode (``graph_like`` on the last
    masked data, which equals ``data``). Other speeds match no ``case`` in MATLAB
    (``case{'1,2'}`` is a string) and the run crashes; the port raises
    :class:`FormDiscoveryError` (``KNOWN_ISSUES.md`` KI-1). If the chosen candidate was
    set to ``-inf``, ``ll = -inf`` (l.141).

    ``part1``/``part2`` are the members of ``c1``/``c2`` in the new graph's component,
    but for a high-level split they come from the *input* ``graph.z`` (l.142-145), so
    they are all of ``c``'s members and ``[]`` (``KNOWN_ISSUES.md`` KI-24). The
    ``disp(i)`` progress output and the ``ps.showbestsplit`` figure are dropped.

    If ``info`` is a dict it receives the candidates: ``gs`` (graphs), ``ls0`` (scores
    before the ``simplify_graph`` pass), ``ls`` (after it), ``mind`` (the chosen one) and
    the child nodes ``c1``/``c2``.
    """
    rng = as_provider(rng)
    if ps.speed > 1:
        ps = ps.replace(fast=1)
    seedpairs = np.atleast_2d(np.asarray(seedpairs, dtype=np.int64))

    if compind < 0:
        partmembers = np.flatnonzero(np.asarray(graph.z).ravel() == c)
        c1, c2 = c, pind
        e_graph = graph
    else:
        partmembers = np.flatnonzero(np.asarray(graph.components[compind].z).ravel() == c)
        e_graph, c1, c2 = split_node(graph, compind, c, pind, partmembers[0:1],
                                     partmembers[1:], ps)
    if c1 is None:  # if we can't apply the current production
        return -np.inf, _EMPTY.copy(), _EMPTY.copy(), None
    e_graph = empty_graph(e_graph, compind, c1, c2)
    if seedpairs.shape[0] == 0 or seedpairs.size == 0:
        raise FormDiscoveryError("best_split: no seed pairs")

    gs, ls = [], []
    d = data
    for i in range(seedpairs.shape[0]):
        g = add_element(e_graph, compind, c1, int(seedpairs[i, 0]), ps)
        g = add_element(g, compind, c2, int(seedpairs[i, 1]), ps)

        membout = setdiff(partmembers, seedpairs[i, :]).astype(np.int64)
        membout = membout[rng.randperm(membout.size)]

        d = data if ps.runps.type == "rel" else _mask(data, membout, ps)
        l, g = likelihood.graph_like(d, g, ps)
        l = l + graph_prior(g, ps)

        # go through the remaining cluster members, greedily choosing which child
        # node to put them in
        while membout.size:
            newobj = int(membout[0])
            membout = membout[1:]
            g1 = add_element(g, compind, c1, newobj, ps)
            g2 = add_element(g, compind, c2, newobj, ps)
            d = _mask(data, membout, ps)
            g1l, g1new = likelihood.graph_like(d, g1, ps)
            g1l = g1l + graph_prior(g1, ps)
            g2l, g2new = likelihood.graph_like(d, g2, ps)
            g2l = g2l + graph_prior(g2, ps)
            l, choice = max_first([g1l, g2l])
            g = g1new if choice == 0 else g2new
        gs.append(g)
        ls.append(l)
    ls = np.array(ls, dtype=float)
    ls0 = ls.copy()

    # chain splits: sometimes splitting the cluster at the end of a chain makes
    # no real difference. Try not to choose splits like these
    sind = stable_argsort(ls, descending=True)
    psclean = ps.replace(cleanstrong=1)
    for ind in sind:
        gsimp = simplify_graph(gs[ind], psclean)
        if unique_matlab(np.asarray(gsimp.z)[partmembers])[0].size == 1:
            ls[ind] = -np.inf
        else:
            break

    if ps.speed == 3:  # optimize once per split
        ll, mind = max_first(ls)
        gl, gnew = likelihood.graph_like(d, gs[mind], ps.replace(fast=0))
        ll = gl + graph_prior(gnew, ps)
        newgraph = gnew
    elif ps.speed in (4, 5):  # optimize about once per depth
        ll, mind = max_first(ls)
        newgraph = gs[mind]
    else:
        raise FormDiscoveryError(
            f"best_split: ps.speed = {ps.speed} matches no case (KI-1)")

    if info is not None:
        info.update(gs=gs, ls0=ls0, ls=ls, mind=mind, c1=c1, c2=c2)
    if ls[mind] == -np.inf:
        ll = -np.inf
    if compind < 0:
        z = np.asarray(graph.z).ravel()
    else:
        z = np.asarray(newgraph.components[compind].z).ravel()
    part1 = np.flatnonzero(z == c1)
    part2 = np.flatnonzero(z == c2)
    return ll, part1, part2, newgraph


def choose_node_split(graph, compind, splitind, pind, data, ps, rng=None, info=None):
    """``choose_node_split.m:1-23``: split node ``splitind`` of component ``compind``
    with production ``pind`` (see :func:`best_split` for ``compind < 0``).

    Indices are 0-based. A node with one member cannot be split:
    ``(-inf, [splitind], [], None)`` (MATLAB returns the node index as ``part1``, l.13).
    Otherwise :func:`choose_seedpairs` then :func:`best_split`, sharing one permutation
    provider. A NaN score raises :class:`FormDiscoveryError` (MATLAB's ``keyboard``,
    patched to ``error``). The ``disp`` lines are dropped. ``info`` is passed to
    :func:`best_split`.
    """
    rng = as_provider(rng)
    if compind < 0:
        partmembers = np.flatnonzero(np.asarray(graph.z).ravel() == splitind)
    else:
        partmembers = np.flatnonzero(
            np.asarray(graph.components[compind].z).ravel() == splitind)

    if partmembers.size == 1:
        ll, part1, part2, newgraph = -np.inf, np.array([splitind], dtype=np.int64), \
            _EMPTY.copy(), None
    else:
        seedpairs = choose_seedpairs(graph, compind, splitind, pind, ps, rng=rng)
        ll, part1, part2, newgraph = best_split(graph, compind, splitind, pind, data,
                                                seedpairs, ps, rng=rng, info=info)
    if np.isnan(ll):
        raise FormDiscoveryError("choose_node_split: NaN log-likelihood")
    return ll, part1, part2, newgraph


# --- swapobjclust (item 24) ------------------------------------------------------------------

# sourceobjs.m l.241-244 and sourcecls.m l.266-267 (the lists differ: 'tree' is in
# neither, 'dirtree'/'undirhierarchy' only in the second, the chains/rings only in the
# first)
_SOURCEOBJS_TYPES = ('hierarchy', 'dirhierarchynoself', 'dirchain', 'dirring',
                     'dirhierarchy', 'dirchainnoself', 'dirringnoself', 'undirintree',
                     'undirhierarchynoself', 'undirchain', 'undirchainnoself',
                     'undirring', 'undirringnoself')
_SOURCECLS_TYPES = ('hierarchy', 'dirtree', 'dirhierarchynoself', 'undirhierarchy',
                    'undirhierarchynoself')


def cltypes(graph, i):
    """``swapobjclust.m:277-283`` (``cltypes``): the external clusters of component ``i``
    (column sums of ``adjsym`` at most 1) and the internal ones (the rest). 0-based;
    returns two sorted int64 arrays."""
    c = graph.components[i]
    adj = np.atleast_2d(np.asarray(c.adjsym, dtype=float))
    extcls = np.flatnonzero(adj.sum(axis=0) <= 1)
    intcls = setdiff(np.arange(int(c.nodecount)), extcls).astype(np.int64)
    return extcls.astype(np.int64), intcls


def sourceobjs(graph):
    """``swapobjclust.m:239-255`` (``sourceobjs``): the objects that may be moved.

    For the types in MATLAB's list (hierarchies, dir/undir chains and rings; not
    ``tree``) an object alone in an *internal* cluster of component 1 stays put; every
    other object may move. ``graph.z`` is compared with component 1's node numbers,
    which is right for the single-component types in the list. 0-based int64 array.
    """
    objcount = int(graph.objcount)
    if graph.type in _SOURCEOBJS_TYPES:
        _, intcls = cltypes(graph, 0)
        z = np.asarray(graph.z).ravel()
        inds = np.ones(objcount, dtype=bool)
        for i in intcls:
            if np.sum(z == i) == 1:
                inds[:z.size][z == i] = False
        return np.flatnonzero(inds).astype(np.int64)
    return np.arange(objcount, dtype=np.int64)


def sourcecls(graph, i=None):
    """``swapobjclust.m:259-272`` (``sourcecls``): the clusters whose objects may be moved.

    The occupied clusters of the combined graph (``i is None``) or of component ``i``;
    for the types in MATLAB's list only those that are external in component 1
    (:func:`cltypes`). 0-based, sorted int64 array.
    """
    z = graph.z if i is None else graph.components[i].z
    csource = np.unique(np.asarray(z, dtype=np.int64).ravel())
    if graph.type in _SOURCECLS_TYPES:
        extcls, _ = cltypes(graph, 0)
        csource = intersect(csource, extcls)
    return np.asarray(csource, dtype=np.int64)


def _rows(col0, col1, rest, ncol):
    """Stack swap rows ``[col0, col1, rest...]`` as a float array with ``ncol`` columns."""
    col1 = np.asarray(col1, dtype=float).ravel()
    out = np.full((col1.size, ncol), np.nan)
    out[:, 0] = col0
    out[:, 1] = col1
    if rest is not None:
        out[:, 2:] = np.asarray(rest, dtype=float).reshape(col1.size, ncol - 2)
    return out


def chooseswaps(graph, whole, oflag, comp, fastflag, graphngb=3):
    """``swapobjclust.m:68-199`` (``chooseswaps``): the candidate moves and swaps.

    Returns ``(sw1, sw2)``, float arrays with ``2 + ncomp`` columns, one row per
    candidate, holding 0-based indices and NaN (MATLAB's format, l.60-66):
    ``[c, j, z_1, ..., z_ncomp]``. ``sw1`` row ``[c, j, z]``: move component ``c``'s
    node ``j`` (or, with ``c`` NaN, combined cluster ``j``, or object ``j`` when
    ``oflag``) to the node(s) ``z`` (NaN in the components that do not change).
    A swap has a second row in ``sw2`` (all NaN for a move).

    - ``oflag`` (l.70-95): each movable object (:func:`sourceobjs`) to each legal
      combined cluster (not in ``graph.illegal``), object outer and cluster inner; its
      own cluster included. With ``fastflag`` only clusters at distance
      ``1..graphngb`` in ``adjclustersym`` (``dijkstra``), grouped by the occupied
      clusters in sorted order.
    - ``whole`` (l.96-130): moves of each :func:`sourcecls` cluster to each legal
      cluster (source outer), then swaps of every ``nchoosek`` pair of source clusters.
      With ``fastflag`` both are limited to the ``graphngb`` neighbourhood, and each
      swap is listed once (partner index larger).
    - otherwise, within component ``comp`` (l.131-198): moves of each
      ``sourcecls(graph, comp)`` node to each legal node, source *inner* and target
      outer (the opposite order to the whole-graph case), then swaps of every pair of
      occupied nodes. With one occupied node MATLAB's swap list is the pair
      ``[1 1]``: node 0 with itself (a no-op that is still scored). With ``fastflag``
      as above.

    Deviation (``KNOWN_ISSUES.md`` KI-26): in the ``whole`` full mode with a single
    source cluster, MATLAB's ``nchoosek(csource, 2)`` gives a scalar (Octave: an
    error) and ``pairs(:,2)`` fails; the port raises :class:`FormDiscoveryError`.
    """
    ncomp = int(graph.ncomp)
    ncol = 2 + ncomp
    compinds = np.atleast_2d(np.asarray(graph.compinds, dtype=np.int64))
    if compinds.shape[1] != ncomp:
        compinds = compinds.reshape(-1, ncomp)
    if oflag or whole:
        nnode = np.atleast_2d(graph.adjcluster).shape[0]
        # cluster nodes that are free to accept objects
        clegal = setdiff(np.arange(nnode), np.asarray(graph.illegal, dtype=np.int64))
        clegal = clegal.astype(np.int64)
        clegalv = np.zeros(nnode, dtype=bool)
        clegalv[clegal] = True
    if oflag:
        objmovable = sourceobjs(graph)  # objects that are free to move
        objmovablev = np.zeros(int(graph.objcount), dtype=bool)
        objmovablev[objmovable] = True
        z = np.asarray(graph.z, dtype=np.int64).ravel()
        if fastflag:
            dijk = dijkstra(graph.adjclustersym)
            col1, col2 = [], []
            for c in np.unique(z):
                ds = np.flatnonzero((dijk[c] <= graphngb) & (dijk[c] > 0) & clegalv)
                cmembers = np.flatnonzero((z == c) & objmovablev[:z.size])
                col1 += [m for m in cmembers for _ in ds]
                col2 += [d for _ in cmembers for d in ds]
            col2 = np.asarray(col2, dtype=np.int64)
        else:
            col1 = np.repeat(objmovable, clegal.size)
            col2 = np.tile(clegal, objmovable.size)
        sw1 = _rows(np.nan, col1, compinds[col2], ncol)
        sw2 = np.full(sw1.shape, np.nan)
    elif whole:
        # cluster nodes whose objects we can steal
        csource = sourcecls(graph)
        csourcev = np.zeros(nnode, dtype=bool)
        csourcev[csource] = True
        if fastflag:
            dijk = dijkstra(graph.adjclustersym)
            col1, col2, col1a, col2a = [], [], [], []
            for c in csource:
                near = (dijk[c] <= graphngb) & (dijk[c] > 0)
                ds = np.flatnonzero(near & clegalv)
                col1 += [c] * ds.size
                col2 += list(ds)
                swopts = np.flatnonzero(near & csourcev)
                swopts = swopts[swopts > c]  # don't want to try swaps twice
                col1a += [c] * swopts.size
                col2a += list(swopts)
            col2, col1a, col2a = (np.asarray(v, dtype=np.int64) for v in (col2, col1a, col2a))
        else:
            # moves
            col1 = np.repeat(csource, clegal.size)
            col2 = np.tile(clegal, csource.size)
            # swaps (only bother with swaps of occupied nodes)
            if csource.size < 2:
                raise FormDiscoveryError(
                    "chooseswaps: nchoosek(csource, 2) with one source cluster (KI-26)")
            i, j = np.triu_indices(csource.size, 1)
            col1a, col2a = csource[i], csource[j]
        sw1 = np.vstack([_rows(np.nan, col1, compinds[col2], ncol),
                         _rows(np.nan, col1a, compinds[col2a], ncol)])
        sw2 = np.vstack([np.full((len(col1), ncol), np.nan),
                         _rows(np.nan, col2a, compinds[col1a], ncol)])
    else:  # within component moves/swaps
        cg = graph.components[comp]
        nodecount = int(cg.nodecount)
        clegal = setdiff(np.arange(nodecount), np.asarray(cg.illegal, dtype=np.int64))
        clegal = clegal.astype(np.int64)
        clegalv = np.zeros(nodecount, dtype=bool)
        clegalv[clegal] = True
        csourcemove = sourcecls(graph, comp)
        csourceswap = np.unique(np.asarray(cg.z, dtype=np.int64).ravel())
        csourceswapv = np.zeros(nodecount, dtype=bool)
        csourceswapv[csourceswap] = True
        if fastflag:
            dijk = dijkstra(cg.adjsym)
            col1, col2 = [], []
            for c in csourcemove:
                ds = np.flatnonzero((dijk[c] <= graphngb) & (dijk[c] > 0) & clegalv)
                col1 += [c] * ds.size
                col2 += list(ds)
            p1, p2 = [], []
            for c in csourceswap:
                ds = np.flatnonzero((dijk[c] <= graphngb) & (dijk[c] > 0) & csourceswapv)
                ds = ds[ds > c]  # don't want to try swaps twice
                p1 += [c] * ds.size
                p2 += list(ds)
        else:
            # moves
            col1 = np.tile(csourcemove, clegal.size)
            col2 = np.repeat(clegal, csourcemove.size)
            # swaps (only bother with swaps of occupied nodes)
            if csourceswap.size > 1:
                i, j = np.triu_indices(csourceswap.size, 1)
                p1, p2 = csourceswap[i], csourceswap[j]
            else:
                p1, p2 = [0], [0]
        sw1 = _rows(comp, col1, None, ncol)
        sw1[:, 2 + comp] = col2
        sw2 = np.full(sw1.shape, np.nan)
        sw1b = _rows(comp, p1, None, ncol)
        sw1b[:, 2 + comp] = p2
        sw2b = _rows(comp, p2, None, ncol)
        sw2b[:, 2 + comp] = p1
        sw1 = np.vstack([sw1, sw1b])
        sw2 = np.vstack([sw2, sw2b])
    return sw1, sw2


def doswap(graph, sw1, sw2, oflag, ps):
    """``swapobjclust.m:205-235`` (``doswap``): apply one row of :func:`chooseswaps`.

    ``oflag``: object ``sw1[1]`` goes to node ``sw1[2 + i]`` of every component ``i``.
    Within component ``c = sw1[0]``: the objects of node ``sw1[1]`` go to node
    ``sw1[2 + c]``, and for a swap those of ``sw2[1]`` to ``sw2[2 + c]`` (both read from
    the old assignment). Whole graph (``sw1[0]`` NaN): the members of combined cluster
    ``sw1[1]`` get component nodes ``sw1[2:]``, and for a swap those of ``sw2[1]`` get
    ``sw2[2:]``. Then ``combinegraphs(..., zonly=1)``. Returns a new graph.
    """
    g = graph.copy()
    sw1 = np.asarray(sw1, dtype=float).ravel()
    sw2 = np.asarray(sw2, dtype=float).ravel()
    ncomp = int(g.ncomp)
    if oflag:  # object move
        obj = int(sw1[1])
        for i in range(ncomp):
            g.components[i].z[obj] = int(sw1[2 + i])
    elif not np.isnan(sw1[0]):  # within component move/swap
        c = int(sw1[0])
        oldz = np.asarray(g.components[c].z)
        newz = oldz.copy()
        newz[oldz == int(sw1[1])] = int(sw1[2 + c])
        if not np.isnan(sw2[0]):
            newz[oldz == int(sw2[1])] = int(sw2[2 + c])
        g.components[c].z = newz
    else:  # move/swap at highest level
        oldz = np.asarray(g.z).ravel()
        clmembers = np.flatnonzero(oldz == int(sw1[1]))
        for i in range(ncomp):
            g.components[i].z[clmembers] = int(sw1[2 + i])
        if not np.isnan(sw2[1]):
            clmembers = np.flatnonzero(oldz == int(sw2[1]))
            for i in range(ncomp):
                g.components[i].z[clmembers] = int(sw2[2 + i])
    return combinegraphs(g, ps, zonly=1)


def swapobjclust(graph, data, ps, comp, epsilon, currscore, overallchange, loopmax,
                 nearmscores, nearmgraphs, objflag=0, debug=0, fastflag=0, rng=None):
    """``swapobjclust.m:1-58``: improve ``graph`` by moving or swapping clusters or
    single objects.

    ``comp`` is a 0-based component, or ``None`` (MATLAB ``[]``) for moves at the level
    of the whole graph; ``objflag``, ``debug`` and ``fastflag`` are MATLAB's name/value
    options (with ``objflag`` set, ``comp`` is ignored). Returns ``(graph, currscore,
    overallchange, nearmscores, nearmgraphs)``; the inputs are not modified.
    ``nearmgraphs`` is a list (MATLAB's cell; empty slots may be ``None``).

    Each pass of the ``while`` loop (at most ``loopmax``) lists the candidates with
    :func:`chooseswaps` (``graphngb = 3``) and draws one ``randperm`` over them. Each
    candidate in that order is applied (:func:`doswap`), simplified
    (``simplify_graph``) and scored (``graph_like + graph_prior``, with ``ps`` as
    given). A gain above ``epsilon`` is accepted, and the candidates are listed again
    for the new graph, **but the loop goes on with the old permutation**: indices past
    the new list are skipped (l.36-37), so the rest of the pass visits the new list in
    an order drawn for the old one. This is replicated. Otherwise, if there is a
    near-miss list and the score beats its last entry, the candidate goes to
    :func:`addnearmiss`. The accepted graph is the simplified candidate, not the graph
    ``graph_like`` returns.

    ``debug`` raises :class:`FormDiscoveryError` on an accepted change (MATLAB's
    ``keyboard``, patched to ``error``). The ``disp`` when ``loopcount == loopmax`` is
    dropped.
    """
    rng = as_provider(rng)
    whole = comp is None
    graphngb = 3  # neighborhood within which to try swaps (fast mode)
    nearmscores = np.asarray(nearmscores, dtype=float).ravel().copy()
    nearmgraphs = list(nearmgraphs)
    nmissflag = nearmscores.size > 0

    change = 1
    loopcount = 0
    while change and loopcount < loopmax:
        change = 0
        loopcount += 1
        sw1, sw2 = chooseswaps(graph, whole, objflag, comp, fastflag, graphngb)
        rp = rng.randperm(sw1.shape[0])
        for j in rp:
            if j >= sw1.shape[0]:
                continue
            testgraph = doswap(graph, sw1[j], sw2[j], objflag, ps)
            testgraph = simplify_graph(testgraph, ps)
            testscore, _ = likelihood.graph_like(data, testgraph, ps)
            testscore = testscore + graph_prior(testgraph, ps)
            if testscore - currscore > epsilon:
                if debug:
                    raise FormDiscoveryError("swapobjclust: debug stop (was keyboard)")
                change = 1
                overallchange = 1
                graph = testgraph
                currscore = testscore
                sw1, sw2 = chooseswaps(graph, whole, objflag, comp, fastflag, graphngb)
            elif nmissflag:  # add graph to list of nearmisses
                if testscore > nearmscores[-1]:
                    nearmscores, nearmgraphs = addnearmiss(
                        nearmscores, nearmgraphs, testgraph, testscore, graph, currscore,
                        epsilon)
    return graph, currscore, overallchange, nearmscores, nearmgraphs


# --- spr (item 25, L4-b2) ---------------------------------------------------------------

_SPR_HIER = ('hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself',
             'undirhierarchy', 'undirhierarchynoself')


def makerp(graph, i, objflag, rng=None):
    """``spr.m:53-60`` (``makerp``): one ``randperm`` over the cluster nodes of component
    ``i`` (``objflag`` 0) or over the objects (``objflag`` 1). 0-based."""
    rng = as_provider(rng)
    if objflag == 0:
        return rng.randperm(int(graph.components[i].nodecount))
    return rng.randperm(int(graph.objcount))


def makers(graph, j, i, objflag):
    """``spr.m:63-99`` (``makers``): where node (or object, with ``objflag``) ``j`` of
    component ``i`` can be regrafted. Returns 0-based int arrays ``(rs, cs)``.

    - ``tree``: the edges ``rs[k] -> cs[k]`` of ``adj`` in column-major ``find`` order.
      For a cluster node, edges inside ``j``'s subtree (``j`` and its
      ``find_descendants``) are removed, and so is every edge touching ``j``'s parent.
    - hierarchy family: ``rs == cs``, the sorted nodes other than object ``j``'s own
      node, or other than ``j``, its descendants and its parent.

    A parentless cluster node gives empty arrays (l.83-85), before the type check. Other
    types (``domtreenoself``, which ``gibbs_clean.m:88-90`` sends to ``spr``) leave ``rs``
    undefined in MATLAB; the port raises :class:`FormDiscoveryError` (KI-27).
    """
    c = graph.components[i]
    adj = np.atleast_2d(np.asarray(c.adj))
    n = int(c.nodecount)
    if objflag:
        if c.type == 'tree':
            rs, cs = _find_rc(adj)
        elif c.type in _SPR_HIER:
            rs = setdiff(np.arange(n), [int(np.asarray(c.z).ravel()[j])]).astype(np.int64)
            cs = rs.copy()
        else:
            raise FormDiscoveryError(f"spr>makers: 'rs' undefined for type {c.type} (KI-27)")
        return rs, cs
    jparent = np.flatnonzero(adj[:, j])
    if jparent.size == 0:
        return _EMPTY.copy(), _EMPTY.copy()
    descendants = find_descendants(adj)
    jds = np.concatenate([[j], np.asarray(descendants[j], dtype=np.int64)]).astype(np.int64)
    if c.type == 'tree':
        edges = adj.copy()
        edges[np.ix_(jds, jds)] = 0
        rs, cs = _find_rc(edges)
        # if j's parent is one of the edge nodes the swap changes nothing
        if jparent.size != 1:
            raise FormDiscoveryError(f"spr>makers: node {j} has {jparent.size} parents")
        keep = (rs != jparent[0]) & (cs != jparent[0])
        return rs[keep], cs[keep]
    if c.type in _SPR_HIER:
        rs = setdiff(np.arange(n), np.concatenate([jds, jparent])).astype(np.int64)
        return rs, rs.copy()
    raise FormDiscoveryError(f"spr>makers: 'rs' undefined for type {c.type} (KI-27)")


def _find_rc(a):
    """MATLAB ``[r, c] = find(a)``: column-major row and column indices (0-based)."""
    c, r = np.nonzero(np.asarray(a).T)
    return r.astype(np.int64), c.astype(np.int64)


def spr(graph, data, ps, i, epsilon, currscore, overallchange, debug, nearmscores,
        nearmgraphs, rng=None):
    """``spr.m:1-50``: subtree pruning and regrafting in component ``i`` (0-based).

    For ``tree`` components cluster nodes (``objflag`` 0) and then objects (``objflag``
    1) are pruned; other types only cluster nodes. For each ``objflag`` one
    :func:`makerp` permutation is drawn, and for each node ``j`` in that order every
    target from :func:`makers` is tried: ``subtreeattach``, ``simplify_graph``, then
    ``graph_like + graph_prior``. A gain above ``epsilon`` is accepted; then ``rp`` is
    **drawn again** (a new ``randperm``), ``j = rp[jind]`` and the targets are listed
    again, but both loops go on with their old lengths: past the end of the new ``rp``
    the inner loop breaks, and targets past the new list are skipped (l.20-44). This is
    replicated. Otherwise, with a near-miss list and a score above its last entry, the
    candidate goes to :func:`addnearmiss`. Returns ``(graph, currscore, overallchange,
    nearmscores, nearmgraphs)``; the inputs are not modified.

    ``debug`` raises :class:`FormDiscoveryError` on an accepted change (MATLAB's
    ``keyboard``, patched to ``error``).
    """
    rng = as_provider(rng)
    nearmscores = np.asarray(nearmscores, dtype=float).ravel().copy()
    nearmgraphs = list(nearmgraphs)
    nmissflag = nearmscores.size > 0
    oflags = (0, 1) if graph.components[i].type == 'tree' else (0,)

    for objflag in oflags:  # snip off an object or a cluster node?
        rp = makerp(graph, i, objflag, rng)
        for jind in range(len(rp)):
            if jind >= len(rp):
                continue
            j = int(rp[jind])
            rs, cs = makers(graph, j, i, objflag)
            if rs.size == 0:
                continue
            for eind in range(rs.size):
                if eind >= rs.size:
                    continue
                testgraph = subtreeattach(graph, j, int(rs[eind]), int(cs[eind]), i, ps,
                                          objflag=objflag)
                testgraph = simplify_graph(testgraph, ps)
                testscore, _ = likelihood.graph_like(data, testgraph, ps)
                testscore = testscore + graph_prior(testgraph, ps)
                if testscore - currscore > epsilon:
                    if debug:
                        raise FormDiscoveryError("spr: debug stop (was keyboard)")
                    overallchange = 1
                    graph = testgraph
                    currscore = testscore
                    rp = makerp(graph, i, objflag, rng)
                    if jind >= len(rp):
                        break
                    j = int(rp[jind])
                    rs, cs = makers(graph, j, i, objflag)
                elif nmissflag:  # add graph to list of nearmisses
                    if testscore > nearmscores[-1]:
                        nearmscores, nearmgraphs = addnearmiss(
                            nearmscores, nearmgraphs, testgraph, testscore, graph,
                            currscore, epsilon)
    return graph, currscore, overallchange, nearmscores, nearmgraphs


# --- collapsedims (item 25, L4-b2) ------------------------------------------------------

def getocc(graph, compind, j):
    """``collapsedims.m:63-69`` (``getocc``): the occupied combined clusters ``occ``
    (sorted ``unique(graph.z)``) and the unoccupied ones ``unocc``, without those whose
    node on component ``compind`` is ``j``. 0-based int arrays."""
    occ = np.unique(np.asarray(graph.z, dtype=np.int64).ravel())
    unocc = setdiff(np.arange(np.atleast_2d(graph.Wcluster).shape[0]), occ)
    compinds = np.atleast_2d(np.asarray(graph.compinds, dtype=np.int64))
    unocc = setdiff(unocc, np.flatnonzero(compinds[:, compind] == j))
    return occ, unocc.astype(np.int64)


def get_occnodescomp(graph, i):
    """``collapsedims.m:74-75``: the sorted occupied nodes of component ``i``."""
    return np.unique(np.asarray(graph.components[i].z, dtype=np.int64).ravel())


def zassign(zjinst, newnode, graph, compind=None, j=None, ps=None):
    """``collapsedims.m:80-85`` (``zassign``): the objects of combined cluster ``zjinst``
    (read from ``graph.z``, which is not updated) go to the component nodes of combined
    cluster ``newnode`` on every component. ``compind``, ``j`` and ``ps`` are unused, as
    in MATLAB. Returns a new graph."""
    g = graph.copy()
    objind = np.flatnonzero(np.asarray(g.z).ravel() == zjinst)
    compinds = np.atleast_2d(np.asarray(g.compinds, dtype=np.int64))
    for i in range(int(g.ncomp)):
        z = np.asarray(g.components[i].z).copy()
        z[objind] = compinds[newnode, i]
        g.components[i].z = z
    return g


def collapsedims(graph, data, ps, epsilon, currscore, overallchange, loopmax, nearmscores,
                 nearmgraphs, debug=0, rng=None):
    """``collapsedims.m:1-58``: squeeze dimensions out of a product graph by moving the
    objects of a slice to the nearest vacant clusters.

    Each pass of the ``while`` loop (at most ``loopmax``) computes
    ``dijkstra(graph.Wclustersym)`` once (it is **not** recomputed after an accepted
    change). For every component ``i`` (the count taken at the start of the pass) and
    every occupied node ``j`` of it (:func:`get_occnodescomp`; after an accept the list
    is recomputed but the loop keeps its old length, skipping indices past the end): the
    occupied combined clusters ``zj`` whose node on ``i`` is ``j`` are listed
    (:func:`getocc`). If there are no more of them than candidate vacant clusters, one
    ``randperm(len(zj))`` orders them and each goes, in turn, to the nearest remaining
    vacant cluster (first minimum; :func:`zassign`). The candidate is recombined
    (``combinegraphs(zonly=1)``), simplified and scored (``graph_like + graph_prior``);
    a gain above ``epsilon`` is accepted, otherwise it may enter the near-miss list
    (:func:`addnearmiss`). Returns ``(graph, currscore, overallchange, nearmscores,
    nearmgraphs)``; the inputs are not modified.

    ``debug`` raises :class:`FormDiscoveryError` on an accepted change (MATLAB's
    ``keyboard``, patched to ``error``). The ``disp`` when ``loopcount == loopmax`` is
    dropped.
    """
    rng = as_provider(rng)
    nearmscores = np.asarray(nearmscores, dtype=float).ravel().copy()
    nearmgraphs = list(nearmgraphs)
    nmissflag = nearmscores.size > 0

    change = 1
    loopcount = 0
    while change and loopcount < loopmax:
        change = 0
        loopcount += 1
        ds = dijkstra(graph.Wclustersym)
        for i in range(int(graph.ncomp)):
            # occupied nodes for this component
            occnodescomp = get_occnodescomp(graph, i)
            for jind in range(occnodescomp.size):
                if jind >= occnodescomp.size:
                    continue
                j = int(occnodescomp[jind])
                testgraph = graph
                occ, unocc = getocc(testgraph, i, j)
                compinds = np.atleast_2d(np.asarray(testgraph.compinds, dtype=np.int64))
                zj = occ[compinds[occ, i] == j]
                if zj.size <= unocc.size:
                    zj = zj[rng.randperm(zj.size)]
                    for zjinst in zj:
                        mind = int(np.argmin(ds[zjinst, unocc]))  # first minimum
                        testgraph = zassign(int(zjinst), int(unocc[mind]), testgraph, i, j)
                        unocc = setdiff(unocc, [unocc[mind]]).astype(np.int64)
                    testgraph = combinegraphs(testgraph, ps, zonly=1)
                    testgraph = simplify_graph(testgraph, ps)
                    testscore, _ = likelihood.graph_like(data, testgraph, ps)
                    testscore = testscore + graph_prior(testgraph, ps)
                    if testscore - currscore > epsilon:
                        if debug:
                            raise FormDiscoveryError("collapsedims: debug stop (was keyboard)")
                        change = 1
                        overallchange = 1
                        graph = testgraph
                        currscore = testscore
                        occnodescomp = get_occnodescomp(graph, i)
                    elif nmissflag:  # add graph to list of nearmisses
                        if testscore > nearmscores[-1]:
                            nearmscores, nearmgraphs = addnearmiss(
                                nearmscores, nearmgraphs, testgraph, testscore, graph,
                                currscore, epsilon)
    return graph, currscore, overallchange, nearmscores, nearmgraphs
