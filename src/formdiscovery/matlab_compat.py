"""MATLAB built-in semantics that numpy/scipy do not reproduce by default.

Each helper mirrors one MATLAB built-in as the formdiscovery1.0 sources use it (see
``CONVENTIONS.md`` and PLAN.md §2, §4.3). Inputs and outputs use 0-based indices; the
values themselves are never shifted. Every helper is pinned against Octave by
``tests/octave/fx_matlab_compat.m`` → ``tests/fixtures/matlab_compat.mat``
(``tests/test_matlab_compat.py``). Where Octave and MATLAB disagree, the helper follows
MATLAB and the difference is recorded in ``KNOWN_ISSUES.md`` (KI-13, KI-14).
"""

import numpy as np
import scipy.linalg


def find_F(A, return_rc=False):
    """Nonzero entries of ``A`` in MATLAB's column-major order.

    ``find_F(A)`` is MATLAB ``k = find(A)`` (0-based linear indices into ``A`` in
    Fortran order, i.e. ``A.flat`` is *not* the right way to use them; use
    ``A.ravel(order='F')[k]`` or ``np.unravel_index(k, A.shape, order='F')``).
    ``find_F(A, return_rc=True)`` is ``[i, j, v] = find(A)`` and returns 0-based row and
    column indices and the values. Used e.g. at ``extract_weights.m:63``,
    ``relgraphinit.m:71``, ``get_edgemap.m``.
    """
    A = np.asarray(A)
    if A.ndim < 2:
        A = A.reshape(1, -1)  # a MATLAB vector: linear index == position either way
    flat = A.ravel(order="F")
    k = np.flatnonzero(flat)
    if not return_rc:
        return k
    i, j = np.unravel_index(k, A.shape, order="F")
    return i, j, flat[k]


def hist_centres(x, centres):
    """MATLAB ``n = hist(x, centres)`` for a vector ``x``; returns counts per bin.

    Bin edges are the midpoints between consecutive centres; the first and last bins are
    open (values below/above the outer centres are lumped into the end bins). A value
    exactly on an edge goes to the *upper* bin (MATLAB's ``histc``; Octave puts it in
    the lower bin, KI-13). NaNs are not counted. A length-1 ``centres`` is MATLAB's
    ``hist(x, nbins)``: ``nbins = centres[0]`` equal bins over ``[min(x), max(x)]``
    (MATLAB hist.m nbins branch; this is how ``hist(z, 1:1)`` and ``hist(z, unique(z))``
    behave when there is one cluster). Callers: ``graph_like_rel.m:105``,
    ``relgraphinit.m:18``, ``simplify_graph.m:110,128``, ``structurefit.m:49``.
    """
    x = np.asarray(x, dtype=float).ravel()
    c = np.asarray(centres, dtype=float).ravel()
    if c.size == 1:
        c = _nbins_centres(x, int(c[0]))
    if np.any(np.diff(c) < 0):
        raise ValueError("hist_centres: centres must be non-decreasing")
    x = x[~np.isnan(x)]
    edges = (c[:-1] + c[1:]) / 2
    # searchsorted(side='right') counts edges <= x, i.e. edge values go to the upper bin
    b = np.searchsorted(edges, x, side="right")
    return np.bincount(b, minlength=c.size).astype(float)


def _nbins_centres(x, n):
    """Bin centres of MATLAB ``hist(x, n)`` (R2007-era hist.m, scalar-nbins branch)."""
    x = x[np.isfinite(x)]
    if x.size == 0:
        raise ValueError("hist_centres: hist(x, nbins) needs a non-empty x")
    miny, maxy = x.min(), x.max()
    if miny == maxy:
        miny = miny - np.floor(n / 2) - 0.5
        maxy = maxy + np.ceil(n / 2) - 0.5
    w = (maxy - miny) / n
    return miny + w * np.arange(n) + w / 2


def _as_row(a):
    return np.asarray(a).ravel()


def unique_matlab(a, occurrence="first"):
    """MATLAB ``[b, i, j] = unique(a)`` for a vector; ``i``/``j`` 0-based.

    ``b`` is sorted, ``a[i] == b`` and ``b[j] == a``. ``occurrence`` picks which duplicate
    ``i`` points at: ``'first'`` (MATLAB R2013a+ and Octave default) or ``'last'`` (the
    MATLAB 7 default the code was written for, KI-14). No caller in the sources uses ``i``
    of a vector ``unique``; ``for c = unique(...)`` loops only need ``b``.
    """
    a = _as_row(a)
    b, i, j = np.unique(a, return_index=True, return_inverse=True)
    if occurrence == "last":
        rev = np.unique(a[::-1], return_index=True)[1]
        i = a.size - 1 - rev
    elif occurrence != "first":
        raise ValueError("occurrence must be 'first' or 'last'")
    return b, i, j.ravel()


def unique_rows(A, occurrence="first"):
    """MATLAB ``[b, i, j] = unique(A, 'rows')``; ``i``/``j`` 0-based.

    Rows of ``b`` are in lexicographic order (first column most significant), matching
    ``np.unique(axis=0)``. ``A[i] == b`` and ``b[j] == A``. ``occurrence`` as in
    :func:`unique_matlab`. Caller: ``scaledata.m:51`` (``makechunks``; uses ``b`` and ``j``
    only, so the first/last choice does not matter there).
    """
    A = np.asarray(A)
    if A.ndim != 2:
        raise ValueError("unique_rows needs a 2-D array")
    if A.shape[0] == 0:
        return A.copy(), np.zeros(0, int), np.zeros(0, int)
    b, i, j = np.unique(A, axis=0, return_index=True, return_inverse=True)
    if occurrence == "last":
        rev = np.unique(A[::-1], axis=0, return_index=True)[1]
        i = A.shape[0] - 1 - rev
    elif occurrence != "first":
        raise ValueError("occurrence must be 'first' or 'last'")
    return b, i, j.ravel()


