"""Static pins for KNOWN_ISSUES.md (item 05).

Each quirk must still be at the cited line of the original source, and every
entry must be present in KNOWN_ISSUES.md. The behavioural pins are added by
the items that port each function (see the "Pin:" line of each entry).
"""
import re

import pytest

from tests.conftest import MATLAB_DIR, REPO_ROOT

KNOWN_ISSUES = REPO_ROOT / "KNOWN_ISSUES.md"

# id -> (file, 1-based line, text that must be on that line)
QUIRKS = {
    "KI-1": ("best_split.m", 120, "case{'1,2'}"),
    "KI-2a": ("combinegraphs.m", 48, "illegal = na*0:(nb-1)+illegal;"),
    "KI-2b": ("combinegraphs.m", 66, "illind(nb*0:(na-1)+newillegal) = 1;"),
    "KI-3a": ("structurefit.m", 38, "part{depth,c,pind,2}"),
    "KI-3b": ("structurefit.m", 59, "part{depth,c,1,2}"),
    "KI-4": ("structurefit.m", 239, "m = lls{depth,i,c, pind}; mi = i; mc = c; mpind = pind;"),
    "KI-5": ("zinit_rel.m", 14, "cd(irmdatadir);"),
    "KI-6": ("dijkstra.m", 111, "P = pred2path(P,s,t);"),
    "KI-8": ("dot_to_graph.m", 89, "lbl_pos = strfind(line, labels{node});"),
    "KI-9": ("find_descendants.m", 29, "ds = union(ds, descendants{c});"),
    "KI-10": ("graph_like_conn.m", 50, "'LargeScale'"),
    "KI-11": ("runmodel.m", 89, "ps.fixedall= 1; ps.fixedall= 1;"),
    "KI-13": ("relgraphinit.m", 18, "counts = hist(z, unique(z));"),
    "KI-14": ("scaledata.m", 51, "[b i j]=unique(datamask', 'rows');"),
    "KI-15": ("find_descendants.m", 24, "queue = [queue, node];"),
    "KI-16": ("structcounts.m", 31, "counts(3, 1:2) = [0,0];"),
}


def source_lines(name):
    return (MATLAB_DIR / name).read_text().splitlines()


@pytest.mark.parametrize("key", sorted(QUIRKS))
def test_quirk_at_cited_line(key):
    name, line, text = QUIRKS[key]
    assert text in source_lines(name)[line - 1]


def test_every_entry_documented():
    doc = KNOWN_ISSUES.read_text()
    ids = set(re.findall(r"^### (KI-\d+) ", doc, flags=re.M))
    assert ids == {f"KI-{n}" for n in range(1, 17)}
    for key in QUIRKS:
        assert re.sub(r"[ab]$", "", key) in ids
    for entry in re.split(r"^### ", doc, flags=re.M)[1:]:
        assert "**Decision:**" in entry and "**Pin:**" in entry, entry[:40]


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
