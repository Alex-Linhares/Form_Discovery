"""legacy/tools/mat_compare.py (loop0002 item 02): content comparison of .mat output directories."""

import numpy as np
import scipy.io

from legacy.tools.mat_compare import compare_dirs, main


def _write(d, name, **vars):
    (d / name).parent.mkdir(parents=True, exist_ok=True)
    scipy.io.savemat(d / name, vars)


def _pair(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        t = np.array([(1.0, np.nan, "chain")], dtype=[("ll", "O"), ("seconds", "O"),
                                                    ("structure", "O")])
        _write(d, "timings.mat", timings=t)
        _write(d, "results/x/g.mat", bestgraph=np.eye(3), names=np.array(["a", "b"], dtype=object))
    return a, b


def test_identical(tmp_path):
    a, b = _pair(tmp_path)
    assert compare_dirs(a, b) == []
    assert main([str(a), str(b)]) == 0


def test_value_file_and_variable_differences(tmp_path):
    a, b = _pair(tmp_path)
    m = np.eye(3)
    m[0, 1] = 1e-300
    _write(b, "results/x/g.mat", bestgraph=m, names=np.array(["a", "b"], dtype=object))
    _write(b, "extra.mat", z=1)
    diffs = compare_dirs(a, b)
    assert any("only in" in d and "extra.mat" in d for d in diffs)
    assert any("bestgraph: values differ" in d for d in diffs)
    assert main([str(a), str(b)]) == 1


def test_ignored_field(tmp_path):
    a, b = _pair(tmp_path)
    t = np.array([(1.0, 99.0, "chain")], dtype=[("ll", "O"), ("seconds", "O"),
                                               ("structure", "O")])
    _write(b, "timings.mat", timings=t)
    assert compare_dirs(a, b) == []
    assert any(".seconds" in d for d in compare_dirs(a, b, ignore=()))
