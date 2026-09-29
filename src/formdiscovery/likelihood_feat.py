"""Feature-data likelihoods (PLAN.md §5).

Item 08 (L0-b) adds ``hessiangrad``; ``inv_covariance``, ``gplike``, ``dataprobwsig`` and
``graph_like_conn`` follow in items 16-19. Pinned against Octave by
``tests/octave/fx_l0b.m`` → ``tests/fixtures/l0b.mat`` (``tests/test_l0b.py``).
"""

import numpy as np

from .util import vec

__all__ = ["hessiangrad"]


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
