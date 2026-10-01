"""Relational-data likelihoods (PLAN.md §5).

Item 08 (L0-b) adds the beta-binomial and Dirichlet-multinomial building blocks
``makehyps``, ``bbloglike``, ``bblikesumhyps`` and ``dirmultloglike``, pinned against
Octave by ``legacy/tests_octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``).
Item 20 (L3-c) adds ``countmatrix``, ``rellikebin``, ``rellikefreqs`` and
``graph_like_rel``, pinned by ``legacy/tests_octave/fx_rellike.m`` → ``tests/fixtures/rellike.mat``
(``tests/test_rellike.py``).
"""

import warnings

import numpy as np
from scipy.special import gammaln

from . import FormDiscoveryError
from .graph import filloutrelgraph
from .matlab_compat import find_F, hist_centres
from .util import meanlogs, trans2orig

__all__ = ["makehyps", "bbloglike", "bblikesumhyps", "dirmultloglike", "countmatrix",
           "rellikebin", "rellikefreqs", "graph_like_rel"]


def makehyps(props, sums):
    """``makehyps.m:6-8``: the grid of beta hyperparameters for every (proportion, sum)
    pair. ``[Ps Ss] = meshgrid(props, sums)`` then ``trans2orig`` and ``(:)``, so the
    proportion varies slowest: entry ``k`` is ``(props[k // len(sums)], sums[k % len(sums)])``.
    Returns 1-D ``(alphas, betas)`` of length ``len(props) * len(sums)``.
    """
    Ps, Ss = np.meshgrid(np.asarray(props, dtype=float).ravel(),
                         np.asarray(sums, dtype=float).ravel())
    alphas, betas = trans2orig(Ps, Ss)
    return alphas.ravel(order="F"), betas.ravel(order="F")


def bbloglike(alpha, beta, ns, ys):
    """``bbloglike.m:11-12``: beta-binomial log likelihood of ``ys`` successes in ``ns``
    trials under hyperparameters ``(alpha, beta)``, summed over the first dimension
    (MATLAB ``sum(..., 1)``, also for a 1-row matrix, which is then returned unchanged).

    Inputs broadcast. A 2-D ``(d, h)`` input gives a length-``h`` array; a 1-D input is a
    MATLAB column vector and gives a scalar.
    """
    alpha, beta, ns, ys = (np.asarray(x, dtype=float) for x in (alpha, beta, ns, ys))
    return np.sum(gammaln(alpha + ys) + gammaln(beta + (ns - ys)) - gammaln(ns + alpha + beta)
                  - gammaln(alpha) - gammaln(beta) + gammaln(alpha + beta), axis=0)


def bblikesumhyps(ys, ns, alphas, betas):
    """``bblikesumhyps.m:6-27``: ``log(mean_h p(ys | ns, alphas[h], betas[h]))``, the
    beta-binomial likelihood averaged over a flat prior on the hyperparameter grid
    (``makehyps``), computed with a max offset.

    ``ys`` and ``ns`` are vectors (MATLAB columns; callers ``graph_like_rel.m:62,79,82``).
    Entries with ``ns == 0`` are dropped; empty input (before or after dropping) gives 0.
    """
    ys = np.asarray(ys, dtype=float).ravel()
    ns = np.asarray(ns, dtype=float).ravel()
    if len(ys) == 0:
        return 0.0
    ys = ys[ns > 0]
    ns = ns[ns > 0]
    if ns.size == 0:
        return 0.0
    alphas = np.asarray(alphas, dtype=float).ravel()
    betas = np.asarray(betas, dtype=float).ravel()
    # the repmat grid of the MATLAB code, as broadcasting: data down, hypotheses across
    lls = bbloglike(alphas[None, :], betas[None, :], ns[:, None], ys[:, None])
    offset = np.max(lls)
    with np.errstate(invalid="ignore"):
        return float(np.log(np.mean(np.exp(lls - offset))) + offset)


