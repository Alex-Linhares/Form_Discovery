"""Parity of ``formdiscovery.preprocess`` (item 10, L1 preprocess) with Octave.

The fixture ``tests/fixtures/preprocess.mat`` comes from ``legacy/tests_octave/fx_preprocess.m``
(regenerate with ``python legacy/tools/gen_fixtures.py preprocess``). It holds ``scaledata`` on every
data set (defaults; ``makesimlike`` and ``none`` on feature sets; ``simtransform='center'`` on
similarity sets; colors with ``featforce``), with ``judges`` covering the missing-data chunk
path, plus constructed inputs for the ``makesimlike`` no-root branch and chunk ties. The live
tests rerun the script and compare on fresh random inputs.
"""

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.io import FIXTURES_DIR, load_dataset, load_fixture, to0
from formdiscovery.params import DATASETS, Params, setrunps
from formdiscovery.preprocess import makechunks, makesimlike, scaledata, simpleshiftscale

FX = load_fixture("preprocess")
TOL = dict(rtol=1e-10, atol=1e-12)
PS = Params.default()
FIELDS = ("SS", "chunkcount", "chunknum", "featind", "objind", "chunksize", "chunkSS")


def _cells(v, n):
    """A MATLAB cell of ``n`` entries after ``simplify_cells`` -> list."""
    if n == 1 and not isinstance(v, list):
        return [v]
    return list(v)


def check_case(c, data, ps):
    label = f"{c['name']}/{c['cfg']}"
    dout, pout = scaledata(data, ps)
    assert pout.runps.type == c["type"], label
    if c["type"] == "rel":
        assert c["unchanged"] and not c["has_missingdata"], label
        assert dout is data and pout.missingdata is None, label
        assert pout.runps.chunknum is None and pout.runps.SS is None, label
        return
    np.testing.assert_allclose(dout, np.atleast_2d(c["data"]), err_msg=label, **TOL)
    assert pout.missingdata == c["missingdata"], label
    has = dict(zip(FIELDS, np.atleast_1d(c["has"]).astype(bool)))
    for f in FIELDS:
        assert (getattr(pout.runps, f) is not None) == has[f], (label, f)
    if has["SS"]:
        np.testing.assert_allclose(pout.runps.SS, c["r_SS"], err_msg=label, **TOL)
        assert pout.runps.chunkcount == c["r_chunkcount"], label
    if has["chunknum"]:
        n = int(c["r_chunknum"])
        assert pout.runps.chunknum == n, label
        feat = _cells(c["r_featind"], n)
        obj = _cells(c["r_objind"], n)
        size = _cells(c["r_chunksize"], n)
        css = _cells(c["r_chunkSS"], n)
        for k in range(n):
            np.testing.assert_array_equal(pout.runps.featind[k], to0(np.atleast_1d(feat[k])))
            np.testing.assert_array_equal(pout.runps.objind[k], to0(np.atleast_1d(obj[k])))
            assert pout.runps.chunksize[k] == size[k]
            np.testing.assert_allclose(pout.runps.chunkSS[k], np.atleast_2d(css[k]),
                                       err_msg=f"{label} chunk {k}", **TOL)
        # every feature is in exactly one chunk, chunk masks are sorted lexicographically
        allf = np.sort(np.concatenate(pout.runps.featind))
        np.testing.assert_array_equal(allf, np.arange(dout.shape[1]))


def _ps_for(c):
    if c["name"] in DATASETS:
        data = load_dataset(c["name"])
        ps = PS.replace(featforce=1) if c["cfg"] == "featforce" else PS
        _, ps = setrunps(data, int(c["dind"]) - 1, ps)
        if c["cfg"] == "makesimlike":
            ps = ps.replace(datatransform="makesimlike")
        elif c["cfg"] == "none":
            ps = ps.replace(datatransform="none")
        elif c["cfg"] == "center":
            ps = ps.replace(simtransform="center")
        return data, ps
    raise KeyError(c["name"])


