"""Feature-data likelihoods (PLAN.md §5).

Item 08 (L0-b) adds ``hessiangrad``, pinned by ``tests/octave/fx_l0b.m`` →
``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``). Item 16 (L3-a1) adds
``inv_covariance``, ``gplike`` and ``dataprobwsig`` without the missing-data chunk path,
pinned by ``tests/octave/fx_dataprob.m`` → ``tests/fixtures/dataprob.mat``
(``tests/test_dataprob.py``). Item 17 (L3-a2) adds the missing-data chunk path
(``dataprobwsig.m:24-60``), pinned by ``tests/octave/fx_dpmiss.m`` →
``tests/fixtures/dpmiss.mat`` (``tests/test_dpmiss.py``). Item 18 (L3-b1) adds ``graph_like_conn`` in fast mode,
pinned by ``tests/octave/fx_graphlike.m`` → ``tests/fixtures/graphlike.mat``
(``tests/test_graphlike.py``); slow mode is item 19.

Matrix products keep MATLAB's left-to-right order, so rounding is close to Octave's.
MATLAB errors (non-positive-definite ``chol``, out-of-bound reads, nonconformant
products) raise :class:`~formdiscovery.FormDiscoveryError`.
"""

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import stable_argsort
from .util import inv_posdef, logdet, matrixpartition, triplepartition, vec
from .weights import combineWs, extract_weights, mat2vec, weightprior
from .graph import reordermissing

__all__ = ["hessiangrad", "inv_covariance", "gplike", "dataprobwsig", "graph_like_conn"]


def hessiangrad(f, X, e, *args):
    """``hessiangrad.m:15-25``: finite-difference Hessian from central differences of the
    gradient.

    ``f(X, *args)`` returns ``(value, gradient)`` (MATLAB ``[Y dY] = feval(f, X, ...)``);
    the gradient is a vector of either orientation, flattened with ``vec``. Column ``j``
    of the result is ``(g(X + e*u_j) - g(X - e*u_j)) / (2e)``. Returns a
    ``length(g) x len(X)`` array (not symmetrised, as in MATLAB). As in MATLAB the row
    count is ``length(dY)`` (largest dimension), so a matrix-shaped gradient fails on
    assignment (``ValueError`` here, a nonconformant-arguments error in MATLAB). Caller:
    ``graph_like_conn.m:81`` (``H = -hessiangrad(datal, X, 1e-5)``).
    """
    X = np.asarray(X, dtype=float).ravel()
    Y, dY = f(X, *args)
    H = np.zeros((max(np.shape(dY), default=1), len(X)))  # MATLAB length(dY)
    for j in range(len(X)):
        dX = np.zeros(len(X))
        dX[j] = dX[j] + e  # perturb a single dimension
        Y1, dY1 = f(X + dX, *args)
        dX = -dX
        Y2, dY2 = f(X + dX, *args)
        H[:, j] = vec(np.asarray(dY1, dtype=float) - np.asarray(dY2, dtype=float)) / (2 * e)
    return H


def inv_covariance(W, nobj, sigma, ps):
    """``inv_covariance.m:1-26``: the inverse covariance ``J = L + P`` of the Gaussian over
    graph ``W`` (Zhu, Ghahramani and Lafferty). ``L = diag(sum(W, 2)) - W`` is the graph
    Laplacian; ``P`` is ``1/sigma^2`` on the diagonal of the first ``nobj`` nodes (all nodes
    when ``ps.zglreg``). Returns ``(J, L)``.

    The 'holes' hack (l.24-26) is replicated: for the nodes whose column of ``W`` has no
    nonzero entry, the whole block ``J(holes, holes)`` is set to 1, so two or more holes
    make ``J`` singular (``chol`` then fails in the caller). ``nobj > size(W, 1)`` raises
    (MATLAB grows ``P`` and then fails on ``L + P``).
    """
    W = np.atleast_2d(np.asarray(W, dtype=float))
    n = W.shape[0]
    nobj = int(nobj)
    D = np.diag(np.sum(W, axis=1))
    L = D - W
    # prior on object nodes
    if ps.zglreg:
        P = 1 / sigma ** 2 * np.eye(n)
    else:
        if nobj > n:
            raise FormDiscoveryError(
                f"inv_covariance: operator +: nonconformant arguments (op1 is {n}x{n}, "
                f"op2 is {nobj}x{nobj})")
        P = np.zeros((n, n))
        P[:nobj, :nobj] = 1 / sigma ** 2 * np.eye(nobj)
    # inverse covariance
    J = L + P
    # identify holes -- a hack to deal with orphaned cluster nodes lying around (MATLAB)
    holes = np.flatnonzero(np.sum(W != 0, axis=0) == 0)
    J[np.ix_(holes, holes)] = 1
    return J, L