def dirmultloglike(alpha, counts):
    """``dirmultloglike.m:13-20``: Dirichlet-multinomial log likelihood of each row of
    ``counts`` under the matching row of ``alpha`` (MATLAB ``sum(..., 2)``).

    Zero entries of ``alpha`` and of ``counts + alpha`` are replaced by 1 before
    ``gammaln`` (so they contribute 0), as in MATLAB. Inputs broadcast. A 2-D ``(k, m)``
    input gives a length-``k`` array; a 1-D input is one row and gives a scalar. Caller:
    ``rellikefreqs.m:18``.
    """
    alpha = np.asarray(alpha, dtype=float)
    counts = np.asarray(counts, dtype=float)
    countsplusalpha = counts + alpha
    countsplusalpha = np.where(countsplusalpha == 0, 1.0, countsplusalpha)
    alphanonz = np.where(alpha == 0, 1.0, alpha)
    with np.errstate(invalid="ignore"):  # an all-zero row is Inf - Inf = NaN, as in MATLAB
        return (gammaln(np.sum(alpha, axis=-1)) + np.sum(gammaln(countsplusalpha), axis=-1)
                - np.sum(gammaln(alphanonz), axis=-1) - gammaln(np.sum(counts + alpha, axis=-1)))


def countmatrix(data, graph):
    """``countmatrix.m:1-21``: ``counts[i, j]``, the sum of ``data`` over the objects in
    cluster ``i`` (rows) and cluster ``j`` (columns), for the ``size(adjcluster, 1)``
    clusters. Objects with ``z == -1`` belong to no cluster.

    MATLAB first overwrites ``counts`` with the scalar ``size(adj,1) - objcount`` (l.13)
    and then fills it; with no clusters that scalar is the result (a 1 x 1 array here).
    """
    nclass = np.atleast_2d(graph.adjcluster).shape[0]
    z = np.asarray(graph.z).ravel()
    data = np.asarray(data, dtype=float)
    if nclass == 0:
        return np.array([[float(np.atleast_2d(graph.adj).shape[0] - graph.objcount)]])
    members = [np.flatnonzero(z == i) for i in range(nclass)]
    counts = np.zeros((nclass, nclass))
    for i in range(nclass):
        for j in range(nclass):
            counts[i, j] = np.sum(np.sum(data[np.ix_(members[i], members[j])], axis=0))
    return counts


def rellikebin(countvec, adjvec, sizevec, mags, thetas):
    """``rellikebin.m:1-41``: log probability of binary relational data.

    ``countvec``/``adjvec``/``sizevec`` are the column-major vectors of the cluster count,
    cluster adjacency and pair-count matrices; ``mags`` the hyperparameter sums and
    ``thetas`` the proportions. For each edge value ``v`` in (0, 1), every block with
    ``adjvec == v`` gets a beta-binomial likelihood under every ``(mag, theta)``; the mean
    over mags gives ``zs``/``os`` per theta. The result averages ``zs[a] + os[b]`` over
    the pairs ``a <= b`` (MATLAB ``find(triu(ones))`` order), in log space.
    """
    countvec, adjvec, sizevec = (np.asarray(x, dtype=float).ravel()
                                 for x in (countvec, adjvec, sizevec))
    mags = np.asarray(mags, dtype=float).ravel()
    thetas = np.asarray(thetas, dtype=float).ravel()
    magsmat = np.tile(mags[:, None], (1, len(thetas)))
    thetasmat = np.tile(thetas[None, :], (len(mags), 1))
    alphasmat = thetasmat * magsmat
    betasmat = magsmat - alphasmat
    alphas = alphasmat.ravel(order="F")
    betas = betasmat.ravel(order="F")
    llsmat = []
    for v in (0, 1):
        sel = adjvec == v
        ys, ns = countvec[sel], sizevec[sel]
        if ys.size == 0:
            llsmat.append(0 * magsmat)
        else:
            with np.errstate(invalid="ignore", divide="ignore"):
                lls = bbloglike(alphas[None, :], betas[None, :], ns[:, None], ys[:, None])
            llsmat.append(lls.reshape(alphasmat.shape, order="F"))
    ncol = llsmat[0].shape[1]
    with warnings.catch_warnings():  # all-NaN columns (e.g. counts > sizes) give NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        zs = np.array([meanlogs(llsmat[0][:, i]) for i in range(ncol)])
        os_ = np.array([meanlogs(llsmat[1][:, i]) for i in range(ncol)])
        zind, oind, _ = find_F(np.triu(np.ones((len(zs), len(zs)))), return_rc=True)
        return float(meanlogs(zs[zind] + os_[oind]))


