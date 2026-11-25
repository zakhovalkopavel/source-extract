"""Critical geometry helpers ported from diagram-review."""

from __future__ import annotations

from source_extract.review.barycentric import (
    corners_from_calibration,
    page_pixel_to_wt,
    wt_to_page_pixel,
)
from source_extract.review.retrace import (
    densify_polyline_wt,
    heal_control_wt_order,
    order_image_waypoints_nearest,
    polylines_cross,
    smooth_image_polyline,
)


def test_wt_roundtrip_near_corner() -> None:
    corners = [(0.0, 0.0), (100.0, 0.0), (50.0, 86.6)]
    page = wt_to_page_pixel([100, 0, 0], corners)
    wt = page_pixel_to_wt(page, corners)
    assert wt[0] > 99


def test_corners_from_calibration_order() -> None:
    cal = {"A": [1, 2], "B": [3, 4], "C": [5, 6]}
    assert corners_from_calibration(["A", "B", "C"], cal) == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_densify_inserts_points() -> None:
    poly = densify_polyline_wt([[100, 0, 0], [0, 100, 0]], max_segment_wt=20)
    assert len(poly) > 2
    assert abs(sum(poly[0]) - 100) < 1e-6


def test_order_waypoints_nearest_ignores_click_order() -> None:
    ordered = order_image_waypoints_nearest([(50, 0), (100, 0), (0, 0)])
    xs = [p[0] for p in ordered]
    assert xs == sorted(xs) or xs == sorted(xs, reverse=True)


def test_heal_control_wt_order_fixes_scrambled_path() -> None:
    corners = [(0.0, 1000.0), (1000.0, 1000.0), (500.0, 100.0)]
    origin = (0.0, 0.0)
    img = [(400, 200), (420, 400), (440, 600), (450, 800)]
    good = [list(page_pixel_to_wt((x, y), corners)) for x, y in img]
    bad = [good[0], good[3], good[1], good[2]]
    healed = heal_control_wt_order(bad, corners=corners, origin=origin)
    assert healed is not None
    ys = [wt_to_page_pixel(w, corners)[1] for w in healed]
    assert ys == sorted(ys) or ys == sorted(ys, reverse=True)


def test_polylines_cross_detects_x_and_ignores_shared_end() -> None:
    assert polylines_cross([(0, 0), (10, 10)], [(0, 10), (10, 0)])
    assert not polylines_cross([(0, 0), (10, 0)], [(10, 0), (20, 0)])


def test_smooth_polyline_passes_controls() -> None:
    controls = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (20.0, 10.0)]
    dense = smooth_image_polyline(controls, samples_per_segment=24)
    assert len(dense) > len(controls)
    for cx, cy in controls:
        assert any(abs(px - cx) < 1e-6 and abs(py - cy) < 1e-6 for px, py in dense)
