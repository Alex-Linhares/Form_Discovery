"""The neato layout of ``draw_dot.m`` through pygraphviz (item 32, PLAN.md §6 phase A).

``draw_dot.m:37-50`` writes the graph with ``graph_to_dot`` and runs::

    neato -Tdot  -Gmaxiter=25000 -Gregular-Gminlen=5 -Goverlap=false -o_LAYout.dot _GtDout.dot

The command is built with ``strcat``, which drops the trailing blank of each piece. So
``-Gregular`` and ``-Gminlen=5`` are glued into one attribute ``"regular-Gminlen"=5``
(KI-32), and for ``n > 100`` the ``-x`` meant to follow ``-Goverlap=false `` is glued to
it: ``-Goverlap=false-x``, which neato reads as an unknown overlap value (it warns and uses
``false``); ``-x`` is never applied (KI-35).

``flags='matlab'`` (default) passes exactly these attributes, so the layout text is
Octave's byte for byte (same Graphviz). ``flags='intended'`` passes what the comments
describe: ``maxiter=25000``, ``regular``, ``minlen=5``, ``overlap=false`` and, for
``n > 100``, ``-x`` (neato's reduce flag, command line only). Neither ``regular`` nor
``minlen`` is a neato layout attribute, so the intended flags give the same positions for
``n <= 100`` (``tests/test_viz_draw.py``).

Layout engines: ``'pygraphviz'`` (libgvc through ``AGraph.draw(format='dot',
prog='neato')``), ``'cli'`` (the ``neato`` executable, as draw_dot does) and ``'auto'``
(pygraphviz when importable, else a working ``neato``, see :func:`find_neato`).

:func:`render` draws with Graphviz itself (PNG, SVG, PDF, ...) without matplotlib.
"""

import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .dot import adj_is_directed, graph_to_dot

__all__ = ["NEATO_MAXITER", "neato_attrs", "neato_args", "find_neato", "have_pygraphviz",
           "neato_layout", "layout_text", "render"]

NEATO_MAXITER = 25000
FLAGS = ("matlab", "intended")
ENGINES = ("auto", "pygraphviz", "cli")


def neato_attrs(n, flags="matlab"):
    """The graph attributes of draw_dot's neato call for an ``n``-node graph, as a list of
    ``(name, value)``, and whether ``-x`` is passed. See the module docstring."""
    if flags == "matlab":
        return [("maxiter", str(NEATO_MAXITER)), ("regular-Gminlen", "5"),
                ("overlap", "false-x" if n > 100 else "false")], False
    if flags == "intended":
        return [("maxiter", str(NEATO_MAXITER)), ("regular", "true"), ("minlen", "5"),
                ("overlap", "false")], n > 100
    raise ValueError(f"flags must be one of {FLAGS}, not {flags!r}")


def neato_args(n, flags="matlab"):
    """The command line arguments after ``neato`` (``-Tdot`` first). ``'matlab'`` is
    draw_dot's command (l.46-50) without the file names."""
    attrs, reduce = neato_attrs(n, flags)
    args = ["-Tdot"]
    for k, v in attrs:
        args.append(f"-G{k}" if (flags == "intended" and k == "regular") else f"-G{k}={v}")
    if reduce:
        args.append("-x")
    return args


def have_pygraphviz():
    try:
        import pygraphviz  # noqa: F401
    except ImportError:
        return False
    return True


