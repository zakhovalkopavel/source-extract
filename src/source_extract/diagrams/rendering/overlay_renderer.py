"""
source_extract.diagrams.rendering.overlay_renderer — Review PNG: measurements drawn in colour over the scan.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from source_extract.diagrams.models.traced_curve import TracedCurve

_LEGEND = (
    ("traced path", (0, 90, 255)),
    ("sampled point", (230, 0, 0)),
    ("invariant line", (0, 160, 0)),
    ("tick", (200, 0, 200)),
    ("junction", (255, 140, 0)),
)


def render_overlay(
    image: np.ndarray,
    box: tuple[float, float, float, float],
    curves: list[TracedCurve] = (),
    points: list[tuple[float, float]] = (),
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = (),
    ticks: list[tuple[float, float]] = (),
    junctions: dict[str, tuple[float, float]] | None = None,
    margin: int = 60,
) -> Image.Image:
    """Crop ``box`` (page pixels, plus ``margin``) and draw the given layers in page coordinates.

    ``info["pageOrigin"]`` ("x0,y0") is the page pixel of the top-left corner, so a
    tile of the overlay can be drawn with page rulers.
    """
    x0 = max(0, int(box[0]) - margin)
    y0 = max(0, int(box[1]) - margin)
    x1 = min(image.shape[1], int(box[2]) + margin)
    y1 = min(image.shape[0], int(box[3]) + margin)
    out = Image.fromarray(image[y0:y1, x0:x1]).convert("RGB")
    out.info["pageOrigin"] = f"{x0},{y0}"
    draw = ImageDraw.Draw(out)
    colours = dict(_LEGEND)

    def local(p):
        return p[0] - x0, p[1] - y0

    for curve in curves:
        if len(curve.pixels) > 1:
            draw.line([local(p) for p in curve.pixels], fill=colours["traced path"], width=2)
    for (a, b) in lines:
        draw.line([local(a), local(b)], fill=colours["invariant line"], width=2)
    for p in ticks:
        x, y = local(p)
        draw.line([(x - 6, y), (x + 6, y)], fill=colours["tick"], width=2)
        draw.line([(x, y - 6), (x, y + 6)], fill=colours["tick"], width=2)
    for p in points:
        x, y = local(p)
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=colours["sampled point"])
    for name, p in (junctions or {}).items():
        x, y = local(p)
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], outline=colours["junction"], width=2)
        draw.text((x + 9, y - 14), name, fill=colours["junction"])
    for row, (name, colour) in enumerate(_LEGEND):
        draw.rectangle([8, 8 + row * 16, 20, 20 + row * 16], fill=colour)
        draw.text((26, 8 + row * 16), name, fill=colour)
    return out
