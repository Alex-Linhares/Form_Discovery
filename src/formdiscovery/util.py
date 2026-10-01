"""L0-a numeric and index utilities (PLAN.md §5, item 07).

Faithful ports of the small helper files of formdiscovery1.0 (several from Tom Minka's
lightspeed toolbox and Kevin Murphy's BNT). Indices are 0-based (``CONVENTIONS.md``);
vectors are 1-D arrays. Pinned against Octave by ``legacy/tests_octave/fx_util.m`` →
``tests/fixtures/util.mat`` (``tests/test_util.py``); ``stirling2`` and ``dijkstra`` (item 08)
by ``legacy/tests_octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``). ``weightprior`` lives in
:mod:`formdiscovery.weights`.
"""

import numpy as np
import scipy.linalg

from . import FormDiscoveryError
from .matlab_compat import chol_upper, mysetdiff  # noqa: F401  (mysetdiff.m lives there)

__all__ = [
    "vec", "inv_triu", "inv_posdef", "logdet", "inv_posdef_logdet", "mylogdet", "sumlogs", "meanlogs",
    "mysetdiff", "subv2ind", "trans2orig", "matrixpartition", "triplepartition",
    "stirling2", "dijkstra",
]


def matlab_reduce(f, X):
    """Apply a MATLAB column reduction (``sum``, ``mean``) the way MATLAB picks the
    dimension: a vector (any orientation) or scalar reduces to a scalar, a matrix reduces
    each column to a 1-D array. ``f`` is a numpy reduction taking ``axis``."""
    X = np.asarray(X, dtype=float)
    if X.ndim <= 1 or min(X.shape) == 1 or X.size == 0:
        return float(f(X.ravel()))
    return f(X, axis=0)


def vec(a):
    """``vec.m`` (whole file): ``a(:)``, i.e. column-major flattening, as a 1-D array."""
    return np.asarray(a).ravel(order="F")


def inv_triu(U):
    """``inv_triu.m:5``: inverse of an upper-triangular matrix (``inv(U)``).

    The MATLAB file's ``solve_triu`` line is commented out; ``inv`` on a triangular matrix
    uses a triangular solve, which is what ``solve_triangular`` does here.
    """
    U = np.asarray(U, dtype=float)
    return scipy.linalg.solve_triangular(U, np.eye(U.shape[0]), lower=False)


def _inv_triu_checked(U):
    """:func:`inv_triu` of a factor from :func:`chol_upper` (finite, since ``chol``
    checked its input): the same LAPACK solve without scipy's finiteness check
    (item 35)."""
    return scipy.linalg.solve_triangular(U, np.eye(U.shape[0]), lower=False,
                                         check_finite=False)


def _chol_or_raise(A, where):
    U, p = chol_upper(A)
    if p != 0:
        # MATLAB's chol(A) with one output errors on non-PD input.
        raise FormDiscoveryError(f"{where}: chol: input matrix must be positive definite")
    return U


def inv_posdef(A):
    """``inv_posdef.m:5-7``: inverse of a positive-definite matrix via ``chol``.

    Only the upper triangle of ``A`` is read (as MATLAB's ``chol``). Raises
    :class:`FormDiscoveryError` if ``A`` is not positive definite (MATLAB errors).
    """
    iU = _inv_triu_checked(_chol_or_raise(A, "inv_posdef"))
    return iU @ iU.T


def logdet(A):
    """``logdet.m:7-8``: ``log(det(A))`` for positive-definite ``A`` via ``chol``.

    Only the upper triangle of ``A`` is read. Raises :class:`FormDiscoveryError` if ``A``
    is not positive definite (MATLAB's ``chol`` errors).
    """
    U = _chol_or_raise(A, "logdet")
    return float(2 * np.sum(np.log(np.diag(U))))


def inv_posdef_logdet(A):
    """``(inv_posdef(A), logdet(A))`` from one ``chol`` (item 35). ``gplike.m:10-11``
    calls both on the same matrix, and each starts with ``chol(A)``; the factor is the
    same, so the results equal the two calls bit for bit. A non-positive-definite ``A``
    raises :func:`inv_posdef`'s error (the first of the two calls in MATLAB)."""
    U = _chol_or_raise(A, "inv_posdef")
    iU = _inv_triu_checked(U)
    return iU @ iU.T, float(2 * np.sum(np.log(np.diag(U))))


