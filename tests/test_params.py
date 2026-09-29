"""Parity of ``formdiscovery.params`` (item 09, L1 params) with Octave.

The fixture ``tests/fixtures/params.mat`` comes from ``tests/octave/fx_params.m``
(regenerate with ``python tools/gen_fixtures.py params``). It holds ``setps``/``defaultps``,
``setrunps`` on every data set, ``structcounts`` for n in {1, 2, 3, 8, 12, 14, 28, 33, 35, 40},
``gridpriors`` with another theta, ``graph_prior`` for every structure name and cluster
count (n = 12), and ``graph_prior`` on the 63 final baseline graphs. The live tests rerun the
script and compare with Octave on fresh inputs.
"""

import math

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.io import DATA_DIR, FIXTURES_DIR, load_dataset, load_fixture
from formdiscovery.params import (
    DATASETS, STRUCTURES, Params, defaultps, graph_prior, gridpriors, setps, setrunps,
    structcounts,
)
from formdiscovery.util import stirling2, sumlogs

FX = load_fixture("params")
TOL = dict(rtol=1e-10, atol=1e-12)
PS = Params.default()


def test_setps():
    ps = setps()
    o = FX["setps"]
    assert ps.structures == list(o["structures"]) == list(STRUCTURES)
    assert ps.data == list(o["data"]) == list(DATASETS)
    np.testing.assert_array_equal(ps.repeats, o["repeats"])
    np.testing.assert_array_equal(ps.simdim, o["simdim"])
    assert list(FX["dlocs_rel"]) == ["data/" + d for d in DATASETS]
    assert ps.dlocs == [f"{DATA_DIR}/{d}" for d in DATASETS]
    assert setps("/x/y/").dlocs[0] == "/x/y/demo_chain_feat"
    # the setps-only struct has no defaultps fields
    assert set(o) == {"structures", "data", "repeats", "simdim"}
    assert ps.theta is None and ps.speed is None


def test_defaultps_fields_and_values():
    o = FX["defaultps"]
    ps = PS
    setfields = {k for k, v in vars(ps).items()
                 if k not in ("runps", "dlocs") and v is not None}
    assert setfields == set(o)
    for k, v in o.items():
        got = getattr(ps, k)
        if isinstance(v, str):
            assert got == v, k
        elif k in ("outsideinit", "relinitdir"):     # '' loads as an empty array
            assert got == "" and np.size(v) == 0, k
        elif k in ("structures", "data"):
            assert got == list(v), k
        else:
            np.testing.assert_allclose(np.asarray(got, dtype=float),
                                       np.asarray(v, dtype=float), rtol=1e-15,
                                       err_msg=k)


def test_defaultps_does_not_mutate_argument():
    ps0 = setps()
    ps1 = defaultps(ps0)
    assert ps0.theta is None and ps1.theta == pytest.approx(1 - math.exp(-3), rel=1e-15)
    p2 = ps1.replace(speed=5)
    assert ps1.speed == 54 and p2.speed == 5


def test_setrunps_every_dataset():
    for dind, name in enumerate(DATASETS):
        data = load_dataset(name)
        n, ps = setrunps(data, dind, PS)
        assert n == FX["sr_nobjects"][dind] == ps.runps.nobjects, name
        assert ps.runps.type == FX["sr_type"][dind], name
        dim = FX["sr_dim"][dind]
        assert (ps.runps.dim is None) == np.isnan(dim), name
        if ps.runps.dim is not None:
            assert ps.runps.dim == dim
        assert ps.speed == FX["sr_speed"][dind], name
        assert ps.init == FX["sr_init"][dind], name
    # value semantics: the input ps is unchanged
    assert PS.speed == 54 and PS.init == "intext" and PS.runps.type is None


def test_setrunps_featforce_and_shapes():
    n, ps = setrunps(load_dataset("colors"), 13, PS.replace(featforce=1))
    assert (n, ps.runps.type) == (FX["sr_featforce_nobjects"], FX["sr_featforce_type"])
    assert ps.runps.dim is None and not FX["sr_featforce_hasdim"]
    n, ps = setrunps(np.zeros((3, 5)), 0, PS)
    assert (n, ps.runps.type) == (FX["sr_rect_nobjects"], FX["sr_rect_type"])
    n, ps = setrunps(np.zeros((4, 4)), 1, PS)
    assert (n, ps.runps.type, ps.runps.dim) == (
        FX["sr_sq_nobjects"], FX["sr_sq_type"], FX["sr_sq_dim"])


@pytest.mark.parametrize("k", range(len(FX["sc_n"])))
def test_structcounts(k):
    n = int(FX["sc_n"][k])
    want = FX["sc_logps"][k]
    if n < 2:
        # KI-16: Octave broadcasts the phantom second column and returns a complex tree prior
        assert np.iscomplexobj(np.asarray(want[3]))
        assert not FX["sc_isreal"][k, 3]
        with pytest.raises(FormDiscoveryError, match="KI-16"):
            structcounts(n, PS)
        return
    assert FX["sc_isreal"][k].all()
    ps = structcounts(n, PS)
    np.testing.assert_array_equal(ps.T, np.atleast_2d(FX["sc_T"][k]))
    assert len(ps.logps) == 10
    for i in range(10):
        w = np.atleast_1d(want[i])
        assert ps.logps[i].shape == w.shape == ((n * n,) if i >= 8 else (n,))
        np.testing.assert_allclose(ps.logps[i], w, **TOL, err_msg=f"n={n} logps{{{i + 1}}}")
    assert PS.logps is None and PS.T is None


