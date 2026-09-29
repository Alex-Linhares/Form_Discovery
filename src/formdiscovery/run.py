"""L5 drivers: ``runmodel`` (+ ``brlencases``) (item 28) and ``masterrun`` (item 29,
PLAN.md §5 L5, the ``formdiscovery run`` CLI in :mod:`formdiscovery.cli`).

Pinned by ``tests/octave/fx_runmodel.m`` → ``tests/fixtures/runmodel.mat``
(``tests/test_runmodel.py``) and ``tests/octave/fx_masterrun.m`` →
``tests/fixtures/masterrun.mat`` (``tests/test_masterrun.py``).

Deviation (planned, CONVENTIONS.md): ``runmodel.m`` makes the directory
``results/<struct>out/<data><rind>`` below ``pwd``, ``cd``s into it so that ``structurefit``
saves its growth histories there, and ``cd``s back. Here the base directory is the explicit
``outdir`` (``None``: nothing is written) and the working directory never changes. The
nested ``runmodel`` calls of the dimension searches use the run directory as their base,
as MATLAB's relative ``mkdir`` does.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.io import loadmat

from . import FormDiscoveryError, likelihood, search
from .graph import combinegraphs, relgraphinit, simplify_graph
from .io import graph_from_mat, load_dataset
from .params import Params, graph_prior, setrunps, structcounts
from .preprocess import scaledata
from .rng import NumpyPermutations, as_provider

__all__ = ["runmodel", "brlencases", "run_dir", "REL_EXTERNAL_INIT", "REL_OVERD_INIT",
           "masterrun", "masterrun_ps", "masterrun_pairs", "MasterResults", "save_results",
           "load_results", "graph_summary"]

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



# --- masterrun ----------------------------------------------------------------------------

# masterrun.m:30-33 (0-based): chain, ring, tree x demo_chain_feat, demo_ring_feat,
# demo_tree_feat
MASTERRUN_STRUCT = (1, 3, 5)
MASTERRUN_DATA = (0, 1, 2)
RESULTS_FORMAT = "formdiscovery-masterrun-1"


def masterrun_ps(data_dir=None):
    """``masterrun.m:12-25``: ``defaultps(setps())`` with ``reloutsideinit = 'overd'``.
    The ``which neato`` probe that turns on ``showinferredgraph``/``showpostclean``
    (l.15-19) is dropped with the figures."""
    ps = Params.default(data_dir)
    ps.reloutsideinit = "overd"
    return ps


def masterrun_pairs(thisstruct, thisdata, extraspairs=(), extradpairs=()):
    """``masterrun.m:52-56``: the (sind, dind) pairs in run order. ``repmat`` and ``(:)``
    make the structures vary fastest; the extra pairs come first."""
    pairs = [(int(s), int(d)) for s, d in zip(extraspairs, extradpairs)]
    if len(extraspairs) != len(extradpairs):
        raise FormDiscoveryError("extraspairs and extradpairs differ in length")
    pairs += [(int(s), int(d)) for d in thisdata for s in thisstruct]
    return pairs


def _grow_set(a, idx, value, fill):
    """MATLAB ``a(i, j, k) = value`` / ``a{i, j, k} = value`` (0-based ``idx``): grows the
    n-d array ``a`` with ``fill`` as needed. Returns the (possibly new) array."""
    shape = tuple(max(n, i + 1) for n, i in zip(a.shape, idx))
    if shape != a.shape:
        new = np.full(shape, fill, dtype=a.dtype)
        new[tuple(slice(0, n) for n in a.shape)] = a
        a = new
    a[idx] = value
    return a


@dataclass
class MasterResults:
    """The variables ``masterrun.m`` saves in its ``masterfile`` (l.70-71), 0-based:

    - ``modellike[sind, dind, rind - 1]``: the final score (0 where no run);
    - ``structure``, ``pss``, ``llhistory``: object arrays of the same kind (``None`` for
      empty cells) with the final graph, masterrun's own ``ps`` (not runmodel's) and
      runmodel's ``bestglls`` history cell;
    - ``names[dind]``: the object names.

    Entries read back from a results file (:func:`load_results`) hold what the file
    keeps: ``structure`` a dict (``type``, ``objcount``, ``z``, ``adj``, ``W``), ``pss``
    a dict of ``ps``'s scalar fields. ``runs`` has one :func:`graph_summary`-style
    record per run (the JSON summary), in the order they were stored."""
    modellike: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 0)))
    structure: np.ndarray = field(default_factory=lambda: np.empty((0, 0, 0), dtype=object))
    pss: np.ndarray = field(default_factory=lambda: np.empty((0, 0, 0), dtype=object))
    llhistory: np.ndarray = field(default_factory=lambda: np.empty((0, 0, 0), dtype=object))
    names: np.ndarray = field(default_factory=lambda: np.empty((1, 0), dtype=object))
    runs: list = field(default_factory=list)

    def store(self, sind, dind, rind, ps, ll, graph, names, llhistory, run=None):
        """``masterrun.m:65-69`` (0-based ``sind``, ``dind``; ``rind`` from 1)."""
        idx = (sind, dind, rind - 1)
        self.pss = _grow_set(self.pss, idx, ps, None)
        self.modellike = _grow_set(self.modellike, idx, ll, 0.0)
        self.structure = _grow_set(self.structure, idx, graph, None)
        self.names = _grow_set(self.names, (0, dind), names, None)
        self.llhistory = _grow_set(self.llhistory, idx, llhistory, None)
        if run is not None:
            self.runs = [r for r in self.runs if _run_idx(r) != idx] + [run]


def _run_idx(r):
    return (int(r["sind"]), int(r["dind"]), int(r["rind"]) - 1)


def graph_summary(graph):
    """Cluster statistics of a final graph for the summary: ``nclusters`` (occupied
    clusters, distinct ``z``), ``nnodes`` (all cluster nodes, latent ones included) and
    ``z`` (0-based, -1 for a missing object)."""
    z = np.asarray(graph.z).ravel().astype(int)
    return {"type": graph.type, "nobjects": int(graph.objcount),
            "nclusters": int(np.unique(z[z >= 0]).size),
            "nnodes": int(np.shape(graph.adj)[0] - graph.objcount), "z": z.tolist()}


def _ps_summary(ps):
    """The scalar and string fields of a ``ps`` (what the JSON summary keeps)."""
    if isinstance(ps, dict):
        return dict(ps)
    out = {}
    for k, v in vars(ps).items():
        if isinstance(v, (str, int, float)) or v is None:
            out[k] = v
        elif isinstance(v, np.generic):
            out[k] = v.item()
    return out


def masterrun(ps=None, thisstruct=MASTERRUN_STRUCT, thisdata=MASTERRUN_DATA, repeats=1,
              extraspairs=(), extradpairs=(), outdir=None, masterfile="resultsdemo",
              rng=None, seed=1, log=None):
    """``masterrun.m:1-81``: fit every structure ``ps.structures[s]`` (``s`` in
    ``thisstruct``) to every data set ``ps.data[d]`` (``d`` in ``thisdata``), both
    0-based, ``repeats`` times, with :func:`runmodel`. Returns a :class:`MasterResults`.

    - ``ps`` defaults to :func:`masterrun_ps` (``reloutsideinit = 'overd'``); the
      defaults of ``thisstruct``/``thisdata`` are masterrun's chain, ring, tree x the
      three feature demos. The run order is :func:`masterrun_pairs` (the ``extra`` pairs
      first) inside the loop over ``rind = 1..repeats``.
    - Randomness: MATLAB seeds ``rand('state', rind)`` before each run (l.60). Here each
      run gets ``NumpyPermutations(seed + rind - 1)`` (so the default ``seed = 1`` seeds
      with ``rind``, as MATLAB does; the streams are not MATLAB's). ``rng`` overrides
      this: a provider (with ``randperm``, or a seed for :func:`as_provider`) is
      shared by all runs in order (replay), a callable ``rng(rind)`` returns each run's
      provider.
    - ``pss[sind, dind, rind - 1]`` is masterrun's ``ps`` (the input), not runmodel's;
      ``llhistory`` is runmodel's ``bestglls``.
    - With ``outdir``: runmodel's growth histories go below it (:func:`run_dir`), and
      after each run the results are saved as ``<outdir>/<masterfile>.npz`` and
      ``.json`` (:func:`save_results`). Replicated behaviour (l.62-65): if that file
      exists, its entries are loaded before each store, so a new run is added to the
      results of earlier sessions. The retry loop around the load/save (l.61-78, for
      parallel writers) and the ``disp`` are dropped; ``log(text)`` gets the ``disp``
      text and a line per finished run.
    """
    ps = masterrun_ps() if ps is None else ps
    pairs = masterrun_pairs(thisstruct, thisdata, extraspairs, extradpairs)
    res = MasterResults()
    for rind in range(1, int(repeats) + 1):
        for sind, dind in pairs:
            if log:
                log(f"  {ps.data[dind]} {ps.structures[sind]}")
            runseed = None
            if rng is None:
                runseed = int(seed) + rind - 1
                runrng = NumpyPermutations(runseed)
            elif callable(rng) and not hasattr(rng, "randperm"):
                runrng = rng(rind)
            else:
                runrng = rng = as_provider(rng)
            t0 = time.perf_counter()
            ll, graph, names, bestglls, _ = runmodel(ps, sind, dind, rind, outdir=outdir,
                                                     rng=runrng)
            secs = time.perf_counter() - t0
            run = {"structure": ps.structures[sind], "data": ps.data[dind], "sind": sind,
                   "dind": dind, "rind": rind, "seed": runseed, "ll": float(ll),
                   "seconds": secs, **graph_summary(graph)}
            if log:
                log(f"  -> ll = {float(ll):.10g}, {run['nclusters']} clusters, "
                    f"{secs:.1f} s")
            if outdir is not None:
                path = Path(outdir) / masterfile
                if path.with_suffix(".json").exists():
                    res = _merge(load_results(path), res)
            res.store(sind, dind, rind, ps.copy(), float(ll), graph, names, bestglls, run)
            if outdir is not None:
                save_results(res, Path(outdir) / masterfile, ps)
    return res


def _merge(old, new):
    """``old`` (read from the file) with every entry of ``new`` stored on top."""
    for r in new.runs:
        s, d, k = _run_idx(r)
        old.store(s, d, k + 1, new.pss[s, d, k], new.modellike[s, d, k],
                  new.structure[s, d, k], new.names[0, d], new.llhistory[s, d, k], r)
    return old


def _key(idx):
    return "r{}_{}_{}".format(*idx)


def save_results(res, path, ps=None):
    """Write ``res`` as ``<path>.npz`` (arrays) and ``<path>.json`` (summary).

    The ``.npz`` holds ``modellike`` (``S x D x R``) and, for every stored run
    ``k = r<sind>_<dind>_<rind - 1>`` (0-based): ``k.z`` (0-based, -1 missing), ``k.adj``,
    ``k.W`` and the history cell as ``k.llhistory_shape`` plus ``k.llhistory.<i>_<j>`` for
    each non-empty cell. The ``.json`` holds the format tag, ``ps.structures`` and
    ``ps.data`` (when ``ps`` is given), ``names`` (by 0-based ``dind``), and ``runs``: per
    run the structure and data names, ``sind``/``dind`` (0-based), ``rind``, ``seed``,
    ``ll``, ``seconds``, ``type``, ``nobjects``, ``nclusters``, ``nnodes``, ``z`` and
    ``ps`` (masterrun's ``ps``, scalar fields)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {"modellike": res.modellike}
    runs = []
    for r in res.runs:
        idx = _run_idx(r)
        k = _key(idx)
        g = res.structure[idx]
        get = g.get if isinstance(g, dict) else lambda f: getattr(g, f)
        arrays[f"{k}.z"] = np.asarray(get("z")).astype(np.int64)
        arrays[f"{k}.adj"] = np.asarray(get("adj"), dtype=float)
        arrays[f"{k}.W"] = np.asarray(get("W"), dtype=float)
        h = res.llhistory[idx]
        h = np.empty((0, 0), dtype=object) if h is None else h
        arrays[f"{k}.llhistory_shape"] = np.asarray(h.shape, dtype=np.int64)
        for (i, j), v in np.ndenumerate(h):
            if v is not None:
                arrays[f"{k}.llhistory.{i}_{j}"] = np.asarray(v, dtype=float)
        runs.append({**r, "key": k, "ps": _ps_summary(res.pss[idx])})
    np.savez(path.with_suffix(".npz"), **arrays)
    summary = {"format": RESULTS_FORMAT,
               "names": {str(d): n for d, n in enumerate(res.names[0]) if n is not None},
               "runs": runs}
    if ps is not None:
        summary["structures"], summary["data"] = list(ps.structures), list(ps.data)
    path.with_suffix(".json").write_text(json.dumps(summary, indent=1) + "\n")


def load_results(path):
    """Read back :func:`save_results` output as a :class:`MasterResults` (graphs and
    ``ps`` as dicts, see there)."""
    path = Path(path)
    summary = json.loads(path.with_suffix(".json").read_text())
    if summary.get("format") != RESULTS_FORMAT:
        raise FormDiscoveryError(f"{path}: not a masterrun results file")
    res = MasterResults()
    with np.load(path.with_suffix(".npz")) as a:
        for r in summary["runs"]:
            k = r["key"]
            s, d, i = _run_idx(r)
            shape = tuple(int(x) for x in a[f"{k}.llhistory_shape"])
            h = np.empty(shape, dtype=object)
            for idx in np.ndindex(shape):
                name = f"{k}.llhistory.{idx[0]}_{idx[1]}"
                h[idx] = a[name] if name in a else None
            g = {"type": r["type"], "objcount": r["nobjects"], "z": a[f"{k}.z"],
                 "adj": a[f"{k}.adj"], "W": a[f"{k}.W"]}
            run = {x: v for x, v in r.items() if x not in ("key", "ps")}
            res.store(s, d, i + 1, r["ps"], r["ll"], g, summary["names"].get(str(d)), h, run)
        # modellike as saved: its zero fill can be larger than the stored runs
        m = a["modellike"]
        if m.ndim == 3 and m.size:
            res.modellike = _grow_set(res.modellike, tuple(n - 1 for n in m.shape), 0.0, 0.0)
            res.modellike[tuple(slice(0, n) for n in m.shape)] = m
    return res
