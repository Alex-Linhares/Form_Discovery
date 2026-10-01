"""Parity of ``weights.mat2vec``, ``weights.combineWs`` and ``weights.extract_weights``
(item 15, L2-b2) with Octave.

The fixture ``tests/fixtures/weights.mat`` comes from ``legacy/tests_octave/fx_weights.m``
(regenerate with ``python legacy/tools/gen_fixtures.py weights``):

- ``gr``: 55 graphs over 10 objects (one-cluster graphs, seeded ``split_node`` sequences
  for chain, ring, tree, hierarchy, partition, connected, grid and cylinder, and graphs
  with unassigned objects), each 'raw' and with random weights ('rw'), plus 46 'zw'
  graphs ('rw' with the first component's ``Wsym`` zeroed);
- ``rt``: for each graph and each of the 8 tying modes in ``modes`` (fixedall,
  fixedinternal, fixedexternal, prodtied): ``mat2vec``, ``combineWs`` of a random
  ``Wvec``, ``mat2vec`` of the log-weight result, ``extract_weights`` on random gradients;
- ``bl``: calls captured by spies while re-running the chain, ring and tree feature
  baselines.

Fixture values are 1-based; the port is 0-based (``CONVENTIONS.md``). Every comparison is
exact for structure and rtol 1e-10 for weights.
"""

from collections import Counter

import numpy as np
import pytest
from scipy.io import loadmat

from formdiscovery import FormDiscoveryError
from formdiscovery.io import FIXTURES_DIR, graph_from_mat, load_fixture
from formdiscovery.params import Params
from formdiscovery.weights import combineWs, extract_weights, mat2vec
from tests.helpers import assert_graph_equal

FX = load_fixture("weights")
PS = Params.default()
MODES = [tuple(int(x) for x in m) for m in np.atleast_2d(FX["modes"])]
MODE_IDS = ["fa%d-fi%d-fe%d-pt%d" % m for m in MODES]
GRAPHS = [graph_from_mat(g["graph"]) for g in FX["gr"]]


def _ps(mode):
    fa, fi, fe, pt = (int(x) for x in np.atleast_1d(mode))
    return PS.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt)


def _vec(x):
    return np.atleast_1d(np.asarray(x, dtype=float)).ravel()


def _err(x):
    return str(x) if np.size(x) else ""


def assert_vec(a, b, msg=""):
    b = _vec(b)
    assert a.ndim == 1 and len(a) == len(b), f"{msg}: length {len(a)} != {len(b)}"
    np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-12, err_msg=msg)


def _loglike(g):
    """graph_like_conn.m:7: log of the Wsym entries on adjsym."""
    g = g.copy()
    m = g.adjsym > 0
    g.Wsym = g.Wsym.copy()
    g.Wsym[m] = np.log(g.Wsym[m])
    return g


def check_rt(r, graphs, modes):
    g = graphs[int(r["graph"]) - 1]
    ps = _ps(modes[int(r["mode"]) - 1])
    msg = f"graph {int(r['graph'])} mode {int(r['mode'])}"
    for key in ("v0err", "v1err", "ewerr"):
        assert not _err(r[key]), (msg, key, _err(r[key]))
    v0 = mat2vec(g.Wsym, g, ps)
    assert_vec(v0, r["v0"], msg + " mat2vec")
    if _err(r["cwerr"]):
        assert "out of bound" in _err(r["cwerr"])
        with pytest.raises(FormDiscoveryError, match="out of bound"):
            combineWs(g, _vec(r["Wvec"]), ps)
        return v0, None
    cw = combineWs(g, _vec(r["Wvec"]), ps)
    assert_graph_equal(cw, r["cw"], msg=msg + " combineWs")
    gl = _loglike(cw)
    assert_vec(mat2vec(gl.Wsym, gl, ps), r["v1"], msg + " mat2vec round trip")
    dW, dWp = extract_weights(np.zeros((g.objcount, g.objcount)), r["Wb"], r["Wbp"],
                              r["Wd"], r["Wdp"], cw, ps)
    assert_vec(dW, r["dW"], msg + " dWvec")
    assert_vec(dWp, r["dWp"], msg + " dWvecprior")
    return v0, cw


