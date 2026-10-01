"""Property tests (item 30, PLAN.md §7.3), all marked ``slow``.

These check invariants of the port that the original code also has; they need no Octave
fixture. Graphs come from :func:`random_graph`: ``makeemptygraph`` followed by random
``split_node`` calls (random component, production, node and partition, as
``legacy/tests_octave/fx_split.m`` draws them), random component weights and, optionally, random
object moves that leave some cluster nodes empty or with one object, so that
``simplify_graph`` has work to do. Hypothesis draws the structure, the size and a seed for
the numpy generator that builds the graph.

- ``simplify_graph`` is idempotent (``cleanstrong`` 0 and 1).
- ``combinegraphs`` keeps ``objcount`` and puts every object in exactly one cluster.
- ``graph_like`` is invariant when the objects are relabelled consistently in the data and
  the graph (feature data, similarity data and relational data; fast mode to rtol 1e-9,
  slow mode on one case to the optimizer tolerance).
- ``graph_prior``: for each form, ``sum_k P(k clusters) <= 1``, and the first 8 priors are
  normalised over all structures (``structcounts.m``'s counts).
"""

import numpy as np
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from formdiscovery.graph import combinegraphs, makeemptygraph, simplify_graph, split_node  # noqa: E402
from formdiscovery.io import load_dataset  # noqa: E402
from formdiscovery.likelihood import graph_like  # noqa: E402
from formdiscovery.params import DATASETS, Params, setrunps, structcounts  # noqa: E402
from formdiscovery.preprocess import scaledata  # noqa: E402
from formdiscovery.util import stirling2, sumlogs  # noqa: E402
from tests.helpers import graph_diff  # noqa: E402

pytestmark = pytest.mark.slow

FEAT_FORMS = ("partition", "chain", "ring", "tree", "hierarchy", "order", "connected",
              "grid", "cylinder")
REL_FORMS = ("partition", "partitionnoself", "dirchain", "undirchain", "dirring",
             "undirring", "dirhierarchy", "undirhierarchy", "connected", "order")
SETTINGS = settings(max_examples=200, deadline=None, derandomize=True,
                    suppress_health_check=[HealthCheck.too_slow])


def _ps(name, nobj, type="feat", ps=None):
    ps = (ps or Params.default()).copy()
    ps.runps.structname = name
    ps.runps.nobjects = nobj
    ps.runps.type = type
    return ps


def _set_weights(g, ps, rs):
    for comp in g.components:
        comp.W = np.asarray(comp.adj, dtype=float) * (0.5 + rs.random(np.shape(comp.adj)))
    return combinegraphs(g, ps)


def random_graph(name, nobj, seed, nsplits, moves, type="feat", ps=None):
    """A random graph of form ``name`` over ``nobj`` objects (see the module docstring)."""
    ps = _ps(name, nobj, type, ps)
    rs = np.random.default_rng(seed)
    g = makeemptygraph(ps)
    for _ in range(nsplits):
        g = _set_weights(g, ps, rs)
        i = int(rs.integers(g.ncomp))
        comp = g.components[i]
        pind = 1 + int(rs.integers(comp.prodcount))
        counts = np.bincount(comp.z, minlength=comp.nodecount)
        cands = np.flatnonzero(counts >= 2)
        if not cands.size:
            continue
        c = int(rs.choice(cands))
        members = rs.permutation(np.flatnonzero(comp.z == c))
        m = 1 + int(rs.integers(members.size - 1))
        out, c1, _ = split_node(g, i, c, pind, members[:m], members[m:], ps)
        if c1 is not None:
            g = out
    g = _set_weights(g, ps, rs)
    for _ in range(moves):  # move objects to random legal nodes of one component
        i = int(rs.integers(g.ncomp))
        comp = g.components[i]
        legal = np.setdiff1d(np.arange(comp.nodecount), comp.illegal)
        comp.z[int(rs.integers(nobj))] = int(rs.choice(legal))
        g = combinegraphs(g, ps)
    g.sigma = float(0.5 + rs.random())
    return g, ps


graphs = st.builds(
    lambda name, nobj, seed, nsplits, moves: (name, nobj, seed, nsplits, moves),
    st.sampled_from(FEAT_FORMS), st.integers(2, 12), st.integers(0, 2**32 - 1),
    st.integers(0, 8), st.integers(0, 4))


# --- simplify_graph ------------------------------------------------------------------------

