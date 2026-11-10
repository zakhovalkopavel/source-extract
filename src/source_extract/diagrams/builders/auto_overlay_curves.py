"""
source_extract.diagrams.builders.auto_overlay_curves — Curves of the automatic overlay: traced boundaries and the detected isotherm pieces.
"""
from __future__ import annotations

from source_extract.diagrams.models.isotherm_detection import IsothermDetection
from source_extract.diagrams.models.ternary_calibration import TernaryCalibration
from source_extract.diagrams.models.traced_curve import TracedCurve


def auto_overlay_curves(system: dict, detection: IsothermDetection, calibration: TernaryCalibration) -> list[TracedCurve]:
    """``render_ternary_overlay`` curves (page pixels): each boundary curve of ``system`` with a
    ``polyline_wt`` (kind ``boundary``, no arrow: arrows are read by hand) and each detected piece,
    kind ``isotherm`` with its temperature (``inferred`` unless read on the line or continued from
    a reading) or ``isotherm-open`` without one."""
    components = list(system["components"])

    def page(wt) -> tuple[float, float]:
        return calibration.to_page([float(wt.get(c, 0.0)) for c in components] if isinstance(wt, dict) else wt)

    curves = [TracedCurve(pixels=[page(w) for w in curve["polyline_wt"]], kind="boundary",
                          label="/".join(f or "?" for f in curve.get("fields", [])))
              for curve in system.get("boundaryCurves", []) if curve.get("polyline_wt")]
    for piece in detection.isotherms:
        known = piece.temperature_C is not None
        curves.append(TracedCurve(pixels=list(piece.pixels), kind="isotherm" if known else "isotherm-open",
                                  label=piece.field, temperature_C=piece.temperature_C,
                                  inferred=known and piece.source not in ("label", "continuation")))
    return curves
