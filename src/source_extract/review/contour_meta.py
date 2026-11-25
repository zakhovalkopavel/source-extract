"""Boundary / isotherm metadata, arrows, and crossing cleanup."""

from __future__ import annotations

from typing import Any

from source_extract.review.retrace import (
    densify_from_image_waypoints,
    polyline_wt_to_image_pixels,
    polylines_cross,
    rebuild_smooth_from_control_wt,
    smooth_curve_from_image_waypoints,
)
from source_extract.review.session_common import ARROW_CYCLE, ContourKind, _corners_origin, _default_arrows
from source_extract.review.session_persist import _push_undo, save_session

def add_boundary(
    session: dict[str, Any],
    *,
    image_waypoints: list[list[float]],
    fields: list[str | None] | None = None,
    dashed: bool = False,
) -> dict[str, Any]:
    """Create a new field boundary from ≥2 image-pixel waypoints."""
    if len(image_waypoints) < 2:
        raise ValueError("Need at least 2 waypoints to seed a boundary")
    _push_undo(session)
    _, corners, origin = _corners_origin(session)
    poly = densify_from_image_waypoints(
        [(p[0], p[1]) for p in image_waypoints],
        corners=corners,
        origin=origin,  # type: ignore[arg-type]
    )
    field_pair: list[Any] = list(fields) if fields is not None else [None, None]
    while len(field_pair) < 2:
        field_pair.append(None)
    entry = {
        "fields": field_pair[:2],
        "path": [],
        "dashed": dashed,
        "arrows": ["?"],
        "polyline_wt": poly,
        "notes": "user-seeded boundary",
    }
    session["draft"].setdefault("boundaryCurves", []).append(entry)
    # Track phases mentioned
    for name in field_pair[:2]:
        if name and name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(name)
    idx = len(session["draft"]["boundaryCurves"]) - 1
    session["provenance"]["boundaries"][str(idx)] = "user"
    save_session(session)
    return session


