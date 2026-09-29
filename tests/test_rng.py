"""Permutation replay (item 22, PLAN.md §4.2): ``formdiscovery.rng`` and the Octave
``randperm`` shim ``matlab/octave_shims/randperm.m``.

The fixture ``tests/fixtures/rng.mat`` comes from ``tests/octave/fx_rng.m`` (regenerate
with ``python tools/gen_fixtures.py rng``). It records the shim's four behaviours:

- ``bi``: pass-through. Seeded, it equals the built-in.
- ``id``: identity.
- ``qu``: queue replay, rewind and reload.
- ``er``: the error messages.

It also records ``cs``, the shim at the real call site ``choose_seedpairs.m:24``. The
tests check that the Python providers draw exactly what the shim draws, and that the
queue/log text format is identical on both sides. The live tests use the ``replay``
fixture (``tests/conftest.py``) to run fresh queues and seeds through Octave.

Everything here is integer data and is compared exactly (PLAN.md §2).
"""

import itertools
import re

import numpy as np
import pytest

from formdiscovery.io import load_fixture, to0
from formdiscovery.rng import (
    IdentityPermutations,
    NumpyPermutations,
    PermutationProvider,
    RecordingPermutations,
    ReplayError,
    ReplayPermutations,
    as_provider,
    check_perm,
    parse_queue,
    read_queue,
    write_queue,
)

FX = load_fixture("rng")
SIZES = [int(n) for n in FX["sizes"]]


def perms0(cell):
    """A fixture cell of 1-based permutations -> list of 0-based int arrays."""
    return [to0(np.atleast_1d(p)) for p in cell]


def draw(provider, sizes):
    return [provider.randperm(n) for n in sizes]


def assert_perms_equal(a, b):
    assert len(a) == len(b)
    for i, (x, y) in enumerate(zip(a, b)):
        assert np.array_equal(x, y), (i, x, y)


def queue_text(perms):
    """The exact text ``write_queue`` produces, which is also the shim's log format."""
    return "".join(" ".join(map(str, [p.size, *(p + 1)])) + "\n" for p in perms)


def seedpairs_top(z, c, rng):
    """Test-only mirror of ``choose_seedpairs.m:10-37`` for a top-level split
    (``compind < 0``, pc = 1). It exists only to consume permutations at a real call
    site; the port is item 23. ``z`` holds MATLAB cluster labels, and the result is
    0-based."""
    z = np.asarray(z)
    part = np.flatnonzero(z == c)
    if part.size <= 5:
        sp = np.array(list(itertools.combinations(part, 2)))
    else:
        pair2 = []
        for m in part:
            cm = np.flatnonzero(z == z[m])
            cm = cm[cm != m]
            cm = cm[rng.randperm(cm.size)]
            if cm.size == 0:
                cm = part[part != m]
            pair2.append(cm[0])
        sp = np.column_stack([part, pair2])
    return np.vstack([sp, sp[:, ::-1]])


# --- fixture parity ----------------------------------------------------------------------

@pytest.mark.parametrize("rec", FX["bi"], ids=lambda r: f"seed{int(r['seed'])}")
def test_passthrough_is_builtin(rec):
    """With FD_RANDPERM unset the shim leaves the Octave stream unchanged (the baselines
    stay valid), and its log replays to the same draws in Python."""
    out, ref = perms0(rec["out"]), perms0(rec["ref"])
    assert_perms_equal(out, ref)
    assert [p.size for p in out] == SIZES
    log = parse_queue(rec["logtext"])
    assert_perms_equal(log, out)
    assert rec["logtext"] == queue_text(out)
    rp = ReplayPermutations(log)
    assert_perms_equal(draw(rp, SIZES), out)
    rp.assert_exhausted()


def test_identity():
    out = perms0(FX["id"]["out"])
    assert_perms_equal(out, draw(IdentityPermutations(), SIZES))
    assert FX["id"]["logtext"] == queue_text(out)


def test_queue_replay():
    qu = FX["qu"]
    sizes = [int(n) for n in qu["sizes"]]
    queue = parse_queue(qu["qtext"])
    assert [p.size for p in queue] == sizes and 0 in sizes
    out = perms0(qu["out"])
    assert_perms_equal(out, queue)
    rp = ReplayPermutations(queue)
    assert_perms_equal(draw(rp, sizes), out)
    rp.assert_exhausted()
    # Octave's log, Octave's queue file and write_queue are byte-identical
    assert qu["logtext"] == qu["qtext"] == queue_text(queue)


