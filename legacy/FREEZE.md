# Freeze record: the Octave oracle

Date: 2026-10-01. Repository commit before this freeze: bdc201f.
Tag: `octave-oracle-final` (this commit). After it, `legacy/` is removed from `main`
(PLAN_LEGACY.md Phase 5). To reconstruct the oracle: `git checkout octave-oracle-final`,
create the env from `environment.yml` + `legacy/environment-octave.yml`, then
`make legacy-check`.

## Environment that produced every committed fixture and baseline

| Component | Version |
|---|---|
| GNU Octave | 10.3.0 (conda-forge, build pl5321hd0fbda6_4) |
| oct2py | 6.1.1 |
| OpenBLAS (libopenblas) | 0.3.34 pthreads (conda-forge), libblas 3.11.0 |
| Python / numpy / scipy | 3.12.14 / 2.5.3 / 1.18.1 |
| Graphviz | 14.1.2 (conda-forge; the system neato has no layout plugin) |
| OS / CPU | Ubuntu 26.04, 32 cores |

BLAS policy (ANOMALIES.md A16, A19): every Octave process and Python worker runs with
`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, except the `gibbs` fixture, which is
regenerated with OpenBLAS's default thread count because its recorded search path depends
on summation order (`tests/conftest.py::BLAS_DEFAULT_FIXTURES`).

## Final verification, run on the freeze date

| Check | Result |
|---|---|
| `make legacy-check` (strict live-Octave gate, `-n 16`) | 3866 passed, 3 skipped (none Octave), 9 min 38 s |
| `legacy/tools/gen_fixtures.py --jobs 16 --compare tests/fixtures` | 31 fixtures regenerated: **31 identical, 0 differ** (10 min 38 s) |
| `legacy/tools/gen_baselines.py --kind feat --compare` | 21 files: **0 differences** |
| `legacy/tools/gen_baselines.py --kind rel --compare` | 56 files: **0 differences** |
| `make fixture-sums` | all 115 entries of `tests/fixtures/SHA256SUMS` verified |

## What the fixtures are

`tests/fixtures/*.mat` (31 files) and `tests/fixtures/baseline/{feat,rel}` are the
reference answers produced by the original MATLAB code (Charles Kemp, 2008, with the
documented Octave-compatibility edits in `legacy/matlab/PATCHES.md`) running in the
environment above. They stay in the repository after `legacy/` is deleted and remain the
oracle for every parity test. Their SHA-256 hashes are committed and checked by
`tests/test_fixture_integrity.py`.

Policy after deletion (CLAUDE.md): a change that alters any fixture value requires the
oracle to be rerun from the tag before the fixture is updated.
