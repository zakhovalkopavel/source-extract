"""Seed / retrace / remap contours."""

from __future__ import annotations

from typing import Any

from source_extract.review.retrace import (
    densify_from_image_waypoints,
    polyline_wt_to_image_pixels,
    polylines_cross,
    rebuild_smooth_from_control_wt,
    smooth_curve_from_image_waypoints,
)
from source_extract.review.session_common import ContourKind, _corners_origin
from source_extract.review.session_persist import _push_undo, save_session
from source_extract.review.contour_meta import _isotherm_temps_equal, _reindex_provenance
from source_extract.review.contour_point_helpers import _rekey_provenance

def retrace_contour(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    contour_index: int,
    image_waypoints: list[list[float]],
) -> dict[str, Any]:
    """Rebuild densified polyline from ≥2 image-pixel waypoints."""
    if len(image_waypoints) < 2:
        raise ValueError("Need at least 2 waypoints")
    _push_undo(session)
    _, corners, origin = _corners_origin(session)
    if contour_kind == "boundary":
        poly = densify_from_image_waypoints(
            [(p[0], p[1]) for p in image_waypoints],
            corners=corners,
            origin=origin,  # type: ignore[arg-type]
        )
        session["draft"]["boundaryCurves"][contour_index]["polyline_wt"] = poly
        session["provenance"]["boundaries"][str(contour_index)] = "user"
    else:
        control_wt, poly = smooth_curve_from_image_waypoints(
            [(p[0], p[1]) for p in image_waypoints],
            corners=corners,
            origin=origin,  # type: ignore[arg-type]
            samples_per_segment=24,
        )
        iso = session["draft"]["isotherms"][contour_index]
        iso["control_wt"] = control_wt
        iso["polyline_wt"] = poly
        session["provenance"]["isotherms"][str(contour_index)] = "user"
    save_session(session)
    return session


def add_isotherm(
    session: dict[str, Any],
    *,
    field: str,
    temperature_C: float,
    image_waypoints: list[list[float]],
    dashed: bool = False,
    replace_index: int | None = None,
) -> dict[str, Any]:
    """Seed a new isotherm, or replace an existing one in-place when ``replace_index`` is set.

    Any existing isotherm whose polyline properly crosses the new curve is removed
    (shared endpoints alone do not count). ``replace_index`` is always removed/replaced.
    """
    if len(image_waypoints) < 2:
        raise ValueError("Need at least 2 waypoints to seed an isotherm")
    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    control_wt, poly = smooth_curve_from_image_waypoints(
        [(p[0], p[1]) for p in image_waypoints],
        corners=corners,
        origin=origin,  # type: ignore[arg-type]
        samples_per_segment=24,
    )
    entry = {
        "field": field,
        "temperature_C": temperature_C,
        "dashed": dashed,
        "control_wt": control_wt,
        "polyline_wt": poly,
        "notes": "user-seeded isotherm",
    }
    isos = session["draft"].setdefault("isotherms", [])
    new_img = polyline_wt_to_image_pixels(poly, corners=corners, origin=origin, components=components)

    remove: set[int] = set()
    if replace_index is not None:
        if replace_index < 0 or replace_index >= len(isos):
            raise IndexError(f"Isotherm index {replace_index} out of range")
        old = isos[replace_index] or {}
        if not entry["field"]:
            entry["field"] = old.get("field")
        if entry["temperature_C"] is None and old.get("temperature_C") is not None:
            entry["temperature_C"] = old.get("temperature_C")
        if not dashed and old.get("dashed"):
            entry["dashed"] = bool(old.get("dashed"))
        entry["notes"] = "user-replaced isotherm"
        remove.add(replace_index)

    for i, iso in enumerate(isos):
        if i in remove:
            continue
        # Same °C may cross (branched / multi-piece isotherm); different °C may not
        if _isotherm_temps_equal(entry, iso):
            continue
        other = iso.get("polyline_wt") or []
        if len(other) < 2:
            continue
        other_img = polyline_wt_to_image_pixels(
            other, corners=corners, origin=origin, components=components
        )
        if polylines_cross(new_img, other_img):
            remove.add(i)

    # Drop crossed / replaced isotherms (high → low), then append the new curve
    for i in sorted(remove, reverse=True):
        del isos[i]
        session["provenance"]["isotherms"].pop(str(i), None)
        _rekey_provenance(session["provenance"]["isotherms"], removed=i)

    isos.append(entry)
    idx = len(isos) - 1
    from source_extract.review.temperature_labels import assign_isotherm_temps_from_labels

    # Fill °C from printed labels the new curve passes through when still unset
    assign_isotherm_temps_from_labels(session, only_missing=True, respect_user=False)
    # Same °C neighbours that meet/cross → merge into this curve / circuit
    from source_extract.review.isotherm_join import join_same_temperature_isotherms

    join_summary = join_same_temperature_isotherms(session, anchor_index=idx)
    if join_summary.get("joined"):
        idx = int(join_summary["index"])
    session["provenance"]["isotherms"][str(idx)] = "user"
    save_session(session)
    # Ephemeral (not persisted) — UI status only
    session["_lastIsothermBuild"] = {
        "index": idx,
        "removedCrossed": sorted(remove),
        "removedCount": len(remove),
    }
    return session