def mylogdet(A):
    """``mylogdet.m:7-12`` (the file declares ``function y = logdet``): ``log(det(A))``
    with a fallback when ``A`` is not positive definite.

    If ``[U,p] = chol(A)`` succeeds this equals :func:`logdet`. Otherwise it is
    ``log(det(A))`` on the full matrix, replicated as MATLAB computes it (KI-12): a
    ``complex`` ``log|det| + i*pi`` when ``det(A) < 0``, a real ``float`` when
    ``det(A) > 0``, and ``-inf`` when ``det(A) == 0``. The only caller,
    ``graph_like_conn.m:90``, tests ``isreal(logI)`` and recomputes from the positive
    eigenvalues, so the complex value must survive. Test with ``isinstance(y, complex)``
    (the Python analogue of ``~isreal``).
    """
    A = np.asarray(A, dtype=float)
    U, p = chol_upper(A)
    if p == 0:
        return float(2 * np.sum(np.log(np.diag(U))))
    d = float(np.linalg.det(A))
    if d < 0:
        return complex(np.log(complex(d)))
    with np.errstate(divide="ignore"):
        return float(np.log(d))


def _logs(f, X):
    X = np.asarray(X, dtype=float)
    if X.size == 0:
        return np.empty(0)  # MATLAB: max(max([])) is [], and [] propagates to L
    with np.errstate(invalid="ignore"):  # all -Inf -> X-mx is NaN, as in MATLAB
        mx = np.nanmax(X)  # max(max(X)) over everything, NaN skipped
        Xp = np.exp(X - mx)
        return np.log(matlab_reduce(f, Xp)) + mx


def sumlogs(X):
    """``sumlogs.m:4-7``: ``log(sum(exp(X)))`` computed stably, shifting by the overall
    maximum ``max(max(X))``.

    Vectors give a float; a matrix gives one value per column (MATLAB ``sum``), all
    shifted by the same global maximum. All ``-Inf`` input gives NaN (as MATLAB).
    """
    return _logs(np.sum, X)


def meanlogs(X):
    """``meanlogs.m:4-7``: ``log(mean(exp(X)))``, stably, as :func:`sumlogs`."""
    return _logs(np.mean, X)


def subv2ind(siz, subv):
    """``subv2ind.m:20-52``: linear (column-major) indices of the rows of ``subv``.

    0-based in and out: ``subv`` is ``(N, d)`` of 0-based subscripts (a 1-D ``subv`` is one
    row, as a MATLAB row vector); the result is a length-``N`` int array. The leftmost
    subscript varies fastest. As in MATLAB there is no bounds checking and the last entry
    of ``siz`` is never used. Empty ``subv`` gives an empty array; empty ``siz`` gives
    ``[0]`` (MATLAB returns the scalar ``1`` whatever ``N`` is). When every ``siz`` is 2,
    the weights are ``2**(0:d-1)`` with ``d`` taken from ``subv`` (``subv2ind.m:39``).
    """
    subv = np.asarray(subv)
    if subv.size == 0:
        return np.empty(0, dtype=np.int64)
    siz = np.asarray(siz).ravel()
    if siz.size == 0:
        return np.zeros(1, dtype=np.int64)
    subv = np.atleast_2d(subv).astype(np.int64)
    if np.all(siz == 2):
        cp = 2 ** np.arange(subv.shape[1], dtype=np.int64)
    else:
        cp = np.concatenate([[1], np.cumprod(siz[:-1])]).astype(np.int64)
    return subv @ cp


def trans2orig(Ps, Ss):
    """``trans2orig.m:3-4``: beta-distribution mean/strength ``(P, S)`` → ``(alpha, beta)``,
    elementwise: ``alpha = P*S``, ``beta = S - alpha``."""
    Ps = np.asarray(Ps, dtype=float)
    Ss = np.asarray(Ss, dtype=float)
    alphas = Ps * Ss
    betas = Ss - alphas
    return alphas, betas


def matrixpartition(J, nobjects):
    """``matrixpartition.m:5-8``: split ``J`` into the blocks ``A B; C D`` with ``A``
    ``nobjects x nobjects``. Returns copies (MATLAB value semantics)."""
    J = np.asarray(J)
    n = int(nobjects)
    return J[:n, :n].copy(), J[:n, n:].copy(), J[n:, :n].copy(), J[n:, n:].copy()


def triplepartition(J, nobs, nmiss):
    """``triplepartition.m:3-8``: blocks of ``J`` for observed (``nobs``), missing
    (``nmiss``) and latent (the rest) nodes. Returns ``A1, A2, B1, B2, D`` in MATLAB's
    output order (``B1`` = observed × latent, ``B2`` = missing × latent). Copies."""
    J = np.asarray(J)
    nobs = int(nobs)
    nobj = nobs + int(nmiss)
    A1 = J[:nobs, :nobs].copy()
    B1 = J[:nobs, nobj:].copy()
    A2 = J[nobs:nobj, nobs:nobj].copy()
    B2 = J[nobs:nobj, nobj:].copy()
    D = J[nobj:, nobj:].copy()
    return A1, A2, B1, B2, D


