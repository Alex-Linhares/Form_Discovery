"""Parity of the ``dataprobwsig`` missing-data chunk path (``dataprobwsig.m:24-60``, item 17,
L3-a2) with Octave on the ``judges`` data (13 objects, 38 chunks).

The fixture ``tests/fixtures/dpmiss.mat`` comes from ``legacy/tests_octave/fx_dpmiss.m``
(regenerate with ``python legacy/tools/gen_fixtures.py dpmiss``):

- ``data``: judges after ``scaledata`` (``Inf`` = missing);
- ``gr``: 25 graphs over the 13 objects with random weights (one cluster, seeded
  ``split_node`` sequences for chain, ring, tree, partition, connected, grid and cylinder,
  and 4 graphs with unassigned objects);
- ``cs``: every graph in the 8 tying modes (``modes``), with ``d = data(z > 0, :)`` as
  ``graph_like.m:7-10`` passes it: the two outputs, the one-output value and (mode 1 and
  ``fixedexternal``) Octave's ``checkgrad`` value, or Octave's error message;
- ``ch``: every recursive per-chunk call (``ps.missingdata = 0``) of the first 6 mode-1
  cases, recorded by a spy with its inputs and outputs;
- ``bl``: outer calls captured while re-running partition x judges with
  ``run_baseline.m``'s settings (8 value-only calls and 8 gradient calls); ``bl_ll`` is
  the run's final score;
- ``err3``: Octave's message for three outputs on the chunk path (KI-21).

Tolerances (PLAN.md §2): rtol 1e-10 for values and gradients; the finite-difference check
uses ``e = 1e-5`` as ``graph_like_conn.m:45`` does.
"""

from collections import Counter

import numpy as np
import pytest

import formdiscovery.likelihood_feat as lf
from formdiscovery import FormDiscoveryError
from formdiscovery.graph import makeemptygraph
from formdiscovery.io import graph_from_mat, load_dataset, load_fixture
from formdiscovery.likelihood_feat import dataprobwsig
from formdiscovery.params import DATASETS, Params, setrunps
from formdiscovery.preprocess import scaledata
from formdiscovery.weights import mat2vec
from tests.helpers import assert_graph_equal, checkgrad

FX = load_fixture("dpmiss")
MODES = [tuple(int(x) for x in m) for m in np.atleast_2d(FX["modes"])]
FD_TOL = 1e-6


def _judges():
    data = load_dataset("judges")
    _, ps = setrunps(data, DATASETS.index("judges"), Params.default())
    data, ps = scaledata(data, ps)
    return data, ps.replace(overrideSS=0)


DATA, PJ = _judges()
GRAPHS = [graph_from_mat(g["graph"]) for g in FX["gr"]]
OK = [r for r in FX["cs"] if not np.size(r["err"])]


def _vec(x):
    return np.atleast_1d(np.asarray(x, dtype=float)).ravel()


def _err(x):
    return str(x) if np.size(x) else ""


def _mode_ps(mode, ps=PJ):
    fa, fi, fe, pt = mode
    return ps.replace(fixedall=fa, fixedinternal=fi, fixedexternal=fe, prodtied=pt)


def case_inputs(r, graphs=GRAPHS):
    g = graphs[int(r["graph"]) - 1]
    return _vec(r["Wvec"]), DATA[g.z >= 0], g, _mode_ps(MODES[int(r["mode"]) - 1])


def _msg(r, fx=FX):
    return f"graph {int(r['graph'])} ({fx['gr'][int(r['graph']) - 1]['src']}) mode {int(r['mode'])}"


def assert_vec(a, b, msg=""):
    b = _vec(b)
    assert a.ndim == 1 and len(a) == len(b), f"{msg}: length {len(a)} != {len(b)}"
    np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-10, err_msg=msg)


def _expect_error(octmsg, fn):
    with pytest.raises(FormDiscoveryError) as exc:
        fn()
    got = str(exc.value)
    if "chol" in octmsg:
        assert "positive definite" in got
    elif "out of bound" in octmsg:
        assert "out of bound" in got
    elif "nonconformant" in octmsg:
        assert "nonconformant" in got
    else:  # pragma: no cover
        raise AssertionError(f"unexpected Octave error {octmsg!r}")


