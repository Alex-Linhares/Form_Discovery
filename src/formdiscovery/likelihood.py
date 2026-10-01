"""The ``graph_like`` dispatcher (``graph_like.m``, item 18, L3-b1; PLAN.md §5).

Pinned by ``legacy/tests_octave/fx_graphlike.m`` → ``tests/fixtures/graphlike.mat``
(``tests/test_graphlike.py``).
"""

import numpy as np

from . import likelihood_feat, likelihood_rel

__all__ = ["graph_like"]


def graph_like(data, graph, ps):
    """``graph_like.m:1-22``: ``log p(data | graph)``. Returns ``(logI, graph)``.

    The data are restricted to the assigned objects (``graph.z >= 0``, MATLAB's
    ``find(graph.z > 0)``, l.7): rows and columns for ``ps.runps.type == 'sim'``, rows for
    ``'feat'``; relational data are passed whole (the subsetting is commented out in the
    original, l.13). ``'rel'`` goes to
    :func:`formdiscovery.likelihood_rel.graph_like_rel` (item 20), every other type to
    :func:`formdiscovery.likelihood_feat.graph_like_conn` (both called through their
    modules so a test can wrap them). The input graph is not modified.
    """
    currobj = np.flatnonzero(np.asarray(graph.z).ravel() >= 0)
    kind = ps.runps.type
    if kind == "sim":
        data = np.asarray(data)[np.ix_(currobj, currobj)]
    elif kind == "feat":
        data = np.asarray(data)[currobj, :]

    if kind == "rel":
        return likelihood_rel.graph_like_rel(data, graph, ps)
    return likelihood_feat.graph_like_conn(data, graph, ps)
