"""Regenerate the image-regression baselines of ``tests/test_viz_draw.py`` (item 32).

    python tools/gen_viz_baselines.py

Writes ``tests/baseline_images/<case>.png`` and ``<case>_notext.png`` for every case in
``tests/viz_images.py`` (and the same under ``networkx/`` for the networkx backend, item
33), and the matplotlib version to ``matplotlib_version.txt``.
These are renders of the Python port (not Octave output); regenerate them only after a
deliberate change to :mod:`formdiscovery.viz.graph_draw`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from formdiscovery.io import load_fixture  # noqa: E402
import matplotlib  # noqa: E402

from tests.viz_images import BACKEND_DIRS, IMAGE_CASES, VERSION_FILE, render_case  # noqa: E402


def main():
    fx = load_fixture("viz_draw")
    for backend, bdir in BACKEND_DIRS.items():
        bdir.mkdir(exist_ok=True)
        for name in IMAGE_CASES:
            for suffix, text in (("", True), ("_notext", False)):
                path = bdir / f"{name}{suffix}.png"
                render_case(fx, name, path, text=text, backend=backend)
                print(f"wrote {path.relative_to(ROOT)}")
    VERSION_FILE.write_text(matplotlib.__version__ + "\n")


if __name__ == "__main__":
    main()
