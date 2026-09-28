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
DATA_DIR = Path(os.environ.get("FORMDISCOVERY_DATA", REPO_ROOT / "matlab" / "formdiscovery1.0" / "data"))
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
