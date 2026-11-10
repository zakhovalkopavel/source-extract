"""
source_extract.diagrams.builders.boundary_arrow_segments — Page-pixel pieces of the stored boundary polylines with their arrows.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.ternary_calibration import TernaryCalibration


def boundary_arrow_segments(system: dict, pixel_origin: tuple[float, float] = (0.0, 0.0)) -> list[tuple[list[tuple[float, float]], str]]:
    """``(page pixels, arrow)`` per path segment of every boundary curve with ``arrows`` and ``polyline_wt``.

    The polyline is cut at the vertex nearest (wt%) to each inner path point, in order along it;
    an open end adds the piece from the last path point to the polyline end. Curves whose inner
    path points have no ``liquid_wt`` in the system file are skipped.
    """
    calibration = TernaryCalibration.from_system(system, pixel_origin)
    components = list(system["components"])
    wt_of = {p["id"]: p.get("liquid_wt") for p in system.get("invariantPoints", [])}
    pieces = []
    for curve in system.get("boundaryCurves", []):
        path, arrows, polyline = list(curve.get("path") or []), curve.get("arrows"), curve.get("polyline_wt")
        if not isinstance(arrows, list) or not polyline or len(polyline) < 2:
            continue
        vertices = np.asarray(polyline, float)
        cuts, start = [0], 0
        for point_id in path[1:-1] if len(arrows) == len(path) - 1 else path[1:]:
            wt = wt_of.get(point_id)
            if not isinstance(wt, dict):
                cuts = []
                break
            target = np.array([float(wt.get(c) or 0.0) for c in components])
            start += int(np.argmin(np.linalg.norm(vertices[start:] - target, axis=1)))
            cuts.append(start)
        if not cuts:
            continue
        cuts.append(len(vertices) - 1)
        for arrow, a, b in zip(arrows, cuts, cuts[1:]):
            if b > a:
                pieces.append(([calibration.to_page(list(v)) for v in vertices[a:b + 1]], arrow))
    return pieces
