"""Command line interface: ``formdiscovery run`` (``masterrun.m``, item 29),
``formdiscovery draw`` (``draw_dot.m``, item 32) and ``formdiscovery gui [FILE]`` (the
PySide6 desktop app, :mod:`formdiscovery.gui`, loop0003; extra ``gui``).

Usage::

    formdiscovery run --structures chain,ring,tree --datasets 1,2,3 --seed 1 --out results/
    formdiscovery draw results/resultsdemo.npz --out fig.png
    formdiscovery gui data/demo_chain_feat.mat
    python -m formdiscovery run ...

``--structures`` and ``--datasets`` take names or MATLAB's 1-based indices into
``ps.structures``/``ps.data`` (``setps.m``), as masterrun's ``thisstruct``/``thisdata``.
The defaults are masterrun's. Output in ``--out``: ``resultsdemo.npz`` and
``resultsdemo.json`` (:func:`formdiscovery.run.save_results`) and runmodel's growth
histories under ``results/<struct>out/<data><rind>/``. ``run --figures DIR`` sets
``ps.showpostclean`` and ``ps.showinferredgraph`` (what masterrun.m:17-21 does when
``which neato`` succeeds) and saves the figures there
(:class:`formdiscovery.viz.draw.ProgressFigures`). ``run --blas-threads N`` sets
:data:`formdiscovery.threads.BLAS_THREADS` (default 1, item 35; 0 = no limit).

``draw`` reads a ``run`` results file and draws the final graphs
(:func:`formdiscovery.viz.draw.draw_results`: neato layout, matplotlib), all runs in one
figure or the ``--runs`` chosen (0-based, in the file's order). ``--graphviz`` renders
one run with Graphviz itself (:func:`formdiscovery.viz.pygraphviz_backend.render`).
``--backend networkx`` (item 33) lays out and draws with networkx
(:mod:`formdiscovery.viz.networkx_backend`); ``--layout kamada_kawai`` needs no Graphviz.
``--backend plotly`` (item 34, extra ``interactive``) writes an interactive HTML page with
all the runs (hover: object → cluster, cluster → members); ``--backend pyvis`` writes one
run (``--runs``) as a vis-network page. Both use the networkx backend's layout.
"""

import argparse
import sys

from .run import MASTERRUN_DATA, MASTERRUN_STRUCT, load_results, masterrun, masterrun_ps

__all__ = ["main", "parse_list"]


def parse_list(text, names, what):
    """Comma-separated names or 1-based indices into ``names`` -> 0-based indices."""
    out = []
    for item in (x.strip() for x in text.split(",")):
        if not item:
            continue
        if item.isdigit():
            i = int(item) - 1
            if not 0 <= i < len(names):
                raise ValueError(f"{what} index {item} out of range 1..{len(names)}")
        elif item in names:
            i = names.index(item)
        else:
            raise ValueError(f"unknown {what} {item!r}")
        out.append(i)
    if not out:
        raise ValueError(f"no {what} given")
    return out


def _cmd_run(args, ps):
    from . import threads
    threads.BLAS_THREADS = args.blas_threads or None
    thisstruct = parse_list(args.structures, ps.structures, "structure")
    thisdata = parse_list(args.datasets, ps.data, "data set")
    if args.speed is not None:
        ps.speed = args.speed
    log = None if args.quiet else (lambda s: print(s, flush=True))
    show = None
    if args.figures:
        from .viz.draw import ProgressFigures
        show = ProgressFigures(outdir=args.figures)
        # masterrun.m:17-21 turns these two on when neato is available
        ps = show.enable(ps, ("postclean", "inferredgraph"))
    res = masterrun(ps, thisstruct, thisdata, repeats=args.repeats, outdir=args.out,
                    masterfile=args.masterfile, seed=args.seed, log=log, show=show)
    if not args.quiet:
        print(f"{'structure':<18s} {'data':<24s} {'rind':>4s} {'ll':>16s} {'clusters':>8s}")
        for r in res.runs:
            print(f"{r['structure']:<18s} {r['data']:<24s} {r['rind']:>4d} "
                  f"{r['ll']:>16.6f} {r['nclusters']:>8d}")
        print(f"saved {args.out}/{args.masterfile}.npz and .json")
    return 0