def _probe(exe):
    try:
        r = subprocess.run([exe, "-Tdot"], input="graph { 1 -- 2; }", capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and "pos=" in r.stdout


@functools.lru_cache(maxsize=None)
def _find_neato(env, path):
    cands = []
    if env:
        cands.append(env)
    w = shutil.which("neato", path=path)
    if w:
        cands.append(w)
    cands.append(str(Path(sys.prefix) / "bin" / "neato"))
    for c in cands:
        if Path(c).is_file() and _probe(c):
            return c
    return None


def find_neato():
    """A ``neato`` executable that can lay out a graph: ``$FORMDISCOVERY_NEATO``, then
    ``neato`` on ``PATH``, then next to the running Python. Each candidate is probed with
    a two-node layout (a Graphviz without the neato plugin fails). ``None`` if none
    works."""
    return _find_neato(os.environ.get("FORMDISCOVERY_NEATO"), os.environ.get("PATH"))


def _engine(engine):
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {ENGINES}, not {engine!r}")
    if engine == "auto":
        if have_pygraphviz():
            return "pygraphviz"
        if find_neato():
            return "cli"
        raise RuntimeError("no Graphviz layout available: install pygraphviz or put a "
                           "working neato on PATH (or set FORMDISCOVERY_NEATO)")
    return engine


def neato_layout(dot_text, n, flags="matlab", engine="auto"):
    """Run neato on ``dot_text`` (an ``n``-node graph) with draw_dot's attributes and
    return the layout as DOT text (``_LAYout.dot``). ``engine='pygraphviz'`` cannot pass
    ``-x`` (``flags='intended'`` with ``n > 100``) and raises; use ``'cli'``."""
    engine = _engine(engine)
    if engine == "pygraphviz":
        import pygraphviz

        attrs, reduce = neato_attrs(n, flags)
        if reduce:
            raise ValueError("neato's -x (flags='intended', n > 100) needs engine='cli'")
        g = pygraphviz.AGraph(string=dot_text)
        for k, v in attrs:
            g.graph_attr[k] = v
        return g.draw(format="dot", prog="neato").decode()
    exe = find_neato()
    if exe is None:
        raise RuntimeError("no working neato executable found (set FORMDISCOVERY_NEATO)")
    args = neato_args(n, flags)
    r = subprocess.run([exe, *args], input=dot_text, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"neato failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def layout_text(adj, flags="matlab", engine="auto"):
    """``draw_dot.m:33-50``: ``(gt, lay, directed)``, the ``graph_to_dot`` text of
    ``adj > 0`` (``directed`` from the unbinarised ``adj``, l.35) and neato's layout."""
    adj = np.asarray(adj, dtype=float)
    directed = int(adj_is_directed(adj))
    b = (adj > 0).astype(float)
    gt = graph_to_dot(b, directed=directed)
    return gt, neato_layout(gt, b.shape[0], flags, engine), directed


def render(adj, labels=None, path=None, format=None, flags="matlab"):
    """Draw with Graphviz only (pygraphviz ``AGraph.draw``): neato with draw_dot's
    attributes, node ``i`` labelled ``labels[i]`` (default ``'1'..'n'``), grey fill for
    self-loop nodes, arrows when the graph is directed (``adj`` not symmetric, as in
    draw_dot). ``path=None`` returns the bytes; ``format`` defaults from the suffix."""
    import pygraphviz

    adj = np.asarray(adj, dtype=float)
    n = adj.shape[0]
    b = (adj > 0).astype(float)
    g = pygraphviz.AGraph(string=graph_to_dot(b, directed=int(adj_is_directed(adj))))
    attrs, reduce = neato_attrs(n, flags)
    if reduce:
        raise ValueError("neato's -x (flags='intended', n > 100) is not available here")
    for k, v in attrs:
        g.graph_attr[k] = v
    g.node_attr["fontsize"] = "10"
    for i in range(n):
        node = g.get_node(str(i + 1)) if g.has_node(str(i + 1)) else None
        if node is None:
            g.add_node(str(i + 1))
            node = g.get_node(str(i + 1))
        node.attr["label"] = str(i + 1) if labels is None else str(labels[i] or "")
        if b[i, i]:
            node.attr["style"] = "filled"
            node.attr["fillcolor"] = "grey80"
    if path is not None and format is None:
        format = Path(path).suffix.lstrip(".") or "png"
    return g.draw(path=None if path is None else str(path), format=format or "png",
                  prog="neato")
