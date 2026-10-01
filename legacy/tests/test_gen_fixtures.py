"""legacy/tools/gen_fixtures.py --jobs N (loop0002 item 03): parallel fixture generation.

The scheduler is checked with a stand-in for ``octave-cli`` (dependencies, longest task
first, failures, the job limit). The live test regenerates a set of quick fixtures with
``--jobs 1`` and ``--jobs 4`` and asserts that the two runs and the committed fixtures have
the same content. The full comparison (all 31 fixtures, ``--jobs 16`` vs ``--jobs 1``) is
recorded in RalphLoops/loop0002/PROGRESS.md, iteration 4.
"""

import re
import threading
import time

import numpy as np
import pytest
import scipy.io

from tests.conftest import FIXTURES_DIR
from legacy.tools import gen_fixtures as gf

QUICK = ["graph", "matlab_compat", "params", "preprocess", "rng", "truegraphs", "util"]


def test_depends_matches_scripts():
    """:data:`DEPENDS` lists exactly the fixtures each script loads from tests/fixtures."""
    found = {}
    for name, path in gf.fixture_scripts().items():
        src = path.read_text()
        deps = set(re.findall(r"load\(fullfile\(fxdir, '(\w+)\.mat'\)\)", src))
        if deps:
            found[name] = deps
    assert found == {k: set(v) for k, v in gf.DEPENDS.items()}


def test_plan_tasks(tmp_path):
    scripts = gf.fixture_scripts()
    tasks = gf.plan_tasks(list(scripts), scripts, tmp_path / "out", tmp_path / "stage")
    keys = [t["key"] for t in tasks]
    assert len(keys) == len(set(keys)) == len(scripts) - 1 + gf.PAPERLEVEL_JOBS + 1
    by = {t["key"]: t for t in tasks}
    assert by["paperlevel"]["deps"] == tuple(f"paperlevel_job{j:02d}"
                                             for j in range(1, gf.PAPERLEVEL_JOBS + 1))
    assert by["paperlevel_job07"]["out"] is None
    assert "fx_paperlevel(" in by["paperlevel_job07"]["call"]
    assert ", 7);" in by["paperlevel_job07"]["call"]
    assert by["perf"]["deps"] == ("paperlevel",)
    assert by["glslow"]["deps"] == ("dataprob", "dpmiss")
    assert by["util"]["out"] == tmp_path / "out" / "util.mat"
    # a dependency that is not regenerated is read from tests/fixtures as it is
    only = gf.plan_tasks(["perf", "glslow", "dpmiss"], scripts, tmp_path, tmp_path)
    assert {t["key"]: t["deps"] for t in only} == {"perf": (), "glslow": ("dpmiss",),
                                                   "dpmiss": ()}


def _fake_octave(monkeypatch, fail=(), delay=None):
    """Stand-in for ``_run_octave``: writes a small .mat (the task's call string) after a
    short sleep and records start/end order and concurrency."""
    log, lock, live = [], threading.Lock(), [0, 0]

    def run(exe, name, call, logfile):
        key = logfile.stem
        with lock:
            live[0] += 1
            live[1] = max(live[1], live[0])
            log.append(("start", key))
        time.sleep((delay or {}).get(key, 0.02))
        m = re.search(r"'([^']+\.mat)'", call)
        ok = key not in fail
        if ok:
            scipy.io.savemat(m.group(1), {"call": call.split("(")[0], "x": np.arange(3.0)})
        logfile.write_text(call)
        with lock:
            live[0] -= 1
            log.append(("end", key))
        return ok, 0.01, 0.01

    monkeypatch.setattr(gf, "_run_octave", run)
    return log, live


def test_run_tasks_deps_and_order(monkeypatch, tmp_path):
    log, live = _fake_octave(monkeypatch, delay={"dpmiss": 0.2})
    scripts = gf.fixture_scripts()
    names = ["util", "dataprob", "dpmiss", "glslow", "graphlike", "gibbs"]
    tasks = gf.plan_tasks(names, scripts, tmp_path / "out", tmp_path / "stage")
    (tmp_path / "stage").mkdir()
    res = gf.run_tasks("octave", tasks, 3, tmp_path / "logs")
    assert all(s == "ok" for s, _, _ in res.values())
    assert sorted(p.stem for p in (tmp_path / "out").glob("*.mat")) == sorted(names)
    assert sorted(p.stem for p in (tmp_path / "logs").glob("*.log")) == sorted(names)
    pos = {e: i for i, e in enumerate(log)}
    for dep in ("dataprob", "dpmiss"):
        for user in ("glslow", "graphlike"):
            assert pos[("end", dep)] < pos[("start", user)]
    assert log[0] == ("start", "gibbs")        # longest expected first
    assert live[1] <= 3


