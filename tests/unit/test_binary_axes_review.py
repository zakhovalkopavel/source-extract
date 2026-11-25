"""Binary T–x axes parsing (review port)."""

from __future__ import annotations

from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft


def test_parse_calibration_prose() -> None:
    draft = {
        "components": ["MgO", "SiO2"],
        "liquidus": [{"points": [[0, 2822]]}],
        "digitization": {
            "calibration": (
                "x: mass% SiO2 ticks 0→1426, 10→1574.5, 20→1724.5, 100→2921 (piecewise linear); "
                "y: ticks °C 3000→2173.5, 2800→2286, 1000→3296; "
                "scan rotation: frame bottom +1.4 px over 1495 px, left frame dx/dy = +0.0005"
            )
        },
    }
    assert is_binary_draft(draft)
    axes = axes_from_digitization(draft)
    assert axes is not None
    assert axes.x_component == "SiO2"
    px, py = axes.to_pixel(0.0, 3000.0)
    assert abs(px - 1426) < 2
    assert abs(py - 2173.5) < 2
