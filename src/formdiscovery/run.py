"""L5 drivers: ``runmodel`` (+ ``brlencases``) (item 28, PLAN.md §5 L5).

Pinned by ``tests/octave/fx_runmodel.m`` → ``tests/fixtures/runmodel.mat``
(``tests/test_runmodel.py``).

Deviation (planned, CONVENTIONS.md): ``runmodel.m`` makes the directory
``results/<struct>out/<data><rind>`` below ``pwd``, ``cd``s into it so that ``structurefit``
saves its growth histories there, and ``cd``s back. Here the base directory is the explicit
``outdir`` (``None``: nothing is written) and the working directory never changes. The
nested ``runmodel`` calls of the dimension searches use the run directory as their base,
as MATLAB's relative ``mkdir`` does.
"""

from pathlib import Path

import numpy as np
from scipy.io import loadmat

from . import FormDiscoveryError, likelihood, search
from .graph import combinegraphs, relgraphinit, simplify_graph
from .io import graph_from_mat, load_dataset
from .params import graph_prior, setrunps, structcounts
from .preprocess import scaledata
from .rng import as_provider

__all__ = ["runmodel", "brlencases", "run_dir", "REL_EXTERNAL_INIT", "REL_OVERD_INIT"]

# runmodel.m:57-61: structures initialised from an external z (partitionnoself missing:
# that is what is used to initialise the others)
REL_EXTERNAL_INIT = (
    "partition", "dirchain", "dirchainnoself", "dirring", "dirringnoself", "dirhierarchy",
    "dirhierarchynoself", "undirchain", "undirchainnoself", "undirring", "undirringnoself",
    "undirhierarchy", "undirhierarchynoself", "order", "ordernoself",
)
# runmodel.m:69-72: only for certain structures (not partition, domhier)
REL_OVERD_INIT = (
    "dirchain", "dirchainnoself", "dirring", "dirringnoself", "dirhierarchy",
    "dirhierarchynoself", "undirchain", "undirchainnoself", "undirring", "undirringnoself",
    "undirhierarchy", "undirhierarchynoself",
)

# runmodel.m:86-142: name -> (0-based ps.structures index of the first search (MATLAB 2
# or 3), component 1 type, component 2 type, final structure name). KI-29: MATLAB's 3 is
# 'order' in setps.m, not 'ring'.
_DIMSEARCH = {
    "griddimsearch": (1, "chain", "chain", "grid"),
    "cyldimsearchring": (2, "ring", "chain", "cylinder"),
    "cyldimsearchchain": (1, "chain", "ring", "cylinder"),
}


def _num2str(x):
    """MATLAB ``num2str`` for the integers used in file names."""
    x = float(x)
    return str(int(x)) if x.is_integer() else f"{x:.4g}"


def run_dir(ps, sind, dind, rind, outdir):
    """``runmodel.m:18-19``: ``<outdir>/results/<struct>out/<data><rind>``."""
    return (Path(outdir) / "results" / f"{ps.structures[sind]}out"
            / f"{ps.data[dind]}{_num2str(rind)}")


def _cellset(cell, i, j, value):
    """MATLAB ``cell{i, j} = value`` (0-based ``i``, ``j``): grows the 2-D object array
    ``cell`` with ``None`` (empty cells) as needed. Returns the (possibly new) array."""
    r, c = cell.shape
    if i >= r or j >= c:
        new = np.empty((max(r, i + 1), max(c, j + 1)), dtype=object)
        new[:r, :c] = cell
        cell = new
    cell[i, j] = value
    return cell


def _cellset_linear(cell, k, value):
    """MATLAB ``cell{k} = value`` (0-based linear index, column-major). Only ``k`` inside
    the array, or ``k == 0`` on an empty cell (which becomes 1 x 1), is needed here."""
    if cell.size == 0:
        return _cellset(cell, 0, 0, value)
    i, j = np.unravel_index(k, cell.shape, order="F")
    cell[i, j] = value
    return cell


def empty_cell():
    """MATLAB ``{}``: a 0 x 0 object array."""
    return np.empty((0, 0), dtype=object)


