"""
source_extract.diagrams.builders.field_regions_builder — Primary-field regions of a ternary: the triangle divided by its boundary curves.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from source_extract.diagrams.models.field_approximation import FieldApproximation
from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.ternary_calibration import TernaryCalibration

_BARRIER_PX = 3
_ADJACENT_PX = 9
_CONTACT_SHARE = 0.8
_MIN_REGION_PX2 = 400


def build_field_regions(
    system: dict,
    calibration: TernaryCalibration,
    scale: LineScale | None = None,
) -> FieldApproximation:
    """Field regions (``origin``, ``labels``, ``phases``, ``log``; no surfaces) of ``system``.

    Regions: the triangle divided by the boundary curves (``polyline_wt``; inversions
    and two-liquid branches do not divide a field). A region takes the field of an
    isotherm whose middle lies in it, else the phase of the boundaries along ≥ 80 % of
    its outline (contact pixels in a 9 px band; curves meeting at a corner only touch
    it); regions under 400 px² or without such a phase stay unassigned (label 0).
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    components = list(system["components"])

    def page(wt) -> tuple[float, float]:
        values = [float(wt.get(c, 0.0)) for c in components] if isinstance(wt, dict) else [float(w) for w in wt]
        return calibration.to_page(values)

    corners = np.array([calibration.stored_to_page(*calibration.corners[c]) for c in components])
    x0, y0 = (np.floor(corners.min(axis=0)) - 2).astype(int)
    x1, y1 = (np.ceil(corners.max(axis=0)) + 2).astype(int)
    size = (int(x1 - x0), int(y1 - y0))
    origin = (int(x0), int(y0))

    def local(p):
        return p[0] - origin[0], p[1] - origin[1]

    boundaries = [(c, [page(w) for w in c["polyline_wt"]]) for c in system.get("boundaryCurves", []) if c.get("polyline_wt")]
    isotherms = [(i, [page(w) for w in i["polyline_wt"]]) for i in system.get("isotherms", []) if i.get("polyline_wt")]

    inside = Image.new("1", size, 0)
    ImageDraw.Draw(inside).polygon([local(c) for c in corners], fill=1)
    barrier = Image.new("1", size, 0)
    draw = ImageDraw.Draw(barrier)
    draw.line([*(local(c) for c in corners), local(corners[0])], fill=1, width=s.count(_BARRIER_PX))
    for _, pixels in boundaries:
        draw.line([local(p) for p in pixels], fill=1, width=s.count(_BARRIER_PX))
    regions, count = ndimage.label(np.array(inside, bool) & ~np.array(barrier, bool))
    areas = ndimage.sum(np.ones_like(regions), regions, index=np.arange(1, count + 1))

    phases = list(dict.fromkeys(p for p in system.get("phases", []) if p))
    kept = [r for r in range(1, count + 1) if areas[r - 1] >= s.area(_MIN_REGION_PX2)]
    contact: dict[int, dict[str, float]] = {r: {} for r in kept}
    total: dict[int, float] = {r: 0.0 for r in kept}
    for curve, pixels in boundaries:
        band = Image.new("1", size, 0)
        ImageDraw.Draw(band).line([local(p) for p in pixels], fill=1, width=s.count(_ADJACENT_PX))
        touched = regions[np.array(band, bool)]
        for region, pixels_in in zip(*np.unique(touched[touched > 0], return_counts=True)):
            if int(region) not in contact:
                continue
            total[int(region)] += float(pixels_in)
            for phase in {f for f in curve.get("fields", []) if f}:
                contact[int(region)][phase] = contact[int(region)].get(phase, 0.0) + float(pixels_in)
    assigned: dict[int, str] = {}
    for isotherm, pixels in isotherms:
        x, y = (int(round(v)) for v in local(_middle(pixels)))
        if 0 <= y < size[1] and 0 <= x < size[0] and int(regions[y, x]) in contact:
            assigned.setdefault(int(regions[y, x]), isotherm["field"])
    log: list[str] = []
    for region in kept:
        if region in assigned:
            continue
        ranked = sorted(contact[region].items(), key=lambda item: -item[1])
        if ranked and ranked[0][1] >= _CONTACT_SHARE * total[region] and (len(ranked) == 1 or ranked[1][1] < ranked[0][1]):
            assigned[region] = ranked[0][0]
        else:
            shares = ", ".join(f"{p} {v / total[region]:.0%}" for p, v in ranked[:3]) if ranked else "no boundary"
            log.append(f"region of {areas[region - 1]:.0f} px² at {_px(_centre(regions == region), origin)}: "
                       f"no single field ({shares}); not approximated")
    for phase in assigned.values():
        if phase not in phases:
            phases.append(phase)
    labels = np.zeros(regions.shape, np.int16)
    for region, phase in assigned.items():
        labels[regions == region] = phases.index(phase) + 1
    return FieldApproximation(origin=origin, labels=labels, phases=phases, log=log)


def _middle(pixels: list[tuple[float, float]]) -> tuple[float, float]:
    points = np.asarray(pixels, float)
    length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    return float(np.interp(length[-1] / 2, length, points[:, 0])), float(np.interp(length[-1] / 2, length, points[:, 1]))


def _centre(mask: np.ndarray) -> tuple[float, float]:
    rows, cols = np.nonzero(mask)
    return float(cols.mean()), float(rows.mean())


def _px(point: tuple[float, float], origin: tuple[int, int]) -> str:
    return f"({point[0] + origin[0]:.0f}, {point[1] + origin[1]:.0f})"
