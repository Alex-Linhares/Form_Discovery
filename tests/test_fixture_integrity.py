"""Fixture integrity (loop0004 item 05, PLAN_LEGACY.md Phase 3).

``tests/fixtures/SHA256SUMS`` lists the SHA-256 of every committed fixture, in
``sha256sum`` format with paths relative to ``tests/fixtures``. The default gate needs no
Octave, so nothing else would notice a fixture edited by hand or by a regeneration; this
test fails on any changed, missing or extra file. Check by hand with
``cd tests/fixtures && sha256sum -c --quiet SHA256SUMS``. After a deliberate regeneration
(the oracle rerun first, see CLAUDE.md) rewrite the list with
``cd tests/fixtures && git ls-files ':!SHA256SUMS' | LC_ALL=C sort | xargs sha256sum > SHA256SUMS``.
"""
from __future__ import annotations

import hashlib

import pytest

from formdiscovery.io import FIXTURES_DIR as FIXTURES

SUMS = FIXTURES / "SHA256SUMS"


def read_sums(path=SUMS):
    """``{relative path: hex digest}`` from a ``sha256sum`` listing."""
    sums = {}
    for line in path.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.lstrip("*")] = digest
    return sums


def fixture_files(root=FIXTURES):
    """Every file under ``root`` except the listing itself and Python caches."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and p.name != SUMS.name and "__pycache__" not in p.parts}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def test_sums_cover_every_fixture():
    listed = set(read_sums())
    present = fixture_files()
    assert not present - listed, f"fixtures not in SHA256SUMS: {sorted(present - listed)}"
    assert not listed - present, f"SHA256SUMS lists missing files: {sorted(listed - present)}"


def test_sums_sorted_and_well_formed():
    lines = SUMS.read_text().splitlines()
    names = [line.split(maxsplit=1)[1] for line in lines]
    assert names == sorted(names)
    assert all(len(line.split(maxsplit=1)[0]) == 64 for line in lines)


@pytest.mark.parametrize("name", sorted(read_sums()))
def test_fixture_hash(name):
    assert sha256(FIXTURES / name) == read_sums()[name], (
        f"tests/fixtures/{name} changed; fixtures come only from the Octave oracle "
        "(legacy/tools/gen_fixtures.py), see CLAUDE.md")


def test_edit_is_detected(tmp_path):
    (tmp_path / "a.mat").write_bytes(b"one")
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{sha256(tmp_path / 'a.mat')}  a.mat\n")
    assert sha256(tmp_path / "a.mat") == read_sums(sums)["a.mat"]
    (tmp_path / "a.mat").write_bytes(b"two")
    assert sha256(tmp_path / "a.mat") != read_sums(sums)["a.mat"]
    (tmp_path / "b.mat").write_bytes(b"new")
    assert fixture_files(tmp_path) - set(read_sums(sums)) == {"b.mat"}