def check_case(r, graphs=GRAPHS, fx=FX):
    Wvec, d, g, ps = case_inputs(r, graphs)
    msg = _msg(r, fx)
    if _err(r["err"]):
        _expect_error(_err(r["err"]), lambda: dataprobwsig(Wvec, d, g, ps, nargout=2))
        return
    ll, dW = dataprobwsig(Wvec, d, g, ps, nargout=2)
    np.testing.assert_allclose(ll, float(r["ll"]), rtol=1e-10, err_msg=msg)
    assert_vec(dW, r["dW"], msg + " dWvec")
    np.testing.assert_allclose(dataprobwsig(Wvec, d, g, ps, nargout=1), float(r["ll1"]),
                               rtol=1e-10, err_msg=msg)


# --- fixture contents ---------------------------------------------------------------------

def test_fixture_contents():
    assert int(FX["chunknum"]) == PJ.runps.chunknum == 38
    np.testing.assert_array_equal(np.isinf(FX["data"]), np.isinf(DATA))
    fin = ~np.isinf(DATA)
    np.testing.assert_allclose(DATA[fin], FX["data"][fin], rtol=1e-10, atol=1e-12)
    assert len(FX["gr"]) == 25 and len(FX["cs"]) == 25 * 8 and len(OK) == 161
    errs = Counter(_err(r["err"]).split(":")[0] for r in FX["cs"] if _err(r["err"]))
    assert errs == {"Wvec(14)": 21, "Wvec(13)": 2, "Wvec(11)": 1, "Wvec(3)": 1,
                    "operator *": 7, "chol": 7}
    assert {int(r["mode"]) for r in OK} == set(range(1, 9)) - {5}
    assert sum(np.any(g.z < 0) for g in GRAPHS) == 4
    assert sum(g.ncomp == 2 for g in GRAPHS) >= 6


# --- cases ----------------------------------------------------------------------------------

@pytest.mark.parametrize("mode", range(1, 9), ids=lambda m: "fa%d-fi%d-fe%d-pt%d" % MODES[m - 1])
def test_cases(mode):
    rs = [r for r in FX["cs"] if int(r["mode"]) == mode]
    assert len(rs) == 25
    for r in rs:
        check_case(r)


def test_unassigned_objects():
    """Graphs with unassigned objects (best_split.m:26-32): d holds only the assigned rows
    and the per-chunk rows are picked by rank (tind), as in dataprobwsig.m:40."""
    rs = [r for r in OK if np.any(case_inputs(r)[2].z < 0)]
    assert len(rs) >= 15
    for r in rs:
        check_case(r)


def test_fixedall_errors():
    """KI-20: fixedall without fixedexternal (mode 5) fails in reordermissing.m:22."""
    rs = [r for r in FX["cs"] if int(r["mode"]) == 5]
    assert all("out of bound 2" in _err(r["err"]) for r in rs)
    for r in rs:
        Wvec, d, g, ps = case_inputs(r)
        with pytest.raises(FormDiscoveryError, match="out of bound"):
            dataprobwsig(Wvec, d, g, ps, nargout=1)


def test_three_outputs_error():
    """KI-21: MATLAB never sets dWvecprior on the chunk path."""
    assert _err(FX["err3"]) == "element number 3 undefined in return list"
    g = GRAPHS[0]
    Wvec = np.log(0.5 + np.ones(2 + g.objcount))
    ll, dW = dataprobwsig(Wvec, DATA, g, PJ, nargout=2)
    with pytest.raises(FormDiscoveryError, match="element number 3 undefined"):
        dataprobwsig(Wvec, DATA, g, PJ)


def test_inputs_not_mutated():
    for r in OK[::20]:
        Wvec, d, g, ps = case_inputs(r)
        g0, d0, ps0, W0 = g.copy(), d.copy(), ps.copy(), Wvec.copy()
        dataprobwsig(Wvec, d, g, ps, nargout=2)
        assert_graph_equal(g, g0, rtol=0, atol=0)
        np.testing.assert_array_equal(d, d0)
        np.testing.assert_array_equal(Wvec, W0)
        assert repr(ps) == repr(ps0)