def test_run_tasks_failure_skips_dependents(monkeypatch, tmp_path):
    _fake_octave(monkeypatch, fail={"paperlevel_job03"})
    scripts = gf.fixture_scripts()
    tasks = gf.plan_tasks(["paperlevel", "perf", "util"], scripts, tmp_path / "out",
                          tmp_path / "stage")
    (tmp_path / "stage").mkdir()
    res = gf.run_tasks("octave", tasks, 8, tmp_path / "logs")
    assert res["paperlevel_job03"][0] == "failed"
    assert res["paperlevel"][0] == "skipped" and res["perf"][0] == "skipped"
    assert res["util"][0] == "ok" and res["paperlevel_job04"][0] == "ok"
    assert sorted(p.name for p in (tmp_path / "out").glob("*.mat")) == ["util.mat"]
    text = gf.summary_table(res, 1.0, 2.0, 8)
    assert "skipped" in text and "--jobs 8" in text


def test_publish_across_file_systems(monkeypatch, tmp_path):
    """``--outdir`` on another file system than the temporary directory (loop0004 item
    01): the first ``os.replace`` fails with EXDEV, ``_publish`` copies then renames."""
    import errno
    import os

    real = os.replace
    calls = []

    def replace(a, b):
        calls.append((str(a), str(b)))
        if len(calls) == 1:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real(a, b)

    monkeypatch.setattr(gf.os, "replace", replace)
    src = tmp_path / "stage" / "x.mat"
    src.parent.mkdir()
    src.write_bytes(b"abc")
    out = tmp_path / "out" / "x.mat"
    gf._publish(src, out)
    assert out.read_bytes() == b"abc" and not src.exists()
    assert calls[1] == (f"{out}.part", str(out))
    assert sorted(p.name for p in out.parent.iterdir()) == ["x.mat"]


def test_compare_fixture_volatile(tmp_path):
    """Timing fields are skipped, temp directory names are masked, anything else counts."""
    def rec(t, msg, ll):
        return {"sf": np.array([[{"ll": ll, "total": t,
                                  "ev": np.array([[1, 1, t, 0, t, 0, t]])}]], dtype=object),
                "er": {"m": msg}}
    for name in ("perf", "other"):
        a, b, c = (tmp_path / f"{name}{i}.mat" for i in "abc")
        scipy.io.savemat(a, rec(0.5, "bad /tmp/oct-kptLyL/q.txt", -1.0))
        scipy.io.savemat(b, rec(0.7, "bad /tmp/oct-Ab12Cd/q.txt", -1.0))
        scipy.io.savemat(c, rec(0.5, "bad /tmp/oct-kptLyL/q.txt", -1.5))
        assert (gf.compare_fixture(name, a, b) == []) == (name == "perf")
        assert gf.compare_fixture(name, a, c)
    d = tmp_path / "perfd.mat"
    s = rec(0.5, "x", -1.0)
    s["sf"][0, 0]["ev"] = np.array([[1, 2, 0.5, 0, 0.5, 0, 0.5]])   # a count column
    scipy.io.savemat(d, s)
    scipy.io.savemat(tmp_path / "perfe.mat", rec(0.5, "x", -1.0))
    assert gf.compare_fixture("perf", tmp_path / "perfe.mat", d) == ["sf.ev: count columns differ"]


@pytest.mark.octave
def test_live_parallel_equals_serial(tmp_path):
    """``--jobs 4`` and ``--jobs 1`` write the same fixtures, equal to the committed ones."""
    out = {}
    for jobs in (1, 4):
        d = tmp_path / f"j{jobs}"
        rc = gf.main([*QUICK, "--jobs", str(jobs), "--outdir", str(d),
                      "--logdir", str(tmp_path / f"logs{jobs}"),
                      "--compare", str(FIXTURES_DIR)])
        assert rc == 0
        out[jobs] = d
        assert sorted(p.stem for p in d.glob("*.mat")) == sorted(QUICK)
        assert sorted(p.stem for p in (tmp_path / f"logs{jobs}").glob("*.log")) == sorted(QUICK)
    diffs = gf.compare_outputs(QUICK, out[1], out[4])
    assert diffs == {n: [] for n in QUICK}
