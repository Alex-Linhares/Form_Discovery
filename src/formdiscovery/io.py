"""Loading data sets and Octave fixtures, and the 1-based ↔ 0-based index boundary.

The MATLAB code loads data with ``load(ps.dlocs{dind})`` (``runmodel.m:29``) and then
treats ``data`` as double (``setrunps.m`` decides feature / similarity / relational from
it). The ``.mat`` files store uint8/uint16, so everything here is read with
``mat_dtype=True``. Index conversion happens in this module and in the parity helpers
only (``CONVENTIONS.md``).
"""

import os
from pathlib import Path

import numpy as np
from scipy.io import loadmat

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("FORMDISCOVERY_DATA", REPO_ROOT / "data"))
FIXTURES_DIR = Path(os.environ.get("FORMDISCOVERY_FIXTURES", REPO_ROOT / "tests" / "fixtures"))


def _names(obj):
    """MATLAB cell array of strings (as read by loadmat) -> list of str."""
    if obj is None:
        return None
    out = []
    for e in np.asarray(obj, dtype=object).ravel():
        while isinstance(e, np.ndarray) and e.dtype == object and e.size == 1:
            e = e.ravel()[0]
        out.append(str(np.asarray(e).ravel()[0]) if np.size(e) else "")
    return out


def load_mat(name, data_dir=None):
    """All variables of ``data/<name>.mat`` (loadmat, ``mat_dtype=True``), MATLAB
    header entries removed. ``name`` may include ``.mat``."""
    path = Path(data_dir or DATA_DIR) / (name if name.endswith(".mat") else name + ".mat")
    d = loadmat(path, mat_dtype=True)
    return {k: v for k, v in d.items() if not k.startswith("__")}


def load_dataset(name, with_names=False, data_dir=None):
    """The ``data`` variable of ``data/<name>.mat`` as ``runmodel.m:29`` sees it.

    Feature and similarity data sets return a float ndarray (objects × features, or
    objects × objects). Relational data sets (where ``data`` is a struct, see
    ``setrunps.m:5``) return a dict ``{'R', 'type', 'nobj', 'names'}``: ``R`` float
    ndarray, ``type`` ``'relbin'``/``'relfreq'``, ``nobj`` int, ``names`` list of str or
    None. With ``with_names=True`` a feature/similarity set returns ``(data, names)``.
    """
    d = load_mat(name, data_dir)
    names = _names(d.get("names"))
    data = d["data"]
    if data.dtype.names is None:
        data = np.asarray(data, dtype=float)
        return (data, names) if with_names else data
    s = data[0, 0]
    return {
        "R": np.asarray(s["R"], dtype=float),
        "type": str(np.asarray(s["type"]).ravel()[0]),
        "nobj": int(np.asarray(s["nobj"]).ravel()[0]),
        "names": names,
    }


def load_fixture(name, fixtures_dir=None, simplify=True):
    """Variables of ``tests/fixtures/<name>.mat`` (written by ``tools/gen_fixtures.py``).

    With ``simplify=True`` (default) structs become dicts, cells become lists and
    singleton dimensions are squeezed (``loadmat(simplify_cells=True)``); use
    ``simplify=False`` where exact array shapes matter. Values keep MATLAB's 1-based
    indices; shift them with :func:`to0`.
    """
    path = Path(fixtures_dir or FIXTURES_DIR) / (name if name.endswith(".mat") else name + ".mat")
    d = loadmat(path, simplify_cells=simplify)
    return {k: v for k, v in d.items() if not k.startswith("__")}


def to0(idx):
    """MATLAB 1-based index (array, scalar, or list/tuple of them, e.g. a cell array of
    index vectors) -> 0-based int array(s)."""
    if isinstance(idx, (list, tuple)):
        return type(idx)(to0(i) for i in idx)
    a = np.asarray(idx)
    out = a.astype(np.int64) - 1
    if not np.array_equal(out + 1, a):
        raise ValueError("to0: indices must be integers")
    return out


def to1(idx):
    """0-based index (array, scalar, or list/tuple of them) -> MATLAB 1-based indices as
    float, the type MATLAB uses."""
    if isinstance(idx, (list, tuple)):
        return type(idx)(to1(i) for i in idx)
    return np.asarray(idx, dtype=float) + 1


# --- graph structs (item 11) -----------------------------------------------------------
_G_SQUARE = ("adjcluster", "adjclustersym", "adj", "Wcluster", "W", "Wclustersym",
             "adjsym", "Wsym")
_G_BOOL = ("adj", "adjsym")
_C_SQUARE = ("adj", "W", "adjsym", "Wsym", "edgemap", "edgemapsym")
_C_INT = ("prodcount", "nodecount", "edgecount", "edgecountsym")


def _struct_dict(d):
    """scipy ``mat_struct`` (left inside heterogeneous cells by ``simplify_cells``) -> dict."""
    if hasattr(d, "_fieldnames"):
        return {f: getattr(d, f) for f in d._fieldnames}
    return d


