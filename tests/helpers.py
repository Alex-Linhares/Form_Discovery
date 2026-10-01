"""Parity helpers shared by the tests.

``graph_diff`` / ``graph_equal`` / ``assert_graph_equal`` compare two graph structs field by
field (PLAN.md §2) and report the first field that differs. Either side may be a
:class:`formdiscovery.graph.Graph` or a MATLAB struct as loaded from a fixture (a dict,
converted with :func:`formdiscovery.io.graph_from_mat`, i.e. shifted to 0-based).
Structure (adjacency, ``z``, maps, indices, counts, names) must match exactly; the weight
fields and ``sigma`` to ``rtol``/``atol``. Arrays are compared by value, so a MATLAB
logical and a bool array, or a double and an int array, are equal when their entries are.
"""

import numpy as np

from formdiscovery.graph import COMPONENT_FIELDS, GRAPH_FIELDS, Graph
from formdiscovery.io import graph_from_mat

FLOAT_FIELDS = {"sigma", "Wcluster", "W", "leaflengths", "extlen", "intlen", "Wclustersym",
                "Wsym"}
COMPONENT_FLOAT_FIELDS = {"W", "Wsym"}


def _as_graph(g):
    return g if isinstance(g, Graph) else graph_from_mat(g)


def _value_diff(name, a, b, is_float, rtol, atol):
    if a is None or b is None:
        return None if a is None and b is None else f"{name}: {a!r} vs {b!r}"
    if isinstance(a, str) or isinstance(b, str):
        return None if a == b else f"{name}: {a!r} vs {b!r}"
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return f"{name}: shape {a.shape} vs {b.shape}"
    a = a.astype(float)
    b = b.astype(float)
    if is_float:
        ok = np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=True)
    else:
        ok = (a == b) | (np.isnan(a) & np.isnan(b))
    if ok.all():
        return None
    k = np.flatnonzero(~ok.ravel(order="F"))[0]
    where = np.unravel_index(k, a.shape, order="F") if a.ndim else ()
    return (f"{name}: {np.count_nonzero(~ok)} entries differ, first at {tuple(map(int, where))}:"
            f" {a.ravel(order='F')[k]!r} vs {b.ravel(order='F')[k]!r}")


def graph_diff(a, b, rtol=1e-10, atol=1e-12, fields=None):
    """Description of the first differing field of graphs ``a`` and ``b`` (``None`` if they
    are equal). ``fields`` restricts the top-level fields compared (default: all)."""
    a, b = _as_graph(a), _as_graph(b)
    for f in fields or GRAPH_FIELDS:
        va, vb = getattr(a, f), getattr(b, f)
        if f == "components":
            if len(va) != len(vb):
                return f"components: {len(va)} vs {len(vb)} entries"
            for i, (ca, cb) in enumerate(zip(va, vb)):
                for cf in COMPONENT_FIELDS:
                    d = _value_diff(f"components[{i}].{cf}", getattr(ca, cf), getattr(cb, cf),
                                    cf in COMPONENT_FLOAT_FIELDS, rtol, atol)
                    if d:
                        return d
            continue
        d = _value_diff(f, va, vb, f in FLOAT_FIELDS, rtol, atol)
        if d:
            return d
    return None


def graph_equal(a, b, **kw):
    """True when :func:`graph_diff` finds no difference."""
    return graph_diff(a, b, **kw) is None


def assert_graph_equal(a, b, msg="", **kw):
    """Raise ``AssertionError`` naming the first differing field."""
    d = graph_diff(a, b, **kw)
    if d:
        raise AssertionError(f"{msg}: {d}" if msg else d)


def checkgrad(f, X, e, *args):
    """``checkgrad.m:18-42`` (Carl Edward Rasmussen): compare the analytic gradient of
    ``f`` with central finite differences.

    ``f(X, *args)`` returns ``(value, gradient)``; only its value is used at the perturbed
    points (MATLAB's ``y2 = eval(argstrd)`` takes the first output). Returns
    ``(d, dy, dh)``: ``d = norm(dh - dy) / norm(dh + dy)``, the analytic gradient ``dy``
    and the finite-difference one ``dh``, both 1-D. MATLAB prints ``[dy dh]``; here the
    caller can.
    """
    X = np.asarray(X, dtype=float).ravel()
    y, dy = f(X, *args)  # get the partial derivatives dy
    dy = np.asarray(dy, dtype=float).ravel()
    dh = np.zeros(len(X))
    for j in range(len(X)):
        dx = np.zeros(len(X))
        dx[j] = dx[j] + e  # perturb a single dimension
        y2 = f(X + dx, *args)[0]
        dx = -dx
        y1 = f(X + dx, *args)[0]
        dh[j] = (y2 - y1) / (2 * e)
    d = np.linalg.norm(dh - dy) / np.linalg.norm(dh + dy)  # norm of diff over norm of sum
    return float(d), dy, dh


def adjusted_rand_index(a, b):
    """Adjusted Rand index (Hubert & Arabie 1985) of two labellings of the same objects,
    used for the end-to-end partition comparison (PLAN.md §7.1). 1 when the partitions
    are equal up to relabelling."""
    from math import comb
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    if a.shape != b.shape:
        raise ValueError("labellings differ in length")
    _, ia = np.unique(a, return_inverse=True)
    _, ib = np.unique(b, return_inverse=True)
    table = np.zeros((ia.max() + 1, ib.max() + 1), dtype=np.int64)
    np.add.at(table, (ia, ib), 1)
    sum_ij = sum(comb(int(x), 2) for x in table.ravel())
    sum_a = sum(comb(int(x), 2) for x in table.sum(axis=1))
    sum_b = sum(comb(int(x), 2) for x in table.sum(axis=0))
    expected = sum_a * sum_b / comb(a.size, 2)
    top = (sum_a + sum_b) / 2
    if top == expected:  # both trivial (one cluster each, or all singletons)
        return 1.0
    return (sum_ij - expected) / (top - expected)


def xdist_shared(name, tmp_path_factory, compute):
    """``compute()`` once per test run, also under pytest-xdist (loop0002 item 07).

    Serially this is just ``compute()``. Under xdist every worker that runs a test using a
    module fixture would run the fixture again; here the first worker computes it under a
    lock and writes it as JSON to the run's shared temp directory, and the others read that
    file. ``compute`` must return a list of JSON values (floats round-trip exactly).
    """
    import fcntl
    import json
    import os

    if not os.environ.get("PYTEST_XDIST_WORKER"):
        return compute()
    shared = tmp_path_factory.getbasetemp().parent / f"{name}.json"
    with open(shared.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not shared.exists():
            shared.write_text(json.dumps(compute()))
        return json.loads(shared.read_text())