def test_queue_rewind_and_reload():
    qu = FX["qu"]
    queue = parse_queue(qu["qtext"])
    assert_perms_equal(perms0(qu["rew"]), queue[:2])
    assert np.array_equal(to0(qu["sw"]), [2, 0, 1])


def test_write_queue_file_matches_shim_format(tmp_path):
    queue = parse_queue(FX["qu"]["qtext"])
    f = tmp_path / "q.txt"
    write_queue(f, queue)
    assert f.read_text() == FX["qu"]["qtext"]
    assert_perms_equal(read_queue(f), queue)


def _strip(msg):
    """Drop the prefix and file paths, which differ between Octave, Python and runs."""
    msg = re.sub(r" in \S+\)", ")", msg)
    return re.sub(r"(randperm shim|randperm replay)|\S*/\S+", "", msg)


def test_errors_match_shim():
    er = FX["er"]
    rp = ReplayPermutations([[1, 0]])
    rp.randperm(2)
    with pytest.raises(ReplayError) as e:
        rp.randperm(2)
    assert _strip(str(e.value)) == _strip(er["exhausted"])
    with pytest.raises(ReplayError) as e:
        ReplayPermutations([[1, 0]]).randperm(3)
    assert _strip(str(e.value)) == _strip(er["length"])
    assert "is not a permutation of 1:3" in er["notperm"]
    with pytest.raises(ValueError, match="not a permutation"):
        parse_queue("3 1 1 2\n")
    assert er["header"].endswith("line 1: header says 3 entries, found 2")
    with pytest.raises(ValueError, match="line 1: header says 3 entries, found 2"):
        parse_queue("3 1 2\n")
    assert "only randperm(n)" in er["twoarg_identity"]
    assert "only randperm(n)" in er["twoarg_queue"]
    assert np.size(er["twoarg_builtin"]) == 2


def test_call_site_choose_seedpairs():
    """choose_seedpairs.m:24 draws through the shim. Python makes the same draws, in
    the same order, and gets the same seed pairs."""
    cs = FX["cs"]
    z, c = cs["z"], cs["c"]
    assert np.array_equal(seedpairs_top(z, c, IdentityPermutations()), to0(cs["ident"]))
    log = parse_queue(cs["reclog"])
    assert [p.size for p in log] == [6] * 7
    rp = ReplayPermutations(log)
    got = seedpairs_top(z, c, rp)
    rp.assert_exhausted()
    assert np.array_equal(got, to0(cs["rec"]))
    assert np.array_equal(to0(cs["rep"]), to0(cs["rec"]))
    assert not np.array_equal(to0(cs["rec"]), to0(cs["ident"]))


# --- Python providers ------------------------------------------------------------------

def test_providers_satisfy_protocol():
    for p in (NumpyPermutations(0), IdentityPermutations(), ReplayPermutations([]),
              RecordingPermutations()):
        assert isinstance(p, PermutationProvider)


@pytest.mark.parametrize("n", [0, 1, 2, 7, 50])
def test_numpy_provider(n):
    a = NumpyPermutations(3).randperm(n)
    assert a.dtype == np.int64 and np.array_equal(np.sort(a), np.arange(n))
    assert np.array_equal(a, NumpyPermutations(3).randperm(n))


def test_bad_sizes():
    for prov in (NumpyPermutations(0), IdentityPermutations()):
        for n in (-1, 2.5):
            with pytest.raises(ValueError):
                prov.randperm(n)
    assert IdentityPermutations().randperm(4.0).tolist() == [0, 1, 2, 3]


def test_as_provider():
    assert isinstance(as_provider(), NumpyPermutations)
    assert np.array_equal(as_provider(5).randperm(9), NumpyPermutations(5).randperm(9))
    g = np.random.default_rng(1)
    assert as_provider(g).generator is g
    ident = IdentityPermutations()
    assert as_provider(ident) is ident
    with pytest.raises(TypeError):
        as_provider("seed")