def stirling2(n, m):
    """``stirling2.m:87-106`` (John Burkardt): the ``n x m`` table of Stirling numbers of
    the second kind, ``s2[i-1, j-1] = S2(i, j)``, as float64.

    Built with the same recursion in the same floating-point order as MATLAB
    (``s2(i,j) = j*s2(i-1,j) + s2(i-1,j-1)``), so entries above ``2**53`` round exactly as
    they do in MATLAB; ``stirling2(40, 40)`` feeds the structure priors
    (``structcounts.m:12``). ``n <= 0`` or ``m <= 0`` gives an empty ``(0, 0)`` array.
    """
    n = int(n)
    m = int(m)
    if n <= 0 or m <= 0:
        return np.zeros((0, 0))
    s2 = np.zeros((n, m))
    s2[0, 0] = 1.0
    for i in range(1, n):
        s2[i, 0] = 1.0
        # row i depends only on row i-1, so the vectorised form does the same operations
        j = np.arange(2, m + 1, dtype=float)
        s2[i, 1:] = j * s2[i - 1, 1:] + s2[i - 1, :-1]
    return s2


def dijkstra(A, s=None, t=None, paths=False):
    """``dijkstra.m:33-113`` (Michael G. Kay, the file declares ``function [D,P] = dijk``):
    shortest-path distances from the nodes ``s`` to the nodes ``t``.

    ``A`` is an ``n x n`` weighted adjacency matrix of arc lengths: ``A[i, j] == 0`` means
    no arc, ``NaN`` means an arc of length 0. ``s`` and ``t`` are 0-based node indices;
    ``None`` or empty means all nodes. Returns the ``len(s) x len(t)`` distance matrix
    (``inf`` where unreachable). As in MATLAB, a matrix with an all-zero lower (upper)
    triangle, diagonal included, is treated as acyclic and scanned in index order
    (``dijkstra.m:40-45``); negative lengths are then allowed. Otherwise the usual
    node-selection loop runs, taking the first minimum on ties.

    Only the distance output is ported (KI-6): the MATLAB second output calls the missing
    ``pred2path``, and every caller (``swapobjclust.m:79,105,144``, ``collapsedims.m:24``)
    uses one output, so ``paths=True`` raises ``NotImplementedError``. MATLAB ``error``
    calls raise :class:`FormDiscoveryError`.
    """
    if paths:
        raise NotImplementedError("dijkstra: predecessor output needs pred2path (KI-6)")
    A = np.asarray(A, dtype=float)
    if A.ndim != 2:
        A = np.atleast_2d(A)
    n, cA = A.shape
    s = np.arange(n) if s is None or np.size(s) == 0 else np.asarray(s, dtype=np.int64).ravel()
    t = np.arange(n) if t is None or np.size(t) == 0 else np.asarray(t, dtype=np.int64).ravel()

    if not np.any(np.tril(A) != 0):  # A is upper triangular
        isAcyclic = 1
    elif not np.any(np.triu(A) != 0):  # A is lower triangular
        isAcyclic = 2
    else:  # graph may not be acyclic
        isAcyclic = 0

    if n != cA:
        raise FormDiscoveryError("A must be a square matrix")
    elif not isAcyclic and np.any(A < 0):
        raise FormDiscoveryError("A must be non-negative")
    elif np.any((s < 0) | (s > n - 1)):
        raise FormDiscoveryError(f"'s' must be an integer between 1 and {n}")
    elif np.any((t < 0) | (t > n - 1)):
        raise FormDiscoveryError(f"'t' must be an integer between 1 and {n}")

    A = A.T  # column j of A.T lists the arcs leaving node j
    D = np.zeros((len(s), len(t)))
    for i in range(len(s)):
        j = int(s[i])
        Di = np.full(n, np.inf)
        Di[j] = 0.0
        isLab = np.zeros(len(t), dtype=bool)
        if isAcyclic == 1:
            nLab = j  # MATLAB j - 1 with 1-based j
        elif isAcyclic == 2:
            nLab = n - 1 - j  # MATLAB n - j
        else:
            nLab = 0
            UnLab = list(range(n))
            isUnLab = np.ones(n, dtype=bool)

        while nLab < n and not np.all(isLab):
            if isAcyclic:
                Dj = Di[j]
            else:  # node selection; MATLAB min skips NaN and takes the first minimum
                cand = Di[isUnLab]
                jj = int(np.argmin(np.where(np.isnan(cand), np.inf, cand)))
                Dj = cand[jj]
                j = UnLab.pop(jj)
                isUnLab[j] = False

            nLab += 1
            if len(t) < n:
                isLab = isLab | (j == t)

            col = A[:, j]
            jA = np.flatnonzero(col)
            Aj = col[jA].copy()
            Aj[np.isnan(Aj)] = 0.0

            Dk = np.inf if Aj.size == 0 else Dj + Aj
            Di[jA] = np.fmin(Di[jA], Dk)  # MATLAB min(a, b) ignores NaN

            if isAcyclic == 1:  # increment node index for upper triangular A
                j += 1
            elif isAcyclic == 2:  # decrement node index for lower triangular A
                j -= 1
        D[i, :] = Di[t]
    return D