# --- fixture contents ---------------------------------------------------------------------

def test_fixture_contents():
    assert len(FX["gr"]) == 156 and len(FX["rt"]) == 156 * 8
    variants = Counter(str(g["variant"]) for g in FX["gr"])
    assert variants == {"raw": 55, "rw": 55, "zw": 46}
    assert set(MODES) == {(0, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 1, 1, 0),
                          (1, 0, 0, 0), (0, 0, 0, 1), (0, 0, 1, 1), (0, 1, 0, 1)}
    nclust = Counter(g.adjcluster.shape[0] == 1 for g in GRAPHS)
    assert nclust[True] >= 4 and nclust[False] >= 100
    assert sum(g.ncomp == 2 and g.adjcluster.shape[0] > 2 for g in GRAPHS) >= 20
    assert sum(np.any(np.asarray(g.z) < 0) for g in GRAPHS) >= 14
    assert sum(np.any(np.tril(g.adjcluster, -1) != np.triu(g.adjcluster, 1).T)
               for g in GRAPHS) >= 20  # directed cluster graphs
    for r in FX["rt"]:
        for key in ("v0err", "v1err", "ewerr"):
            assert not _err(r[key])
        zw_pt = (str(FX["gr"][int(r["graph"]) - 1]["variant"]) == "zw"
                 and MODES[int(r["mode"]) - 1] in ((0, 0, 0, 1), (0, 0, 1, 1)))
        assert bool(_err(r["cwerr"])) == zw_pt


def test_prodtied_skips_zero_weight_component():
    """mat2vec.m:25 drops a prodtied component whose Wsym sums to 0, so combineWs, which
    still takes edgecountsym entries for it (combineWs.m:41), runs out of Wvec."""
    n = 0
    for r in FX["rt"]:
        q = int(r["graph"]) - 1
        mode = MODES[int(r["mode"]) - 1]
        if str(FX["gr"][q]["variant"]) != "zw" or mode not in ((0, 0, 0, 1), (0, 0, 1, 1)):
            continue
        g, rw = GRAPHS[q], GRAPHS[q - 1]  # the 'rw' graph precedes its 'zw' variant
        assert str(FX["gr"][q - 1]["variant"]) == "rw"
        k = int(g.components[0].edgecountsym)
        assert len(mat2vec(g.Wsym, g, _ps(mode))) == len(mat2vec(rw.Wsym, rw, _ps(mode))) - k
        assert _err(r["cwerr"])
        n += 1
    assert n == 92


# --- round trips --------------------------------------------------------------------------

@pytest.mark.parametrize("mode", range(1, 9), ids=MODE_IDS)
def test_parity(mode):
    recs = [r for r in FX["rt"] if int(r["mode"]) == mode]
    assert len(recs) == 156
    for r in recs:
        check_rt(r, GRAPHS, MODES)


def test_round_trip():
    """exp(mat2vec(log Wsym of combineWs(g, Wvec))) == Wvec, except the internal entries
    with prodtied, which come back as log(w) (KI-18)."""
    broken = Counter()
    for r in FX["rt"]:
        if _err(r["cwerr"]):
            continue
        mode = MODES[int(r["mode"]) - 1]
        g = GRAPHS[int(r["graph"]) - 1]
        ps = _ps(mode)
        Wvec = _vec(r["Wvec"])
        gl = _loglike(combineWs(g, Wvec, ps))
        v1 = mat2vec(gl.Wsym, gl, ps)
        assert len(v1) == len(Wvec)
        fa, fi, fe, pt = mode
        if pt and not fi and np.sum(g.adjcluster) > 0:
            k = 1 if fe else g.objcount
            np.testing.assert_allclose(np.exp(v1[:k]), Wvec[:k], rtol=1e-12)
            np.testing.assert_allclose(v1[k:], Wvec[k:], rtol=1e-12)  # raw, not log
            assert not np.allclose(np.exp(v1), Wvec)
            broken[mode] += 1
        else:
            np.testing.assert_allclose(np.exp(v1), Wvec, rtol=1e-12)
    assert broken == {(0, 0, 0, 1): 94, (0, 0, 1, 1): 94}


