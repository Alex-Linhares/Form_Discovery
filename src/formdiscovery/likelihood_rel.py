"""Relational-data likelihoods (PLAN.md §5).

Item 08 (L0-b) adds the beta-binomial and Dirichlet-multinomial building blocks
``makehyps``, ``bbloglike``, ``bblikesumhyps`` and ``dirmultloglike``; ``countmatrix``,
``rellikebin``, ``rellikefreqs`` and ``graph_like_rel`` follow in item 20. Pinned against
Octave by ``tests/octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``).
"""

import numpy as np
from scipy.special import gammaln

from .util import trans2orig

__all__ = ["makehyps", "bbloglike", "bblikesumhyps", "dirmultloglike"]


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
