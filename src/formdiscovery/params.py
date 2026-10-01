"""L1 parameters and structure priors (PLAN.md §5, item 09).

``setps``, ``defaultps``, ``setrunps``, ``gridpriors``, ``structcounts``, ``graph_prior``.
The MATLAB ``ps`` struct becomes the :class:`Params` dataclass, with the per-run fields of
``ps.runps`` in a nested :class:`RunPs`. Field names are MATLAB's. A field that MATLAB has
not set yet (``isfield(ps, ...)`` false) is ``None``.

MATLAB passes ``ps`` by value. Every function here that "modifies" ``ps`` returns a changed
copy and leaves its argument alone, so a caller that keeps an old ``ps`` (``oldps`` in
``runmodel.m:103``) sees the same thing it would in MATLAB. Callers that go on to mutate the
result should use :meth:`Params.copy` in the same places MATLAB would copy.

Indices: ``setrunps`` takes a 0-based data set index ``dind``; ``ps.logps[i][n - 1]`` is
MATLAB's ``ps.logps{i+1}(n)``; ``ps.T[n - 1, k - 1]`` is MATLAB's ``ps.T(n, k)``.
Pinned against Octave by ``legacy/tests_octave/fx_params.m`` → ``tests/fixtures/params.mat``
(``tests/test_params.py``).
"""

import copy
import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.special import gammaln

from . import FormDiscoveryError
from .io import DATA_DIR
from .util import stirling2, sumlogs

__all__ = [
    "Params", "RunPs", "STRUCTURES", "DATASETS", "setps", "defaultps", "setrunps",
    "gridpriors", "structcounts", "graph_prior", "prior_index",
]

# setps.m:3-9, the order of ps.structures (masterrun's sind is 1-based into this)
STRUCTURES = (
    "partition", "chain", "order", "ring", "hierarchy", "tree", "grid", "cylinder",
    "partitionnoself",
    "dirchain", "dirchainnoself", "undirchain", "undirchainnoself",
    "ordernoself", "connected", "connectednoself",
    "dirring", "dirringnoself", "undirring", "undirringnoself",
    "dirhierarchy", "dirhierarchynoself", "undirhierarchy", "undirhierarchynoself",
)

# setps.m:11-18, the order of ps.data (masterrun's dind is 1-based into this)
DATASETS = (
    "demo_chain_feat", "demo_ring_feat", "demo_tree_feat", "demo_ring_rel_bin",
    "demo_hierarchy_rel_bin", "demo_order_rel_freq",
    "synthpartition", "synthchain", "synthring", "synthtree", "synthgrid", "animals",
    "judges", "colors", "faces", "cities", "mangabeys", "bushcabinet", "kularing",
    "prisoners",
)


@dataclass
class RunPs:
    """``ps.runps``: settings for one run. ``setrunps.m`` fills ``type``, ``nobjects`` and
    (similarity data only) ``dim``. The other fields are filled by ``runmodel.m``
    (``structname``, ``names``) and ``scaledata.m`` (``SS``, the chunk fields, ...)."""
    type: str | None = None          # 'feat' | 'sim' | 'rel'
    nobjects: int | None = None
    dim: float | None = None
    structname: str | None = None
    names: list | None = None
    SS: Any = None
    chunknum: Any = None
    chunkcount: Any = None
    chunksize: Any = None
    chunkSS: Any = None
    objind: Any = None
    featind: Any = None
    dataind: Any = None