def rellikefreqs(countvec, adjvec, sizevec, alphas, betas):
    """``rellikefreqs.m:1-27``: log probability of frequency relational data.

    One Dirichlet-multinomial likelihood (:func:`dirmultloglike`) per hyperparameter pair
    ``h``, with parameter ``sizevec * alphas[h]`` on blocks with an edge and
    ``sizevec * betas[h]`` elsewhere, averaged over ``h`` in log space (max offset). Then
    ``sum(countvec * log(sizevec))`` is subtracted (``sizevec == 0`` read as 1), which
    turns ``p(countvec | graph)`` into ``p(data | graph)``. ``graph_like_rel.m:150`` passes
    the edge hyperparameters ``alphasedge``/``betasedge`` as ``alphas``/``betas``.
    """
    countvec, adjvec, sizevec = (np.asarray(x, dtype=float).ravel()
                                 for x in (countvec, adjvec, sizevec))
    alphas = np.asarray(alphas, dtype=float).ravel()
    betas = np.asarray(betas, dtype=float).ravel()
    allalphas = sizevec[None, :] * (adjvec[None, :] * alphas[:, None]
                                    + (1 - adjvec[None, :]) * betas[:, None])
    lls = dirmultloglike(allalphas, countvec[None, :])
    offset = np.max(lls)
    with np.errstate(invalid="ignore", divide="ignore"):
        ll = np.log(np.mean(np.exp(lls - offset))) + offset
        sizevec = np.where(sizevec == 0, 1.0, sizevec)
        return float(ll - np.sum(countvec * np.log(sizevec)))


# graph_like_rel.m:8-13: forms stored as the backbone of a transitive relation
_FILLOUT = ("order", "domtree", "ordernoself", "dirdomtreenoself", "undirdomtree",
            "undirdomtreenoself", "connected", "connectednoself")
# graph_like_rel.m:108-110: forms that expect links within classes
_SELF = ("partition", "order", "dirchain", "dirring", "dirhierarchy", "domtree",
         "connected", "undirchain", "undirring", "undirhierarchy", "undirdomtree")
# graph_like_rel.m:115-118: forms that expect symmetric links
_UNDIR = ("undirchain", "undirring", "undirhierarchy", "undirdomtree", "undirchainnoself",
          "undirringnoself", "undirhierarchynoself", "undirdomtreenoself")


def _reldom(data, graph, clustmembers, nclust):
    """``graph_like_rel.m:22-101``, the ``'reldom'`` branch ("not currently used").

    ``data['R'][:, :, 0]`` holds successes and ``[:, :, 1]`` trials. The edge-direction
    flip for two-cluster one-edge graphs (l.93-100) only changes ``graph.adj``, which l.162
    then discards (``graph = origgraph``), so it has no effect and is not ported (KI-22).
    """
    alphas, betas = makehyps(np.arange(1, 6) / 5 - 1 / 10, 2.0 ** np.arange(1, 6))
    alphasnoedge, betasnoedge = makehyps(0.5, 2.0 ** np.arange(-3, 3))
    R = np.asarray(data["R"], dtype=float)
    yobs = np.zeros((nclust, nclust))
    nobs = np.zeros((nclust, nclust))
    for i in range(nclust):
        for j in range(nclust):
            ix = np.ix_(clustmembers[i], clustmembers[j])
            yobs[i, j] = np.sum(R[:, :, 0][ix])
            nobs[i, j] = np.sum(R[:, :, 1][ix])
    clustgraph = np.asarray(graph.adjcluster, dtype=float)
    edgeones = find_F(clustgraph)
    edgezeros = find_F(1 - clustgraph)
    lowdiag = data.get("lowdiag")
    if lowdiag:
        if np.sum(np.diag(R[:, :, 1])) > 0:
            raise FormDiscoveryError("data not lower diagonal!")
        eps = np.finfo(float).eps
        doubgraph = clustgraph + clustgraph.T
        doubgraph = doubgraph + eps * np.tril(np.ones(clustgraph.shape), -1)
        nopreds = find_F((doubgraph == 0) | (doubgraph == 2))
        diagind = np.arange(nclust) * (nclust + 1)
        nopredys = yobs.ravel(order="F").copy()
        nopredns = nobs.ravel(order="F").copy()
        nopredys[diagind] = nopredys[diagind] / 2
        nopredns[diagind] = nopredns[diagind] / 2
        yobsnopreds, nobsnopreds = nopredys[nopreds], nopredns[nopreds]
        lognopredI = 0.0
        if np.any(nobsnopreds > 0):
            lognopredI = bblikesumhyps(yobsnopreds, nobsnopreds, alphasnoedge, betasnoedge)
        tmp = (clustgraph + eps * np.tril(np.ones(clustgraph.shape))).ravel(order="F")
        tmp[nopreds] = tmp[nopreds] + eps
        edgeones = np.flatnonzero(tmp == 1)
        edgezeros = np.flatnonzero(tmp == 0)
        yf = yobs.ravel(order="F")
        yf[edgezeros] = nobs.ravel(order="F")[edgezeros] - yf[edgezeros]
        yobs = yf.reshape(yobs.shape, order="F")
        edgeones = np.concatenate([edgezeros, edgeones])
        edgezeros = np.zeros(0, dtype=np.int64)
    yf, nf = yobs.ravel(order="F"), nobs.ravel(order="F")
    ysones, nsones = yf[edgeones], nf[edgeones]
    yszeros, nszeros = yf[edgezeros], nf[edgezeros]
    logI1 = logI2 = 0.0
    if np.any(nsones > 0):
        logI1 = bblikesumhyps(ysones, nsones, alphas, betas)
    if np.any(nszeros > 0):
        logI2 = bblikesumhyps(yszeros, nszeros, alphas, betas)
    logI = logI1 + logI2
    if lowdiag:
        logI = logI + lognopredI
    return logI


