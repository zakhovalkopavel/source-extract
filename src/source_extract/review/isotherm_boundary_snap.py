"""Snap isotherm edge controls onto nearby field boundaries / frame corners."""

from __future__ import annotations

import math
from typing import Any, Sequence

from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt
from source_extract.review.retrace import (
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
)
from source_extract.review.session_common import _corners_origin

# Image-pixel radius (screen ≈ this × canvas scale). Shared with point coalesce.
IMAGE_POINT_TOL_PX = 4.0
ISOTHERM_BOUNDARY_SNAP_PX = IMAGE_POINT_TOL_PX * 4.5  # ~18 px — ends latch onto boundaries


def _project_onto_polyline(
    image_pixel: Sequence[float],
    polyline_img: Sequence[Sequence[float]],
) -> tuple[list[float], float] | None:
    """Closest point on ``polyline_img`` to ``image_pixel`` and distance in px."""
    if len(polyline_img) < 2:
        return None
    px, py = float(image_pixel[0]), float(image_pixel[1])
    best: tuple[list[float], float] | None = None
    for i in range(len(polyline_img) - 1):
        ax, ay = float(polyline_img[i][0]), float(polyline_img[i][1])
        bx, by = float(polyline_img[i + 1][0]), float(polyline_img[i + 1][1])
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy
        if len2 < 1e-12:
            qx, qy = ax, ay
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
            qx, qy = ax + t * dx, ay + t * dy
        d = math.hypot(px - qx, py - qy)
        if best is None or d < best[1]:
            best = ([qx, qy], d)
    return best


def snap_image_to_frame_corner(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    radius_px: float = ISOTHERM_BOUNDARY_SNAP_PX,
) -> list[float] | None:
    """If within ``radius_px`` of a calibration corner, return that corner pixel."""
    components, corners, origin = _corners_origin(session)
    if len(components) < 2:
        return None
    pure = [[100.0 if j == i else 0.0 for j in range(len(components))] for i in range(len(components))]
    corners_img = polyline_wt_to_image_pixels(
        pure, corners=corners, origin=origin, components=components
    )
    px, py = float(image_pixel[0]), float(image_pixel[1])
    best: tuple[list[float], float] | None = None
    for c in corners_img:
        if not c or len(c) < 2:
            continue
        d = math.hypot(px - float(c[0]), py - float(c[1]))
        if best is None or d < best[1]:
            best = ([float(c[0]), float(c[1])], d)
    if best is None or best[1] > radius_px:
        return None
    return [round(best[0][0], 2), round(best[0][1], 2)]


def snap_image_to_nearest_boundary(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    radius_px: float = ISOTHERM_BOUNDARY_SNAP_PX,
) -> list[float] | None:
    """If within ``radius_px`` of a boundary or frame corner, return the snap pixel.

    Frame corners win over boundary projections when both are in range (diagram vertices).
    """
    frame = snap_image_to_frame_corner(session, image_pixel, radius_px=radius_px)
    components, corners, origin = _corners_origin(session)
    best: tuple[list[float], float] | None = None
    for bc in session["draft"].get("boundaryCurves") or []:
        poly = bc.get("polyline_wt") or []
        if len(poly) < 2:
            continue
        pix = polyline_wt_to_image_pixels(
            poly, corners=corners, origin=origin, components=components
        )
        hit = _project_onto_polyline(image_pixel, pix)
        if hit is None:
            continue
        if best is None or hit[1] < best[1]:
            best = hit
    boundary = None
    if best is not None and best[1] <= radius_px:
        boundary = [round(best[0][0], 2), round(best[0][1], 2)]

    if frame is not None and boundary is not None:
        fd = math.hypot(float(image_pixel[0]) - frame[0], float(image_pixel[1]) - frame[1])
        bd = math.hypot(float(image_pixel[0]) - boundary[0], float(image_pixel[1]) - boundary[1])
        return frame if fd <= bd else boundary
    return frame if frame is not None else boundary


def snap_image_to_existing_landmark(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    radius_px: float = IMAGE_POINT_TOL_PX,
    exclude_contour: tuple[str, int] | None = None,
) -> list[float] | None:
    """Reuse an existing discrete point (invariant / node / control / frame) if close.

    Does **not** sample dense boundary polyline interiors — only sparse landmarks —
    so shared vertices can sit on several curves without inventing duplicates.
    """
    from source_extract.review.contour_point_helpers import _list_discrete_landmarks

    px, py = float(image_pixel[0]), float(image_pixel[1])
    r2 = radius_px * radius_px
    best: tuple[list[float], float] | None = None
    for loc in _list_discrete_landmarks(session):
        if exclude_contour is not None and loc.get("type") == "vertex":
            if (str(loc.get("kind")), int(loc.get("index", -1))) == exclude_contour:
                continue
        dx = float(loc["x"]) - px
        dy = float(loc["y"]) - py
        d2 = dx * dx + dy * dy
        if d2 > r2:
            continue
        if best is None or d2 < best[1]:
            best = ([float(loc["x"]), float(loc["y"])], d2)
    if best is None:
        return None
    return [round(best[0][0], 2), round(best[0][1], 2)]


def snap_isotherm_ends_to_boundaries(
    session: dict[str, Any],
    *,
    contour_index: int,
    radius_px: float = ISOTHERM_BOUNDARY_SNAP_PX,
) -> int:
    """Snap first/last control of an isotherm onto nearby boundaries/frame. Returns # snapped."""
    isos = session["draft"].get("isotherms") or []
    if contour_index < 0 or contour_index >= len(isos):
        return 0
    iso = isos[contour_index]
    controls = list(iso.get("control_wt") or [])
    if len(controls) < 2:
        poly = list(iso.get("polyline_wt") or [])
        if len(poly) < 2:
            return 0
        step = max(1, (len(poly) - 1) // 12)
        controls = [poly[j] for j in range(0, len(poly), step)]
        if controls[-1] != poly[-1]:
            controls.append(poly[-1])
    if len(controls) < 2:
        return 0

    components, corners, origin = _corners_origin(session)
    img = polyline_wt_to_image_pixels(
        controls, corners=corners, origin=origin, components=components
    )
    snapped = 0
    for end_i in (0, len(controls) - 1):
        # Prefer an existing landmark (shared vertex), else project onto boundary/frame.
        landmark = snap_image_to_existing_landmark(
            session,
            img[end_i],
            radius_px=IMAGE_POINT_TOL_PX,
            exclude_contour=("isotherm", contour_index),
        )
        proj = landmark or snap_image_to_nearest_boundary(
            session, img[end_i], radius_px=radius_px
        )
        if proj is None:
            continue
        page = image_to_page_pixel((proj[0], proj[1]), origin)  # type: ignore[arg-type]
        wt = page_pixel_to_wt(page, corners)
        controls[end_i] = [round(float(v), 2) for v in wt]
        snapped += 1
    if not snapped:
        return 0
    iso["control_wt"] = controls
    iso["polyline_wt"] = rebuild_smooth_from_control_wt(
        controls, corners=corners, origin=origin  # type: ignore[arg-type]
    )
    session["provenance"].setdefault("isotherms", {})[str(contour_index)] = "user"
    return snapped
