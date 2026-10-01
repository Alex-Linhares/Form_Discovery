"""Priors on edge weights (PLAN.md §5, item 07) and the weight-vector <-> graph maps
``mat2vec``, ``combineWs`` and ``extract_weights`` (item 15, L2-b2).

``weightprior`` is pinned against Octave by ``legacy/tests_octave/fx_util.m`` →
``tests/fixtures/util.mat`` (``tests/test_util.py``); the weight maps by
``legacy/tests_octave/fx_weights.m`` → ``tests/fixtures/weights.mat`` (``tests/test_weights.py``).

All three walk MATLAB matrices in **column-major** order (``A(find(M))``, ``A(M)``); here
every such read or write goes through ``ravel(order="F")``. Weight and gradient vectors
are 1-D arrays (MATLAB columns). The tying modes are ``ps.fixedall``,
``ps.fixedinternal``, ``ps.fixedexternal`` and ``ps.prodtied`` (``defaultps.m:54-57``).
"""

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import find_F, stable_argsort
from .util import matlab_reduce, matrixpartition

__all__ = ["weightprior", "mat2vec", "combineWs", "extract_weights"]


def weightprior(w, beta):
    """``weightprior.m:7``: log prior of the edge weights ``w`` under an exponential prior
    (rate ``beta``) on ``1/w``, expressed in log-weight space::

        lp = sum(-log(beta) - 2*log(w) - 1./(beta*w) + log(w))

    A vector (or scalar) ``w`` gives a float; empty ``w`` gives 0 (MATLAB ``sum([])``).
    Callers: ``dataprobwsig.m:26,84-85,92``.
    """
    w = np.asarray(w, dtype=float)
    return matlab_reduce(np.sum, -np.log(beta) - 2 * np.log(w) - 1.0 / (beta * w) + np.log(w))


def _F(A):
    """Column-major flattening (MATLAB ``A(:)``)."""
    return np.asarray(A).ravel(order="F")


def _mask_F(M):
    """Column-major linear indices of the nonzeros of ``M`` (MATLAB ``find(M)``)."""
    return find_F(np.atleast_2d(np.asarray(M)))


def _take(v, n, where):
    """MATLAB ``v(1:n)``: an error (not a silent truncation) when ``v`` is too short."""
    if len(v) < n:
        raise FormDiscoveryError(f"{where}: index ({n}) out of bound {len(v)}")
    return v[:n]


def _assign(dst, idx, vals, where):
    """MATLAB ``dst(idx) = vals`` on a flat array: lengths must agree, except that a
    scalar ``vals`` is broadcast (a nonconformant assignment raises)."""
    vals = np.asarray(vals, dtype=float).ravel()
    if len(vals) != len(idx) and len(vals) != 1:
        raise FormDiscoveryError(
            f"{where}: =: nonconformant arguments (op1 is 1x{len(idx)}, op2 is {len(vals)}x1)")
    dst[idx] = vals


def _sum(x):
    return float(np.sum(x)) if np.size(x) else 0.0


