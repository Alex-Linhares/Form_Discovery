"""Search heuristics, part a (item 23, L4-a; PLAN.md §5): ``addnearmiss``,
``choose_seedpairs``, ``best_split`` and ``choose_node_split``.

Randomness enters through ``randperm`` at ``choose_seedpairs.m:24`` and
``best_split.m:35``. The ports take ``rng=None`` and draw with
``as_provider(rng).randperm(n)`` exactly as often, and in the same order, as the MATLAB
code (``rng.py``, item 22).

Pinned by ``tests/octave/fx_search.m`` → ``tests/fixtures/search.mat``
(``tests/test_search.py``), which replays Octave's recorded draws.
"""

import numpy as np

from . import FormDiscoveryError, likelihood
from .graph import add_element, empty_graph, simplify_graph, split_node
from .matlab_compat import max_first, setdiff, stable_argsort, unique_matlab
from .params import graph_prior
from .rng import as_provider

__all__ = ["addnearmiss", "choose_seedpairs", "best_split", "choose_node_split"]

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
