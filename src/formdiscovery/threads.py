"""BLAS thread limit for the model drivers (item 35, PLAN.md §7.4).

The model works on small matrices (at most a few hundred nodes; 40 x 2000 data at most
in the bundled sets). A multithreaded BLAS spends far longer waking its threads than
computing on them. With OpenBLAS on 32 cores, a 40 x 40 triangular solve takes 3 ms on
32 threads and 15 µs on one, and ``chain x synthtree`` took 16 times Octave's time.
:func:`runmodel <formdiscovery.run.runmodel>` and :func:`structurefit
<formdiscovery.search.structurefit>` therefore run under :func:`blas_threads`, which
limits every loaded BLAS to :data:`BLAS_THREADS` threads (``threadpoolctl``) and restores
the previous limits on exit.

The limit does not change the results. ``tests/test_perf.py`` checks that the benchmark
graphs score bit for bit the same under 1 thread and the library default, and the
regression gate passes under both. Set ``formdiscovery.threads.BLAS_THREADS = None`` (or
``formdiscovery run --blas-threads 0``) to keep the library's own setting. Without
``threadpoolctl`` the limit is skipped with a warning.

Processes (loop0002 item 02). Parallelism comes from processes, one BLAS thread each.
:data:`PIN_ENV` holds the environment variables that pin OpenBLAS, OpenMP and MKL to one
thread. They are read when the library loads, so they must be in the environment of every
``octave-cli``/``Oct2Py`` started (:func:`pinned_env`, :func:`pin_blas_env`). Octave's
``nproc()`` honours ``OMP_NUM_THREADS``, so it returns 1 in a pinned Octave. Pinning is
not always bit-neutral in Octave: ``fx_gibbs.m``'s ``grid x synthgrid`` run scores
differently under 1 thread (ANOMALIES A19), so :func:`unpinned_env` gives the library
default back for the fixtures listed in ``tests/conftest.py`` ``BLAS_DEFAULT_FIXTURES``.
For a Python
process whose BLAS is already loaded, :func:`pin_process_blas` sets the limit with
``threadpoolctl`` until the returned controller is restored (the test suite does this at
session start).
"""

import contextlib
import functools
import os
import warnings

__all__ = ["BLAS_THREADS", "PIN_ENV", "blas_threads", "limit_blas_threads",
           "have_threadpoolctl", "pinned_env", "unpinned_env", "pin_blas_env",
           "pin_process_blas"]

# threads per BLAS inside the model drivers; None = leave the library's setting
BLAS_THREADS = 1

# environment for one BLAS/OpenMP thread per process (Octave children, pool workers)
PIN_ENV = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

_warned = False


def pinned_env(env=None):
    """Copy of ``env`` (default ``os.environ``) with :data:`PIN_ENV` applied."""
    out = dict(os.environ if env is None else env)
    out.update(PIN_ENV)
    return out


def unpinned_env(env=None):
    """Copy of ``env`` (default ``os.environ``) without the :data:`PIN_ENV` variables, so
    the libraries use their own thread count (OpenBLAS: one per core)."""
    return {k: v for k, v in (os.environ if env is None else env).items()
            if k not in PIN_ENV}


def pin_blas_env():
    """Put :data:`PIN_ENV` into ``os.environ``: every process started afterwards (and
    any BLAS this process loads afterwards) runs one thread."""
    os.environ.update(PIN_ENV)


def have_threadpoolctl():
    try:
        import threadpoolctl  # noqa: F401
    except ImportError:
        return False
    return True


@contextlib.contextmanager
def blas_threads(n="default"):
    """Limit every loaded BLAS to ``n`` threads inside the block (``'default'``:
    :data:`BLAS_THREADS`; ``None`` or ``0``: no limit). Nested blocks restore the outer
    limit on exit."""
    global _warned
    if n == "default":
        n = BLAS_THREADS
    if not n:
        yield
        return
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        if not _warned:
            warnings.warn("formdiscovery: threadpoolctl is not installed, so BLAS threads "
                          "are not limited (the model can run several times slower)")
            _warned = True
        yield
        return
    with threadpool_limits(limits=int(n), user_api="blas"):
        yield


def limit_blas_threads(fn):
    """Decorator: run ``fn`` under :func:`blas_threads` (read at call time)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with blas_threads():
            return fn(*args, **kwargs)
    return wrapper


def pin_process_blas(n=1):
    """Limit every BLAS already loaded in this process to ``n`` threads, until
    ``.restore_original_limits()`` is called on the returned controller. Returns None
    without ``threadpoolctl``."""
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        return None
    return threadpool_limits(limits=int(n), user_api="blas")