def brlencases(data, ps, graph, bestglls, bestgraph, savefile, rng=None):
    """``runmodel.m:198-234``: fit at the current ``ps.speed`` with the branch-length
    schedule ``ps.init``. Returns ``(ll, graph, bestglls, bestgraph, ps)``.

    - ``'none'``: one ``structurefit`` (``noinit``);
    - ``'ext'``: external lengths tied (``exttie``), then untied (``notie``);
    - ``'int'``: internal lengths tied (``inttie``), then untied (``notie``);
    - ``'intext'``: both tied (``alltie``), internal untied (``exttie``), then external
      untied (``notie``).

    Stage ``k`` (0-based) stores its growth history in ``bestglls[k, speed - 1]`` and
    ``bestgraph[k, speed - 1]`` (2-D object arrays, grown as MATLAB cells are). Replicated
    quirk: ``'ext'`` stores its first history in ``bestgraph{1}`` (linear index, l.208),
    not ``bestgraph{1, ps.speed}``. The returned ``ps`` keeps the untied flags. ``savefile``
    is the growth-history file prefix (``None``: nothing saved); the stage name and speed
    are appended, as in MATLAB. Any other ``ps.init`` raises (MATLAB leaves ``ll``
    undefined).
    """
    rng = as_provider(rng)
    ps = ps.copy()
    s = int(ps.speed) - 1
    speedstr = _num2str(ps.speed)

    def fit(name):
        sf = None if savefile is None else f"{savefile}{name}{speedstr}"
        return search.structurefit(data, ps, graph, savefile=sf, rng=rng)

    init = ps.init
    if init == "none":
        ll, graph, lls, bg = fit("noinit")
        bestglls = _cellset(bestglls, 0, s, lls)
        bestgraph = _cellset(bestgraph, 0, s, bg)
    elif init == "ext":
        ps.fixedexternal = 1
        ll, graph, lls, bg = fit("exttie")
        bestglls = _cellset(bestglls, 0, s, lls)
        bestgraph = _cellset_linear(bestgraph, 0, bg)  # quirk: bestgraph{1}
        # untie external...
        ps.fixedexternal = 0
        ll, graph, lls, bg = fit("notie")
        bestglls = _cellset(bestglls, 1, s, lls)
        bestgraph = _cellset(bestgraph, 1, s, bg)
    elif init == "int":
        ps.fixedinternal = 1
        ll, graph, lls, bg = fit("inttie")
        bestglls = _cellset(bestglls, 0, s, lls)
        bestgraph = _cellset(bestgraph, 0, s, bg)
        # untie internal...
        ps.fixedinternal = 0
        ll, graph, lls, bg = fit("notie")
        bestglls = _cellset(bestglls, 1, s, lls)
        bestgraph = _cellset(bestgraph, 1, s, bg)
    elif init == "intext":
        ps.fixedinternal = 1
        ps.fixedexternal = 1
        ll, graph, lls, bg = fit("alltie")
        bestglls = _cellset(bestglls, 0, s, lls)
        bestgraph = _cellset(bestgraph, 0, s, bg)
        # untie internal...
        ps.fixedinternal = 0
        ll, graph, lls, bg = fit("exttie")
        bestglls = _cellset(bestglls, 1, s, lls)
        bestgraph = _cellset(bestgraph, 1, s, bg)
        # untie external...
        ps.fixedexternal = 0
        ll, graph, lls, bg = fit("notie")
        bestglls = _cellset(bestglls, 2, s, lls)
        bestgraph = _cellset(bestgraph, 2, s, bg)
    else:
        raise FormDiscoveryError(f"brlencases: ps.init {init!r} leaves ll undefined")
    return ll, graph, bestglls, bestgraph, ps


def _load_bestz(path):
    """``load([ps.relinitdir, dataname, '_bestz'])`` (runmodel.m:62): an ASCII file of
    1-based cluster labels -> 0-based labels. Untested (no such files in the release)."""
    return np.loadtxt(path).ravel().astype(np.int64) - 1


def _add_second_dimension(graph, ps, comptypes):
    """runmodel.m:91-102 (and 110-121, 129-140): make the grown one-component graph the
    first dimension of a product, with a one-node second component holding every object,
    and ``combinegraphs``."""
    graph = graph.copy()
    graph.ncomp = 2
    graph.components[0].type = comptypes[0]
    # initialize second component
    c = graph.components[0].copy()
    c.type = comptypes[1]
    c.adj = np.zeros((1, 1))
    c.W = np.zeros((1, 1))
    c.adjsym = np.zeros((1, 1))
    c.Wsym = np.zeros((1, 1))
    c.nodecount = 1
    c.nodemap = np.zeros(1, dtype=np.int64)
    c.edgecount = 0
    c.edgemap = np.zeros((1, 1))
    c.edgecountsym = 0
    c.edgemapsym = np.zeros((1, 1))
    c.z = np.zeros(graph.objcount, dtype=np.int64)
    c.illegal = np.empty(0, dtype=np.int64)
    graph.components = [graph.components[0], c]
    return combinegraphs(graph, ps)