def test_vector_lengths():
    """mat2vec lengths per mode: 1 (fixedall), 1-2 (fixedint+ext), nobj [+1], ..."""
    for r in FX["rt"]:
        fa, fi, fe, pt = MODES[int(r["mode"]) - 1]
        g = GRAPHS[int(r["graph"]) - 1]
        n = len(_vec(r["v0"]))
        nint = int(np.sum(np.tril(g.adjclustersym, -1) != 0))
        has_int = np.sum(g.adjcluster) > 0
        if fa:
            assert n == 1
        elif fi and fe:
            assert n == 1 + has_int
        elif fi:
            assert n == g.objcount + has_int
        elif fe and not pt:
            assert n == 1 + nint
        elif not pt:
            assert n == g.objcount + nint


def test_prodtied_matches_untied_on_single_component():
    """One component: the edge map numbers the same lower-triangle edges, so combineWs
    gives the same cluster weights with and without prodtied."""
    n = 0
    for r in FX["rt"]:
        g = GRAPHS[int(r["graph"]) - 1]
        if MODES[int(r["mode"]) - 1] != (0, 0, 0, 0) or g.ncomp != 1:
            continue
        Wvec = _vec(r["Wvec"])
        a = combineWs(g, Wvec, _ps((0, 0, 0, 0)))
        b = combineWs(g, Wvec, _ps((0, 0, 0, 1)))
        np.testing.assert_array_equal(a.Wclustersym, b.Wclustersym)
        np.testing.assert_array_equal(a.Wsym, b.Wsym)
        n += 1
    assert n >= 60


# --- spied baseline runs ------------------------------------------------------------------

def test_spied_runs_match_baseline():
    """The spies do not change the runs: final scores equal the committed baselines."""
    feat = loadmat(FIXTURES_DIR / "baseline" / "feat" / "resultsdemo.mat")["modellike"]
    assert len(FX["bl_run"]) == 3
    for r in range(3):
        s, d = int(FX["bl_sind"][r]), int(FX["bl_dind"][r])
        np.testing.assert_allclose(FX["bl_ll"][r], feat[s - 1, d - 1], rtol=1e-10,
                                   err_msg=FX["bl_run"][r])


def check_bl(r):
    g = graph_from_mat(r["graph"])
    ps = _ps(r["mode"])
    fn = str(r["fn"])
    if fn == "mat2vec":
        assert_vec(mat2vec(np.atleast_2d(r["W"]), g, ps), r["out"], fn)
    elif fn == "combineWs":
        assert_graph_equal(combineWs(g, _vec(r["Wvec"]), ps), r["out"], msg=fn)
    else:
        dW, dWp = extract_weights(None, r["Wb"], r["Wbp"], r["Wd"], r["Wdp"], g, ps)
        assert_vec(dW, r["out"], fn)
        assert_vec(dWp, r["out2"], fn + " prior")
    return fn


def test_baseline_calls():
    seen = Counter()
    for r in FX["bl"]:
        seen[(check_bl(r), tuple(int(x) for x in np.atleast_1d(r["mode"])))] += 1
    # runmodel's 'intext' init: all tied, then external tied, then untied (runmodel.m:222-233)
    for fn in ("mat2vec", "combineWs", "extract_weights"):
        for mode in ((0, 1, 1, 0), (0, 0, 1, 0), (0, 0, 0, 0)):
            assert seen[(fn, mode)] == 18


