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
"""

import contextlib
import functools
import warnings

__all__ = ["BLAS_THREADS", "blas_threads", "limit_blas_threads", "have_threadpoolctl"]

# threads per BLAS inside the model drivers; None = leave the library's setting
BLAS_THREADS = 1

_warned = False


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