def mat2vec(W, graph, ps):
    """``mat2vec.m:1-50``: the weight vector ``V`` (1-D) of graph ``graph`` with weight
    matrix ``W`` (``nobj + N`` square; ``graph_like_conn.m:14,41`` passes the log-weight
    ``graph.Wsym``).

    - ``fixedall``: ``[log(extlen)]``. ``fixedexternal`` and ``fixedinternal``:
      ``[log(extlen)]`` when ``adjcluster`` has no edge, else ``log([extlen, intlen])``.
    - Otherwise, with ``A B; C D = W`` and ``mA mB; mC mD = graph.adjsym``
      (``matrixpartition``): the leaf weights ``C[mC]`` (cluster x object block,
      column-major, i.e. one per object in object order) and the cluster weights
      ``Dvec``. ``Dvec`` is ``D`` on the strict lower triangle of ``mD`` (column-major;
      empty for one cluster) or, with ``prodtied``, the concatenation over components of
      ``comp.Wsym`` on the strict lower triangle of ``comp.adjsym``, skipping components
      whose ``Wsym`` sums to 0. The result is ``[log(extlen), Dvec]`` (``fixedexternal``),
      ``[C[mC], log(intlen)]`` (``fixedinternal``; no ``intlen`` without cluster edges)
      or ``[A[tril(mA)], C[mC], Dvec]``.

    Replicated quirk (KI-18): the ``prodtied`` ``Dvec`` reads ``comp.Wsym``, which
    ``graph_like_conn`` does not log-transform, so it holds raw weights where every other
    entry is a log weight. The row-``C`` transpose of ``mat2vec.m:38-40`` does not change
    linear indexing and is omitted.
    """
    if ps.fixedall:
        return np.array([np.log(float(graph.extlen))])
    if ps.fixedexternal and ps.fixedinternal and np.sum(graph.adjcluster) == 0:
        return np.array([np.log(float(graph.extlen))])
    if ps.fixedexternal and ps.fixedinternal:
        return np.log(np.array([graph.extlen, graph.intlen], dtype=float))

    nobj = int(graph.objcount)
    A, B, C, D = matrixpartition(np.asarray(W, dtype=float), nobj)
    mA, mB, mC, mD = matrixpartition(graph.adjsym, nobj)
    mA = np.tril(mA, -1)

    if ps.prodtied:
        parts = []
        for comp in graph.components:
            Wc = np.atleast_2d(np.asarray(comp.Wsym, dtype=float))
            mW = np.tril(np.atleast_2d(comp.adjsym), -1) != 0
            if np.sum(Wc) > 0:
                parts.append(_F(Wc)[_F(mW)])
        Dvec = np.concatenate(parts) if parts else np.empty(0)
    else:
        if mD.shape[0] == 1:
            Dvec = np.empty(0)
        else:
            Dvec = _F(D)[_F(np.tril(mD, -1) != 0)]

    Cvec = _F(C)[_mask_F(mC)]
    if ps.fixedexternal:
        return np.concatenate([[np.log(float(graph.extlen))], Dvec])
    if ps.fixedinternal and np.sum(graph.adjcluster) == 0:
        return Cvec
    if ps.fixedinternal:
        return np.concatenate([Cvec, [np.log(float(graph.intlen))]])
    return np.concatenate([_F(A)[_mask_F(mA)], Cvec, Dvec])


