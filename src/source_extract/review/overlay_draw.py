"""Render color-coded review / confirmed overlays with Pillow."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from source_extract.review.barycentric import corners_from_calibration
from source_extract.review.retrace import polyline_wt_to_image_pixels


# Match SPA: dark green boundaries (thicker); cyan isotherms; red = missing °C; no other greens
BOUNDARY_COLOR = (13, 92, 46, 235)
ISOTHERM_COLOR = (0, 229, 255, 200)
ISOTHERM_MISSING_TEMP_COLOR = (225, 6, 0, 230)
POINT_COLOR = (255, 200, 0, 255)
ARROW_COLOR = (15, 107, 54, 255)
CORNER_COLOR = (76, 201, 240, 255)


def _draw_arrowhead(draw: ImageDraw.ImageDraw, x0: float, y0: float, x1: float, y1: float, color, size: float = 10.0):
    ang = math.atan2(y1 - y0, x1 - x0)
    left = (x1 - size * math.cos(ang - 0.4), y1 - size * math.sin(ang - 0.4))
    right = (x1 - size * math.cos(ang + 0.4), y1 - size * math.sin(ang + 0.4))
    draw.polygon([(x1, y1), left, right], fill=color)


def _segment_mid(pixels: list[list[float]], seg_i: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return (start, end) direction sample for arrow segment i along a dense polyline."""
    n = len(pixels)
    if n < 2:
        return ((0.0, 0.0), (0.0, 0.0))
    # Map logical path segments onto polyline thirds if more arrows than edges
    t0 = seg_i / max(1, seg_i + 1)
    # Use evenly spaced windows along the polyline
    return (
        (pixels[max(0, n // 2 - 5)][0], pixels[max(0, n // 2 - 5)][1]),
        (pixels[min(n - 1, n // 2 + 5)][0], pixels[min(n - 1, n // 2 + 5)][1]),
    )


def _arrow_placement(pixels: list[list[float]], n_arrows: int) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if n_arrows <= 0 or len(pixels) < 2:
        return []
    n = len(pixels)
    out = []
    for i in range(n_arrows):
        # place along polyline
        c = (i + 0.5) / n_arrows
        mid = int(c * (n - 1))
        a = max(0, mid - 4)
        b = min(n - 1, mid + 4)
        if a == b:
            b = min(n - 1, a + 1)
        out.append(((pixels[a][0], pixels[a][1]), (pixels[b][0], pixels[b][1])))
    return out


def render_overlay_image(session: dict[str, Any], *, show_points=True, show_curves=True, show_arrows=True) -> Image.Image:
    src = Path(session["image"]["path"])
    base = Image.open(src).convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    draft = session["draft"]
    from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft

    if is_binary_draft(draft):
        _render_binary_overlay(draw, session, show_points=show_points, show_curves=show_curves)
    else:
        components = draft["components"]
        corners = corners_from_calibration(components, draft["digitization"]["calibration"])
        origin = tuple(session["image"]["pageOrigin"])

        if show_curves:
            for bc in draft.get("boundaryCurves", []):
                pixels = polyline_wt_to_image_pixels(
                    bc.get("polyline_wt") or [], corners=corners, origin=origin, components=components
                )  # type: ignore[arg-type]
                if len(pixels) >= 2:
                    draw.line([tuple(p) for p in pixels], fill=BOUNDARY_COLOR, width=5)
                arrows = bc.get("arrows") or []
                if show_arrows and arrows and len(pixels) >= 2:
                    placements = _arrow_placement(pixels, len(arrows))
                    for arrow, (p0, p1) in zip(arrows, placements):
                        if arrow == "?":
                            continue
                        if arrow == "<":
                            p0, p1 = p1, p0
                        elif arrow == "<>":
                            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
                            _draw_arrowhead(draw, mx, my, p0[0], p0[1], ARROW_COLOR)
                            _draw_arrowhead(draw, mx, my, p1[0], p1[1], ARROW_COLOR)
                            continue
                        _draw_arrowhead(draw, p0[0], p0[1], p1[0], p1[1], ARROW_COLOR)

            for iso in draft.get("isotherms", []):
                pixels = polyline_wt_to_image_pixels(
                    iso.get("polyline_wt") or [], corners=corners, origin=origin, components=components
                )  # type: ignore[arg-type]
                if len(pixels) >= 2:
                    temp = iso.get("temperature_C")
                    missing = temp is None or temp == "" or not isinstance(temp, (int, float))
                    fill = ISOTHERM_MISSING_TEMP_COLOR if missing else ISOTHERM_COLOR
                    draw.line([tuple(p) for p in pixels], fill=fill, width=2)

        if show_points:
            for inv in draft.get("invariantPoints", []):
                wt = [inv["liquid_wt"][c] for c in components]
                pix = polyline_wt_to_image_pixels(
                    [wt], corners=corners, origin=origin, components=components
                )[0]  # type: ignore[arg-type]
                x, y = pix
                r = 5
                draw.ellipse((x - r, y - r, x + r, y + r), fill=POINT_COLOR, outline=(0, 0, 0, 255))

            corner_px = polyline_wt_to_image_pixels(
                [[100, 0, 0], [0, 100, 0], [0, 0, 100]],
                corners=corners,
                origin=origin,  # type: ignore[arg-type]
                components=components,
            )
            for p in corner_px:
                x, y = p
                draw.rectangle((x - 4, y - 4, x + 4, y + 4), fill=CORNER_COLOR, outline=(0, 0, 0, 255))

    out = Image.alpha_composite(base, layer).convert("RGB")
    origin_str = ",".join(str(int(v)) for v in session["image"]["pageOrigin"])
    out.text = {"pageOrigin": origin_str}
    return out


def _render_binary_overlay(
    draw: ImageDraw.ImageDraw,
    session: dict[str, Any],
    *,
    show_points: bool,
    show_curves: bool,
) -> None:
    from source_extract.review.binary_axes import axes_from_digitization

    draft = session["draft"]
    axes = axes_from_digitization(draft)
    if axes is None:
        return
    origin = tuple(session["image"]["pageOrigin"])
    ox, oy = float(origin[0]), float(origin[1])

    def to_img(wt: float, t: float) -> tuple[float, float]:
        px, py = axes.to_pixel(wt, t)
        return px - ox, py - oy

    if show_curves:
        for branch in draft.get("liquidus") or []:
            pts = []
            for pt in branch.get("points") or []:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    pts.append(to_img(float(pt[0]), float(pt[1])))
            if len(pts) >= 2:
                draw.line(pts, fill=BOUNDARY_COLOR, width=4)
        dome = (draft.get("liquidImmiscibility") or {}).get("boundary") or []
        dome_pts = []
        for pt in dome:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                dome_pts.append(to_img(float(pt[0]), float(pt[1])))
        if len(dome_pts) >= 2:
            draw.line(dome_pts, fill=ISOTHERM_COLOR, width=2)

    if show_points:
        for inv in draft.get("invariantPoints", []):
            src = (inv.get("sources") or [{}])[0]
            page = src.get("pixel")
            if isinstance(page, (list, tuple)) and len(page) == 2:
                x, y = float(page[0]) - ox, float(page[1]) - oy
            else:
                x_wt = float(inv.get("liquid_wt", {}).get(axes.x_component, 0.0))
                t = float(inv.get("temperature_C") or 0.0)
                x, y = to_img(x_wt, t)
            r = 5
            draw.ellipse((x - r, y - r, x + r, y + r), fill=POINT_COLOR, outline=(0, 0, 0, 255))


def render_confirmed_overlay(session: dict[str, Any], dest: Path) -> None:
    img = render_overlay_image(session)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, pnginfo=_pnginfo(session))


def _pnginfo(session: dict[str, Any]):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("pageOrigin", ",".join(str(int(v)) for v in session["image"]["pageOrigin"]))
    info.add_text("system", str(session.get("systemId", "")))
    return info
