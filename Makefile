# Test entry points (loop0004 item 05, PLAN_LEGACY.md Phase 3).
#   make test          default gate: fixture-only, needs neither Octave nor legacy/
#   make legacy-check  strict live gate: Octave runs, a skipped `octave` test fails;
#                      run it before touching any fixture (fd env + legacy/environment-octave.yml)
#   make slow          long runs (Octave live)
#   make fixture-sums  check tests/fixtures against tests/fixtures/SHA256SUMS
# Override the interpreter or worker count: make test PY=python JOBS=8

PY ?= $(HOME)/anaconda3/envs/fd/bin/python
JOBS ?= 16

.PHONY: test legacy-check slow fixture-sums

test:
	$(PY) -m pytest -q -m "not slow and not octave" -n $(JOBS)

legacy-check:
	RALPH_REQUIRE_OCTAVE=1 $(PY) -m pytest -q -m "not slow" -n $(JOBS)

slow:
	RALPH_REQUIRE_OCTAVE=1 $(PY) -m pytest -q -m slow -n $(JOBS)

fixture-sums:
	cd tests/fixtures && sha256sum -c --quiet SHA256SUMS
