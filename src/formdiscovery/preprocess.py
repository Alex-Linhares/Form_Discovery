"""L1 preprocessing: ``scaledata`` (+``makechunks``), ``simpleshiftscale``, ``makesimlike``.

``runmodel.m:33`` calls ``[data ps] = scaledata(data, ps)`` once per run, after
``setrunps``. Relational data is returned untouched. Feature data is shifted and scaled;
similarity data is optionally double-centred. Missing entries are ``Inf``; they split the
features into *chunks* (features with the same set of observed objects), which
``dataprobwsig.m:30-58`` later scores one at a time.

Index fields set here are 0-based (``CONVENTIONS.md``): ``ps.runps.featind[c]`` and
``ps.runps.objind[c]`` are int arrays, and the chunk fields are Python lists with one entry
per chunk (MATLAB cells).
"""

import numpy as np

from . import FormDiscoveryError
from .matlab_compat import unique_rows


def _chunks(data, ps):
    """``datac`` in ``simpleshiftscale.m:10-16`` / ``makesimlike.m:8-14``: the observed
    block of each chunk, or the whole matrix without missing data."""
    if ps.missingdata:
        return [data[np.ix_(ps.runps.objind[i], ps.runps.featind[i])]
                for i in range(ps.runps.chunknum)]
    return [data]


def _largest_chunk_max(datac):
    """``simpleshiftscale.m:18-29`` / ``makesimlike.m:66-79``: ``max(op1(:))`` of the chunk
    with the most features, ``op1 = d*d'/fnum`` (``max(csize)`` takes the first tie).

    A chunk with no observed objects (a feature missing for every object) makes
    ``maxs(ch) = max([])`` fail in MATLAB/Octave; it raises :class:`FormDiscoveryError`
    here. No data set has such a feature."""
    maxs, csize = [], []
    for dnew in datac:
        fnum = dnew.shape[1]
        op1 = dnew @ dnew.T / fnum
        if op1.size == 0:
            raise FormDiscoveryError("scaledata: a chunk has no observed objects "
                                     "(maxs(ch) = max([]) fails in MATLAB)")
        maxs.append(np.max(op1))
        csize.append(dnew.shape[1])
    return maxs[int(np.argmax(csize))]


def simpleshiftscale(data, ps):
    """``simpleshiftscale.m:1-30``: subtract the global mean of the observed entries, then
    divide by ``sqrt(m)``, where ``m`` is the largest entry of ``d*d'/nfeatures`` in the
    chunk with the most features. ``Inf`` entries stay ``Inf``. Needs ``ps.missingdata``
    (and the chunk fields when it is set)."""
    data = np.asarray(data, dtype=float)
    obs = ~np.isinf(data)
    globmean = np.sum(data.T[obs.T]) / np.sum(obs)   # column-major order, as data(~isinf)
    shifted = data - globmean
    m = _largest_chunk_max(_chunks(shifted, ps))
    return (data - globmean) / np.sqrt(m)


def makesimlike(data, ps):
    """``makesimlike.m:1-81``: shift by ``k = ub`` so the smallest entry of ``d*d'`` over all
    chunks is 0 (``ub`` is the smallest upper root of the quadratics
    ``cov(i,j)(k) = a k^2 + b k + c``), then scale like :func:`simpleshiftscale`.

    When no pair has a real root (``ub == inf``) the shift is the minimiser ``kmins`` of the
    pair with the smallest nonzero minimum ``fmins`` (first on ties, zeros count as
    ``inf``). ``lb`` is computed but unused, as in MATLAB. With missing data the shift is
    applied to each chunk before the scale is taken. If no pair has a negative
    discriminant, MATLAB fails at ``makesimlike.m:48``; this raises
    :class:`FormDiscoveryError`.
    """
    data = np.asarray(data, dtype=float)
    origdata = data
    datac = _chunks(data, ps)

    lb, ub = -np.inf, np.inf
    kmins, fmins = {}, {}
    count = 0
    for d in datac:
        nobjects, fnum = d.shape
        outerproduct = d @ d.T
        rowsums = d.sum(axis=1)
        a = fnum
        for i in range(nobjects):
            for j in range(nobjects):
                count += 1
                c = outerproduct[i, j]
                b = -(rowsums[i] + rowsums[j])
                disc = b ** 2 - 4 * a * c
                if disc < 0:                      # ~isreal(delta)
                    kmins[count] = -b / (2 * a)
                    fmins[count] = (4 * a * c - b ** 2) / (4 * a)
                    continue
                delta = np.sqrt(disc)
                newlb = (-b + delta) / (2 * a)
                newub = (-b - delta) / (2 * a)
                if newlb > lb:
                    lb = newlb
                if newub < ub:
                    ub = newub

    if not fmins:
        # makesimlike.m:48 fails with "'fmins' undefined" when no discriminant is negative
        # (e.g. every chunk has one feature, where b^2 - 4ac is exactly 0)
        raise FormDiscoveryError("makesimlike: 'fmins' undefined (no pair without a real "
                                 "root)")
    if ub == np.inf:
        # MATLAB grows kmins/fmins by index, filling the gaps with 0; fmins == 0 -> inf
        last = max(fmins)
        fm = np.zeros(last)
        km = np.zeros(last)
        for k, v in fmins.items():
            fm[k - 1] = v
            km[k - 1] = kmins[k]
        fm[fm == 0] = np.inf
        ub = km[int(np.argmin(fm))]

    if ps.missingdata:
        datac = [d - ub for d in datac]
    else:
        datac = [origdata - ub]
    m = _largest_chunk_max(datac)
    return (origdata - ub) / np.sqrt(m)


