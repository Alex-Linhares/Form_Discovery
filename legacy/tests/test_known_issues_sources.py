"""Source pins for KNOWN_ISSUES.md (item 05; moved here in loop0004 item 03).

Each quirk of :data:`tests.test_known_issues.QUIRKS` must still be at the cited line of the
original source; ``zinit_rel.m`` is unreferenced and ``dijkstra`` is always called with one
output. These read ``legacy/matlab/formdiscovery1.0``; the decision/pin checks stay in
``tests/test_known_issues.py``.
"""
import re

import pytest

from tests.conftest import MATLAB_DIR
from tests.test_known_issues import QUIRKS


def source_lines(name):
    return (MATLAB_DIR / name).read_text().splitlines()


@pytest.mark.parametrize("key", sorted(QUIRKS))
def test_quirk_at_cited_line(key):
    name, line, text = QUIRKS[key]
    assert text in source_lines(name)[line - 1]


def test_zinit_rel_is_unreferenced():
    for f in MATLAB_DIR.glob("*.m"):
        if f.name != "zinit_rel.m":
            assert "zinit_rel" not in f.read_text(errors="replace"), f.name


def test_dijkstra_called_with_one_output():
    calls = []
    for f in MATLAB_DIR.glob("*.m"):
        if f.name == "dijkstra.m":
            continue
        for ln in f.read_text(errors="replace").splitlines():
            code = ln.split("%", 1)[0]
            if "dijkstra(" in code:
                calls.append((f.name, code))
    assert calls
    for name, code in calls:
        assert re.match(r"\s*\w+\s*=\s*dijkstra\(", code), (name, code)
