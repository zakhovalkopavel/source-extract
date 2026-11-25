"""Build selectable field polygons for the review canvas (image space).

Matches ``diagrams.builders.field_regions_builder``: the triangle is divided only by
boundary curves; a region is filled only when an isotherm midpoint or a clear
boundary-side vote names its phase. Incomplete dividers leave holes — they do
**not** invent nested “fault” fields the way watershed seeding did.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

_BARRIER_PX = 3
_ADJACENT_PX = 9
_CONTACT_SHARE = 0.8
_MIN_REGION_PX2 = 400
_APPROX_EPS_FRAC = 0.004


def build_field_view_regions(
    *,
    corners_image: list[list[float]],
    boundaries: list[dict[str, Any]],
    isotherms: list[dict[str, Any]],
    phase_names: list[str],
) -> list[dict[str, Any]]:
    """Return ``[{name, colorIndex, polygons, centroid}]`` in image pixels."""
    if len(corners_image) < 3:
        return []
    corners = np.asarray(
        [[float(p[0]), float(p[1])] for p in corners_image if p and len(p) >= 2], float
    )
    if corners.shape[0] < 3:
        return []

    x0, y0 = (np.floor(corners.min(axis=0)) - 2).astype(int)
    x1, y1 = (np.ceil(corners.max(axis=0)) + 2).astype(int)
    width, height = int(max(1, x1 - x0)), int(max(1, y1 - y0))
    origin = (int(x0), int(y0))
    size = (width, height)

    def local(p: list[float] | tuple[float, float] | np.ndarray) -> tuple[float, float]:
        return float(p[0]) - origin[0], float(p[1]) - origin[1]

    boundary_curves: list[tuple[dict[str, Any], list[list[float]]]] = []
    for b in boundaries:
        pix = [p for p in (b.get("pixels") or []) if p and len(p) >= 2]
        if len(pix) >= 2:
            boundary_curves.append((b, pix))

    isotherm_curves: list[tuple[dict[str, Any], list[list[float]]]] = []
    for iso in isotherms:
        pix = [p for p in (iso.get("pixels") or []) if p and len(p) >= 2]
        if len(pix) >= 2 and iso.get("field"):
            isotherm_curves.append((iso, pix))

    inside = Image.new("1", size, 0)
    ImageDraw.Draw(inside).polygon([local(c) for c in corners], fill=1)
    barrier = Image.new("1", size, 0)
    draw = ImageDraw.Draw(barrier)
    draw.line(
        [*(local(c) for c in corners), local(corners[0])],
        fill=1,
        width=_BARRIER_PX,
    )
    for _, pixels in boundary_curves:
        draw.line([local(p) for p in pixels], fill=1, width=_BARRIER_PX)

    free = np.array(inside, bool) & ~np.array(barrier, bool)
    regions, count = ndimage.label(free)
    if count <= 0:
        return _empty_phase_list(phase_names)

    areas = ndimage.sum(np.ones_like(regions), regions, index=np.arange(1, count + 1))
    kept = [r for r in range(1, count + 1) if areas[r - 1] >= _MIN_REGION_PX2]

    contact: dict[int, dict[str, float]] = {r: {} for r in kept}
    total: dict[int, float] = {r: 0.0 for r in kept}
    for curve, pixels in boundary_curves:
        band = Image.new("1", size, 0)
        ImageDraw.Draw(band).line([local(p) for p in pixels], fill=1, width=_ADJACENT_PX)
        touched = regions[np.array(band, bool)]
        for region, pixels_in in zip(*np.unique(touched[touched > 0], return_counts=True)):
            rid = int(region)
            if rid not in contact:
                continue
            total[rid] += float(pixels_in)
            for phase in {f for f in (curve.get("fields") or []) if f and not _looks_like_temperature(f)}:
                contact[rid][str(phase)] = contact[rid].get(str(phase), 0.0) + float(pixels_in)

    assigned: dict[int, str] = {}
    for isotherm, pixels in isotherm_curves:
        field = str(isotherm.get("field") or "")
        if not field or _looks_like_temperature(field):
            continue
        x, y = (int(round(v)) for v in local(_middle(pixels)))
        if 0 <= y < height and 0 <= x < width and int(regions[y, x]) in contact:
            assigned.setdefault(int(regions[y, x]), field)

    for region in kept:
        if region in assigned:
            continue
        ranked = sorted(contact[region].items(), key=lambda item: -item[1])
        if (
            ranked
            and ranked[0][1] >= _CONTACT_SHARE * total[region]
            and (len(ranked) == 1 or ranked[1][1] < ranked[0][1])
        ):
            assigned[region] = ranked[0][0]
        # else: leave unassigned — incomplete dividers must not invent a fill

    phases = [
        p
        for p in dict.fromkeys(x for x in phase_names if x)
        if not _looks_like_temperature(p)
    ]
    for phase in assigned.values():
        if phase not in phases:
            phases.append(phase)

    by_phase: dict[str, list[list[list[float]]]] = {p: [] for p in phases}
    centroids: dict[str, list[float]] = {}

    for phase in phases:
        mask = np.zeros((height, width), np.uint8)
        for region, name in assigned.items():
            if name == phase:
                mask[regions == region] = 255
        if int(mask.sum()) // 255 < _MIN_REGION_PX2:
            continue
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys: list[list[list[float]]] = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < _MIN_REGION_PX2:
                continue
            peri = float(cv2.arcLength(cnt, True))
            eps = max(1.5, peri * _APPROX_EPS_FRAC)
            approx = cv2.approxPolyDP(cnt, eps, True)
            if len(approx) < 3:
                continue
            polys.append(
                [
                    [
                        round(float(pt[0][0]) + origin[0], 1),
                        round(float(pt[0][1]) + origin[1], 1),
                    ]
                    for pt in approx
                ]
            )
        if not polys:
            continue
        polys.sort(key=lambda ring: abs(_ring_area(ring)), reverse=True)
        by_phase[phase] = polys
        ys, xs = np.nonzero(mask)
        centroids[phase] = [
            round(float(xs.mean()) + origin[0], 1),
            round(float(ys.mean()) + origin[1], 1),
        ]

    return [
        {
            "name": phase,
            "colorIndex": i,
            "polygons": by_phase.get(phase) or [],
            "centroid": centroids.get(phase),
        }
        for i, phase in enumerate(phases)
    ]


def _empty_phase_list(phase_names: list[str]) -> list[dict[str, Any]]:
    phases = [
        p
        for p in dict.fromkeys(x for x in phase_names if x)
        if not _looks_like_temperature(p)
    ]
    return [
        {"name": p, "colorIndex": i, "polygons": [], "centroid": None}
        for i, p in enumerate(phases)
    ]


def _looks_like_temperature(name: str) -> bool:
    text = str(name).strip().rstrip("°C").strip()
    if not text:
        return False
    try:
        value = float(text)
    except ValueError:
        return False
    return 200.0 <= value <= 4000.0


def _ring_area(ring: list[list[float]]) -> float:
    if len(ring) < 3:
        return 0.0
    area = 0.0
    for i, (x0, y0) in enumerate(ring):
        x1, y1 = ring[(i + 1) % len(ring)]
        area += float(x0) * float(y1) - float(x1) * float(y0)
    return 0.5 * area


def _middle(pixels: list[list[float]]) -> tuple[float, float]:
    points = np.asarray(pixels, float)
    length = np.concatenate(
        [[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    )
    if length[-1] <= 0:
        return float(points[0, 0]), float(points[0, 1])
    return (
        float(np.interp(length[-1] / 2, length, points[:, 0])),
        float(np.interp(length[-1] / 2, length, points[:, 1])),
    )
