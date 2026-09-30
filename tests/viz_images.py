"""Image-regression cases for ``tests/test_viz_draw.py`` (item 32).

Each case draws one graph of ``tests/fixtures/viz_draw.mat`` with
:func:`formdiscovery.viz.graph_draw.graph_draw` at Octave's positions (``dd_x``/``dd_y``,
so no neato is needed), with draw_dot's labels, font size and ``nodemult``, on a
560 x 420 pixel figure (MATLAB's default) in DejaVu Sans. Two baselines per case in
``tests/baseline_images/``: ``<case>.png`` (full) and ``<case>_notext.png`` (labels and
title hidden). They are this port's own renders (the original cannot draw in
Octave, ANOMALIES.md); regenerate them with ``python tools/gen_viz_baselines.py`` after
a deliberate change to the drawing.

Per-backend baselines (item 33): ``render_case(..., backend='networkx')`` draws the same
cases with :func:`formdiscovery.viz.networkx_backend.draw_networkx`; its baselines are in
``tests/baseline_images/networkx/``.
"""
from pathlib import Path

import numpy as np

BASELINE_DIR = Path(__file__).resolve().parent / "baseline_images"
BACKEND_DIRS = {"pygraphviz": BASELINE_DIR, "networkx": BASELINE_DIR / "networkx"}
# matplotlib version the full (text) baselines were rendered with
VERSION_FILE = BASELINE_DIR / "matplotlib_version.txt"
# name -> dd_run of the fixture case, graph_draw options
IMAGE_CASES = {
    "true_demo_chain_feat": ("true demo_chain_feat", {}),
    "feat_tree_demo_tree_feat": ("feat 6 3", {}),
    "rel_dirchain_demo_ring_rel_bin": ("rel 10 4", {}),
    "selfloops": ("selfloops", {}),
    "undirected_lines": ("undirected", {"undirected": "lines"}),
}


def _labels(v):
    if isinstance(v, str):
        return [v]
    return [a if isinstance(a, str) else "" for a in np.atleast_1d(v)]


def render_case(fx, name, path=None, dpi=100, text=True, backend="pygraphviz"):
    """Draw case ``name`` and return the matplotlib figure (saved to ``path``).
    ``text=False`` hides the labels and the title (text rasterisation changes between
    matplotlib versions; the geometry does not)."""
    import matplotlib
    from matplotlib.figure import Figure

    from formdiscovery.viz.graph_draw import graph_draw
    from formdiscovery.viz.networkx_backend import draw_networkx

    run, kw = IMAGE_CASES[name]
    k = list(fx["dd_run"]).index(run)
    adj = (np.atleast_2d(fx["dd_adj"][k]) > 0).astype(float)
    with matplotlib.rc_context({"font.family": "DejaVu Sans", "text.hinting": "none",
                                "savefig.dpi": dpi}):
        fig = Figure(figsize=(5.6, 4.2), dpi=dpi)
        ax = fig.add_subplot()
        opts = dict(fontsize=float(fx["dd_fontsize"][k]),
                    nodemult=float(fx["dd_nodemult"][k]), ax=ax, **kw)
        x, y = np.ravel(fx["dd_x"][k]), np.ravel(fx["dd_y"][k])
        if backend == "networkx":
            _, h = draw_networkx(adj, _labels(fx["dd_labels"][k]), x, y, **opts)
            texts = list(h["labels"].values())
        else:
            _, _, h = graph_draw(adj, node_labels=_labels(fx["dd_labels"][k]), x=x, y=y,
                                 **opts)
            texts = h["labels"]
        if text:
            ax.set_title(name)
        else:
            for t in texts:
                t.set_visible(False)
        if path is not None:
            fig.savefig(path)
    return fig
