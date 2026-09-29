"""Command line interface: ``formdiscovery run`` (``masterrun.m``, item 29).

Usage::

    formdiscovery run --structures chain,ring,tree --datasets 1,2,3 --seed 1 --out results/
    python -m formdiscovery run ...

``--structures`` and ``--datasets`` take names or MATLAB's 1-based indices into
``ps.structures``/``ps.data`` (``setps.m``), as masterrun's ``thisstruct``/``thisdata``.
The defaults are masterrun's. Output in ``--out``: ``resultsdemo.npz`` and
``resultsdemo.json`` (:func:`formdiscovery.run.save_results`) and runmodel's growth
histories under ``results/<struct>out/<data><rind>/``.
"""

import argparse
import sys

from .run import MASTERRUN_DATA, MASTERRUN_STRUCT, masterrun, masterrun_ps

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
    thisstruct = parse_list(args.structures, ps.structures, "structure")
    thisdata = parse_list(args.datasets, ps.data, "data set")
    if args.speed is not None:
        ps.speed = args.speed
    log = None if args.quiet else (lambda s: print(s, flush=True))
    res = masterrun(ps, thisstruct, thisdata, repeats=args.repeats, outdir=args.out,
                    masterfile=args.masterfile, seed=args.seed, log=log)
    if not args.quiet:
        print(f"{'structure':<18s} {'data':<24s} {'rind':>4s} {'ll':>16s} {'clusters':>8s}")
        for r in res.runs:
            print(f"{r['structure']:<18s} {r['data']:<24s} {r['rind']:>4d} "
                  f"{r['ll']:>16.6f} {r['nclusters']:>8d}")
        print(f"saved {args.out}/{args.masterfile}.npz and .json")
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
    r.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    try:
        return _cmd_run(args, ps)
    except ValueError as e:
        ap.error(str(e))


if __name__ == "__main__":
    sys.exit(main())