def runmodel(ps, sind, dind, rind, outdir=None, rng=None):
    """``runmodel.m:1-193``: find the best instance of form ``ps.structures[sind]`` for data
    set ``ps.data[dind]`` (both 0-based; ``rind`` is the repeat number, used only in the
    run directory name). Returns ``(ll, graph, names, bestglls, bestgraph)``.

    Steps, with one ``rng`` shared in MATLAB's call order:

    - load ``ps.dlocs[dind]`` (the data and ``names``; missing names become ``'1'``,
      ``'2'``, ...), :func:`setrunps`, :func:`scaledata`, ``ps.runps.names``;
    - the start graph: ``ps.outsideinit`` (a ``.mat`` file holding ``graph``; only that
      variable is read), else for relational data ``ps.reloutsideinit`` ``'external'``
      (:data:`REL_EXTERNAL_INIT` names, z from ``<relinitdir><data>_bestz``, untested) or
      ``'overd'`` (:data:`REL_OVERD_INIT` names, one object per cluster) through
      :func:`relgraphinit`, else ``None`` (the empty graph);
    - ``ps.overrideSS`` defaults to 0, ``ps.cleanstrong = 0``, :func:`structcounts`;
    - ``griddimsearch``/``cyldimsearchring``/``cyldimsearchchain`` (not in
      ``setps.structures``; append them to use them): a nested ``runmodel`` at speed 5 with
      ``init = 'none'`` and tied lengths grows one dimension, a one-node second
      dimension is added, and the outer ``ps`` goes on as ``grid``/``cylinder``. Replicated
      bug KI-29: ``cyldimsearchring`` grows ``ps.structures{3}``, which is ``order``;
    - speed 1-5: :func:`brlencases` once; speed 54: at speed 5, then at speed 4 with
      ``init = 'none'``; anything else raises ``'Unknown speed value'``;
    - ``tree``: remove the root (``cleanstrong = 1``, :func:`simplify_graph`) and fit once
      more with ``init = 'none'``;
    - final speed 5: the true (slow) score ``graph_like + graph_prior`` of the graph.

    Deviations: ``outdir`` replaces ``mkdir``/``cd`` (module docstring); with ``outdir``
    the growth histories go to :func:`run_dir` as ``growthhistory<stage><speed>.mat``. The
    ``display``/``disp`` lines and the figures (``ps.showtruegraph``,
    ``ps.showinferredgraph``, l.40-48, 182-191) are dropped.
    """
    rng = as_provider(rng)
    ps = ps.copy()
    ps.runps.structname = ps.structures[sind]

    savefile = None
    if outdir is not None:
        rdir = run_dir(ps, sind, dind, rind, outdir)
        rdir.mkdir(parents=True, exist_ok=True)
        savefile = str(rdir / "growthhistory")
    else:
        rdir = None

    # load data, names
    d = load_dataset(ps.dlocs[dind], with_names=True)
    data, names = (d, d["names"]) if isinstance(d, dict) else d
    nobjects, ps = setrunps(data, dind, ps)
    data, ps = scaledata(data, ps)
    if not names:
        names = [str(i + 1) for i in range(nobjects)]
    ps.runps.names = names

    graph = None
    if ps.outsideinit:
        graph = graph_from_mat(loadmat(ps.outsideinit, simplify_cells=True)["graph"])
    elif ps.runps.type == "rel" and ps.reloutsideinit == "external":
        if ps.runps.structname in REL_EXTERNAL_INIT:
            bestz = _load_bestz(f"{ps.relinitdir}{ps.data[dind]}_bestz")
            graph = relgraphinit(data["R"], bestz, ps)
    elif ps.runps.type == "rel" and ps.reloutsideinit == "overd":
        if ps.runps.structname in REL_OVERD_INIT:
            bestz = np.arange(nobjects)
            graph = relgraphinit(data["R"], bestz, ps)

    if ps.overrideSS is None:
        ps.overrideSS = 0
    ps.cleanstrong = 0
    ps = structcounts(nobjects, ps)

    if ps.runps.structname in _DIMSEARCH:
        first, t1, t2, final = _DIMSEARCH[ps.runps.structname]
        oldps = ps
        ps = ps.replace(speed=5, init="none")
        if ps.runps.structname == "griddimsearch":
            ps.fixedall = 1
        else:
            ps.fixedinternal = 1
            ps.fixedexternal = 1
        _, graph, _, _, _ = runmodel(ps, first, dind, rind, outdir=rdir, rng=rng)
        graph = _add_second_dimension(graph, ps, (t1, t2))
        ps = oldps.copy()
        ps.runps.structname = final
        graph.type = final

    bestglls, bestgraph = empty_cell(), empty_cell()
    speed = int(ps.speed)
    if speed in (1, 2, 3, 4, 5):
        ll, graph, bestglls, bestgraph, ps = brlencases(data, ps, graph, bestglls,
                                                        bestgraph, savefile, rng=rng)
    elif speed == 54:
        ps.speed = 5  # starting at speed 5
        ll, graph, bestglls, bestgraph, ps = brlencases(data, ps, graph, bestglls,
                                                        bestgraph, savefile, rng=rng)
        ps.speed = 4  # refining at speed 4
        ps.init = "none"  # branches have already been untied
        ll, graph, bestglls, bestgraph, ps = brlencases(data, ps, graph, bestglls,
                                                        bestgraph, savefile, rng=rng)
    else:
        raise FormDiscoveryError("Unknown speed value")

    if ps.runps.structname == "tree":
        ps.init = "none"
        ps.cleanstrong = 1
        # remove tree root
        graph = simplify_graph(graph, ps)
        ll, graph, bestglls, bestgraph, ps = brlencases(data, ps, graph, bestglls,
                                                        bestgraph, savefile, rng=rng)

    if ps.speed == 5:
        # finding true score for speed 5
        ps.fast = 0
        ll, graph = likelihood.graph_like(data, graph, ps)
        ll = ll + graph_prior(graph, ps)

    return ll, graph, names, bestglls, bestgraph