def remap_contour(
    session: dict[str, Any],
    *,
    from_kind: ContourKind,
    contour_index: int,
    to_kind: ContourKind,
    field: str | None = None,
    temperature_C: float | None = None,
    fields: list[Any] | None = None,
    dashed: bool | None = None,
) -> dict[str, Any]:
    """Reclassify a curve: boundary → isotherm or isotherm → boundary."""
    if from_kind == to_kind:
        raise ValueError(f"Curve is already a {to_kind}")
    if from_kind not in ("boundary", "isotherm") or to_kind not in ("boundary", "isotherm"):
        raise ValueError("Remap only supports boundary ↔ isotherm")
    _push_undo(session)
    components, corners, origin = _corners_origin(session)

    if from_kind == "boundary" and to_kind == "isotherm":
        bcs = session["draft"]["boundaryCurves"]
        if contour_index < 0 or contour_index >= len(bcs):
            raise IndexError(f"Boundary index {contour_index} out of range")
        bc = bcs[contour_index]
        poly = list(bc.get("polyline_wt") or bc.get("control_wt") or [])
        if len(poly) < 2:
            raise ValueError("Boundary has no geometry to remap")
        # Sparse controls from dense polyline, then smooth rebuild
        step = max(1, (len(poly) - 1) // 12)
        controls = [poly[j] for j in range(0, len(poly), step)]
        if controls[-1] != poly[-1]:
            controls.append(poly[-1])
        smooth = rebuild_smooth_from_control_wt(controls, corners=corners, origin=origin)  # type: ignore[arg-type]
        field_name = (field or "").strip() or None
        if not field_name:
            pair = bc.get("fields") or []
            field_name = next((f for f in pair if f), None)
        entry = {
            "field": field_name,
            "temperature_C": float(temperature_C) if temperature_C is not None else None,
            "dashed": bool(dashed if dashed is not None else bc.get("dashed")),
            "control_wt": controls,
            "polyline_wt": smooth,
            "notes": "remapped from boundary",
        }
        del bcs[contour_index]
        session["provenance"]["boundaries"] = _reindex_provenance(
            session["provenance"].get("boundaries", {}), contour_index
        )
        session["draft"].setdefault("isotherms", []).append(entry)
        new_i = len(session["draft"]["isotherms"]) - 1
        session["provenance"].setdefault("isotherms", {})[str(new_i)] = "user"
        if field_name and field_name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(field_name)
        from source_extract.review.temperature_labels import assign_isotherm_temps_from_labels

        assign_isotherm_temps_from_labels(session, only_missing=True, respect_user=False)
        # Removing crossed isotherms would delete the new one if it crosses — only on Save
        session["_lastRemap"] = {"from": "boundary", "to": "isotherm", "index": new_i}
        save_session(session)
        return session

    # isotherm → boundary
    isos = session["draft"]["isotherms"]
    if contour_index < 0 or contour_index >= len(isos):
        raise IndexError(f"Isotherm index {contour_index} out of range")
    iso = isos[contour_index]
    poly = list(iso.get("polyline_wt") or iso.get("control_wt") or [])
    if len(poly) < 2:
        raise ValueError("Isotherm has no geometry to remap")
    pair: list[Any]
    if fields is not None:
        pair = list(fields)[:2]
    else:
        fname = (field or iso.get("field") or "").strip() or None
        pair = [fname, None]
    while len(pair) < 2:
        pair.append(None)
    entry = {
        "fields": pair[:2],
        "path": [],
        "dashed": bool(dashed if dashed is not None else iso.get("dashed")),
        "arrows": ["?"],
        "polyline_wt": poly,
        "notes": "remapped from isotherm",
    }
    del isos[contour_index]
    session["provenance"]["isotherms"] = _reindex_provenance(
        session["provenance"].get("isotherms", {}), contour_index
    )
    session["draft"].setdefault("boundaryCurves", []).append(entry)
    new_i = len(session["draft"]["boundaryCurves"]) - 1
    session["provenance"].setdefault("boundaries", {})[str(new_i)] = "user"
    for name in pair[:2]:
        if name and name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(name)
    session["_lastRemap"] = {"from": "isotherm", "to": "boundary", "index": new_i}
    save_session(session)
    return session

