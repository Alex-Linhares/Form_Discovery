#!/usr/bin/env python
"""Regenerate ``tests/fixtures/paperlevel.mat`` (item 30) with parallel Octave processes.

``tests/octave/fx_paperlevel.m`` has 45 independent ``runmodel`` runs (synthetic data at
speed 5, animals/colors at speed 54, 4 extra animals seeds). Run one after another they
take over an hour; this tool runs each job in its own ``octave-cli`` (``fx_paperlevel(part, job)``), then merges the
parts in Octave (``paperlevel_merge.m``). ``python tools/gen_fixtures.py paperlevel``
also works (all jobs in one process), only slower.

Usage::

    python tools/gen_paperlevel.py [--workers N] [--jobs 1,2,3] [--out PATH]
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tests.conftest import FIXTURES_DIR, MATLAB_DIR, OCTAVE_TESTS_DIR  # noqa: E402
from tests.conftest import _configure_octave_env, find_octave  # noqa: E402
from formdiscovery.threads import pinned_env  # noqa: E402

NJOBS = 45


def _octstr(path):
    return "'" + str(path).replace("'", "''") + "'"


def _octave(exe, cmd):
    return subprocess.run(
        [exe, "--no-gui", "--quiet", "--no-window-system", "--eval",
         f"addpath({_octstr(MATLAB_DIR)}); addpath({_octstr(OCTAVE_TESTS_DIR)}); {cmd}"],
        cwd=REPO_ROOT, capture_output=True, text=True, env=pinned_env())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workers", type=int, default=min(NJOBS, os.cpu_count() or 1))
    ap.add_argument("--jobs", default=None, help="comma-separated 1-based job numbers")
    ap.add_argument("--out", default=str(FIXTURES_DIR / "paperlevel.mat"))
    args = ap.parse_args(argv)
    jobs = ([int(j) for j in args.jobs.split(",")] if args.jobs
            else list(range(1, NJOBS + 1)))
    exe = find_octave()
    if exe is None:
        ap.error("Octave not found (set OCTAVE_EXECUTABLE or create the 'fd' env)")
    _configure_octave_env(exe)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        def run(j):
            part = Path(tmp) / f"part{j:02d}.mat"
            res = _octave(exe, f"fx_paperlevel({_octstr(part)}, {j});")
            ok = res.returncode == 0 and part.is_file()
            msg = res.stdout.strip().splitlines()[-1:] if ok else [res.stdout + res.stderr]
            print(f"job {j}: {'ok' if ok else 'FAILED'} {' '.join(msg)}", flush=True)
            return part if ok else None

        with ThreadPoolExecutor(args.workers) as ex:
            parts = list(ex.map(run, jobs))
        if any(p is None for p in parts):
            return 1
        cell = "{" + ", ".join(_octstr(p) for p in parts) + "}"
        res = _octave(exe, f"paperlevel_merge({_octstr(args.out)}, {cell});")
        if res.returncode != 0:
            sys.stderr.write(res.stdout + res.stderr)
            return 1
    print(f"wrote {args.out} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
