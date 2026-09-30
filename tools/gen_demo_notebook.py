#!/usr/bin/env python
"""Build (and by default execute) ``examples/formdiscovery_demo.ipynb`` (item 34).

The notebook reproduces the original ``masterrun.m`` demo end to end (chain, ring and
tree fitted to the three feature demos), compares the scores with the Octave baseline
(``tests/fixtures/masterrun.mat``), and draws the results with every display backend:
matplotlib (``draw_results``, MATLAB's progress figures 1-3), plotly and pyvis
(interactive, hover shows clusters and members), plus the networkx/GraphML exports.

Usage::

    python tools/gen_demo_notebook.py              # write and execute (about 1 min)
    python tools/gen_demo_notebook.py --no-execute # write the cells only

Execution needs nbformat, nbclient and a ``python3`` Jupyter kernel with plotly and
pyvis (the extra ``interactive``). The committed notebook is executed, so GitHub shows
the matplotlib figures; the plotly/pyvis cells load their JavaScript from a CDN.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO_ROOT / "examples" / "formdiscovery_demo.ipynb"

CELLS = [
    ("md", """\
# formdiscovery: the `masterrun` demo in Python

This notebook runs the Python port of Kemp & Tenenbaum's `formdiscovery1.0`
([*The discovery of structural form*, PNAS 2008](https://doi.org/10.1073/pnas.0802631105))
on the demo of the original `masterrun.m`: three structural forms (chain, ring, tree)
fitted to three small feature data sets (`demo_chain_feat`, `demo_ring_feat`,
`demo_tree_feat`, each 8 objects × 1000 features). It then

1. compares the scores with the original MATLAB code run in GNU Octave,
2. draws the inferred graphs as `draw_dot.m` does (neato layout, matplotlib),
3. shows MATLAB's progress figures 1-3 during one run,
4. draws the graphs interactively with plotly and pyvis (hover a node: its cluster, or
   a cluster's members), and
5. exports a graph to networkx and GraphML.

Plotly and pyvis are optional: `pip install -e .[interactive]`."""),
    ("code", """\
import sys, tempfile
from pathlib import Path

try:
    import formdiscovery
except ImportError:  # not installed: use the repository's src/
    sys.path.insert(0, str(Path.cwd().parent / "src"))
    import formdiscovery

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import HTML, display

from formdiscovery.run import masterrun, masterrun_ps
from formdiscovery.viz.draw import ProgressFigures, draw_graph, draw_results
from formdiscovery.viz.networkx_backend import have_graphviz_layout, to_graphml, to_networkx

%matplotlib inline
# the layout draw_dot uses (neato) needs pygraphviz; otherwise networkx's Kamada-Kawai
LAYOUT = "neato" if have_graphviz_layout() else "kamada_kawai"
print("formdiscovery from", Path(formdiscovery.__file__).parent, "| layout:", LAYOUT)"""),
    ("md", """\
## 1. Run the demo

`masterrun()` with its defaults is `masterrun.m`: `ps = defaultps(setps())` with
`reloutsideinit = 'overd'`, structures chain, ring, tree × data sets 1-3, one repeat.
MATLAB seeds `rand('state', rind)`; the port draws its permutations from numpy
(`seed=1`), so the random choices differ from Octave's, but the search finds the same
structures. This takes about half a minute."""),
    ("code", """\
ps = masterrun_ps()
res = masterrun(ps, log=print)"""),
    ("md", """\
## 2. Compare with the original code

`tests/fixtures/masterrun.mat` holds the `modellike` array of `masterrun.m` run in
Octave 10.3 (`tests/octave/fx_masterrun.m`). The scores are log posteriors
(log P(structure, data)); the highest score in each column is the form the model
discovers."""),
    ("code", """\
from formdiscovery.io import load_fixture

octave = np.asarray(load_fixture("masterrun")["modellike"], dtype=float)
python = res.modellike[:, :, 0]
print(f"{'data set':18s}{'form':8s}{'Python':>14s}{'Octave':>14s}{'rel. diff':>11s}")
for d in range(3):
    for s in (1, 3, 5):
        p, o = python[s, d], octave[s, d]
        print(f"{ps.data[d]:18s}{ps.structures[s]:8s}{p:14.4f}{o:14.4f}"
              f"{abs(p - o) / abs(o):11.1e}")
for d in range(3):
    best_py = ps.structures[int(np.argmax(np.where(python[:, d] != 0, python[:, d], -np.inf)))]
    best_oc = ps.structures[int(np.argmax(np.where(octave[:, d] != 0, octave[:, d], -np.inf)))]
    print(f"{ps.data[d]}: Python picks {best_py}, Octave picks {best_oc}")"""),
    ("md", """\
## 3. The inferred graphs

`draw_results` draws the final graph of every run, titled as `runmodel.m` titles its
figure 3 (`'<form>: estimated structure: <score>'`). Object nodes carry the object
names; the unlabelled nodes are the latent cluster nodes. `backend='networkx'` lays the
graph out with neato through networkx when pygraphviz is installed (then the positions
are exactly those of `draw_dot.m`); `backend='pygraphviz'` also reproduces
`graph_draw.m`'s ellipses and arrows."""),
    ("code", """\
fig = draw_results(res, backend="networkx", layout=LAYOUT)
fig"""),
    ("md", """\
## 4. Progress figures

With the `ps.show*` flags on, the MATLAB code draws while it searches: figure 1 before
and figure 2 after each clean-up (`gibbs_clean`), figure 3 the best split and the final
graph. `ProgressFigures` is a `show` callback that reproduces them; here it keeps the
last drawing of each figure for the chain on `demo_chain_feat`."""),
    ("code", """\
from formdiscovery.run import runmodel

pf = ProgressFigures(backend="networkx", layout=LAYOUT, figsize=(4.2, 3.2))
ps_show = ProgressFigures.enable(masterrun_ps(), ("postclean", "bestsplit", "inferredgraph"))
with tempfile.TemporaryDirectory() as tmp:
    out = runmodel(ps_show, 1, 0, 1, outdir=tmp, rng=1, show=pf)
print(len(pf.calls), "drawings:", sorted({(f, e) for e, f, _, _ in pf.calls}))
for num in sorted(pf.figures):
    display(pf.figures[num])"""),
    ("md", """\
## 5. Interactive graphs

`draw_graph(graph, names, backend=...)` draws one model graph through the same
`draw_dot` facade. With `backend='plotly'` or `'pyvis'`, hovering a node shows its
hover text: an object's cluster, or a cluster node's members.

### plotly

`draw_results(..., backend='plotly')` puts all nine runs in one interactive figure
(zoom, pan, hover)."""),
    ("code", """\
import plotly.io as pio

pio.renderers.default = "notebook_connected"  # plotly.js from the CDN keeps the notebook small
figp = draw_results(res, backend="plotly", layout=LAYOUT, panel=(3.6, 3.0))
figp.show()"""),
    ("md", """\
### pyvis

pyvis (vis-network) draws one graph per page, with the nodes pinned at the layout
positions; drag a node to move it. Here the tree fitted to `demo_tree_feat`."""),
    ("code", """\
import html

tree = res.structure[5, 2, 0]
net = draw_graph(tree, res.names[0, 2], backend="pyvis", layout=LAYOUT,
                 title="demo_tree_feat: tree")
page = net.generate_html()
display(HTML(f'<div><iframe srcdoc="{html.escape(page)}" width="720" height="560" '
             'style="border:none"></iframe></div>'))"""),
    ("md", """\
## 6. Exports

`to_networkx` gives the model graph as a networkx `DiGraph` (node attributes `kind`,
`label`, `cluster_id`; edge attributes `W` and the branch length `weight = 1/W`);
`to_graphml` and `to_dot` write it for Gephi, Cytoscape or Graphviz."""),
    ("code", """\
G = to_networkx(tree, res.names[0, 2])
print(G)
print([(v, G.nodes[v]) for v in list(G.nodes)[:3]])
print(list(G.edges(data=True))[:3])
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "tree.graphml"
    to_graphml(tree, path, res.names[0, 2])
    print(path.name, path.stat().st_size, "bytes")"""),
]


def build():
    import nbformat
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

    nb = new_notebook(cells=[new_markdown_cell(src) if kind == "md" else new_code_cell(src)
                             for kind, src in CELLS])
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3",
                                 "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    return nb


def execute(nb, timeout=900):
    from nbclient import NotebookClient

    NotebookClient(nb, timeout=timeout, kernel_name="python3",
                   resources={"metadata": {"path": str(NOTEBOOK.parent)}}).execute()
    return nb


def main(argv=None):
    import nbformat

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-execute", action="store_true")
    ap.add_argument("--out", default=str(NOTEBOOK))
    args = ap.parse_args(argv)
    nb = build()
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    if not args.no_execute:
        execute(nb)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