def test_every_dataset_covered():
    names = {c["name"] for c in FX["cases"]}
    assert names == set(DATASETS)
    cfgs = {(c["name"], c["cfg"]) for c in FX["cases"]}
    assert ("judges", "makesimlike") in cfgs and ("cities", "center") in cfgs
    assert ("colors", "featforce") in cfgs
    assert len(FX["cases"]) == 20 + 2 * 10 + 3 + 1   # 10 feature, 3 similarity sets


@pytest.mark.parametrize("i", range(44))
def test_scaledata_fixture(i):
    c = FX["cases"][i]
    data, ps = _ps_for(c)
    check_case(c, data, ps)


def test_judges_chunks():
    c = next(c for c in FX["cases"] if c["name"] == "judges" and c["cfg"] == "default")
    assert c["missingdata"] == 1 and int(c["r_chunknum"]) == 38
    data, ps = _ps_for(c)
    dout, pout = scaledata(data, ps)
    # chunk order: unique(~isinf(data)', 'rows') is lexicographic over object masks
    masks = np.array([np.isin(np.arange(13), o) for o in pout.runps.objind])
    keys = [tuple(m) for m in masks.astype(int)]
    assert keys == sorted(keys) and len(set(keys)) == 38
    # scaledata does not set SS/chunkcount with missing data; Inf stays Inf
    assert pout.runps.SS is None and pout.runps.chunkcount is None
    np.testing.assert_array_equal(np.isinf(dout), np.isinf(data))


@pytest.mark.parametrize("key", ["c_tie_cases", "c_miss_cases"])
def test_constructed_missing(key):
    X = FX[key.replace("_cases", "")]
    for c in FX[key]:
        ps = PS.copy()
        ps.runps.type = "feat"
        if c["cfg"] == "makesimlike":
            ps.datatransform = "makesimlike"
        check_case(c, X, ps)


def test_direct_calls():
    ps = PS.replace(missingdata=0)
    for base, fns in (("c_same", ("msl", "sss")), ("c_const", ("msl",)),
                      ("c_rand", ("msl", "sss"))):
        X = FX[base]
        for fn in fns:
            f = makesimlike if fn == "msl" else simpleshiftscale
            np.testing.assert_allclose(f(X, ps), FX[f"{base}_{fn}"], err_msg=f"{base}_{fn}",
                                       **TOL)


def test_makesimlike_no_root_branch():
    # identical rows: every quadratic has negative discriminant, so ub = kmins(argmin fmins)
    X = FX["c_same"]
    out = makesimlike(X, PS.replace(missingdata=0))
    k = X[0].mean()
    np.testing.assert_allclose(out, (X - k) / np.sqrt(np.max((X - k) @ (X - k).T / X.shape[1])),
                               **TOL)


def test_makesimlike_no_negative_discriminant():
    # one feature: b^2 - 4ac == 0 for every pair, so fmins is never assigned
    with pytest.raises(FormDiscoveryError, match="'fmins' undefined"):
        makesimlike(np.array([[1.0], [2.0], [-0.5]]), PS.replace(missingdata=0))


def test_makechunks_no_missing_is_noop():
    ps = PS.replace(missingdata=0)
    assert makechunks(np.ones((2, 2)), ps) is ps and ps.runps.chunknum is None


def test_scaledata_does_not_mutate():
    data = load_dataset("judges")
    _, ps = setrunps(data, DATASETS.index("judges"), PS)
    before = ps.copy()
    d0 = data.copy()
    scaledata(data, ps)
    assert ps.missingdata is None and ps.runps.chunknum is None and ps.runps.SS is None
    assert ps.runps == before.runps
    np.testing.assert_array_equal(data, d0)


def _feat_ps(dt):
    ps = PS.replace(datatransform=dt)
    ps.runps.type = "feat"
    return ps


