"""
source_extract.diagrams.detection.triangle_reading_order — Triangles of a page in the reading order of its figures.
"""
from __future__ import annotations

_ACROSS_MIDDLE = 0.1

Triangle = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def triangle_reading_order(triangles: list[Triangle], page_width: int) -> list[Triangle]:
    """Triangles ``(top, left, right)`` in the reading order of a two-column page.

    A triangle reaching at least 10 % of the page width past the middle on both
    sides spans both columns and is read on its own; between two such, the left
    column is read top-down, then the right one (a right-column apex a little
    higher than the left one does not come first).
    """
    middle, margin = page_width / 2, _ACROSS_MIDDLE * page_width

    def columns(band: list[Triangle]) -> list[Triangle]:
        return sorted(band, key=lambda t: ((t[1][0] + t[2][0]) / 2 > middle, t[0][1]))

    ordered, band = [], []
    for triangle in sorted(triangles, key=lambda t: t[0][1]):
        _, left, right = triangle
        if left[0] <= middle - margin and right[0] >= middle + margin:
            ordered += columns(band) + [triangle]
            band = []
        else:
            band.append(triangle)
    return ordered + columns(band)
