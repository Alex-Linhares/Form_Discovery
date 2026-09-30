#!/usr/bin/env python
"""Compare two directories of ``.mat`` files by content (loop0002 item 02).

Every ``*.mat`` under each directory is loaded with ``scipy.io.loadmat`` and compared
recursively: same file set, same variable names, same struct field names, same shapes and
dtypes, and numbers equal to all digits (``NaN`` equal to ``NaN``, ``-0.0`` equal to
``0.0``, as ``numpy.array_equal(equal_nan=True)``). The MAT header, which carries a
timestamp, is not compared. Fields named in ``ignore`` (default: ``seconds``, the
wall-clock time per run in ``run_baseline``'s ``timings.mat``) are skipped at any depth.

Usage::

    python tools/mat_compare.py DIR_A DIR_B [--ignore seconds,...]

Prints each difference and exits 1 if there is any.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import scipy.io

DEFAULT_IGNORE = ("seconds",)


def _norm_str(x, normalize):
    """``x`` with ``normalize`` applied to each string element (string arrays only)."""
    if (normalize is None or not isinstance(x, np.ndarray) or x.dtype.kind != "U"
            or x.size == 0):
        return x
    return np.array([normalize(str(v)) for v in x.ravel()]).reshape(x.shape)


def _diff(a, b, path, ignore, out, normalize=None):
    if isinstance(a, np.ndarray) and a.dtype.names is not None:
        if not isinstance(b, np.ndarray) or a.dtype.names != b.dtype.names:
            out.append(f"{path}: struct fields {a.dtype.names} vs "
                       f"{getattr(getattr(b, 'dtype', None), 'names', None)}")
            return
        if a.shape != b.shape:
            out.append(f"{path}: shape {a.shape} vs {b.shape}")
            return
        for idx in np.ndindex(a.shape):
            for f in a.dtype.names:
                if f not in ignore:
                    _diff(a[idx][f], b[idx][f], f"{path}{list(idx)}.{f}", ignore, out,
                          normalize)
        return
    if isinstance(a, np.ndarray) and a.dtype == object:
        if not isinstance(b, np.ndarray) or b.dtype != object or a.shape != b.shape:
            out.append(f"{path}: cell {a.shape} vs {getattr(b, 'shape', type(b))}")
            return
        for idx in np.ndindex(a.shape):
            _diff(a[idx], b[idx], f"{path}{{{list(idx)}}}", ignore, out, normalize)
        return
    a, b = _norm_str(np.asarray(a), normalize), _norm_str(np.asarray(b), normalize)
    if a.dtype != b.dtype or a.shape != b.shape:
        out.append(f"{path}: {a.dtype}{a.shape} vs {b.dtype}{b.shape}")
        return
    numeric = a.dtype.kind in "biufc"
    if not (np.array_equal(a, b, equal_nan=True) if numeric else np.array_equal(a, b)):
        out.append(f"{path}: values differ")


def compare_mat(fa, fb, ignore=DEFAULT_IGNORE, normalize=None):
    """List of differences between two ``.mat`` files (empty: identical content).
    ``normalize`` (optional) maps each string before comparison, e.g. to mask temporary
    directory names."""
    ma = {k: v for k, v in scipy.io.loadmat(fa).items() if not k.startswith("__")}
    mb = {k: v for k, v in scipy.io.loadmat(fb).items() if not k.startswith("__")}
    out = []
    if set(ma) != set(mb):
        out.append(f"variables {sorted(ma)} vs {sorted(mb)}")
    for k in sorted(set(ma) & set(mb)):
        if k not in ignore:
            _diff(ma[k], mb[k], k, set(ignore), out, normalize)
    return out


def compare_dirs(da, db, ignore=DEFAULT_IGNORE):
    """List of differences between the ``.mat`` files under two directories."""
    da, db = Path(da), Path(db)
    fa = {p.relative_to(da) for p in da.rglob("*.mat")}
    fb = {p.relative_to(db) for p in db.rglob("*.mat")}
    out = [f"only in {da}: {p}" for p in sorted(fa - fb)]
    out += [f"only in {db}: {p}" for p in sorted(fb - fa)]
    for p in sorted(fa & fb):
        out += [f"{p}: {d}" for d in compare_mat(da / p, db / p, ignore)]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--ignore", default=",".join(DEFAULT_IGNORE),
                    help="comma-separated field/variable names to skip")
    args = ap.parse_args(argv)
    ignore = tuple(s for s in args.ignore.split(",") if s)
    n = len(list(args.a.rglob("*.mat")))
    diffs = compare_dirs(args.a, args.b, ignore)
    for d in diffs:
        print(d)
    print(f"{n} .mat files compared, {len(diffs)} differences")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