@dataclass
class Params:
    """The MATLAB ``ps`` struct.

    Groups: ``setps.m`` (structures, data sets and their locations), ``defaultps.m``
    (hyperparameters and search settings; ``None`` until :func:`defaultps` runs), fields
    set later by ``runmodel.m``/``structurefit.m``/``scaledata.m`` (``cleanstrong``,
    ``fast``, ``missingdata``, ``overrideSS``), the priors from :func:`structcounts`
    (``T``, ``logps``), and ``runps``.
    """
    # setps.m
    structures: list = field(default_factory=list)
    data: list = field(default_factory=list)
    repeats: Any = None
    dlocs: list = field(default_factory=list)
    simdim: list = field(default_factory=list)
    # defaultps.m
    lbeta: float | None = None
    sigbeta: float | None = None
    sigmainit: float | None = None
    theta: float | None = None
    datatransform: str | None = None
    simtransform: str | None = None
    showtruegraph: int | None = None
    showinferredgraph: int | None = None
    showbestsplit: int | None = None
    showpreclean: int | None = None
    showpostclean: int | None = None
    speed: int | None = None
    fixedall: int | None = None
    fixedinternal: int | None = None
    fixedexternal: int | None = None
    prodtied: int | None = None
    init: str | None = None
    gibbsclean: int | None = None
    nauty: int | None = None
    outsideinit: str | None = None
    zglreg: int | None = None
    featforce: int | None = None
    edgesumsteps: int | None = None
    edgesumlambda: float | None = None
    edgeoffset: float | None = None
    reloutsideinit: str | None = None
    relinitdir: str | None = None
    # set later (runmodel.m:80-82, runmodel.m:174-176, scaledata.m)
    cleanstrong: int | None = None
    fast: int | None = None
    missingdata: int | None = None
    overrideSS: int | None = None
    # structcounts.m
    T: Any = None
    logps: list | None = None
    runps: RunPs = field(default_factory=RunPs)

    def copy(self):
        """A deep copy (MATLAB value semantics for ``ps``)."""
        return copy.deepcopy(self)

    def replace(self, **changes):
        """A deep copy with some fields changed (like ``ps2 = ps; ps2.f = v;``)."""
        return dataclasses.replace(self.copy(), **changes)

    @classmethod
    def default(cls, data_dir=None):
        """``defaultps(setps())``, as ``masterrun.m:12-13`` builds it."""
        return defaultps(setps(data_dir))


def setps(data_dir=None):
    """``setps.m:1-42``: the structure and data set lists.

    ``ps.dlocs`` are the data files without the ``.mat`` extension. MATLAB builds them from
    ``[pwd, '/data/']`` (``setps.m:25``). The port uses ``data_dir`` (default
    :data:`formdiscovery.io.DATA_DIR`) instead, so the result does not depend on the
    working directory. ``repeats`` is a float array of ones, and ``simdim`` is a list of
    1000s, one per data set (a cell in MATLAB).
    """
    b = str(DATA_DIR if data_dir is None else data_dir).rstrip("/") + "/"
    return Params(
        structures=list(STRUCTURES),
        data=list(DATASETS),
        repeats=np.ones(len(DATASETS)),
        dlocs=[b + name for name in DATASETS],
        simdim=[1000] * len(DATASETS),
    )


def defaultps(ps):
    """``defaultps.m:1-101``: the default hyperparameters and search settings, set on a
    copy of ``ps``. The comments in ``defaultps.m`` explain each field."""
    ps = ps.copy()
    ps.lbeta = 0.4
    ps.sigbeta = 0.4
    ps.sigmainit = 1 / ps.sigbeta
    ps.theta = 1 - math.exp(-3)
    ps.datatransform = "simpleshiftscale"
    ps.simtransform = "none"
    ps.showtruegraph = 0
    ps.showinferredgraph = 0
    ps.showbestsplit = 0
    ps.showpreclean = 0
    ps.showpostclean = 0
    ps.speed = 54
    ps.fixedall = 0
    ps.fixedinternal = 0
    ps.fixedexternal = 0
    ps.prodtied = 0
    ps.init = "intext"
    ps.gibbsclean = 1
    ps.nauty = 0
    ps.outsideinit = ""
    ps.zglreg = 0
    ps.featforce = 0
    ps.edgesumsteps = 10
    ps.edgesumlambda = 2
    ps.edgeoffset = -5
    ps.reloutsideinit = "none"
    ps.relinitdir = ""
    return ps


def setrunps(data, dind, ps):
    """``setrunps.m:1-27``: fill ``ps.runps.type``/``nobjects``/``dim`` from the data.

    ``data`` is what :func:`formdiscovery.io.load_dataset` returns. A dict with a ``'type'``
    key (``isfield(data, 'type')``) is relational: ``nobjects = data['nobj']``, and
    ``speed`` and ``init`` are forced to ``5`` and ``'none'``. A square array is similarity
    data unless ``ps.featforce`` is set. Everything else is feature data. ``dind`` is the
    0-based data set index, used only for ``ps.simdim``. Returns ``(nobjects, ps)``, with
    ``ps`` a changed copy.
    """
    ps = ps.copy()
    if not (isinstance(data, dict) and "type" in data):
        data = np.asarray(data)
        shape = data.shape + (1,) * (2 - data.ndim)
        nobjects = int(shape[0])
        if shape[1] == shape[0] and not ps.featforce:
            ps.runps.type = "sim"
        else:
            ps.runps.type = "feat"
    else:
        ps.runps.type = "rel"
        nobjects = int(data["nobj"])
        ps.speed = 5
        ps.init = "none"
    ps.runps.nobjects = nobjects
    if ps.runps.type == "sim":
        ps.runps.dim = ps.simdim[dind]
    return nobjects, ps