def _cell_list(v):
    if isinstance(v, (list, tuple)):
        return list(v)
    if isinstance(v, np.ndarray) and v.dtype == object:
        return list(v.ravel(order="F"))
    return [v]


def _scalar(v):
    return np.asarray(v).ravel()[0].item()


def _str(v):
    return v if isinstance(v, str) else str(np.asarray(v).ravel()[0])


def _vec(v, dtype=float):
    return np.asarray(v, dtype=dtype).ravel(order="F")


def _idx0(v):
    """1-based MATLAB index vector -> 0-based 1-D int array (0 becomes -1)."""
    return to0(_vec(v)).ravel()


def component_from_mat(d):
    """A MATLAB ``graph.components{i}`` (dict from ``loadmat(simplify_cells=True)`` or
    oct2py) -> :class:`formdiscovery.graph.Component`, indices shifted to 0-based
    (``z``, ``illegal``, ``nodemap``; edge maps keep MATLAB edge numbers)."""
    from .graph import COMPONENT_FIELDS, Component
    d = _struct_dict(d)
    unknown = set(d) - set(COMPONENT_FIELDS)
    if unknown:
        raise KeyError(f"component_from_mat: unknown fields {sorted(unknown)}")
    c = Component()
    for k, v in d.items():
        if k == "type":
            v = _str(v)
        elif k in _C_INT:
            v = int(_scalar(v))
        elif k in _C_SQUARE:
            v = np.atleast_2d(np.asarray(v, dtype=float))
        else:  # z, illegal, nodemap
            v = _idx0(v)
        setattr(c, k, v)
    return c


def graph_from_mat(d):
    """A MATLAB ``graph`` struct (dict from ``loadmat(simplify_cells=True)`` or oct2py) ->
    :class:`formdiscovery.graph.Graph` (``CONVENTIONS.md``): ``z`` 0-based with ``-1`` for
    missing objects (MATLAB ``z < 0``), ``illegal``/``compinds`` 0-based, ``globinds``
    0-based with -1 for MATLAB's unused 0 entries; ``compinds`` is ``N x ncomp`` and
    ``globinds`` gets back its ``zeros(compsizes)`` shape. ``adj``/``adjsym`` become bool.
    """
    from .graph import GRAPH_FIELDS, Graph
    d = _struct_dict(d)
    unknown = set(d) - set(GRAPH_FIELDS)
    if unknown:
        raise KeyError(f"graph_from_mat: unknown fields {sorted(unknown)}")
    g = Graph()
    ncomp = int(_scalar(d["ncomp"])) if "ncomp" in d else None
    for k, v in d.items():
        if k == "type":
            v = _str(v)
        elif k in ("objcount", "ncomp"):
            v = int(_scalar(v))
        elif k in ("sigma", "extlen", "intlen"):
            v = float(_scalar(v))
        elif k in _G_SQUARE:
            v = np.atleast_2d(np.asarray(v, dtype=float))
            if k in _G_BOOL:
                v = v != 0
        elif k == "z":
            v = _vec(v)
            v = np.where(v < 0, -1, v - 1).astype(np.int64)
        elif k == "leaflengths":
            v = _vec(v)
        elif k == "compsizes":
            v = _vec(v, np.int64)
        elif k == "illegal":
            v = _idx0(v)
        elif k == "compinds":
            v = to0(np.asarray(v, dtype=float).reshape(-1, ncomp, order="F"))
        elif k == "globinds":
            cs = _vec(d["compsizes"], np.int64)
            shape = (int(cs[0]),) * 2 if len(cs) == 1 else tuple(int(s) for s in cs)
            v = to0(np.asarray(v, dtype=float).reshape(shape, order="F"))
        elif k == "components":
            v = [component_from_mat(c) for c in _cell_list(v)]
        setattr(g, k, v)
    return g


def _to_mat_value(k, v, index_fields):
    if v is None or isinstance(v, str):
        return v
    if k in index_fields:
        return to1(v)
    if isinstance(v, np.ndarray):
        return v.astype(float)
    return float(v)


def graph_to_mat(g):
    """Inverse of :func:`graph_from_mat`: a dict of MATLAB values (1-based indices, floats,
    ``components`` a list of dicts) for ``savemat``/oct2py. Fields that are ``None`` are
    left out."""
    from .graph import COMPONENT_FIELDS, GRAPH_FIELDS
    out = {}
    for k in GRAPH_FIELDS:
        v = getattr(g, k)
        if v is None:
            continue
        if k == "components":
            out[k] = [{f: _to_mat_value(f, getattr(c, f), ("z", "illegal", "nodemap"))
                       for f in COMPONENT_FIELDS if getattr(c, f) is not None} for c in v]
        elif k == "z":
            v = np.asarray(v)
            out[k] = np.where(v < 0, -1.0, v + 1.0)
        else:
            out[k] = _to_mat_value(k, v, ("illegal", "compinds", "globinds"))
    return out