def test_structcounts_priors_geometric():
    # logps{i}(n) = log(theta) + n*log(1-theta) - totsum: geometric in n, and the
    # normalising sum includes the structure counts, so the sum over n is < 0 (PLAN §7.3)
    ps = structcounts(40, PS)
    for lp in ps.logps:
        np.testing.assert_allclose(np.diff(lp), math.log(1 - PS.theta), rtol=1e-12)
        assert sumlogs(lp) < 0


def test_gridpriors_direct():
    theta = float(FX["gp_theta"])
    for k, n in enumerate(np.atleast_1d(FX["gp_n"]).astype(int)):
        T = np.array([math.factorial(i) for i in range(1, n + 1)], float) * stirling2(n, n)
        for key, type in (("gp_grid", "grid"), ("gp_cyl", "cylinder")):
            np.testing.assert_allclose(gridpriors(n, theta, T, type),
                                       np.atleast_1d(FX[key][k]), **TOL,
                                       err_msg=f"{type} n={n}")
    assert FX["gp_bogus_err"] == 1
    with pytest.raises(FormDiscoveryError):
        gridpriors(3, 0.5, np.ones((3, 3)), "bogus")


def test_graph_prior_every_type_and_count():
    ps = structcounts(int(FX["gr_maxn"]), PS)
    types = list(FX["gr_types"])
    assert set(STRUCTURES) <= set(types)
    for t, type in enumerate(types):
        want = np.atleast_1d(FX["gr_prior"][t])
        nill = np.atleast_1d(FX["gr_nillegal"][t]).astype(int)
        got = [graph_prior({"type": type, "adjcluster": np.zeros((k, k)),
                            "illegal": np.arange(nill[k - 1])}, ps)
               for k in range(1, len(want) + 1)]
        np.testing.assert_allclose(got, want, **TOL, err_msg=type)
    assert FX["gr_bogus_err"] == 1
    with pytest.raises(FormDiscoveryError, match="Unexpected structure"):
        graph_prior({"type": "bogus", "adjcluster": np.zeros((1, 1)), "illegal": []}, ps)


def test_graph_prior_rejects_out_of_range_counts():
    ps = structcounts(5, PS)
    with pytest.raises(FormDiscoveryError):
        graph_prior({"type": "chain", "adjcluster": np.zeros((6, 6))}, ps)
    with pytest.raises(FormDiscoveryError):   # would wrap to logps[3][-1] in numpy
        graph_prior({"type": "tree", "adjcluster": np.zeros((2, 2)), "illegal": [0, 1]}, ps)
    # a squeezed 1x1 adjcluster (scalar) counts as one node
    assert graph_prior({"type": "chain", "adjcluster": 0.0}, ps) == ps.logps[1][0]


def test_graph_prior_on_baseline_graphs():
    ij = np.atleast_2d(FX["bl_ij"]).astype(int)
    kinds = list(FX["bl_kind"])
    assert len(kinds) == 63
    res = {k: loadmat(FIXTURES_DIR / "baseline" / k / "resultsdemo.mat",
                      struct_as_record=False, squeeze_me=True)["structure"]
           for k in ("feat", "rel")}
    cache = {}
    for m, (kind, (i, j)) in enumerate(zip(kinds, ij)):
        g = res[kind][i - 1, j - 1]
        n = int(g.objcount)
        assert n == FX["bl_nobj"][m]
        if n not in cache:
            cache[n] = structcounts(n, PS)
        np.testing.assert_allclose(graph_prior(g, cache[n]), FX["bl_gp"][m], **TOL,
                                   err_msg=f"{kind} {i},{j} {g.type}")


@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "params.mat"
    octave.feval("fx_params", str(out), nout=0)
    old = loadmat(FIXTURES_DIR / "params.mat")
    new = loadmat(out)

    def same(a, b, k):
        if a.dtype == object:
            assert a.shape == b.shape, k
            for x, y in zip(a.ravel(), b.ravel()):
                same(np.asarray(x), np.asarray(y), k)
        elif a.dtype.names:
            assert a.dtype.names == b.dtype.names, k
            for f in a.dtype.names:
                same(a[f], b[f], f"{k}.{f}")
        else:
            np.testing.assert_array_equal(a, b, err_msg=k)

    for k, v in old.items():
        if not k.startswith("__") and k != "octave_version":
            same(v, new[k], k)


@pytest.mark.octave
def test_live_structcounts_random_theta(octave):
    rng = np.random.default_rng(20260929)
    for n in (4, 17, 26):
        theta = float(rng.uniform(0.05, 0.95))
        ops = octave.structcounts(float(n), {"theta": theta})
        ps = structcounts(n, PS.replace(theta=theta))
        np.testing.assert_array_equal(ps.T, ops["T"])
        logps = np.asarray(ops["logps"], dtype=object).ravel()
        for i in range(10):
            np.testing.assert_allclose(ps.logps[i], np.ravel(logps[i]), **TOL)
        for type in ("tree", "cylinder", "undirdomtree"):
            k = int(rng.integers(1, n))
            g = {"type": type, "adjcluster": np.zeros((k, k)), "illegal": np.zeros((0,))}
            og = octave.graph_prior({"type": type, "adjcluster": np.zeros((k, k)),
                                     "illegal": np.zeros((1, 0))}, ops)
            np.testing.assert_allclose(graph_prior(g, ps), og, **TOL)
