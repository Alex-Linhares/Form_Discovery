#!/usr/bin/env python
"""Regenerate golden fixtures by running the Octave fixture scripts.

Every ``tests/octave/fx_<name>.m`` is a function ``fx_<name>(outfile)`` that calls the
original MATLAB code and writes ``outfile`` with ``save -v7``. This tool runs each one in a
fresh ``octave-cli`` (with ``matlab/formdiscovery1.0`` and ``tests/octave`` on the path)
and writes ``tests/fixtures/<name>.mat``. Other ``.m`` files in ``tests/octave/`` (e.g.
``smoke_patches.m``) are helpers used by live tests and are not run.

Usage::

    python tools/gen_fixtures.py               # all fixtures
    python tools/gen_fixtures.py matlab_compat # only fx_matlab_compat.m
    python tools/gen_fixtures.py --list

Octave is found as in ``tests/conftest.py`` (``$OCTAVE_EXECUTABLE``, the ``fd`` env, PATH).
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.conftest import (  # noqa: E402
    FIXTURES_DIR,
    MATLAB_DIR,
    OCTAVE_TESTS_DIR,
    _configure_octave_env,
    find_octave,
)


def fixture_scripts():
    """Map fixture name -> script path for every ``tests/octave/fx_*.m``."""
    return {p.stem[3:]: p for p in sorted(OCTAVE_TESTS_DIR.glob("fx_*.m"))}


def _octstr(path):
    return "'" + str(path).replace("'", "''") + "'"


def run_one(exe, name, script, outdir):
    outfile = Path(outdir) / f"{name}.mat"
    cmd = (
        f"addpath({_octstr(MATLAB_DIR)}); addpath({_octstr(OCTAVE_TESTS_DIR)}); "
        f"{script.stem}({_octstr(outfile)});"
    )
    t0 = time.time()
    res = subprocess.run(
        [exe, "--no-gui", "--quiet", "--no-window-system", "--eval", cmd],
        cwd=REPO_ROOT, capture_output=True, text=True, env=os.environ.copy(),
    )
    dt = time.time() - t0
    if res.returncode != 0 or not outfile.is_file():
        sys.stderr.write(f"FAILED {name} ({dt:.1f} s)\n{res.stdout}{res.stderr}\n")
        return False
    print(f"wrote {outfile.relative_to(REPO_ROOT) if outfile.is_relative_to(REPO_ROOT) else outfile}"
          f" ({dt:.1f} s)")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="fixture names (default: all)")
    ap.add_argument("--list", action="store_true", help="list fixture scripts and exit")
    ap.add_argument("--outdir", default=str(FIXTURES_DIR), help="output directory")
    args = ap.parse_args(argv)

    scripts = fixture_scripts()
    if args.list:
        for name, p in scripts.items():
            print(f"{name:24s} {p.relative_to(REPO_ROOT)}")
        return 0
    unknown = [n for n in args.names if n not in scripts]
    if unknown:
        ap.error(f"no tests/octave/fx_<name>.m for: {', '.join(unknown)}")
    exe = find_octave()
    if exe is None:
        ap.error("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
    _configure_octave_env(exe)
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    ok = [run_one(exe, n, scripts[n], args.outdir) for n in (args.names or scripts)]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