def test_one_chunk_equals_direct_path():
    """With one chunk holding every object and feature the chunk path reduces to the
    direct call: the prior is counted once and sind is the identity."""
    d = load_dataset("demo_chain_feat")
    _, ps = setrunps(d, 0, Params.default())
    d, ps = scaledata(d, ps)
    ps = ps.replace(overrideSS=0)
    ps.runps.structname = "chain"
    g = makeemptygraph(ps)
    n = len(mat2vec(g.Wsym, g, ps))
    Wvec = np.log(np.linspace(0.6, 1.4, n + 1))
    ll0, dW0 = dataprobwsig(Wvec, d, g, ps, nargout=2)
    pm = ps.replace(missingdata=1)
    pm.runps.chunknum = 1
    pm.runps.objind = [np.arange(d.shape[0])]
    pm.runps.featind = [np.arange(d.shape[1])]
    pm.runps.chunkSS = [ps.runps.SS]
    pm.runps.chunksize = [d.shape[0]]
    ll1, dW1 = dataprobwsig(Wvec, d, g, pm, nargout=2)
    np.testing.assert_allclose(ll1, ll0, rtol=1e-12)
    np.testing.assert_allclose(dW1, dW0, rtol=1e-10, atol=1e-10)


# --- recursive per-chunk calls ------------------------------------------------------------

def _record_inner(monkeypatch):
    calls = []
    orig = lf.dataprobwsig

    def spy(Wvec, d, graph, ps, nargout=3):
        out = orig(Wvec, d, graph, ps, nargout=nargout)
        if not ps.missingdata:
            calls.append((Wvec, d, graph, ps, out))
        return out

    monkeypatch.setattr(lf, "dataprobwsig", spy)
    return calls


def test_chunk_calls(monkeypatch):
    """Each recursive call gets the same reordered Wvec, data block, graph, SS and
    chunkcount as in Octave, and returns the same three outputs."""
    spied = [r for r in FX["cs"] if int(r["spied"])]
    assert len(spied) == 6 and len(FX["ch"]) == 6 * 38
    calls = _record_inner(monkeypatch)
    for r in spied:
        calls.clear()
        Wvec, d, g, ps = case_inputs(r)
        lf.dataprobwsig(Wvec, d, g, ps, nargout=2)
        ch = [c for c in FX["ch"] if int(c["case"]) == FX["cs"].index(r) + 1]
        assert len(calls) == len(ch) == 38
        for (cW, cd, cg, cps, out), c in zip(calls, ch):
            msg = f"{_msg(r)} chunk {int(c['chunk'])}"
            assert int(c["nargout"]) == 3
            np.testing.assert_allclose(cW, _vec(c["Wvec"]), rtol=1e-13, err_msg=msg)
            # the scaled judges data agree with Octave's to ~1 ulp (preprocess.scaledata)
            np.testing.assert_allclose(cd, np.atleast_2d(c["d"]).reshape(cd.shape),
                                       rtol=1e-12, atol=1e-15, err_msg=msg)
            assert_graph_equal(cg, c["graph"], msg=msg)
            np.testing.assert_allclose(np.atleast_2d(cps.runps.SS), np.atleast_2d(c["SS"]),
                                       rtol=1e-12, err_msg=msg)
            assert cps.runps.chunkcount == int(c["chunkcount"])
            ll, dW, dWp = out
            np.testing.assert_allclose(ll, float(c["ll"]), rtol=1e-10, err_msg=msg)
            assert_vec(dW, c["dW"], msg + " dW")
            assert_vec(dWp, c["dWp"], msg + " dWp")


def test_chunk_calls_cover_reordering():
    """The spied cases include chunks whose observed objects are not a prefix (so
    reordermissing and the sind reassembly do something) and unassigned objects."""
    moved = 0
    for c in FX["ch"]:
        r = FX["cs"][int(c["case"]) - 1]
        g = GRAPHS[int(r["graph"]) - 1]
        k = int(c["chunk"]) - 1
        these = np.flatnonzero(g.z >= 0)
        obs = np.intersect1d(these, PJ.runps.objind[k])
        moved += not np.array_equal(obs, these[:len(obs)])
    assert moved >= 150
    assert any(np.any(GRAPHS[int(r["graph"]) - 1].z < 0) for r in FX["cs"] if int(r["spied"]))


# --- finite-difference gradient check -----------------------------------------------------

def test_octave_checkgrad_values():
    cg = [float(r["cg"]) for r in OK if np.size(r["cg"])]
    assert len(cg) >= 80 and max(cg) < FD_TOL


@pytest.mark.parametrize("mode", [1, 2, 3, 4, 6, 7, 8],
                         ids=lambda m: "fa%d-fi%d-fe%d-pt%d" % MODES[m - 1])
def test_checkgrad(mode):
    """The reassembled gradient matches central differences in every tying mode that
    runs (fixedexternal skips the sind reassembly). Every 6th case here; all of them in
    test_checkgrad_all (slow)."""
    _checkgrad_mode(mode, 6)


