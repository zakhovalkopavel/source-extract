"""Move ternary calibration triangle corners (page-space digitization)."""

from __future__ import annotations

from typing import Any

from source_extract.review.barycentric import image_to_page_pixel
from source_extract.review.binary_axes import is_binary_draft
from source_extract.review.nodes_attach import _ensure_page_calibration
from source_extract.review.session_common import _corners_origin
from source_extract.review.session_persist import _push_undo, save_session


def move_calibration_corner(
    session: dict[str, Any],
    *,
    component_index: int,
    image_pixel: list[float],
) -> dict[str, Any]:
    """Relocate one triangle vertex.

    Composition (wt%) is unchanged, so the next ``_build_view`` reprojects every
    curve / field / marker into the updated triangle (affine map of the old
    image-space overlay). Live drag preview applies the same map client-side.
    """
    draft = session["draft"]
    if is_binary_draft(draft):
        raise ValueError("Binary drafts have no ternary calibration triangle")
    components, _corners, origin = _corners_origin(session)
    if component_index < 0 or component_index >= len(components):
        raise IndexError(f"Corner index {component_index} out of range (0..{len(components) - 1})")
    name = components[component_index]

    stored_origin = session.get("pixelOrigin") or draft.get("digitization", {}).get(
        "storedPixelOrigin"
    ) or [0, 0]
    _ensure_page_calibration(draft, (float(stored_origin[0]), float(stored_origin[1])))

    _push_undo(session)
    page = image_to_page_pixel((float(image_pixel[0]), float(image_pixel[1])), origin)  # type: ignore[arg-type]
    dig = draft.setdefault("digitization", {})
    cal = dig.setdefault("calibration", {})
    if not isinstance(cal, dict):
        raise ValueError("digitization.calibration must be a component→pixel map")
    cal[name] = [round(float(page[0]), 2), round(float(page[1]), 2)]
    dig["calibration"] = cal
    dig["calibrationSpace"] = "page"
    session["_lastCalibrationMove"] = {
        "component": name,
        "componentIndex": component_index,
        "pagePixel": cal[name],
    }
    save_session(session)
    return session
