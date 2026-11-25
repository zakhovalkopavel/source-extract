"""Shared session helpers (types, clocks, corners)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from source_extract.review.barycentric import corners_from_calibration, normalize_wt
from source_extract.review.binary_axes import is_binary_draft

ARROW_CYCLE = (">", "<", "<>", "?")
ContourKind = Literal["boundary", "isotherm"]


def _as_wt_list(poly: list, components: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for p in poly or []:
        a, b, c = normalize_wt(p, components)
        out.append([a, b, c])
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_arrows(path: list[str]) -> list[str]:
    n_seg = max(0, len(path) - 1)
    return ["?"] * n_seg


def _corners_origin(session: dict[str, Any]):
    draft = session["draft"]
    components = draft["components"]
    calibration = draft["digitization"]["calibration"]
    corners = corners_from_calibration(components, calibration)
    origin = tuple(session["image"]["pageOrigin"])
    return components, corners, origin