def _chunkcount_is(ps, n):
    cc = ps.runps.chunkcount
    return cc is not None and np.size(cc) == 1 and float(np.asarray(cc).ravel()[0]) == n


def gplike(X, G, dim, ps):
    """``gplike.m:1-26``: log probability of the data ``X`` (one object per row, zero
    mean) under a Gaussian with covariance ``G``; only ``G(1:nobj, 1:nobj)`` is used,
    ``nobj = size(X, 1)``.

    Similarity data (``ps.runps.type == 'sim'``): ``X`` is the similarity matrix and
    ``dim`` the number of features it stands for. Feature data: with
    ``nobj == ps.runps.chunkcount`` and ``ps.overrideSS == 0`` the scatter matrix is
    ``nfeat * ps.runps.SS`` (l.45-46), otherwise ``X @ X.T``; ``dim`` is not used.
    """
    X = np.atleast_2d(np.asarray(X, dtype=float))
    G = np.atleast_2d(np.asarray(G, dtype=float))
    nobj = X.shape[0]
    if nobj > G.shape[0]:
        raise FormDiscoveryError(
            f"gplike: G({nobj},_): out of bound {G.shape[0]} "
            f"(dimensions are {G.shape[0]}x{G.shape[1]})")
    Gsmall = G[:nobj, :nobj]
    invGsmall = inv_posdef(Gsmall)
    logdetGsmall = logdet(Gsmall)
    if ps.runps.type == "sim":  # similarity data
        ll = dim * (-0.5 * logdetGsmall - nobj / 2 * np.log(2 * np.pi))
        ll = ll - 0.5 * np.trace(dim * X @ invGsmall)
    else:
        nfeat = X.shape[1]
        if _chunkcount_is(ps, nobj) and ps.overrideSS == 0:
            XX = nfeat * np.atleast_2d(np.asarray(ps.runps.SS, dtype=float))
        else:
            XX = X @ X.T
        ll = nfeat * (-0.5 * logdetGsmall - nobj / 2 * np.log(2 * np.pi))
        ll = ll - 0.5 * np.trace(XX.T @ invGsmall)
    return float(ll)


def _mm(*mats):
    """MATLAB ``A*B*...`` (left to right); nonconformant shapes raise as in MATLAB."""
    out = mats[0]
    for m in mats[1:]:
        if np.ndim(out) == 0 or np.ndim(m) == 0:
            out = out * m
            continue
        if out.shape[1] != m.shape[0]:
            raise FormDiscoveryError(
                f"dataprobwsig: operator *: nonconformant arguments (op1 is "
                f"{out.shape[0]}x{out.shape[1]}, op2 is {m.shape[0]}x{m.shape[1]})")
        out = out @ m
    return out


def _ew(a, b, where="dataprobwsig"):
    """Shape check for MATLAB elementwise ``+ - .*`` (Octave broadcasts only 1-sized
    dimensions; the operands here are never broadcast in practice)."""
    for x, y in zip(a.shape, b.shape):
        if x != y and x != 1 and y != 1:
            raise FormDiscoveryError(
                f"{where}: operator: nonconformant arguments (op1 is {a.shape[0]}x{a.shape[1]}, "
                f"op2 is {b.shape[0]}x{b.shape[1]})")