def graph_like_rel(data, graph, ps):
    """``graph_like_rel.m:1-163``: ``log p(data | graph)`` for relational data. Returns
    ``(logI, graph)``; the graph is the input graph, unchanged (l.162).

    ``data`` is a dict with ``R`` and ``type`` (``io.load_dataset``); ``'reldom'`` data
    also need ``lowdiag``. Order, domtree and connected graphs are first filled out
    (:func:`formdiscovery.graph.filloutrelgraph`, l.8-13). For ``'relbin'``/``'relfreq'``
    (l.102-155) the pair counts per cluster pair are ``s_i s_j`` off the diagonal and
    ``s_i^2 - s_i`` on it (no self links), where ``s`` counts the assigned objects
    (``z >= 0``) per cluster. Forms in ``_SELF`` get links within every cluster, forms in
    ``_UNDIR`` a symmetrised cluster graph. The hyperparameter grids come from
    ``ps.edgesumsteps``, ``ps.edgeoffset`` and ``ps.edgesumlambda``. Any other data type
    raises 'unknown relational type'; an infinite or NaN ``logI`` raises
    ``FormDiscoveryError`` (the ``keyboard`` of l.160).
    """
    origgraph = graph
    if graph.type in _FILLOUT:
        graph = filloutrelgraph(graph)
    nobj = graph.objcount
    nclust = np.atleast_2d(graph.adj).shape[0] - nobj
    z = np.asarray(graph.z).ravel()
    clustmembers = [np.flatnonzero(z == i) for i in range(nclust)]
    dtype = data["type"]
    if dtype == "reldom":
        logI = _reldom(data, graph, clustmembers, nclust)
    elif dtype in ("relfreq", "relbin"):
        zz = z[z >= 0]
        classsizes = hist_centres(zz + 1, np.arange(1, nclust + 1))
        sizematrix = classsizes[None, :] * classsizes[:, None]
        diagind = np.arange(nclust)
        sizematrix[diagind, diagind] = sizematrix[diagind, diagind] - classsizes
        adjcluster = np.array(graph.adjcluster, dtype=float)
        if graph.type in _SELF:
            adjcluster[diagind, diagind] = 1
        if graph.type in _UNDIR:
            adjcluster = ((adjcluster != 0) | (adjcluster.T != 0)).astype(float)
        g2 = graph.copy()
        g2.adjcluster = adjcluster
        countvec = countmatrix(data["R"], g2).ravel(order="F")
        adjvec = adjcluster.ravel(order="F")
        sizevec = sizematrix.ravel(order="F")

        edgepropsteps = 5
        edgesums = float(ps.edgesumlambda) ** np.arange(ps.edgeoffset + 1,
                                                        ps.edgeoffset + ps.edgesumsteps + 1)
        edgeprops = (np.arange(edgepropsteps + 1, 2 * edgepropsteps + 1) / (2 * edgepropsteps)
                     - 1 / (4 * edgepropsteps))
        alphasedge, betasedge = makehyps(edgeprops, edgesums)
        # l.132-133 also build alphasnoedge/betasnoedge, which nothing reads
        edgepropsteps = 10
        mags = edgesums
        thetas = np.arange(1, edgepropsteps + 1) / edgepropsteps - 1 / (2 * edgepropsteps)
        if dtype == "relbin":
            logI = rellikebin(countvec, adjvec, sizevec, mags, thetas)
        else:
            logI = rellikefreqs(countvec, adjvec, sizevec, alphasedge, betasedge)
    else:
        raise FormDiscoveryError("unknown relational type")
    if np.isinf(logI) or np.isnan(logI):
        raise FormDiscoveryError("graph_like_rel: logI is inf or NaN")
    return float(logI), origgraph
