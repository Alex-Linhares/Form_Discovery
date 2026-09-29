"""Priors on edge weights (PLAN.md §5, item 07).

Pinned against Octave by ``tests/octave/fx_util.m`` → ``tests/fixtures/util.mat``
(``tests/test_util.py``).
"""

import numpy as np

from .util import matlab_reduce

__all__ = ["weightprior"]


def weightprior(w, beta):
    """``weightprior.m:7``: log prior of the edge weights ``w`` under an exponential prior
    (rate ``beta``) on ``1/w``, expressed in log-weight space::

        lp = sum(-log(beta) - 2*log(w) - 1./(beta*w) + log(w))

    A vector (or scalar) ``w`` gives a float; empty ``w`` gives 0 (MATLAB ``sum([])``).
    Callers: ``dataprobwsig.m:26,84-85,92``.
    """
    w = np.asarray(w, dtype=float)
    return matlab_reduce(np.sum, -np.log(beta) - 2 * np.log(w) - 1.0 / (beta * w) + np.log(w))