def _diagtr(c):
    """MATLAB ``diag(c)'`` of a square matrix as a 1 x k row (0 x 0 for an empty one)."""
    return np.diag(c)[None, :] if c.size else np.zeros((0, 0))


def _diagcol(c):
    return np.diag(c)[:, None] if c.size else np.zeros((0, 0))


def _noz(w):
    w = w.copy()
    w[w == 0] = 1
    return w


def _dprior(wtr, beta, pk):
    """``(-pk./w + 1./(beta*w.^2) + 1./w).*w`` (dataprobwsig.m:124-125 and alike)."""
    return (-pk / wtr + 1 / (beta * wtr ** 2) + 1 / wtr) * wtr


def _lin(a, op, b):
    _ew(a, b)
    return a + b if op == "+" else a - b


def dataprobwsig(Wvec, d, graph, ps, nargout=3):
    """``dataprobwsig.m:1-241``: ``-log(P(d | Wvec, graph) P(Wvec))`` for feature or
    similarity data ``d``, and its gradient with respect to the log weights ``Wvec``.

    ``Wvec`` (1-D) holds log weights: ``Wvec[0]`` is ``log(sigma)``, the rest are in
    ``mat2vec`` order (``combineWs`` reads ``exp(Wvec[1:])``). The priors are
    ``weightprior`` with ``ps.lbeta`` (edges) and ``ps.sigbeta`` (sigma), ``pk = 2``.
    The scatter matrix ``SS`` is ``d`` for ``ps.runps.type == 'sim'`` (``dim =
    ps.runps.dim``), ``ps.runps.SS`` when ``size(d, 1) == ps.runps.chunkcount``, else
    ``d @ d.T / size(d, 2)``.

    Returns ``ll`` (``nargout == 1``), ``(ll, dWvec)`` (``nargout == 2``) or ``(ll,
    dWvec, dWvecprior)``, the gradient (1-D, length ``len(Wvec)``) and its prior part. The rows of ``d`` are the first
    ``nobs = size(d, 1)`` objects. ``nobs == graph.objcount`` uses the two-block partition
    (l.96-154); otherwise the remaining ``nmiss = objcount - nobs`` objects are
    unobserved and the three-block partition is used (l.155-236, as the chunk path's
    recursive call does after ``reordermissing``). Replicated: l.179's ``U`` is computed
    and then overwritten (l.180), and the sigma gradient leaves out ``trace(c3)``/
    ``trace(c5)`` unless ``ps.zglreg`` ("as of August 19"). A NaN gradient raises
    (l.237-239, ``keyboard`` in the original).

    With ``ps.missingdata`` the chunk loop (l.24-60) runs instead, see
    :func:`_dataprob_chunks`.
    """
    logWvec = np.asarray(Wvec, dtype=float).ravel()  # noqa: F841  (as MATLAB, unused)
    Wvec = np.exp(logWvec)
    # wbeta: parameter for exponential prior on branch lengths
    # sigbeta: parameter for exponential prior on inverse sigma
    wbeta, sigbeta = ps.lbeta, ps.sigbeta
    pk = 2  # 2 for exponential: 3 for gamma shape 2

    if ps.missingdata:
        return _dataprob_chunks(Wvec, d, graph, ps, nargout, wbeta, sigbeta)

    d = np.atleast_2d(np.asarray(d, dtype=float))
    if ps.runps.type == "sim":
        dim = ps.runps.dim
        SS = d
    elif _chunkcount_is(ps, d.shape[0]):
        dim = d.shape[1]
        SS = np.atleast_2d(np.asarray(ps.runps.SS, dtype=float))
    else:
        dim = d.shape[1]
        SS = 1 / dim * d @ d.T

    nobs = d.shape[0]
    nobj = int(graph.objcount)
    nmiss = nobj - nobs
    nlat = np.atleast_2d(graph.adj).shape[0] - nobj

    sigma = Wvec[0]
    graph = combineWs(graph, Wvec[1:], ps)
    J, _ = inv_covariance(graph.Wsym, nobj, sigma, ps)
    G = inv_posdef(J)
    ll = gplike(d, G, dim, ps) + weightprior(Wvec[1:], wbeta) + weightprior(sigma, sigbeta)
    # since the function is - log posterior prob
    ll = -ll
    if nargout <= 1:
        return ll

    Wsym = np.atleast_2d(np.asarray(graph.Wsym, dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        if nmiss == 0:
            dWvec, dWvecprior = _grad_observed(J, Wsym, SS, dim, nobj, nlat, sigma,
                                               wbeta, sigbeta, pk, graph, ps)
        else:
            dWvec, dWvecprior = _grad_missing(J, Wsym, SS, dim, nobs, nmiss, nlat, sigma,
                                              wbeta, sigbeta, pk, graph, ps)
    if np.sum(np.isnan(dWvec)):
        raise FormDiscoveryError("dataprobwsig: NaNs in gradient")
    if nargout == 2:
        return ll, dWvec
    return ll, dWvec, dWvecprior


def _dataprob_chunks(Wvec, d, graph, ps, nargout, wbeta, sigbeta):
    """``dataprobwsig.m:24-60``: the missing-data path. ``Wvec`` holds the weights (not
    their logs) and ``d`` the rows of the assigned objects (``z >= 0``) in object order,
    as ``graph_like.m:7-10`` passes them; ``Inf`` marks a missing value.

    For each chunk ``c`` (``ps.runps.objind[c]``/``featind[c]``, ``preprocess.makechunks``)
    the assigned objects are split into observed (``obsind``) and unobserved
    (``missind``); ``reordermissing`` moves the unobserved ones behind the observed ones,
    and ``dataprobwsig`` is called recursively (through the module-level name, so a test
    can wrap it) with ``ps.missingdata = 0``, ``ps.runps.SS = chunkSS[c]``,
    ``ps.runps.chunkcount = chunksize[c]`` on ``d[tind[:nobs], featind[c]]``. The recursive
    call therefore takes the ``nmiss > 0`` gradient branch, and uses ``chunkSS`` only when
    every observed object of the chunk is assigned (otherwise ``d*d'/dim``).

    Replicated: ``ll`` starts at ``wpriors = -(prior of Wvec)`` and each chunk adds its
    value minus ``wpriors``, so the prior is counted once. The prior gradient is kept for
    chunk 0 only (``c > 1`` in MATLAB). Unless ``ps.fixedexternal``, the leaf entries
    ``dWvecc[1:len(sind)+1]`` are put back in object order via ``sind``. MATLAB never sets
    ``dWvecprior`` on this path, so ``nargout == 3`` raises as Octave does after the loop
    (KI-21).
    """
    ps = ps.replace(missingdata=0)
    wpriors = -(weightprior(Wvec[1:], wbeta) + weightprior(Wvec[0], sigbeta))
    ll = wpriors
    dWvec = 0
    z = np.asarray(graph.z).ravel()
    theseobjs = z >= 0
    d = np.atleast_2d(np.asarray(d, dtype=float))
    r = ps.runps
    for c in range(int(r.chunknum)):
        inchunk = np.zeros(len(z), dtype=bool)
        inchunk[np.asarray(r.objind[c], dtype=np.int64)] = True
        obsind = np.flatnonzero(theseobjs & inchunk)
        missind = np.flatnonzero(theseobjs & ~inchunk)
        currobs = np.concatenate([obsind, missind])
        sind = stable_argsort(currobs)
        tind = stable_argsort(sind)

        # shuffle the missing objects for this chunk to the end of the list. We can then
        # ignore them when computing probability of the data for this chunk. (MATLAB)
        newgraph, newWvec = reordermissing(graph, Wvec, obsind, missind, ps)
        rows = tind[:len(obsind)]
        if len(rows) and rows.max() >= d.shape[0]:
            raise FormDiscoveryError(
                f"dataprobwsig: index ({rows.max() + 1},_): out of bound {d.shape[0]}")
        newdata = d[np.ix_(rows, np.asarray(r.featind[c], dtype=np.int64))]
        psc = ps.copy()
        psc.runps.SS = r.chunkSS[c]
        psc.runps.chunkcount = r.chunksize[c]
        if nargout > 1:
            llc, dWvecc, dWveccprior = dataprobwsig(np.log(newWvec), newdata, newgraph, psc)
            llc = llc - wpriors
            if c > 0:  # include dWveccprior for first chunk
                dWvecc = dWvecc - dWveccprior
            if not ps.fixedexternal:
                dWvecc = dWvecc.copy()
                dWvecc[1:len(sind) + 1] = dWvecc[sind + 1]
            dWvec = dWvec + dWvecc
        else:
            llc = dataprobwsig(np.log(newWvec), newdata, newgraph, psc, nargout=1) - wpriors
        ll = ll + llc
    if nargout <= 1:
        return ll
    if nargout == 2:
        return ll, np.atleast_1d(dWvec)
    raise FormDiscoveryError("dataprobwsig: element number 3 undefined in return list "
                             "(KI-21)")


def _grad_observed(J, Wsym, SS, dim, nobj, nlat, sigma, wbeta, sigbeta, pk, graph, ps):
    """``dataprobwsig.m:96-154``: gradient when every object is observed."""
    # partition graph because values observed only at objects
    A, B, C, D = matrixpartition(J, nobj)
    wA, wB, wC, wD = matrixpartition(Wsym, nobj)
    wBnoz, wDnoz = _noz(wB), _noz(wD)
    Btr, wBnoztr, wDnoztr = B.T, wBnoz.T, wDnoz.T

    Dinv = inv_posdef(D)
    DinvB = _mm(Dinv, Btr)
    DinvBtr = DinvB.T
    Xinv = _lin(A, "-", _mm(DinvBtr, Btr))
    X = inv_posdef(Xinv)
    XXX = _mm(X, Xinv, X)
    YY = SS
    U = dim * _lin(YY, "-", XXX)

    oneobjtr = np.ones((1, nobj))
    onelat = np.ones((nlat, 1))
    # coefficients for A, B, D
    c1 = U
    c2 = _mm(-2 * DinvB, U)
    c3 = _mm(DinvB, U, DinvBtr)
    diagc1tr = _diagtr(c1)

    # -0.5 out the front is constant from log likelihood
    t = _lin(_lin(_mm(onelat, diagc1tr), "-", c2), "+", _mm(_diagcol(c3), oneobjtr))
    _ew(t, wBnoztr)
    dEdlWb = (-0.5 * t * wBnoztr).T
    dEdlWbprior = _dprior(wBnoztr, wbeta, pk).T
    t = _lin(_mm(onelat, _diagtr(c3)), "-", c3)
    _ew(t, wDnoztr)
    dEdlWddata = -0.5 * (t * wDnoztr).T
    # keep these separate because several of the edges in D are really the same, and we
    # only want to put the prior on one of them (MATLAB)
    dEdlWdprior = _dprior(wDnoztr, wbeta, pk).T

    dEdWa = np.zeros((nobj, nobj))
    # go through Wa, Wb, Wd and pull out component weights
    dWvec, dWvecprior = extract_weights(dEdWa, dEdlWb, dEdlWbprior, dEdlWddata,
                                        dEdlWdprior, graph, ps)
    # 1 not 2 because of the constant out the front!
    if ps.zglreg:
        dEdsig = 1 / sigma ** 3 * (np.trace(c1) + np.trace(c3)) * sigma
    else:  # As of August 19 (MATLAB)
        dEdsig = 1 / sigma ** 3 * (np.trace(c1)) * sigma
    return _finish(dEdsig, sigma, sigbeta, pk, dWvec, dWvecprior)


def _grad_missing(J, Wsym, SS, dim, nobs, nmiss, nlat, sigma, wbeta, sigbeta, pk, graph,
                  ps):
    """``dataprobwsig.m:155-236``: gradient when the last ``nmiss`` objects are
    unobserved."""
    A1, A2, B1, B2, D = triplepartition(J, nobs, nmiss)
    wA1, wA2, wB1, wB2, wD = triplepartition(Wsym, nobs, nmiss)
    wB1noz, wB2noz, wDnoz = _noz(wB1), _noz(wB2), _noz(wD)

    A1inv = inv_posdef(A1)
    A2inv = inv_posdef(A2)
    A1invB1 = _mm(A1inv, B1)
    A2invB2 = _mm(A2inv, B2)
    B2tr, B1tr, A1invB1tr, A2invB2tr = B2.T, B1.T, A1invB1.T, A2invB2.T
    wB1noztr, wB2noztr, wDnoztr = wB1noz.T, wB2noz.T, wDnoz.T

    Y = _lin(_lin(D, "-", _mm(B2tr, A2inv, B2)), "-", _mm(B1tr, A1inv, B1))
    Yinv = inv_posdef(Y)
    YinvB1 = _mm(Yinv, B1tr)
    YinvB1tr = YinvB1.T
    X = _lin(A1inv, "+", _mm(A1invB1, Yinv, A1invB1tr))
    Xinv = inv_posdef(X)
    XXX = _mm(X, Xinv, X)
    YY = SS  # NB: YY and Y are unrelated (MATLAB)
    U = dim * _lin(YY, "-", XXX)  # overwritten on the next line, as in MATLAB
    U = dim * _lin(Xinv, "-", _mm(Xinv, YY, Xinv))
    A1invUA1inv = _mm(A1inv, U, A1inv)
    K = _mm(YinvB1, A1invUA1inv, YinvB1tr)

    oneobstr = np.ones((1, nobs))
    onemisstr = np.ones((1, max(nmiss, 0)))
    onelat = np.ones((nlat, 1))

    # coefficients for A1, A2, B1, B2, D
    c1 = _lin(_lin(-A1invUA1inv, "-", _mm(2 * A1invUA1inv, YinvB1tr, A1invB1tr)), "-",
              _mm(A1invB1, K, A1invB1tr))
    c2 = _mm(-A2invB2, K, A2invB2tr)
    c3 = _lin(_mm(2 * YinvB1, A1invUA1inv), "+", _mm(2 * K, A1invB1tr))
    c4 = _mm(2 * K, A2invB2tr)
    c5 = -K
    diagc1tr, diagc2tr, diagc5tr = _diagtr(c1), _diagtr(c2), _diagtr(c5)

    # -0.5 out the front is constant from log likelihood
    t = _lin(_lin(_mm(onelat, diagc1tr), "-", c3), "+", _mm(_diagcol(c5), oneobstr))
    _ew(t, wB1noztr)
    dEdlWB1 = (-0.5 * t * wB1noztr).T
    dEdlWB1prior = _dprior(wB1noztr, wbeta, pk).T
    t = _lin(_lin(_mm(onelat, diagc2tr), "-", c4), "+", _mm(_diagcol(c5), onemisstr))
    _ew(t, wB2noztr)
    dEdlWB2 = (-0.5 * t * wB2noztr).T
    dEdlWB2prior = _dprior(wB2noztr, wbeta, pk).T
    t = _lin(_mm(onelat, diagc5tr), "-", c5)
    _ew(t, wDnoztr)
    dEdlWDdata = -0.5 * (t * wDnoztr).T
    # keep these separate because several of the edges in D are really the same, and we
    # only want to put the prior on one of them (this applies to cross products) (MATLAB)
    dEdlWDprior = _dprior(wDnoztr, wbeta, pk).T

    # go through Wa, WB1, WB2, WD and pull out component weights
    dEdWa = np.zeros((nobs + nmiss, nobs + nmiss)) if nobs + nmiss > 0 else np.zeros((0, 0))
    dWvec, dWvecprior = extract_weights(dEdWa, _vcat(dEdlWB1, dEdlWB2),
                                        _vcat(dEdlWB1prior, dEdlWB2prior), dEdlWDdata,
                                        dEdlWDprior, graph, ps)
    if ps.zglreg:
        dEdsig = 1 / sigma ** 3 * (np.trace(c1) + np.trace(c2) + np.trace(c5)) * sigma
    else:  # XXX: as of August 19 2005 (MATLAB)
        dEdsig = 1 / sigma ** 3 * (np.trace(c1) + np.trace(c2)) * sigma
    return _finish(dEdsig, sigma, sigbeta, pk, dWvec, dWvecprior)


def _vcat(a, b):
    """MATLAB ``[a; b]`` (a 0 x 0 operand is skipped)."""
    parts = [x for x in (a, b) if x.size or x.shape != (0, 0)]
    if len(parts) == 2 and parts[0].shape[1] != parts[1].shape[1]:
        raise FormDiscoveryError("dataprobwsig: vertical dimensions mismatch "
                                 f"({a.shape[0]}x{a.shape[1]} vs {b.shape[0]}x{b.shape[1]})")
    return np.vstack(parts) if parts else np.zeros((0, 0))


def _finish(dEdsig, sigma, sigbeta, pk, dWvec, dWvecprior):
    """``dataprobwsig.m:148-154`` / ``228-235``: prepend the sigma entry and negate."""
    # with exponential prior on 1/sigma
    dEdsigprior = (-pk / sigma + 1 / (sigbeta * sigma ** 2) + 1 / sigma) * sigma
    dWvec = np.concatenate([[dEdsig + dEdsigprior], np.ravel(dWvec)])
    dWvecprior = np.concatenate([[dEdsigprior], np.ravel(dWvecprior)])
    # since the function is - log posterior prob
    return -dWvec, -dWvecprior


def graph_like_conn(data, graph, ps):
    """``graph_like_conn.m:1-110``: ``log P(data | graph)`` for feature or similarity data.
    Returns ``(logI, graph)``.

    Fast mode (``ps.fast == 1``, l.6-32) scores the graph's current weights without
    optimising them: ``graph.Wsym`` (where ``adjsym > 0``) and ``sigma`` are taken to logs,
    ``Xinit = [log(sigma), mat2vec(log-Wsym, graph, ps)]`` and ``logI =
    -dataprobwsig(Xinit, data, graph, ps)`` (one output, so no gradient). The returned
    graph is the input with ``Wsym`` and ``sigma`` sent through ``exp(log(.))`` as MATLAB
    does (l.29-30), so they can differ from the input by an ulp; its other fields are
    unchanged. ``dataprobwsig`` receives the log-weight graph (l.7-8), which only matters
    for the ``prodtied`` components (KI-18). The input graph is not modified.

    Slow mode (l.35-110, ``fminunc`` + Laplace approximation) is item 19 and raises
    ``NotImplementedError``.
    """
    graph = graph.copy()
    # convert to log weights
    Wsym = np.array(np.atleast_2d(graph.Wsym), dtype=float)
    mask = np.atleast_2d(np.asarray(graph.adjsym)) > 0
    with np.errstate(divide="ignore"):
        Wsym[mask] = np.log(Wsym[mask])
        graph.sigma = np.log(float(graph.sigma))
    graph.Wsym = Wsym

    # FAST MODE
    if getattr(ps, "fast", None) == 1:  # don't optimize branch lengths
        Xinit = mat2vec(graph.Wsym, graph, ps)
        Xinit = np.concatenate([[graph.sigma], Xinit])
        logI = -dataprobwsig(Xinit, data, graph, ps, nargout=1)
        # convert back to original weights
        Wsym = graph.Wsym.copy()
        Wsym[mask] = np.exp(Wsym[mask])
        graph.Wsym = Wsym
        graph.sigma = np.exp(graph.sigma)
        return logI, graph

    raise NotImplementedError("graph_like_conn: slow mode (fminunc + Laplace) is item 19")