def setdiff(a, b):
    """MATLAB ``setdiff(a, b)`` for vectors: sorted unique values of ``a`` not in ``b``."""
    return np.setdiff1d(_as_row(a), _as_row(b))


def intersect(a, b):
    """MATLAB ``intersect(a, b)`` for vectors: sorted unique common values
    (``simplify_graph.m:116``, ``swapobjclust.m:271``)."""
    return np.intersect1d(_as_row(a), _as_row(b))


def union(a, b):
    """MATLAB ``union(a, b)`` for vectors: sorted unique values of both
    (``find_descendants.m:29``, ``combinegraphs.m:67``). Always 1-D, so the Octave
    orientation problem of KI-9 cannot occur."""
    return np.union1d(_as_row(a), _as_row(b))


def mysetdiff(A, B):
    """``mysetdiff.m`` (whole file): elements of ``A`` not in ``B``, in ``A``'s order.

    Unlike :func:`setdiff` this neither sorts nor removes duplicates of ``A``
    (``C = A(logical(bits(A)))``). The MATLAB version assumes positive integers
    (it indexes a bit vector); this one accepts any hashable values, so it works on
    0-based indices. Empty ``A`` gives an empty result.
    """
    A = _as_row(A)
    B = _as_row(B)
    if A.size == 0:
        return A[:0]
    if B.size == 0:
        return A.copy()
    return A[~np.isin(A, B)]


def chol_upper(A):
    """MATLAB ``[U, p] = chol(A)``: upper-triangular ``U`` with ``U.T @ U == A``.

    Only the upper triangle of ``A`` is read. ``p == 0`` on success. If ``A`` is not
    positive definite, ``p`` is the 1-based index of the column where the factorisation
    fails (MATLAB's convention, kept 1-based because callers only test ``p == 0``), and
    ``U`` is the ``(p-1) x (p-1)`` factor of the leading block. Callers:
    ``logdet.m:7``, ``mylogdet.m:7``, ``inv_posdef.m:5``.
    """
    A = np.asarray(A, dtype=float)
    try:
        return scipy.linalg.cholesky(A, lower=False), 0
    except np.linalg.LinAlgError:
        pass
    n = A.shape[0]
    U = np.zeros_like(A)
    for k in range(n):
        d = A[k, k] - U[:k, k] @ U[:k, k]
        if not d > 0:
            return U[:k, :k].copy(), k + 1
        U[k, k] = np.sqrt(d)
        U[k, k + 1:] = (A[k, k + 1:] - U[:k, k] @ U[:k, k + 1:]) / U[k, k]
    return U, 0  # pragma: no cover  (scipy would have succeeded)


def sparse_accum(rows, cols, vals, shape=None):
    """MATLAB ``full(sparse(i, j, v, m, n))`` with 0-based ``rows``/``cols``.

    Duplicate ``(i, j)`` pairs are summed (``extract_weights.m:68``
    ``counts = sparse(1, edgeinds(sind), 1)``). Scalar ``rows``/``cols``/``vals`` are
    broadcast as in MATLAB. Without ``shape`` the size is ``(max(rows)+1, max(cols)+1)``.
    Returns a dense float array.
    """
    rows, cols, vals = (a.ravel() for a in np.broadcast_arrays(
        np.atleast_1d(np.asarray(rows, dtype=int)).ravel(),
        np.atleast_1d(np.asarray(cols, dtype=int)).ravel(),
        np.atleast_1d(np.asarray(vals, dtype=float)).ravel()))
    if shape is None:
        shape = (int(rows.max()) + 1 if rows.size else 0, int(cols.max()) + 1 if cols.size else 0)
    out = np.zeros(shape)
    np.add.at(out, (rows, cols), vals)
    return out


def median_matlab(x):
    """MATLAB ``median(x)`` for a vector: NaN for empty input or if ``x`` has a NaN
    (``combinegraphs.m:113``, ``split_node.m:147``)."""
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0 or np.isnan(x).any():
        return np.nan
    return float(np.median(x))


def stable_argsort(x, descending=False):
    """Permutation ``sind`` (0-based) of MATLAB ``[s, sind] = sort(x)`` for a vector.

    Ties keep their original order in both directions (MATLAB ``'descend'`` is stable too,
    so it is *not* the reverse of an ascending sort). NaNs go last when ascending and
    first when descending, as in MATLAB. Callers: ``best_split.m:105`` (descend),
    ``dataprobwsig.m:34``, ``extract_weights.m:67``, ``reordermissing.m:9``,
    ``split_node.m:142``.
    """
    x = np.asarray(x, dtype=float).ravel()
    nan = np.isnan(x)
    idx = np.arange(x.size)
    key = -x[~nan] if descending else x[~nan]
    ordered = idx[~nan][np.argsort(key, kind="stable")]
    return np.concatenate([idx[nan], ordered] if descending else [ordered, idx[nan]])


def max_first(x):
    """MATLAB ``[m, i] = max(x)`` for a vector; ``i`` 0-based.

    Ties go to the first index; NaNs are ignored unless every element is NaN, in which
    case ``(nan, 0)``. Empty input raises (MATLAB returns ``[]``). Callers:
    ``best_split.m:70,128-137``, ``relgraphinit.m:56,67,121``, ``makesimlike.m:78``.
    """
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0:
        raise ValueError("max_first of an empty vector")
    nan = np.isnan(x)
    if nan.all():
        return np.nan, 0
    keep = np.flatnonzero(~nan)
    i = int(keep[np.argmax(x[keep])])
    return float(x[i]), i