@SETTINGS
@given(graphs, st.sampled_from([0, 1]))
def test_simplify_graph_idempotent(args, cleanstrong):
    g, ps = random_graph(*args)
    ps = ps.replace(cleanstrong=cleanstrong)
    once = simplify_graph(g, ps)
    twice = simplify_graph(once, ps)
    assert graph_diff(once, twice, rtol=0, atol=0) is None, graph_diff(once, twice)
    assert once.objcount == g.objcount


# --- combinegraphs -------------------------------------------------------------------------

@SETTINGS
@given(graphs)
def test_combinegraphs_preserves_objcount(args):
    g, ps = random_graph(*args)
    nobj = args[1]
    for zonly in (0, 1):
        out = combinegraphs(g, ps, zonly=zonly)
        assert out.objcount == g.objcount == nobj
        z = np.asarray(out.z)
        assert z.shape == (nobj,) and (z >= 0).all()
        nclus = int(np.prod([c.nodecount for c in out.components]))
        assert z.max() < nclus
        # each object is joined to exactly one cluster node, the one z names
        adj = np.asarray(out.adj, dtype=bool)
        assert adj.shape == (nobj + nclus, nobj + nclus)
        leaf = adj[nobj:, :nobj] | adj[:nobj, nobj:].T
        np.testing.assert_array_equal(leaf.sum(axis=0), np.ones(nobj))
        np.testing.assert_array_equal(np.argmax(leaf, axis=0), z)
        # the product cluster of each object agrees with its component clusters
        for j, comp in enumerate(out.components):
            np.testing.assert_array_equal(np.asarray(out.compinds)[z, j], comp.z)


# --- relabelling invariance of the likelihood ----------------------------------------------

def _prep(name, perm=None):
    """runmodel.m's preprocessing (setrunps, scaledata, structcounts) of data set ``name``,
    with the objects relabelled by ``perm`` *before* preprocessing (scaledata stores
    ``ps.runps.SS``, which the likelihood reads instead of the data)."""
    data = load_dataset(name)
    if perm is not None:
        data = _relabel_data(data, perm)
    nobj, ps = setrunps(data, DATASETS.index(name), Params.default())
    data, ps = scaledata(data, ps)
    ps = ps.replace(overrideSS=0, cleanstrong=0, fast=1)
    return data, structcounts(nobj, ps), nobj


PREP = {}


def _prepped(name):
    if name not in PREP:
        PREP[name] = _prep(name)
    return PREP[name]


def _relabel_graph(g, perm, ps):
    """The graph with object ``k`` renamed ``perm^-1[k]``: new object ``i`` is old object
    ``perm[i]`` (component ``z`` permuted, then recombined)."""
    h = g.copy()
    for comp in h.components:
        comp.z = np.asarray(comp.z)[perm]
    h.z = np.asarray(h.z)[perm]
    return combinegraphs(h, ps)


def _relabel_data(data, perm):
    """Raw data with new object ``i`` = old object ``perm[i]``."""
    if isinstance(data, dict):  # relational: R is nobj x nobj (x relations)
        d = dict(data)
        R = np.asarray(data["R"])
        d["R"] = R[perm][:, perm]
        return d
    data = np.asarray(data)
    if data.shape[0] == data.shape[1]:  # similarity (as setrunps.m decides)
        return data[np.ix_(perm, perm)]
    return data[perm]


def _check_relabelling(dname, form, seed, nsplits, moves, fast=1, rtol=1e-9):
    data, ps0, nobj = _prepped(dname)
    g, ps = random_graph(form, nobj, seed, nsplits, moves, type=ps0.runps.type, ps=ps0)
    perm = np.random.default_rng(seed + 1).permutation(nobj)
    datap, psp, _ = _prep(dname, perm)
    psp = psp.replace(fast=fast)
    ll, _ = graph_like(data, g, ps.replace(fast=fast))
    llp, _ = graph_like(datap, _relabel_graph(g, perm, psp), psp)
    assert np.isfinite(ll)
    np.testing.assert_allclose(llp, ll, rtol=rtol)


@SETTINGS
@given(st.sampled_from(["demo_chain_feat", "demo_tree_feat", "colors", "animals"]),
       st.sampled_from(FEAT_FORMS), st.integers(0, 2**32 - 1), st.integers(0, 10),
       st.integers(0, 3))
def test_feature_likelihood_relabelling_invariant(dname, form, seed, nsplits, moves):
    _check_relabelling(dname, form, seed, nsplits, moves)


@SETTINGS
@given(st.sampled_from(["demo_ring_rel_bin", "demo_hierarchy_rel_bin",
                        "demo_order_rel_freq"]),
       st.sampled_from(REL_FORMS), st.integers(0, 2**32 - 1), st.integers(0, 10),
       st.integers(0, 3))