def _cmd_draw(args):
    from .viz.draw import draw_results, pad_names

    res = load_results(args.results)
    runs = None if args.runs is None else \
        [int(x) for x in args.runs.split(",") if x.strip()]
    for k in runs or []:
        if not 0 <= k < len(res.runs):
            raise ValueError(f"run {k} out of range 0..{len(res.runs) - 1}")
    if args.graphviz:
        from .viz.pygraphviz_backend import render

        sel = runs if runs is not None else list(range(len(res.runs)))
        if len(sel) != 1:
            raise ValueError("--graphviz draws one run: choose it with --runs")
        r = res.runs[sel[0]]
        g = res.structure[int(r["sind"]), int(r["dind"]), int(r["rind"]) - 1]
        render(g["adj"], pad_names(res.names[0, int(r["dind"])], len(g["adj"])), args.out)
    elif args.backend == "pyvis":
        from .viz.draw import draw_graph

        sel = runs if runs is not None else list(range(len(res.runs)))
        if len(sel) != 1:
            raise ValueError("--backend pyvis draws one run: choose it with --runs")
        r = res.runs[sel[0]]
        g = res.structure[int(r["sind"]), int(r["dind"]), int(r["rind"]) - 1]
        net = draw_graph(g, res.names[0, int(r["dind"])], "pyvis", layout=args.layout,
                         flags=args.flags, undirected=args.undirected,
                         title=f"{r['data']}: {g['type']}")
        net.write_html(args.out, notebook=False)
    else:
        kw = {"layout": args.layout} if args.backend != "pygraphviz" else {}
        draw_results(res, runs, args.out, flags=args.flags, undirected=args.undirected,
                     backend=args.backend, **kw)
    if not args.quiet:
        print(f"saved {args.out}")
    return 0


def main(argv=None):
    ps = masterrun_ps()
    ap = argparse.ArgumentParser(prog="formdiscovery",
                                 description="formdiscovery1.0 (Kemp & Tenenbaum 2008)")
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="fit structures to data sets (masterrun.m)")
    r.add_argument("--structures", default=",".join(ps.structures[i] for i in MASTERRUN_STRUCT),
                   help="names or 1-based indices (default: %(default)s)")
    r.add_argument("--datasets", default=",".join(str(i + 1) for i in MASTERRUN_DATA),
                   help="names or 1-based indices (default: %(default)s)")
    r.add_argument("--seed", type=int, default=1,
                   help="seed of repeat 1; repeat k uses seed + k - 1 (default: 1)")
    r.add_argument("--repeats", type=int, default=1, help="default: 1")
    r.add_argument("--speed", type=int, default=None,
                   help="override ps.speed (default: defaultps's 54)")
    r.add_argument("--out", default="results", help="output directory (default: results)")
    r.add_argument("--masterfile", default="resultsdemo",
                   help="results file name without extension (default: resultsdemo)")
    r.add_argument("--figures", default=None, metavar="DIR",
                   help="save the post-clean and final graph figures in DIR "
                        "(masterrun.m's display)")
    r.add_argument("--blas-threads", type=int, default=1, metavar="N",
                   help="BLAS threads inside the model (default 1, much faster on its "
                        "small matrices; 0 = the library's setting)")
    r.add_argument("-q", "--quiet", action="store_true")
    d = sub.add_parser("draw", help="draw the final graphs of a results file (draw_dot.m)")
    d.add_argument("results", help="results file from 'run' (.npz or .json)")
    d.add_argument("--out", required=True,
                   help="image file (format from the suffix); .html for plotly/pyvis")
    d.add_argument("--runs", default=None,
                   help="comma-separated 0-based run numbers (default: all)")
    d.add_argument("--flags", choices=("matlab", "intended"), default="matlab",
                   help="neato flags: draw_dot's (default) or the intended ones")
    d.add_argument("--undirected", choices=("arrows", "lines"), default="arrows",
                   help="symmetric edges as two arrows (original) or one line")
    d.add_argument("--backend", choices=("pygraphviz", "networkx", "plotly", "pyvis"),
                   default="pygraphviz",
                   help="layout and drawing backend (default: %(default)s); plotly and "
                        "pyvis write HTML")
    d.add_argument("--layout", choices=("auto", "neato", "kamada_kawai"), default="auto",
                   help="networkx/plotly/pyvis layout: neato (needs pygraphviz) or "
                        "kamada_kawai; auto picks neato when available")
    d.add_argument("--graphviz", action="store_true",
                   help="render one run with Graphviz instead of matplotlib")
    d.add_argument("-q", "--quiet", action="store_true")
    from .gui.app import build_parser as gui_parser
    gui_parser(sub.add_parser("gui", help="desktop GUI: pick a data file, watch the "
                                          "search, see the statistics (needs PySide6)"))
    args = ap.parse_args(argv)
    if args.command == "gui":
        from .gui.app import main as gui_main
        return gui_main(args=args)
    try:
        if args.command == "draw":
            return _cmd_draw(args)
        return _cmd_run(args, ps)
    except ValueError as e:
        ap.error(str(e))


if __name__ == "__main__":
    sys.exit(main())
