"""Injectable permutation providers (PLAN.md §4.2, item 22).

formdiscovery1.0 draws all of its randomness from ``randperm(n)``, at five call sites:
``choose_seedpairs.m:24``, ``best_split.m:35``, ``swapobjclust.m:33``, ``spr.m:57/59``
and ``collapsedims.m:35``. MATLAB, Octave and numpy streams all differ, so the Python
search code takes a :class:`PermutationProvider` and calls ``provider.randperm(n)``
where the MATLAB code calls ``randperm(n)``. Permutations are 0-based
(``CONVENTIONS.md``).

For parity tests, ``legacy/matlab/octave_shims/randperm.m`` shadows Octave's ``randperm``:

- It replays a queue file (``FD_RANDPERM=<file>``), and :class:`ReplayPermutations`
  replays the same queue in Python.
- It returns the identity (``FD_RANDPERM=identity``), matching
  :class:`IdentityPermutations`.
- It passes through to the built-in and logs every draw (``FD_RANDPERM_LOG=<file>``).
  The log can then be replayed in Python.

Queue and log files share one text format. Each line holds ``n p1 ... pn``, where the
``p`` are 1-based as in MATLAB. A line with just ``0`` is the empty permutation. Use
:func:`write_queue` and :func:`read_queue` to write and read it; they convert to and from
0-based.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from . import FormDiscoveryError

__all__ = [
    "PermutationProvider", "NumpyPermutations", "IdentityPermutations",
    "ReplayPermutations", "RecordingPermutations", "ReplayError",
    "as_provider", "check_perm", "write_queue", "read_queue", "parse_queue",
]


class ReplayError(FormDiscoveryError):
    """A replayed permutation queue ran out or did not match the requested size.
    The messages follow the Octave shim's."""


@runtime_checkable
class PermutationProvider(Protocol):
    """Source of random permutations. ``randperm(n)`` returns a 0-based permutation of
    ``range(n)`` as a 1-D int64 array. It stands in for MATLAB ``randperm(n)``, which
    returns a 1-based row."""

    def randperm(self, n: int) -> np.ndarray: ...


def _size(n):
    """Check ``n`` the way ``randperm`` does and return it as an int. It must be a
    non-negative integer."""
    k = int(n)
    if k != n or k < 0:
        raise ValueError(f"randperm: n must be a non-negative integer, got {n!r}")
    return k


def check_perm(p, n=None):
    """Return ``p`` as a 1-D int64 array. Raise ``ValueError`` if it is not a 0-based
    permutation (of ``range(n)``, when ``n`` is given)."""
    a = np.asarray(p)
    if a.ndim != 1:
        raise ValueError(f"permutation must be 1-D, got shape {a.shape}")
    out = a.astype(np.int64)
    if not np.array_equal(out, a):
        raise ValueError("permutation entries must be integers")
    if n is not None and out.size != n:
        raise ValueError(f"permutation has length {out.size}, expected {n}")
    if not np.array_equal(np.sort(out), np.arange(out.size)):
        raise ValueError(f"not a permutation of range({out.size}): {out.tolist()}")
    return out


class NumpyPermutations:
    """Default provider: ``numpy.random.Generator.permutation``. ``seed`` is anything
    ``numpy.random.default_rng`` accepts (``None``, an int, a ``Generator``). Its stream
    is not MATLAB's or Octave's; replay is needed for parity."""

    def __init__(self, seed=None):
        self.generator = np.random.default_rng(seed)

    def randperm(self, n):
        return self.generator.permutation(_size(n)).astype(np.int64)


class IdentityPermutations:
    """``randperm(n) = range(n)``. The shim returns the same with ``FD_RANDPERM=identity``."""

    def randperm(self, n):
        return np.arange(_size(n), dtype=np.int64)


class ReplayPermutations:
    """Replay a fixed queue of 0-based permutations, one per call.

    Each call takes the next entry. It raises :class:`ReplayError` if the queue is
    exhausted or the entry's length is not ``n``, as the Octave shim does. ``consumed``
    counts the entries used so far. ``remaining()`` returns the unused ones.
    ``assert_exhausted()`` checks that the whole queue was used, i.e. that Python made
    the same number of draws as Octave.
    """

    def __init__(self, perms):
        self.queue = [check_perm(p) for p in perms]
        self.consumed = 0

    @classmethod
    def from_file(cls, path):
        """Replay a queue or log file written by :func:`write_queue` or by the shim."""
        return cls(read_queue(path))

    def randperm(self, n):
        n = _size(n)
        call = self.consumed + 1
        if self.consumed >= len(self.queue):
            raise ReplayError(
                f"randperm replay: queue exhausted at call {call} (randperm({n}); "
                f"{len(self.queue)} entries)")
        p = self.queue[self.consumed]
        if p.size != n:
            raise ReplayError(
                f"randperm replay: call {call} asked for randperm({n}) but queue entry "
                f"{call} has length {p.size}")
        self.consumed += 1
        return p.copy()

    def remaining(self):
        return [p.copy() for p in self.queue[self.consumed:]]

    def assert_exhausted(self):
        if self.consumed != len(self.queue):
            raise ReplayError(
                f"randperm replay: {len(self.queue) - self.consumed} of {len(self.queue)} "
                f"queue entries unused")


class RecordingPermutations:
    """Wrap a provider and keep every permutation it returns in ``log``.
    ``write_queue(path, rec.log)`` saves the log in the shim's format."""

    def __init__(self, inner=None):
        self.inner = as_provider(inner)
        self.log = []

    def randperm(self, n):
        p = self.inner.randperm(n)
        self.log.append(p.copy())
        return p


def as_provider(rng=None):
    """Normalise an ``rng`` argument. ``None`` gives a fresh :class:`NumpyPermutations`,
    and so does an int or a ``numpy.random.Generator`` (used as the seed). Anything with
    a ``randperm`` method is returned unchanged."""
    if rng is None or isinstance(rng, (int, np.integer, np.random.Generator)):
        return NumpyPermutations(rng)
    if isinstance(rng, PermutationProvider):
        return rng
    raise TypeError(f"not a permutation provider: {rng!r}")


def write_queue(path, perms):
    """Write 0-based permutations to ``path`` as a queue file: one 1-based
    ``n p1 ... pn`` line each. The shim and :meth:`ReplayPermutations.from_file` read
    this format."""
    lines = []
    for p in perms:
        p = check_perm(p)
        lines.append(" ".join(str(v) for v in [p.size, *(p + 1).tolist()]))
    Path(path).write_text("".join(line + "\n" for line in lines))


def read_queue(path):
    """Read a queue or log file (1-based ``n p1 ... pn`` lines, blank lines ignored)
    and return a list of 0-based int64 arrays."""
    return parse_queue(Path(path).read_text(), source=str(path))


def parse_queue(text, source="<text>"):
    """Parse the text of a queue or log file. See :func:`read_queue`."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        v = [int(t) for t in line.split()]
        if not v:
            continue
        if len(v) != v[0] + 1:
            raise ValueError(
                f"{source} line {lineno}: header says {v[0]} entries, found {len(v) - 1}")
        out.append(check_perm(np.array(v[1:], dtype=np.int64) - 1))
    return out
