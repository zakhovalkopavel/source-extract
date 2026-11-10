"""
source_extract.diagrams.builders.field_temperature_builder — Liquidus temperature surface of each primary field of a ternary,
fitted to its isotherms and the temperatures on its boundaries.

"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay, QhullError

from source_extract.diagrams.builders.field_regions_builder import build_field_regions
from source_extract.diagrams.models.field_approximation import FieldApproximation
from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.temperature_point import TemperaturePoint
from source_extract.diagrams.models.ternary_calibration import TernaryCalibration
from source_extract.diagrams.tracing.contour_segments import contour_segments

_ISOTHERM_STEP_WT = 0.5
_BOUNDARY_STEP_WT = 1.0
_ON_CURVE_WT = 0.7
_GRID_PX = 3
_COORD_PX = 1000.0
_SMOOTHING = 1e-4
_SOFT_SMOOTHING = 1e-2
_MIN_POINTS = 4


def build_field_approximation(
    system: dict,
    calibration: TernaryCalibration,
    invariants: dict[str, dict],
    scale: LineScale | None = None,
) -> FieldApproximation:
    """Field regions, a smoothed thin-plate-spline surface per phase, its isotherms and the printed points.

    Regions: ``build_field_regions``.
    Control points of a phase: its isotherms every 0.5 wt%; its invariants and
    inversion points with a temperature; and every 1 wt% along its boundary curves
    and inversion curves, the temperature interpolated by arc length between the
    known temperatures on the curve (path invariants, inversion points and isotherm
    ends within 0.7 wt%). ``RBFInterpolator`` (thin-plate spline, degree 1) is fitted
    in page pixels / 1000 with smoothing 1e-4, 1e-2 for the interpolated boundary
    points; a phase with fewer than 4 control points has no surface. The surface is
    sampled every 3 px inside its region and the convex hull of its control points (no
    extrapolation into undrawn parts); ``isotherms`` are its levels at the field's
    isotherm temperatures. ``invariants`` maps invariant ids of every system file to
    their entries (curve paths may use binary edge points of other files).
    """
    s = scale or LineScale()
    components = list(system["components"])

    def page(wt) -> tuple[float, float]:
        values = [float(wt.get(c, 0.0)) for c in components] if isinstance(wt, dict) else [float(w) for w in wt]
        return calibration.to_page(values)

    corners = np.array([calibration.stored_to_page(*calibration.corners[c]) for c in components])
    boundaries = [(c, [page(w) for w in c["polyline_wt"]]) for c in system.get("boundaryCurves", []) if c.get("polyline_wt")]
    isotherms = [(i, [page(w) for w in i["polyline_wt"]]) for i in system.get("isotherms", []) if i.get("polyline_wt")]
    inversions = [(v, [page(w) for w in v["polyline_wt"]]) for v in system.get("inversions", []) if v.get("polyline_wt")]

    approx = build_field_regions(system, calibration, s)
    origin, labels, phases, log = approx.origin, approx.labels, approx.phases, approx.log

    def temperature(point_id: str) -> float | None:
        entry = invariants.get(point_id) or next((p for p in system.get("invariantPoints", []) if p["id"] == point_id), None)
        return None if entry is None or entry.get("temperature_C") is None else float(entry["temperature_C"])

    isotherm_ends = [(page_point, float(i["temperature_C"])) for i, pixels in isotherms
                     if i.get("temperature_C") is not None for page_point in (pixels[0], pixels[-1])]
    wt_per_px = 100.0 / float(np.linalg.norm(corners[1] - corners[0]))

    def curve_points(pixels, anchors) -> list[tuple[tuple[float, float], float, bool]]:
        """Known anchors (pixel, T) on the curve plus interpolated points between them (soft)."""
        points = np.asarray(pixels, float)
        length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
        known = []
        for pixel, t in anchors:
            at, distance = _project(points, length, pixel)
            if distance * wt_per_px <= _ON_CURVE_WT:
                known.append((at, t))
        known.sort()
        out = [((float(np.interp(a, length, points[:, 0])), float(np.interp(a, length, points[:, 1]))), t, False)
               for a, t in known]
        step = _BOUNDARY_STEP_WT / wt_per_px
        for (a0, t0), (a1, t1) in zip(known, known[1:]):
            n = int((a1 - a0) // step)
            for k in range(1, n):
                a = a0 + (a1 - a0) * k / n
                out.append(((float(np.interp(a, length, points[:, 0])), float(np.interp(a, length, points[:, 1]))),
                            t0 + (t1 - t0) * k / n, True))
        return out

    printed: list[TemperaturePoint] = []
    point_phases: list[list[str]] = []
    for point in system.get("invariantPoints", []):
        if point.get("temperature_C") is not None and point.get("liquid_wt"):
            printed.append(TemperaturePoint(point["id"], page(point["liquid_wt"]), float(point["temperature_C"])))
            point_phases.append(list(point.get("phases", [])))
    for inversion in system.get("inversions", []):
        for item in inversion.get("points", []):
            if item.get("temperature_C") is not None and item.get("liquid_wt"):
                printed.append(TemperaturePoint(f"{inversion['phase']} inversion", page(item["liquid_wt"]),
                                                float(item["temperature_C"])))
                point_phases.append([inversion["phase"]])

    for phase in phases:
        controls: list[tuple[tuple[float, float], float, bool]] = []
        for isotherm, pixels in isotherms:
            if isotherm["field"] == phase and isotherm.get("temperature_C") is not None:
                controls += [(p, float(isotherm["temperature_C"]), False)
                             for p in _densify(pixels, _ISOTHERM_STEP_WT / wt_per_px)]
        controls += [(p.pixel, p.temperature_C, False) for p, owners in zip(printed, point_phases) if phase in owners]
        for curve, pixels in boundaries:
            if phase in curve.get("fields", []):
                anchors = [(page(invariants[i]["liquid_wt"]) if invariants.get(i, {}).get("liquid_wt") else None, temperature(i))
                           for i in curve.get("path", [])]
                anchors = [(p, t) for p, t in anchors if p is not None and t is not None] + isotherm_ends
                controls += [c for c in curve_points(pixels, anchors) if c[2]]
        for inversion, pixels in inversions:
            if inversion.get("phase") == phase:
                anchors = [(page(i["liquid_wt"]), float(i["temperature_C"])) for i in inversion.get("points", [])
                           if i.get("temperature_C") is not None and i.get("liquid_wt")] + isotherm_ends
                controls += [c for c in curve_points(pixels, anchors) if c[2]]
        if len(controls) < _MIN_POINTS:
            log.append(f"{phase}: {len(controls)} control points; no surface")
            continue
        xy = np.array([c[0] for c in controls], float) / _COORD_PX
        values = np.array([c[1] for c in controls], float)
        smoothing = np.where([c[2] for c in controls], _SOFT_SMOOTHING, _SMOOTHING)
        xy, keep = np.unique(xy, axis=0, return_index=True)
        values, smoothing = values[keep], smoothing[keep]
        try:
            surface = RBFInterpolator(xy, values, kernel="thin_plate_spline", degree=1, smoothing=smoothing)
        except (ValueError, np.linalg.LinAlgError) as exc:
            log.append(f"{phase}: no surface ({exc})")
            continue
        hard = smoothing == _SMOOTHING
        residual = surface(xy[hard]) - values[hard] if hard.any() else np.zeros(1)
        approx.fits[phase] = (len(values), float(np.sqrt(np.mean(residual ** 2))), float(np.abs(residual).max()))

        mask = labels == phases.index(phase) + 1
        if not mask.any():
            continue
        rows, cols = np.nonzero(mask)
        r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
        step = s.count(_GRID_PX)
        ys = np.arange(r0, r1 + step, step)
        xs = np.arange(c0, c1 + step, step)
        gx, gy = np.meshgrid(xs, ys)
        near = ndimage.binary_dilation(mask, iterations=step)
        sample = near[np.clip(gy, 0, mask.shape[0] - 1), np.clip(gx, 0, mask.shape[1] - 1)]
        points = np.column_stack([gx.ravel() + origin[0], gy.ravel() + origin[1]]) / _COORD_PX
        try:
            sample &= (Delaunay(xy).find_simplex(points) >= 0).reshape(gx.shape)
        except QhullError:
            pass
        grid = np.full(gx.shape, np.nan)
        grid[sample] = surface(points[sample.ravel()])
        for t in sorted({float(i["temperature_C"]) for i, _ in isotherms
                         if i["field"] == phase and i.get("temperature_C") is not None}):
            segments = [seg for seg in contour_segments(grid, t, (c0 + origin[0], r0 + origin[1]), step)
                        if _inside(mask, ((seg[0] + seg[2]) / 2 - origin[0], (seg[1] + seg[3]) / 2 - origin[1]))]
            approx.isotherms.append((phase, t, segments))
        for point, owners in zip(printed, point_phases):
            if phase in owners:
                point.approx[phase] = float(surface(np.array([point.pixel]) / _COORD_PX)[0])
    for phase, (n, rms, worst) in approx.fits.items():
        log.append(f"{phase}: surface through {n} control points, residual RMS {rms:.1f} °C, max {worst:.1f} °C")
    approx.points = printed
    return approx


def _densify(pixels: list[tuple[float, float]], step: float) -> list[tuple[float, float]]:
    points = np.asarray(pixels, float)
    length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    n = max(1, int(math.ceil(length[-1] / step)))
    at = np.linspace(0.0, length[-1], n + 1)
    return [(float(x), float(y)) for x, y in zip(np.interp(at, length, points[:, 0]), np.interp(at, length, points[:, 1]))]


def _project(points: np.ndarray, length: np.ndarray, pixel: tuple[float, float]) -> tuple[float, float]:
    """Arc length of the nearest point of the polyline to ``pixel`` and the distance to it."""
    best = (0.0, math.inf)
    p = np.asarray(pixel, float)
    for k in range(len(points) - 1):
        a, b = points[k], points[k + 1]
        segment = b - a
        span = float(segment @ segment)
        t = 0.0 if span == 0 else float(np.clip((p - a) @ segment / span, 0.0, 1.0))
        distance = float(np.linalg.norm(p - (a + t * segment)))
        if distance < best[1]:
            best = (float(length[k] + t * math.sqrt(span)), distance)
    return best


def _inside(mask: np.ndarray, point: tuple[float, float]) -> bool:
    x, y = int(round(point[0])), int(round(point[1]))
    return 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and bool(mask[y, x])
