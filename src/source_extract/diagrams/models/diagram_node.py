"""
source_extract.diagrams.models.diagram_node — A numbered point of a node map (corner, invariant, junction, edge point, dash end, free end, ring).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiagramNode:
    """``pixel`` is in the stored coordinates of the system file; ``wt`` follows ``components``.

    ``kind``: ``junction`` (lines meet or cross), ``edge`` (junction on a triangle
    edge), ``dash-end`` (where a dash stopping short of a solid line would meet it),
    ``free-end`` (a solid line stopping in open paper), ``invariant`` (pixel of an invariant of the system file, ``invariant`` = id),
    ``ring`` (small drawn circle, e.g. a compound composition), ``corner``
    (triangle corner, ``invariant`` = the component) or ``user`` (point added
    by hand on a node-map image, label ending in •).
    """

    label: str
    kind: str
    pixel: tuple[float, float]
    wt: list[float]
    invariant: str | None = None

    def to_dict(self) -> dict:
        out = {"label": self.label, "kind": self.kind, "pixel": [round(self.pixel[0], 1), round(self.pixel[1], 1)],
               "wt": [round(v, 1) for v in self.wt]}
        if self.invariant:
            out["invariant"] = self.invariant
        return out
