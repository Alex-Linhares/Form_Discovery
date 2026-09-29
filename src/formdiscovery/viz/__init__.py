"""Graph display port (PLAN.md §6).

- :mod:`formdiscovery.viz.dot`: the DOT text writer and parser (``graph_to_dot.m``,
  ``dot_to_graph.m``, item 31);
- :mod:`formdiscovery.viz.pygraphviz_backend`: draw_dot's neato layout (pygraphviz or the
  ``neato`` executable) and Graphviz rendering (item 32);
- :mod:`formdiscovery.viz.graph_draw`: ``graph_draw.m`` with matplotlib (item 32);
- :mod:`formdiscovery.viz.draw`: the ``draw_dot(adj, labels, backend=...)`` facade, the
  progress figures and results drawing (item 32).
"""