def combineWs(graph, Wvec, ps):
    """``combineWs.m:1-83``: fill in the weights of ``graph`` from the weight vector
    ``Wvec`` (1-D, raw weights; ``dataprobwsig.m:80``, ``graph_like_conn.m:101``). The
    topology does not change. Returns a new :class:`~formdiscovery.graph.Graph`; MATLAB's
    second output ``ps`` is returned unchanged there and is dropped.

    ``Wvec`` is read as ``[extlen]`` (``fixedall``, also used as ``intlen``),
    ``[extlen, intlen]`` (``fixedexternal`` and ``fixedinternal``; ``intlen = 1`` without
    cluster edges), ``[extlen, internal...]`` (``fixedexternal``),
    ``[leaf x nobj, intlen]`` (``fixedinternal``) or ``[leaf x nobj, internal...]``.
    ``extlen``/``intlen`` are stored (0 when not read).

    Internal weights (neither ``fixedinternal`` nor ``fixedall``): without ``prodtied``
    they fill the strict lower triangle of ``adjclustersym`` column-major and are
    symmetrised (and copied into the component's ``Wsym``/``W`` when ``ncomp == 1``).
    With ``prodtied`` each component takes the next ``comp.edgecountsym`` entries
    ``Ws``: the combined ``W`` gets ``Ws[e - 1]`` wherever ``comp.edgemapsym`` holds edge
    number ``e`` (later components overwrite), and ``comp.Wsym`` gets ``Ws`` on the strict
    lower triangle of ``comp.adjsym`` (symmetrised), ``comp.W = comp.adj * comp.Wsym``.
    Tied internal weights: ``W = intlen * adjclustersym``. Then ``Wclustersym = W``,
    ``Wcluster = adjcluster * W``.

    External weights (``leafweights``, or ``extlen`` everywhere when ``fixedexternal`` or
    ``fixedall``) go to row ``nobj + z[o]``, column ``o`` of ``Wsym`` for each observed
    object ``o`` (``z >= 0``; ``graph.z`` may hold -1 for unassigned objects, but the
    columns are always ``0..nobj-1``). The transposed entries are copied where ``adj.T``
    is set, the cluster block is ``Wclustersym``; ``W`` is ``Wsym`` on ``adj``, and
    ``leaflengths[z >= 0] = leafweights``.

    MATLAB errors (too short ``Wvec``, nonconformant assignments, observed objects not
    equal to ``objcount``) raise :class:`FormDiscoveryError`; a length-1 right-hand side
    is broadcast as in MATLAB.
    """
    graph = graph.copy()
    Wvec = np.asarray(Wvec, dtype=float).ravel()
    where = "combineWs"
    nobj = int(graph.objcount)
    z = np.asarray(graph.z, dtype=np.int64).ravel()
    zobs = z[z >= 0]
    if len(zobs) != nobj:
        raise FormDiscoveryError(f"{where}: {len(zobs)} observed objects for objcount {nobj}")
    adjcluster = np.atleast_2d(np.asarray(graph.adjcluster, dtype=float))
    nclust = adjcluster.shape[0]
    has_int = np.sum(adjcluster) != 0

    extlen = 0.0
    intlen = 0.0
    leafweights = None
    if ps.fixedall:
        extlen = intlen = float(_take(Wvec, 1, where)[0])
    elif ps.fixedexternal and ps.fixedinternal:
        extlen = float(_take(Wvec, 1, where)[0])
        intlen = float(_take(Wvec, 2, where)[1]) if has_int else 1.0
    elif ps.fixedexternal:
        extlen = float(_take(Wvec, 1, where)[0])
        Wvec = Wvec[1:]
    elif ps.fixedinternal:
        leafweights = _take(Wvec, nobj, where)
        intlen = float(_take(Wvec, nobj + 1, where)[nobj]) if has_int else 1.0
    else:
        leafweights = _take(Wvec, nobj, where)
        Wvec = Wvec[nobj:]
    graph.extlen = extlen
    graph.intlen = intlen

    # set up internal lengths
    adjclustersym = np.atleast_2d(np.asarray(graph.adjclustersym, dtype=float))
    if not ps.fixedinternal and not ps.fixedall:
        if ps.prodtied:
            Wf = np.zeros(nclust * nclust)
            for comp in graph.components:
                k = int(comp.edgecountsym)
                Ws = _take(Wvec, k, where)
                Wvec = Wvec[k:]
                emap = np.atleast_2d(np.asarray(comp.edgemapsym))
                idx = _mask_F(emap)
                edgeinds = _F(emap)[idx].astype(np.int64)
                if np.any(edgeinds > k):
                    raise FormDiscoveryError(f"{where}: index ({edgeinds.max()}) out of bound {k}")
                Wf[idx] = Ws[edgeinds - 1]
                cadjsym = np.atleast_2d(np.asarray(comp.adjsym, dtype=float))
                localW = np.tril(cadjsym, -1)
                lf = _F(localW).copy()
                _assign(lf, np.flatnonzero(lf != 0), Ws, where)
                localW = lf.reshape(localW.shape, order="F")
                comp.Wsym = localW + localW.T
                comp.W = np.atleast_2d(np.asarray(comp.adj, dtype=float)) * comp.Wsym
            W = Wf.reshape((nclust, nclust), order="F")
        else:
            W = np.tril(adjclustersym, -1)
            wf = _F(W).copy()
            _assign(wf, np.flatnonzero(wf != 0), Wvec, where)
            W = wf.reshape(W.shape, order="F")
            W = W + W.T
            if graph.ncomp == 1:
                # shouldn't need this once we deal with untied products properly (MATLAB)
                c0 = graph.components[0]
                c0.Wsym = W.copy()
                c0.W = W * np.atleast_2d(np.asarray(c0.adj, dtype=float))
    else:
        W = intlen * adjclustersym
    graph.Wclustersym = W
    graph.Wcluster = adjcluster * W

    # set up external lengths
    if ps.fixedexternal or ps.fixedall:
        leafweights = extlen * np.ones(nobj)
    n = nclust + nobj
    fullW = np.zeros((n, n))
    rows = nobj + zobs
    if np.any(rows >= n):
        raise FormDiscoveryError(f"{where}: sub2ind: index out of range")
    fl = _F(fullW).copy()
    _assign(fl, rows + n * np.arange(nobj), leafweights, where)
    fullW = fl.reshape((n, n), order="F")
    adj = np.asarray(graph.adj, dtype=bool)
    fullWtr = fullW.T.copy()
    fullW[adj.T] = fullWtr[adj.T]
    fullW[nobj:, nobj:] = graph.Wclustersym
    graph.Wsym = fullW
    graph.W = np.zeros((n, n))
    graph.W[adj] = fullW[adj]
    obs = z >= 0
    ll = np.asarray(graph.leaflengths, dtype=float).ravel()
    if len(ll) < len(z):  # MATLAB grows the array on a logical-index assignment
        ll = np.concatenate([ll, np.zeros(len(z) - len(ll))])
    else:
        ll = ll.copy()
    ll[:len(z)][obs] = leafweights
    graph.leaflengths = ll
    return graph