def gridpriors(maxn, theta, T, type):
    """``gridpriors.m:1-58``: log prior over node counts for grids or cylinders.

    ``T[n-1, k-1]`` is the number of ways to put ``n`` objects into ``k`` parcels
    (``ps.T``). Returns a 1-D array of length ``maxn**2``: entry ``m - 1`` is
    ``log(theta) + m*log(1-theta) - logtotsum``, where ``logtotsum`` is the log of the
    weighted count of all ``k x l`` grids (``k <= l``) or all ``k x l`` cylinders. As in
    MATLAB, node counts that no grid can have still get a value.
    An unknown ``type`` raises :class:`FormDiscoveryError` (MATLAB: ``G`` undefined).
    """
    maxn = int(maxn)
    T = np.asarray(T, dtype=float)
    G = np.zeros((maxn, maxn))
    if type == "grid":
        # G(k,l), k <= l: ways of putting maxn objects on a k by l grid
        for k in range(1, maxn + 1):
            for l in range(k, maxn + 1):
                count = T[maxn - 1, k - 1] * T[maxn - 1, l - 1]
                if l == 1:
                    pass                       # no symmetries
                elif k == l:
                    onedcount = T[maxn - 1, k - 1]
                    count = (count - 2 * onedcount) / 8 + onedcount / 2
                elif k == 1:
                    count = count / 2          # l dimension can be flipped
                else:
                    count = count / 4          # both dimensions can be flipped
                G[k - 1, l - 1] = count
        occ = np.triu(np.ones((maxn, maxn), dtype=bool))
    elif type == "cylinder":
        # G(k,l): k (line) by l (ring) cylinder
        for k in range(1, maxn + 1):
            for l in range(1, maxn + 1):
                kcount = T[maxn - 1, k - 1]
                if k != 1:
                    kcount = kcount / 2        # chain can be reflected
                lcount = T[maxn - 1, l - 1] / l  # ring can be rotated
                if l > 2:
                    lcount = lcount / 2        # chain representation of ring can be flipped
                G[k - 1, l - 1] = kcount * lcount
        occ = np.ones((maxn, maxn), dtype=bool)
    else:
        raise FormDiscoveryError(f"gridpriors: unknown type {type!r}")
    # occind = find(...): column-major order
    occind = np.flatnonzero(occ.ravel(order="F"))
    logG = np.zeros(maxn * maxn)
    logG[occind] = np.log(G.ravel(order="F")[occind])
    ks = np.arange(1, maxn + 1)
    gridsizes = np.outer(ks, ks).ravel(order="F")
    logweights = math.log(theta) + np.arange(1, maxn * maxn + 1) * math.log(1 - theta)
    loggridweights = logweights[gridsizes - 1]
    logtotsum = sumlogs(logG[occind] + loggridweights[occind])
    return logweights - logtotsum