def test_relational_likelihood_relabelling_invariant(dname, form, seed, nsplits, moves):
    _check_relabelling(dname, form, seed, nsplits, moves)


def test_slow_likelihood_relabelling_invariant():
    """Slow mode (optimizer + Laplace) on one tree over demo_tree_feat: the relabelled
    problem is the same problem up to object order, so the optimum agrees to the
    optimizer's tolerance (LOGI_RTOL in test_glslow.py is 1e-4; this is much tighter)."""
    _check_relabelling("demo_tree_feat", "tree", 5, 6, 0, fast=0, rtol=1e-6)


# --- graph_prior ---------------------------------------------------------------------------

@pytest.mark.parametrize("nobj", [2, 5, 12, 33, 40])
def test_graph_prior_sums_below_one(nobj):
    """PLAN §7.3: ``sum_k exp(graph_prior(k clusters)) <= 1`` for the 8 single-component
    families. It does *not* hold for grid/cylinder with few objects (nobj = 2: 1.0024):
    ``gridpriors.m`` gives weight to every node count up to ``nobj^2``, including counts no
    grid has ("weights for some impossible nodecounts will be represented"), and
    normalises over the possible ones only. Those two are checked over structures in
    :func:`test_grid_prior_normalised_over_structures`."""
    ps = structcounts(nobj, Params.default())
    for i, lp in enumerate(ps.logps[:8]):
        assert sumlogs(np.asarray(lp, dtype=float).ravel()) <= 1e-12, i


@pytest.mark.parametrize("nobj", [2, 5, 12, 33, 40])
def test_grid_prior_normalised_over_structures(nobj):
    """gridpriors.m: prior of one k x l grid (cylinder) times the number of ways G(k, l) to
    put the objects on it, summed over the possible shapes, is 1."""
    ps = structcounts(nobj, Params.default())
    n = nobj
    s2 = np.asarray(stirling2(n, n), dtype=float)[n - 1]
    from scipy.special import gammaln
    logT = np.log(s2) + gammaln(np.arange(1, n + 1) + 1)  # log T(n, k), k = 1..n
    for idx, kind in ((8, "grid"), (9, "cylinder")):
        lp = np.asarray(ps.logps[idx], dtype=float).ravel()
        terms = []
        for k in range(1, n + 1):
            for l in range(1, n + 1):
                if kind == "grid":
                    if l < k:
                        continue
                    logc = logT[k - 1] + logT[l - 1]
                    if l == 1:
                        pass
                    elif k == l:
                        c1 = np.exp(logT[k - 1])
                        c = (np.exp(logc) - 2 * c1) / 8 + c1 / 2
                        logc = np.log(c)
                    elif k == 1:
                        logc -= np.log(2)
                    else:
                        logc -= np.log(4)
                else:
                    logc = logT[k - 1] - (np.log(2) if k != 1 else 0)
                    logc += logT[l - 1] - np.log(l) - (np.log(2) if l > 2 else 0)
                terms.append(logc + lp[k * l - 1])
        total = sumlogs(np.array(terms))
        assert abs(total) < 1e-9, (kind, total)


@pytest.mark.parametrize("nobj", [2, 5, 12, 33, 40])
def test_graph_prior_normalised_over_structures(nobj):
    """structcounts.m: the prior of one structure times the number of structures with k
    clusters, summed over k, is 1 for each of the 8 single-component families."""
    ps = structcounts(nobj, Params.default())
    k = np.arange(1, nobj + 1)
    from scipy.special import gammaln
    arch = np.zeros((8, nobj))
    arch[1] = gammaln(k + 1) - np.log(2)
    arch[1, 0] = 0
    arch[2] = gammaln(k) - np.log(2)
    arch[2, :2] = 0
    with np.errstate(invalid="ignore"):
        arch[3] = gammaln(k - 1.5) + (k - 2) * np.log(2) - 0.5 * np.log(np.pi)
    arch[3, 0] = 0
    arch[4] = (k - 2) * np.log(k)
    arch[5] = (k - 1) * np.log(k)
    arch[6] = gammaln(k + 1)
    arch[7] = gammaln(k)
    logs2 = np.log(np.asarray(stirling2(nobj, nobj), dtype=float)[nobj - 1])
    for i in range(8):
        total = sumlogs(np.asarray(ps.logps[i], dtype=float).ravel() + arch[i] + logs2)
        assert abs(total) < 1e-9, (i, total)
