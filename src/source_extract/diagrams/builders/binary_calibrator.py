"""
source_extract.diagrams.builders.binary_calibrator — Frame + ticks → BinaryCalibration for a binary config.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.axis_calibration import AxisCalibration
from source_extract.diagrams.models.binary_calibration import BinaryCalibration
from source_extract.diagrams.models.calibration_result import CalibrationResult
from source_extract.diagrams.config.diagram_config import DiagramConfig
from source_extract.diagrams.detection.frame_detector import detect_frame
from source_extract.diagrams.models.review_item import ReviewItem
from source_extract.diagrams.detection.tick_detector import detect_ticks
from source_extract.diagrams.detection.tick_matcher import match_ticks

_TICK_RESIDUAL_LIMIT = 2.0


def calibrate_binary(mask: np.ndarray, config: DiagramConfig) -> CalibrationResult:
    """Detect frame and ticks, pair them with the config values and build the calibration.

    ``tickPixels`` entries override detection (``null`` = use the detected tick).
    Raises ValueError when a tick value stays unmatched.
    """
    frame = detect_frame(mask, config.frame_search_box)
    corners = frame.corners()
    candidates = detect_ticks(mask, frame)
    x_anchors = [(s.label_composition, s.seed_pixel[0]) for s in config.invariants if s.label_composition is not None]
    y_anchors = [(s.label_temperature, s.seed_pixel[1]) for s in config.invariants if s.label_temperature is not None]
    x_pixels, _ = match_ticks(
        candidates["bottom"], config.x_ticks, (corners["bottomLeft"][0], corners["bottomRight"][0]), x_anchors
    )
    y_pixels, _ = match_ticks(
        _merge_side_ticks(candidates, frame, corners), config.y_ticks,
        (corners["topLeft"][1], corners["bottomLeft"][1]), y_anchors,
    )
    x_pixels = _apply_override(x_pixels, config.x_tick_pixels)
    y_pixels = _apply_override(y_pixels, config.y_tick_pixels)
    missing = [f"x {v}" for v, p in zip(config.x_ticks, x_pixels) if p is None]
    missing += [f"y {v}" for v, p in zip(config.y_ticks, y_pixels) if p is None]
    if missing:
        raise ValueError(
            f"{config.name}: ticks not found for {', '.join(missing)}; "
            "remove the value from axes.*.ticks or give axes.*.tickPixels"
        )
    x_axis = AxisCalibration(list(config.x_ticks), list(x_pixels))
    y_axis = AxisCalibration(list(config.y_ticks), list(y_pixels))
    calibration = BinaryCalibration(
        x=x_axis,
        y=y_axis,
        bottom_slope=frame.bottom[1],
        left_slope=frame.left[1],
        ref_px=corners["bottomLeft"][0],
        ref_py=corners["bottomLeft"][1],
    )
    x_residuals = x_axis.residuals()
    y_residuals = y_axis.residuals()
    review: list[ReviewItem] = []
    for axis, values, residuals in (("x", config.x_ticks, x_residuals), ("y", config.y_ticks, y_residuals)):
        for value, residual in zip(sorted(values, key=lambda v: v if axis == "x" else -v), residuals):
            if abs(residual) > _TICK_RESIDUAL_LIMIT:
                review.append(ReviewItem("tick-residual", f"{axis} {value}", f"tick residual {residual:+.1f} px"))
    log = [
        f"frame ({corners['topLeft'][0]:.1f}, {corners['topLeft'][1]:.1f})–"
        f"({corners['bottomRight'][0]:.1f}, {corners['bottomRight'][1]:.1f}), rotation {calibration.rotation_text()}",
        f"x ticks {len(config.x_ticks)}/{len(config.x_ticks)} matched, max residual {max(abs(r) for r in x_residuals):.1f} px; "
        f"y ticks {len(config.y_ticks)}/{len(config.y_ticks)} matched, max residual {max(abs(r) for r in y_residuals):.1f} px",
    ]
    return CalibrationResult(
        frame=frame,
        calibration=calibration,
        x_tick_pixels=[float(p) for p in x_pixels],
        y_tick_pixels=[float(p) for p in y_pixels],
        x_residuals=x_residuals,
        y_residuals=y_residuals,
        tick_candidates=candidates,
        review=review,
        log=log,
    )


def _merge_side_ticks(candidates: dict[str, list[float]], frame, corners) -> list[float]:
    """Left-edge ticks plus right-edge ticks moved to the left edge along the frame rotation.

    A tick found on both edges is averaged; one hidden by a curve on the left
    edge is taken from the right edge.
    """
    run = corners["bottomRight"][0] - corners["bottomLeft"][0]
    shift = frame.bottom[1] * run
    left = list(candidates.get("left", []))
    right = [y - shift for y in candidates.get("right", [])]
    merged: list[float] = []
    used_right: set[int] = set()
    for y in left:
        partner = min(range(len(right)), key=lambda i: abs(right[i] - y), default=None)
        if partner is not None and abs(right[partner] - y) <= 2.5:
            merged.append((y + right[partner]) / 2.0)
            used_right.add(partner)
        else:
            merged.append(y)
    merged.extend(y for i, y in enumerate(right) if i not in used_right)
    return sorted(merged)


def _apply_override(pixels: list[float | None], override: list[float | None] | None) -> list[float | None]:
    if not override:
        return pixels
    return [o if o is not None else p for p, o in zip(pixels, override)]
