"""
source_extract.diagrams.models.boundary_graph — Boundary curves found on a page: nodes (invariant points, edge points, open ends) and the curves between them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BoundaryNode:
    """A curve end in page pixels: ``junction`` (three or more curves meet: an invariant point),
    ``edge`` (on a triangle edge, ``side`` the index of the corner pair) or ``end`` (an open end)."""

    pixel: tuple[float, float]
    kind: str
    side: int | None = None


@dataclass
class BoundaryEdge:
    """One boundary curve between ``nodes`` (indices into ``BoundaryGraph.nodes``), ``pixels``
    (``(N, 2)``, page x y) from the first node to the second; ``gaps`` the bridged gaps
    (``(index, kind)`` as in ``BranchChain``), ``dashed`` when most of its length is dash gaps and dashes."""

    pixels: np.ndarray
    nodes: tuple[int, int]
    gaps: list[tuple[int, str]] = field(default_factory=list)
    ink_px: float = 0.0
    gap_px: float = 0.0
    dashed: bool = False

    @property
    def length_px(self) -> float:
        return self.ink_px + self.gap_px


@dataclass
class BoundaryGraph:
    nodes: list[BoundaryNode]
    edges: list[BoundaryEdge]
    log: list[str] = field(default_factory=list)

    def degree(self, node: int) -> int:
        return sum((e.nodes[0] == node) + (e.nodes[1] == node) for e in self.edges)
