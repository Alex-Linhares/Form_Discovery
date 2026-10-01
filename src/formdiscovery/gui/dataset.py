"""What the data picker shows about a ``.mat`` data file (loop0003 item 01).

:func:`dataset_info` loads the file as ``runmodel.m:29`` does
(:func:`formdiscovery.io.load_dataset`) and classifies it with
:func:`formdiscovery.params.setrunps` (``setrunps.m:1-27``: relational struct, square
similarity matrix, or features), so the GUI applies the model's own rule. No Qt here.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..io import load_dataset
from ..params import setrunps
from ..run import masterrun_ps

__all__ = ["DatasetInfo", "dataset_info", "NAMES_SHOWN"]

NAMES_SHOWN = 8  # names listed in the info panel before "(+k more)"

KIND_LABEL = {"feat": "features", "sim": "similarity", "rel": "relational"}


@dataclass
class DatasetInfo:
    """A loaded data file: ``data`` as :func:`load_dataset` returns it (ndarray, or the
    relational dict), ``kind`` ``'feat'``/``'sim'``/``'rel'`` (``ps.runps.type``),
    ``nobjects``; ``nfeatures`` (feature data), ``reltype`` (``'relbin'``/``'relfreq'``)
    and ``nrelations`` (relational data); ``names`` (empty when the file has none)."""

    path: Path
    data: object
    kind: str
    nobjects: int
    nfeatures: int | None = None
    reltype: str | None = None
    nrelations: int | None = None
    names: list = field(default_factory=list)

    @property
    def stem(self):
        return self.path.stem

    def summary_lines(self):
        """The info panel's lines (``label: value``)."""
        lines = [f"File: {self.path.name}",
                 f"Type: {self.kind} ({KIND_LABEL[self.kind]})",
                 f"Objects: {self.nobjects}"]
        if self.kind == "feat":
            lines.append(f"Features: {self.nfeatures}")
        elif self.kind == "sim":
            lines.append(f"Similarity matrix: {self.nobjects} × {self.nobjects}")
        else:
            lines.append(f"Relation type: {self.reltype}, relations: {self.nrelations}")
            lines.append("Note: runmodel uses speed 5 and init 'none' for relational data")
        if self.names:
            shown = ", ".join(self.names[:NAMES_SHOWN])
            more = len(self.names) - NAMES_SHOWN
            lines.append(f"Names: {shown}" + (f" (+{more} more)" if more > 0 else ""))
        else:
            lines.append("Names: none (objects are numbered)")
        return lines

    def summary(self):
        return "\n".join(self.summary_lines())


def dataset_info(path):
    """Load ``path`` (a MATLAB ``.mat`` with ``data`` and optional ``names``) and describe
    it. Raises (``OSError``, ``MatReadError``, ``KeyError``, ...) for unreadable or
    unsuitable files."""
    path = Path(path)
    if path.suffix != ".mat":
        raise ValueError(f"not a .mat file: {path.name}")
    loaded = load_dataset(path.stem, with_names=True, data_dir=path.parent)
    if isinstance(loaded, dict):
        data, names = loaded, loaded["names"]
    else:
        data, names = loaded
    nobjects, ps = setrunps(data, 0, masterrun_ps())  # dind only sets ps.simdim's dim
    info = DatasetInfo(path=path, data=data, kind=ps.runps.type, nobjects=nobjects,
                       names=list(names or []))
    if info.kind == "feat":
        a = np.asarray(data)
        info.nfeatures = int(a.shape[1]) if a.ndim > 1 else 1
    elif info.kind == "rel":
        r = np.asarray(data["R"])
        info.reltype = data["type"]
        info.nrelations = int(r.shape[2]) if r.ndim > 2 else 1
    return info
