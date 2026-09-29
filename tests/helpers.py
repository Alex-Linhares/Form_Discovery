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