EMPTY_CHUNK = np.array([[1.0, np.inf, 2.0], [0.5, np.inf, -1.0], [np.inf, np.inf, 3.0]])


EMPTY_ERR = {"simpleshiftscale": ("no observed objects", "nonconformant"),
             "makesimlike": ("'fmins' undefined", "'fmins' undefined")}


@pytest.mark.parametrize("dt", ["simpleshiftscale", "makesimlike"])
def test_feature_missing_everywhere_raises(dt):
    # every chunk here has one feature, so makesimlike fails before the empty chunk
    with pytest.raises(FormDiscoveryError, match=EMPTY_ERR[dt][0]):
        scaledata(EMPTY_CHUNK, _feat_ps(dt))
    # without a transform the empty chunk is harmless: chunkSS is 0x0
    d, ps = scaledata(EMPTY_CHUNK, _feat_ps("none"))
    assert ps.runps.chunknum == 3 and ps.runps.objind[0].size == 0
    assert ps.runps.chunkSS[0].shape == (0, 0)


@pytest.mark.octave
def test_live_feature_missing_everywhere_errors(octave):
    from oct2py import Oct2PyError
    for dt in ("simpleshiftscale", "makesimlike"):
        with pytest.raises(Oct2PyError, match=EMPTY_ERR[dt][1]):
            octave.scaledata(EMPTY_CHUNK, {"runps": {"type": "feat"}, "datatransform": dt,
                                           "simtransform": "none"}, nout=2)
    with pytest.raises(Oct2PyError, match="'fmins' undefined"):
        octave.makesimlike(np.array([[1.0], [2.0], [-0.5]]), {"missingdata": 0.0})


@pytest.mark.octave
def test_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "preprocess.mat"
    octave.feval("fx_preprocess", str(out), nout=0)
    old = loadmat(FIXTURES_DIR / "preprocess.mat")
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
def test_live_random_inputs(octave):
    rng = np.random.default_rng(20260929)
    for trial in range(4):
        n, p = int(rng.integers(3, 9)), int(rng.integers(4, 30))
        X = rng.normal(size=(n, p)) + rng.normal()
        if trial >= 2:
            X[rng.random((n, p)) < 0.3] = np.inf
            X[:, 0] = rng.normal(size=n)          # keep one fully observed feature
            X[0, :] = rng.normal(size=p)          # and no feature missing everywhere
        for dt in ("simpleshiftscale", "makesimlike"):
            ps = PS.replace(datatransform=dt)
            ps.runps.type = "feat"
            od, ops = octave.scaledata(X, {"runps": {"type": "feat"}, "datatransform": dt,
                                           "simtransform": "none"}, nout=2)
            d, pp = scaledata(X, ps)
            np.testing.assert_allclose(d, od, **TOL)
            assert pp.missingdata == ops["missingdata"]
            if pp.missingdata:
                r = ops["runps"]
                assert pp.runps.chunknum == r["chunknum"]
                feat = np.asarray(r["featind"], dtype=object).ravel()
                css = np.asarray(r["chunkSS"], dtype=object).ravel()
                for k in range(pp.runps.chunknum):
                    np.testing.assert_array_equal(pp.runps.featind[k],
                                                  to0(np.ravel(feat[k])))
                    np.testing.assert_allclose(pp.runps.chunkSS[k], np.atleast_2d(css[k]),
                                               **TOL)
            else:
                np.testing.assert_allclose(pp.runps.SS, ops["runps"]["SS"], **TOL)
    # similarity data, centred
    S = rng.random((7, 7))
    S = S + S.T
    od, _ = octave.scaledata(S, {"runps": {"type": "sim"}, "datatransform": "none",
                                 "simtransform": "center"}, nout=2)
    ps = PS.replace(simtransform="center")
    ps.runps.type = "sim"
    np.testing.assert_allclose(scaledata(S, ps)[0], od, **TOL)
