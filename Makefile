# Test entry points.
#   make test          default gate: fixture-only (no Octave; ~1 min with 16 workers)
#   make slow          long runs (Python only since the oracle was frozen)
#   make fixture-sums  check tests/fixtures against tests/fixtures/SHA256SUMS
#   make legacy-check  the strict live-Octave gate: only at tag octave-oracle-final
# Override the interpreter or worker count: make test PY=python JOBS=8

PY ?= $(HOME)/anaconda3/envs/fd/bin/python
JOBS ?= 16

.PHONY: test slow fixture-sums legacy-check

test:
	$(PY) -m pytest -q -m "not slow and not octave" -n $(JOBS)

slow:
	$(PY) -m pytest -q -m "slow and not octave" -n $(JOBS)

fixture-sums:
	cd tests/fixtures && sha256sum -c --quiet SHA256SUMS

legacy-check:
	@echo "The Octave oracle (legacy/) was frozen and removed; see legacy/FREEZE.md at the tag:"
	@echo "    git checkout octave-oracle-final && make legacy-check"
	@exit 1