# --- error paths and value semantics ------------------------------------------------------

def _some(pred):
    for r in FX["rt"]:
        g = GRAPHS[int(r["graph"]) - 1]
        if pred(g, MODES[int(r["mode"]) - 1]):
            return r, g
    raise AssertionError("no such record")


def test_errors():
    r, g = _some(lambda g, m: m == (0, 0, 0, 0) and np.sum(g.adjcluster) > 2)
    Wvec = _vec(r["Wvec"])
    with pytest.raises(FormDiscoveryError, match="out of bound"):
        combineWs(g, Wvec[:g.objcount - 1], _ps((0, 0, 0, 0)))
    with pytest.raises(FormDiscoveryError, match="nonconformant"):
        combineWs(g, Wvec[:-1], _ps((0, 0, 0, 0)))
    with pytest.raises(FormDiscoveryError, match="nonconformant"):
        combineWs(g, np.concatenate([Wvec, [1.0]]), _ps((0, 0, 0, 0)))
    bad = g.copy()
    bad.objcount = g.objcount - 1
    with pytest.raises(FormDiscoveryError, match="objcount"):
        combineWs(bad, Wvec, _ps((0, 0, 0, 0)))
    with pytest.raises(FormDiscoveryError, match="out of bound"):
        combineWs(g, [], _ps((1, 0, 0, 0)))


def test_scalar_internal_weight_broadcasts():
    """MATLAB W(find(W)) = scalar fills every edge."""
    r, g = _some(lambda g, m: m == (0, 0, 0, 0) and np.sum(g.adjcluster) > 2)
    Wvec = _vec(r["Wvec"])[:g.objcount + 1]
    cw = combineWs(g, Wvec, _ps((0, 0, 0, 0)))
    np.testing.assert_array_equal(cw.Wclustersym, Wvec[-1] * g.adjclustersym)


def test_inputs_not_mutated():
    for r in FX["rt"][::7]:
        g = GRAPHS[int(r["graph"]) - 1]
        before = g.copy()
        Wvec = _vec(r["Wvec"])
        Wb = np.array(r["Wb"], dtype=float, copy=True)
        check_rt(r, GRAPHS, MODES)
        assert_graph_equal(g, before)
        np.testing.assert_array_equal(Wvec, _vec(r["Wvec"]))
        np.testing.assert_array_equal(Wb, np.asarray(r["Wb"], dtype=float))


# --- live Octave --------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "weights.mat"
    octave.eval(f"fx_weights('{out}');", nout=0)
    new = load_fixture("weights", fixtures_dir=tmp_path)
    for key in ("gr", "rt", "bl"):
        assert len(new[key]) == len(FX[key])
    for a, b in zip(new["rt"], FX["rt"]):
        np.testing.assert_array_equal(_vec(a["v0"]), _vec(b["v0"]))
        np.testing.assert_array_equal(_vec(a["dW"]), _vec(b["dW"]))
        assert _err(a["cwerr"]) == _err(b["cwerr"])
        if not _err(b["cwerr"]):  # cw stays the placeholder 0 when combineWs errored
            assert_graph_equal(a["cw"], b["cw"], rtol=0, atol=0)
    np.testing.assert_allclose(new["bl_ll"], FX["bl_ll"], rtol=1e-12)


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    """Fresh split sequences, weights and gradients."""
    out = tmp_path / "weights.mat"
    octave.eval(f"fx_weights('{out}', 7919);", nout=0)
    new = load_fixture("weights", fixtures_dir=tmp_path)
    graphs = [graph_from_mat(g["graph"]) for g in new["gr"]]
    modes = [tuple(int(x) for x in m) for m in np.atleast_2d(new["modes"])]
    for r in new["rt"]:
        check_rt(r, graphs, modes)
    for r in new["bl"]:
        check_bl(r)