def _reindex_provenance(prov: dict[str, Any], removed: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in prov.items():
        try:
            i = int(k)
        except ValueError:
            continue
        if i < removed:
            out[str(i)] = v
        elif i > removed:
            out[str(i - 1)] = v
    return out


def delete_boundary(session: dict[str, Any], *, contour_index: int) -> dict[str, Any]:
    _push_undo(session)
    curves = session["draft"]["boundaryCurves"]
    if contour_index < 0 or contour_index >= len(curves):
        raise IndexError(f"Boundary index {contour_index} out of range")
    del curves[contour_index]
    session["provenance"]["boundaries"] = _reindex_provenance(
        session["provenance"].get("boundaries", {}), contour_index
    )
    save_session(session)
    return session


def update_boundary(
    session: dict[str, Any],
    *,
    contour_index: int,
    fields: list[Any] | None = None,
    dashed: bool | None = None,
) -> dict[str, Any]:
    _push_undo(session)
    bc = session["draft"]["boundaryCurves"][contour_index]
    if fields is not None:
        pair = list(fields)
        while len(pair) < 2:
            pair.append(None)
        bc["fields"] = pair[:2]
        for name in pair[:2]:
            if name and name not in session["draft"].setdefault("phases", []):
                session["draft"]["phases"].append(name)
    if dashed is not None:
        bc["dashed"] = bool(dashed)
    session["provenance"]["boundaries"][str(contour_index)] = "user"
    save_session(session)
    return session


def delete_isotherm(session: dict[str, Any], *, contour_index: int) -> dict[str, Any]:
    _push_undo(session)
    isotherms = session["draft"]["isotherms"]
    if contour_index < 0 or contour_index >= len(isotherms):
        raise IndexError(f"Isotherm index {contour_index} out of range")
    del isotherms[contour_index]
    session["provenance"]["isotherms"] = _reindex_provenance(
        session["provenance"].get("isotherms", {}), contour_index
    )
    save_session(session)
    return session


def _isotherm_temps_equal(a: dict[str, Any], b: dict[str, Any], *, tol_C: float = 0.5) -> bool:
    """True when both isotherms have finite temperatures that match (same °C band)."""
    try:
        ta = a.get("temperature_C")
        tb = b.get("temperature_C")
        if ta is None or tb is None or ta == "" or tb == "":
            return False
        fa, fb = float(ta), float(tb)
        if not (fa == fa and fb == fb):  # NaN
            return False
        return abs(fa - fb) <= tol_C
    except (TypeError, ValueError):
        return False


def _remove_isotherms_crossing(
    session: dict[str, Any],
    *,
    contour_index: int,
) -> tuple[int, list[int]]:
    """Delete other isotherms that properly cross ``contour_index``.

    Crossing curves with the **same temperature** are allowed and kept.
    Different (or missing) °C still conflict — those crossed curves are removed.
    Returns ``(new_index_of_kept_curve, removed_old_indexes)``.
    """
    isos = session["draft"]["isotherms"]
    if contour_index < 0 or contour_index >= len(isos):
        raise IndexError(f"Isotherm index {contour_index} out of range")
    components, corners, origin = _corners_origin(session)
    kept = isos[contour_index]
    poly = kept.get("polyline_wt") or kept.get("control_wt") or []
    if len(poly) < 2:
        return contour_index, []
    img = polyline_wt_to_image_pixels(poly, corners=corners, origin=origin, components=components)
    remove: list[int] = []
    for i, iso in enumerate(isos):
        if i == contour_index:
            continue
        if _isotherm_temps_equal(kept, iso):
            continue
        other = iso.get("polyline_wt") or []
        if len(other) < 2:
            continue
        other_img = polyline_wt_to_image_pixels(
            other, corners=corners, origin=origin, components=components
        )
        if polylines_cross(img, other_img):
            remove.append(i)
    new_index = contour_index
    for i in sorted(remove, reverse=True):
        del isos[i]
        session["provenance"]["isotherms"].pop(str(i), None)
        _rekey_provenance(session["provenance"]["isotherms"], removed=i)
        if i < new_index:
            new_index -= 1
    return new_index, remove


def update_isotherm(
    session: dict[str, Any],
    *,
    contour_index: int,
    field: str | None = None,
    temperature_C: float | None = None,
    dashed: bool | None = None,
) -> dict[str, Any]:
    _push_undo(session)
    iso = session["draft"]["isotherms"][contour_index]
    if field is not None:
        name = field.strip()
        iso["field"] = name
        if name and name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(name)
    if temperature_C is not None:
        iso["temperature_C"] = float(temperature_C)
    if dashed is not None:
        iso["dashed"] = bool(dashed)
    # Accepting an isotherm: remove crossed curves with a *different* °C
    new_index, removed = _remove_isotherms_crossing(session, contour_index=contour_index)
    session["provenance"]["isotherms"][str(new_index)] = "user"
    # Same °C pieces that meet/cross → one curve or closed circuit
    from source_extract.review.isotherm_join import join_same_temperature_isotherms

    join_summary = join_same_temperature_isotherms(session, anchor_index=new_index)
    if join_summary.get("joined"):
        new_index = int(join_summary["index"])
    session["provenance"]["isotherms"][str(new_index)] = "user"
    session["_lastIsothermBuild"] = {
        "index": new_index,
        "removedCrossed": sorted(removed),
        "removedCount": len(removed),
    }
    # Manual °C → nudge closest neighbours on each side when the gradient is clear
    if temperature_C is not None:
        from source_extract.review.temperature_propagate import propagate_from_manual_temperature

        propagate_from_manual_temperature(session, anchor_index=new_index)
    save_session(session)
    return session


def set_arrows(
    session: dict[str, Any],
    *,
    contour_index: int,
    arrows: list[str],
) -> dict[str, Any]:
    for a in arrows:
        if a not in ARROW_CYCLE:
            raise ValueError(f"Invalid arrow '{a}'")
    _push_undo(session)
    session["draft"]["boundaryCurves"][contour_index]["arrows"] = list(arrows)
    session["provenance"]["boundaries"][str(contour_index)] = "user"
    save_session(session)
    return session


def cycle_arrow(
    session: dict[str, Any],
    *,
    contour_index: int,
    segment_index: int,
) -> dict[str, Any]:
    bc = session["draft"]["boundaryCurves"][contour_index]
    arrows = list(bc.get("arrows") or [])
    while len(arrows) <= segment_index:
        arrows.append("?")
    cur = arrows[segment_index]
    nxt = ARROW_CYCLE[(ARROW_CYCLE.index(cur) + 1) % len(ARROW_CYCLE)] if cur in ARROW_CYCLE else ">"
    arrows[segment_index] = nxt
    return set_arrows(session, contour_index=contour_index, arrows=arrows)