@pytest.mark.slow
@pytest.mark.parametrize("mode", [1, 2, 3, 4, 6, 7, 8],
                         ids=lambda m: "fa%d-fi%d-fe%d-pt%d" % MODES[m - 1])
def test_checkgrad_all(mode):
    _checkgrad_mode(mode, 1)


def _checkgrad_mode(mode, step):
    rs = [r for r in OK if int(r["mode"]) == mode]
    assert len(rs) >= 15
    for r in rs[::step]:
        Wvec, d, g, ps = case_inputs(r)
        dval, dy, dh = checkgrad(lambda x: dataprobwsig(x, d, g, ps, nargout=2), Wvec, 1e-5)
        assert dval < FD_TOL, (_msg(r), dval)


# --- spied partition x judges run ---------------------------------------------------------

def _bl_ps(q):
    q = {k: (np.asarray(v).item() if np.size(v) == 1 and not isinstance(v, str) else v)
         for k, v in q.items()}
    assert str(q["type"]) == "feat"
    return PJ.replace(lbeta=q["lbeta"], sigbeta=q["sigbeta"], zglreg=int(q["zglreg"]),
                      overrideSS=int(q["overrideSS"]), fixedall=int(q["fixedall"]),
                      fixedinternal=int(q["fixedinternal"]),
                      fixedexternal=int(q["fixedexternal"]), prodtied=int(q["prodtied"]))


def test_spied_run_score():
    """The spy does not change the run: its final score equals the partition x judges
    score of run_baseline.m (-16201.27918, iteration 20 timing run, 42 s)."""
    assert abs(float(FX["bl_ll"]) - (-16201.27918)) < 1e-5
    assert [int(x) for x in np.ravel(FX["bl_ncalls"])] == [3216, 1313]


def test_baseline_calls():
    assert len(FX["bl"]) == 16
    assert Counter(int(b["nargout"]) for b in FX["bl"]) == {1: 8, 2: 8}
    for b in FX["bl"]:
        assert int(b["dsame"]) and int(b["samechunks"])
        g = graph_from_mat(b["graph"])
        ps = _bl_ps(b["ps"])
        Wvec = _vec(b["Wvec"])
        d = DATA[g.z >= 0]
        msg = f"call {int(b['n'])}"
        if int(b["nargout"]) > 1:
            ll, dW = dataprobwsig(Wvec, d, g, ps, nargout=2)
            assert_vec(dW, b["dW"], msg + " dWvec")
        else:
            ll = dataprobwsig(Wvec, d, g, ps, nargout=1)
        np.testing.assert_allclose(ll, float(b["ll"]), rtol=1e-10, err_msg=msg)


# --- live Octave ----------------------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "dpmiss.mat"
    octave.eval(f"fx_dpmiss('{out}');", nout=0)
    new = load_fixture("dpmiss", fixtures_dir=tmp_path)
    for key in ("gr", "cs", "ch", "bl"):
        assert len(new[key]) == len(FX[key])
    for a, b in zip(new["cs"], FX["cs"]):
        np.testing.assert_array_equal(_vec(a["Wvec"]), _vec(b["Wvec"]))
        np.testing.assert_array_equal(_vec(a["ll"]), _vec(b["ll"]))
        np.testing.assert_array_equal(_vec(a["dW"]), _vec(b["dW"]))
        assert _err(a["err"]) == _err(b["err"])
    assert float(new["bl_ll"]) == float(FX["bl_ll"])


@pytest.mark.octave
def test_live_fresh_seeds(octave, tmp_path):
    """Fresh split sequences and weights; every case matches and passes checkgrad."""
    out = tmp_path / "dpmiss.mat"
    octave.eval(f"fx_dpmiss('{out}', 7919);", nout=0)
    new = load_fixture("dpmiss", fixtures_dir=tmp_path)
    graphs = [graph_from_mat(g["graph"]) for g in new["gr"]]
    nok = 0
    for r in new["cs"]:
        check_case(r, graphs, new)
        if not _err(r["err"]):
            Wvec, d, g, ps = case_inputs(r, graphs)
            f = lambda x: dataprobwsig(x, d, g, ps, nargout=2)  # noqa: E731
            assert checkgrad(f, Wvec, 1e-5)[0] < FD_TOL
            nok += 1
    assert nok >= 100