def test_replay_bookkeeping():
    rp = ReplayPermutations([[2, 0, 1], [], [0]])
    first = rp.randperm(3)
    first[0] = 99                       # callers get copies
    assert rp.queue[0].tolist() == [2, 0, 1]
    assert rp.consumed == 1 and len(rp.remaining()) == 2
    with pytest.raises(ReplayError, match="2 of 3 queue entries unused"):
        rp.assert_exhausted()
    assert rp.randperm(0).size == 0 and rp.randperm(1).tolist() == [0]
    rp.assert_exhausted()
    with pytest.raises(ValueError):
        ReplayPermutations([[0, 0]])
    with pytest.raises(ValueError):
        check_perm([[0, 1]])
    with pytest.raises(ValueError):
        check_perm([0, 1], n=3)


def test_record_write_replay_roundtrip(tmp_path):
    rec = RecordingPermutations(NumpyPermutations(11))
    sizes = [4, 0, 1, 9, 3, 3]
    drawn = draw(rec, sizes)
    f = tmp_path / "log.txt"
    write_queue(f, rec.log)
    assert f.read_text().splitlines()[1] == "0"     # empty permutation: no trailing space
    rp = ReplayPermutations.from_file(f)
    assert_perms_equal(draw(rp, sizes), drawn)
    rp.assert_exhausted()


# --- live Octave parity -----------------------------------------------------------------

@pytest.mark.octave
def test_live_fixture_regenerates(octave, tmp_path):
    out = tmp_path / "rng.mat"
    octave.eval(f"fx_rng('{out}');", nout=0)
    new = load_fixture(str(out))
    for r0, r1 in zip(FX["bi"], new["bi"]):
        assert_perms_equal(perms0(r0["out"]), perms0(r1["out"]))
        assert r0["logtext"] == r1["logtext"]
    for part in ("qu", "cs"):
        for k, v in FX[part].items():
            if isinstance(v, str):
                assert v == new[part][k], (part, k)
    assert FX["id"]["logtext"] == new["id"]["logtext"]
    assert np.array_equal(to0(FX["cs"]["rec"]), to0(new["cs"]["rec"]))
    for k, v in FX["er"].items():
        if isinstance(v, str):
            assert _strip(v) == _strip(new["er"][k]), k


def _octave_draws(octave, sizes):
    octave.push("rp_sizes", np.asarray(sizes, dtype=float).reshape(1, -1))
    octave.eval("for rp_k = 1:numel(rp_sizes), randperm(rp_sizes(rp_k)); end", nout=0)


@pytest.mark.octave
def test_live_queue_consumed_identically(replay):
    """A fresh numpy queue: Octave (through the shim) and Python draw the same
    sequence, entry for entry."""
    g = np.random.default_rng(7919)
    sizes = [int(n) for n in g.integers(0, 15, size=40)]
    queue = [g.permutation(n) for n in sizes]
    py = replay.queue(queue)
    _octave_draws(replay.octave, sizes)
    assert_perms_equal(replay.octave_log(), queue)
    assert_perms_equal(draw(py, sizes), queue)
    py.assert_exhausted()
    with pytest.raises(Exception, match="queue exhausted"):
        replay.octave.eval("randperm(1);", nout=0)


@pytest.mark.octave
@pytest.mark.parametrize("seed", [1, 5, 7919])
def test_live_record_then_replay_call_site(replay, seed):
    """Octave's own seeded stream, recorded at choose_seedpairs.m:24, replays in
    Python to the same seed pairs. Identity mode agrees too."""
    g = np.random.default_rng(seed)
    z = g.integers(1, 3, size=14).astype(float)
    z[:7] = 1                                  # cluster 1 has > 5 members
    octave = replay.octave
    octave.push("rp_z", z.reshape(1, -1))
    cmd = "rp_sp = choose_seedpairs(struct('z', rp_z), -1, 1, 1, struct());"
    replay.record(seed)
    octave.eval(cmd, nout=0)
    sp = to0(octave.pull("rp_sp"))
    py = replay.from_log()
    assert [p.size for p in py.queue] == [int((z == 1).sum()) - 1] * int((z == 1).sum())
    assert np.array_equal(seedpairs_top(z, 1, py), sp)
    py.assert_exhausted()

    ident = replay.identity()
    octave.eval(cmd, nout=0)
    assert np.array_equal(seedpairs_top(z, 1, ident), to0(octave.pull("rp_sp")))