def extract_weights(dEdlWa, dEdlWb, dEdlWbprior, dEdlWddata, dEdlWdprior, graph, ps):
    """``extract_weights.m:1-89``: collect the gradient of ``-log P`` with respect to the
    entries of the weight vector (``mat2vec`` order) from the gradient matrices
    (``dataprobwsig.m:137,214``). ``dEdlWb``/``dEdlWbprior`` are ``nobj x N`` (object x
    cluster), ``dEdlWddata``/``dEdlWdprior`` ``N x N``; ``dEdlWa`` is unused. Returns
    ``(dWvec, dWvecprior)``, 1-D (length 1 for ``fixedall``).

    With ``mB``/``mC``/``mD`` the blocks of ``graph.adjsym``: ``Bvec`` is the data + prior
    gradient of the leaf edges (``dEdlWb.T`` on ``mC``, column-major), ``dext`` the data
    gradient on ``mB``, ``dint`` the symmetrised (``X + X.T - diag``) data gradient on the
    strict lower triangle of ``mD`` (empty for one cluster); ``extcount = nnz(mB)``,
    ``intcount = 2 * nnz(tril(mD, -1))``.

    - ``fixedall``: one entry, prior averaged over ``extcount + intcount`` plus the summed
      data gradient.
    - ``fixedexternal`` and ``fixedinternal``: ``[ext]`` or ``[ext, int]`` (no ``int``
      when ``intcount == 0``), priors averaged.
    - ``fixedinternal``: the leaf entries (data + prior, as ``Bvec``) and, when
      ``intcount > 0``, one tied internal entry (summed data, averaged prior).
    - Otherwise the cluster entries ``Dvec``: with ``prodtied``, per component, the
      *unsymmetrised* data gradient summed and the prior averaged over the cells holding
      each edge number of ``comp.edgemapsym`` (sorted-cumsum-diff, as MATLAB);
      without, ``dint + dintprior / 2``. The result is ``[ext, Dvec...]``
      (``fixedexternal``) or ``[Bvec..., Dvec...]``.
    """
    nobj = int(graph.objcount)
    nclust = np.atleast_2d(graph.adjcluster).shape[0]
    Wb = np.atleast_2d(np.asarray(dEdlWb, dtype=float))
    Wbp = np.atleast_2d(np.asarray(dEdlWbprior, dtype=float))
    Wd = np.atleast_2d(np.asarray(dEdlWddata, dtype=float))
    Wdp = np.atleast_2d(np.asarray(dEdlWdprior, dtype=float))
    eye = np.eye(nclust)
    dsym = Wd + Wd.T - eye * Wd
    dpsym = Wdp + Wdp.T - eye * Wdp

    mA, mB, mC, mD = matrixpartition(graph.adjsym, nobj)
    # Bvec should be leafweights in order (the row-vector transpose of l.17-20 does not
    # change linear indexing)
    iC = _mask_F(mC)
    Wc, Wcp = _F(Wb.T), _F(Wbp.T)
    Bvec = Wc[iC] + Wcp[iC]
    Bvecprior = Wcp[iC]
    mB = _F(mB != 0)
    mDl = np.zeros(0, dtype=bool) if mD.shape[0] == 1 else _F(np.tril(mD, -1) != 0)

    # we need to consider forward and backward edges even though the matrix is symmetric
    extcount = int(np.sum(mB))
    intcount = 2 * int(np.sum(mDl))
    dext, dextprior = _F(Wb)[mB], _F(Wbp)[mB]
    if len(mDl):
        dint, dintprior = _F(dsym)[mDl], _F(dpsym)[mDl]
    else:
        dint = dintprior = np.empty(0)

    with np.errstate(divide="ignore", invalid="ignore"):
        if ps.fixedall:
            prior = np.float64(_sum(dextprior) + _sum(dintprior)) / (extcount + intcount)
            return np.array([prior + _sum(dext) + _sum(dint)]), np.array([prior])
        if ps.fixedexternal and ps.fixedinternal:
            if intcount == 0:
                prior = np.array([np.float64(_sum(dextprior)) / extcount])
                return prior + _sum(dext), prior
            prior = np.array([np.float64(_sum(dextprior)) / extcount,
                              np.float64(_sum(dintprior)) / intcount])
            return prior + np.array([_sum(dext), _sum(dint)]), prior
        if ps.fixedinternal:
            if intcount == 0:
                return Bvecprior + Wc[iC], Bvecprior
            prior = np.concatenate([Bvecprior, [np.float64(_sum(dintprior)) / intcount]])
            return prior + np.concatenate([Wc[iC], [_sum(dint)]]), prior

        if ps.prodtied:
            Dparts, Dpparts = [], []
            for comp in graph.components:
                emap = np.atleast_2d(np.asarray(comp.edgemapsym))
                idx = _mask_F(emap)
                edgeinds = _F(emap)[idx].astype(np.int64)
                vd, vp = _F(Wd)[idx], _F(Wdp)[idx]
                sind = stable_argsort(edgeinds)
                # counts = sparse(1, edgeinds(sind), 1): 1 x max(edgeinds), summed
                counts = (np.bincount(edgeinds, minlength=1)[1:] if len(edgeinds)
                          else np.zeros(0, dtype=np.int64))
                cs = np.cumsum(counts)
                if len(cs) and cs[0] == 0:
                    raise FormDiscoveryError("extract_weights: index (0): out of bound")
                sumsdata = np.diff(np.concatenate([[0.0], np.cumsum(vd[sind])[cs - 1]]))
                sumsprior = np.diff(np.concatenate([[0.0], np.cumsum(vp[sind])[cs - 1]]))
                sumsprior = sumsprior / counts
                Dparts.append(sumsdata + sumsprior)
                Dpparts.append(sumsprior)
            Dvec = np.concatenate(Dparts) if Dparts else np.empty(0)
            Dvecprior = np.concatenate(Dpparts) if Dpparts else np.empty(0)
        else:
            Dvecprior = dintprior / 2  # D is symmetric, but only want the prior on one edge
            Dvec = dint + Dvecprior

        if ps.fixedexternal:
            ext = np.float64(_sum(dextprior)) / extcount
            return (np.concatenate([[ext + _sum(dext)], Dvec]),
                    np.concatenate([[ext], Dvecprior]))
        return np.concatenate([Bvec, Dvec]), np.concatenate([Bvecprior, Dvecprior])