def makechunks(data, ps):
    """``scaledata.m:46-62`` (subfunction ``makechunks``): with missing data, group the
    features by their observed-object mask. Chunks follow the lexicographic row order of
    ``unique(~isinf(data)', 'rows')``. Sets, per chunk, ``featind`` (0-based feature
    indices, ascending), ``objind`` (0-based observed objects), ``chunksize``
    (``len(objind)``) and ``chunkSS`` (``d*d'/len(featind)`` of the observed block), and
    ``chunknum``. Without missing data ``ps`` is returned unchanged. Modifies ``ps`` in
    place and returns it (the caller passes a copy)."""
    if ps.missingdata:
        datamask = ~np.isinf(data)
        b, _, j = unique_rows(datamask.T)
        r = ps.runps
        r.chunknum = b.shape[0]
        r.featind, r.objind, r.chunksize, r.chunkSS = [], [], [], []
        for chunk in range(b.shape[0]):
            featind = np.flatnonzero(j == chunk)
            objind = np.flatnonzero(b[chunk])
            dtemp = data[np.ix_(objind, featind)]
            r.featind.append(featind)
            r.objind.append(objind)
            r.chunksize.append(len(objind))
            r.chunkSS.append(dtemp @ dtemp.T / len(featind))
    return ps


def scaledata(data, ps):
    """``scaledata.m:1-44``: returns ``(data, ps)`` with ``ps`` a changed copy.

    Relational data (``ps.runps.type == 'rel'``) is returned as is, and ``ps.missingdata``
    is left unset. Otherwise ``ps.missingdata`` is 1 if any entry is ``Inf``, the chunks are
    built, and then:

    * similarity data: ``Z*data*Z`` with the centring matrix if ``ps.simtransform ==
      'center'``;
    * feature data: :func:`simpleshiftscale` or :func:`makesimlike` per
      ``ps.datatransform`` (anything else leaves the data alone); without missing data
      ``runps.SS = d*d'/nfeatures`` and ``runps.chunkcount = nobjects``.

    Finally the chunks are rebuilt from the transformed data. The unused ``dmean``/``stdev``
    of ``scaledata.m:18-19`` are not computed.
    """
    ps = ps.copy()
    if ps.runps.type == "rel":
        return data, ps
    data = np.asarray(data, dtype=float)
    ps.missingdata = 1 if np.isinf(data).any() else 0

    nobjects = data.shape[0]
    ps = makechunks(data, ps)

    if ps.runps.type == "sim":
        if ps.simtransform == "center":
            Z = np.eye(nobjects) - np.ones((nobjects, nobjects)) * (1.0 / nobjects)
            data = Z @ data @ Z
    elif ps.runps.type == "feat":
        if ps.datatransform == "simpleshiftscale":
            data = simpleshiftscale(data, ps)
        elif ps.datatransform == "makesimlike":
            data = makesimlike(data, ps)
        if not ps.missingdata:
            ps.runps.SS = data @ data.T / data.shape[1]
            ps.runps.chunkcount = data.shape[0]

    ps = makechunks(data, ps)
    return data, ps
