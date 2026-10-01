"""Qt desktop GUI (PySide6, loop0003): ``formdiscovery gui [FILE]``.

A thin shell over the verified port: no model logic lives here. The window picks a
``.mat`` data file (:mod:`.dataset` describes it with :func:`formdiscovery.io.load_dataset`
and :func:`formdiscovery.params.setrunps`), the forms (``ps.structures``) and the seed and
speed settings (:mod:`.main_window`); :func:`.app.main` starts it. :mod:`.worker` runs
``runmodel`` on a ``QThread`` and sends its graphs to the GUI thread as signals; Stop uses
the cancel hook :func:`formdiscovery.search.run_hooks`. :mod:`.canvas` draws the frames
live; :mod:`.stats` shows the statistics of a finished run and exports it. PySide6 is the optional
extra ``gui``; importing this package does not import Qt.
"""