def structcounts(nobjects, ps):
    """``structcounts.m:1-68``: precompute the priors over cluster counts.

    Returns a copy of ``ps`` with
    ``T`` (``nobjects x nobjects``, ``T[n-1, k-1] = k! * S2(n, k)``) and ``logps``, a list
    of 10 1-D arrays: ``logps[i][n-1]`` is the log prior of an ``(i+1)``-structure with ``n``
    cluster nodes (1 partition, 2 chain, 3 ring, 4 unrooted tree, 5 unrooted hierarchy,
    6 rooted hierarchy, 7 dirchain, 8 dirring; each of length ``nobjects``; 9 grid and
    10 cylinder from :func:`gridpriors`, each of length ``nobjects**2``).

    ``factorial`` is taken correctly rounded (``math.factorial``), which is what Octave's
    ``round(gamma(n+1))`` gives for every ``n <= 40`` (checked); a ``cumprod`` differs by
    one ulp at n = 28-30, 34-39.

    ``nobjects < 2`` raises :class:`FormDiscoveryError` (KNOWN_ISSUES KI-16):
    ``counts(3, 1:2) = [0,0]`` (``structcounts.m:31``) grows a 1-column ``counts`` to two
    columns, which is a dimension error in MATLAB 7. Octave broadcasts instead and returns
    wrong (partly complex) priors.
    """
    maxn = int(nobjects)
    if maxn < 2:
        raise FormDiscoveryError(
            f"structcounts: nobjects = {maxn} < 2 (structcounts.m:31 grows counts; KI-16)")
    ps = ps.copy()
    theta = ps.theta
    s2 = stirling2(maxn, maxn)
    F = np.array([float(math.factorial(i)) for i in range(1, maxn + 1)])
    ps.T = F[None, :] * s2

    n = np.arange(1, maxn + 1, dtype=float)
    counts = np.zeros((8, maxn))
    # partition, connected: row 0 stays zero
    counts[1] = gammaln(n + 1) - math.log(2)                      # chain
    counts[1, 0] = 0
    counts[2] = gammaln(n) - math.log(2)                          # ring
    counts[2, 0:2] = 0
    with np.errstate(invalid="ignore"):                           # n = 1 is overwritten
        counts[3] = gammaln(n - 1.5) + (n - 2) * math.log(2) - 0.5 * math.log(math.pi)
    counts[3, 0] = 0                                              # unrooted tree
    counts[4] = (n - 2) * np.log(n)                               # hierarchy unrooted
    counts[5] = (n - 1) * np.log(n)                               # rooted hierarchy
    counts[6] = gammaln(n + 1)                                    # dirchain
    counts[7] = gammaln(n)                                        # dirring

    # combine the partitions into each cluster count with the architectures
    logclustercounts = np.log(s2[maxn - 1, :])
    logcounts = counts + logclustercounts[None, :]
    logweights = math.log(theta) + n * math.log(1 - theta)
    totsums = np.array([sumlogs(logweights + logcounts[i]) for i in range(8)])
    lcs = logweights[None, :] - totsums[:, None]

    logcs = [lcs[i].copy() for i in range(8)]
    logcs.append(gridpriors(maxn, theta, ps.T, "grid"))
    logcs.append(gridpriors(maxn, theta, ps.T, "cylinder"))
    ps.logps = logcs
    return ps


# graph_prior.m:13-34: structure name -> 0-based index into ps.logps
_PRIOR_INDEX = {}
for _i, _names in enumerate((
    ("partition", "connected", "partitionnoself", "connectednoself"),
    ("chain", "undirchain", "undirchainnoself"),
    ("ring", "undirring", "undirringnoself"),
    ("tree",),
    ("hierarchy", "undirhierarchy", "undirhierarchynoself", "undirdomtree",
     "undirdomtreenoself"),
    ("domtree", "dirhierarchy", "dirhierarchynoself", "dirdomtreenoself"),
    ("order", "dirchain", "dirchainnoself", "ordernoself"),
    ("dirring", "dirringnoself"),
    ("grid",),
    ("cylinder",),
)):
    for _n in _names:
        _PRIOR_INDEX[_n] = _i
del _i, _names, _n


def prior_index(type):
    """The ``switch graph.type`` of ``graph_prior.m:13-34``: 0-based index into
    ``ps.logps``. Unknown names raise :class:`FormDiscoveryError` (``graph_prior.m:35``)."""
    try:
        return _PRIOR_INDEX[type]
    except KeyError:
        raise FormDiscoveryError("Unexpected structure") from None


def _field(graph, name):
    if isinstance(graph, dict):
        return graph[name]
    return getattr(graph, name)


def graph_prior(graph, ps):
    """``graph_prior.m:1-39``: ``log P(graph)``, the prior on the number of cluster nodes.

    ``graph`` can be anything with ``type``, ``adjcluster`` and (for trees) ``illegal``
    as attributes or dict keys: a Graph, a dict, or a scipy ``mat_struct``. For trees the
    ``len(graph.illegal)`` internal nodes are not counted. ``ps.logps`` must come from
    :func:`structcounts`. A count of 0 or less, or one past the end of the prior, raises
    :class:`FormDiscoveryError`, because MATLAB would error there and a negative numpy
    index would silently wrap around.
    """
    type = _field(graph, "type")
    type = str(np.asarray(type).ravel()[0]) if not isinstance(type, str) else type
    index = prior_index(type)
    adj = np.asarray(_field(graph, "adjcluster"))
    nclusternodes = adj.shape[0] if adj.ndim else 1   # a squeezed 1x1 is a scalar
    if index == 3:
        nclusternodes -= np.size(_field(graph, "illegal"))
    lp = ps.logps[index]
    if not 1 <= nclusternodes <= len(lp):
        raise FormDiscoveryError(
            f"graph_prior: {nclusternodes} cluster nodes, prior has {len(lp)}")
    return float(lp[nclusternodes - 1])
