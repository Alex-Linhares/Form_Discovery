# Legacy: the Octave oracle

Everything here exists to run Kemp & Tenenbaum's original MATLAB code in GNU Octave and
compare it with the Python port. The port, its fixture-based tests and the data sets do
not need it: `src/formdiscovery/`, `tests/`, `tests/fixtures/` and `data/` live outside
`legacy/`, and pytest skips this directory when it is missing (`PLAN_LEGACY.md`, loop0004).
The plan is to freeze this tree at a tag and then delete it from `main` in one commit
(`PLAN_LEGACY.md` Phases 4–5).

## What is here

| Path | Contents |
|---|---|
| `matlab/formdiscovery1.0/` | Verbatim copy of the original MATLAB sources, plus the documented Octave-compatibility edits in `matlab/PATCHES.md` (each marked `PATCH(octave)`). Its `data` is a committed symlink to `../../../data` so `setps.m` still finds the data sets |
| `matlab/octave_shims/` | The `randperm` shim that records or replays permutations (`randperm.m`, `randperm_config.m`) (`src/formdiscovery/CONVENTIONS.md`, "Randomness") |
| `matlab/run_baseline.m`, `matlab/baseline_merge.m` | Headless `masterrun` that wrote `tests/fixtures/baseline/{feat,rel}`; the merge for per-pair parallel runs |
| `tests_octave/` | One fixture script per ported function (`fx_<name>.m`, writes `tests/fixtures/<name>.mat`), plus spies and shims |
| `tools/` | `gen_fixtures.py`, `gen_paperlevel.py`, `gen_baselines.py` (regenerate through Octave), `compare_live.py` (Octave vs Python side by side), `mat_compare.py` (compare two directories of `.mat` outputs) |
| `tests/` | pytest tests that need the `.m` sources or the tools above (`test_patches.py`, `test_toolchain.py`, `test_gen_fixtures.py`, `test_gen_baselines.py`, `test_mat_compare.py`, `test_compare_live.py`, `test_known_issues_sources.py`); `conftest.py` re-exports the `octave` and `replay` fixtures from `tests/conftest.py` |
| `environment-octave.yml` | Adds Octave 10.3.0 and oct2py 6.1.1 (and holds python, numpy, scipy and OpenBLAS at the versions that produced the fixtures) to the Python-only env of `../environment.yml` |

## Environment

```bash
conda env create -f environment.yml                 # Python-only env "fd" (repo root)
conda env update -f legacy/environment-octave.yml   # add Octave and oct2py to it
```

The env does not need to be activated: `tests/conftest.py` and the tools find
`octave-cli` next to the interpreter (or in `~/anaconda3/envs/fd/bin/`) and set
`OCTAVE_EXECUTABLE` and `OCTAVE_HOME`. Every Octave process runs one BLAS thread
(`formdiscovery.threads.PIN_ENV`), except the `gibbs` fixture (ANOMALIES A19).

## The live suite

Tests marked `octave` drive Octave live through oct2py: 74 in the default gate and 3 more
under `slow`, in 38 files under `tests/` and `legacy/tests/`. Strict mode (`RALPH_REQUIRE_OCTAVE=1`, or any
interpreter in a conda env named `fd`) turns a skipped `octave` test into a failure, so a
missing Octave cannot pass silently; `RALPH_REQUIRE_OCTAVE=0` allows skips.

```bash
make legacy-check                                                 # strict live gate, ~6.5 min
~/anaconda3/envs/fd/bin/python -m pytest -q -m "not slow" -n 16   # the same without make
~/anaconda3/envs/fd/bin/python -m pytest -q -m octave -n 16       # live Octave parity only
~/anaconda3/envs/fd/bin/python -m pytest -q legacy/tests          # this directory alone
python -m pytest -q -m "not slow and not octave" -n 16            # default gate (make test), no Octave, ~1 min
```

Since loop0004 item 05 the default gate (and `RalphLoops/loop_template/loop.py`) is the
fixture-only command; `make legacy-check` is the explicit job, run before any fixture is
touched and for any change under `legacy/`.

Without `legacy/` (or without Octave) the `octave` tests skip, or fail in strict mode.
Checked at the end of loop0004 (item 06) in a copy of the tree with `legacy/` deleted: the
default gate passes in the fd env (3696 passed) and under a base interpreter without
oct2py (3426 passed); with `legacy/` present the counts are 3792 and 3521, the difference
being the non-`octave` tests in `legacy/tests/`.

## Regenerating fixtures and baselines

Regenerate into another directory and compare with the committed files; never write over
`tests/fixtures/` unless a change is meant to alter a fixture. When one is, rewrite the
hash list in the same commit (`tests/test_fixture_integrity.py` fails otherwise):
`cd tests/fixtures && git ls-files ':!SHA256SUMS' | LC_ALL=C sort | xargs sha256sum > SHA256SUMS`
(add new files to git first).

```bash
python legacy/tools/gen_fixtures.py --list                              # the fixture scripts
python legacy/tools/gen_fixtures.py --jobs 16 --outdir build/fx --compare tests/fixtures
python legacy/tools/gen_fixtures.py --outdir build/fx --compare tests/fixtures params util   # a few
python legacy/tools/gen_paperlevel.py --workers 16 --out build/paperlevel.mat
python legacy/tools/gen_baselines.py --kind feat --jobs 16 --outdir build/feat --compare tests/fixtures/baseline/feat
python legacy/tools/gen_baselines.py --kind rel  --jobs 16 --outdir build/rel  --compare tests/fixtures/baseline/rel
python legacy/tools/mat_compare.py DIR_A DIR_B                           # two output directories by content
python legacy/tools/compare_live.py --jobs 16                            # Octave vs Python, 63 baseline pairs
```

All 31 fixtures take about 8 minutes with `--jobs 16`, the two baseline grids about 20 s,
`compare_live.py` about 30 s (README, "How it was verified"). `--compare` checks loaded
arrays to all digits, skipping timing fields and masking temp-directory names and the
checkout prefix of data paths (ANOMALIES A32).
