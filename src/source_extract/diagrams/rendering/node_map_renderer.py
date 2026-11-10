"""
source_extract.diagrams.rendering.node_map_renderer — Tile of the scan with the numbered node-map points.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from source_extract.diagrams.models.diagram_node import DiagramNode
from source_extract.diagrams.rendering.arrowheads import arrowheads
from source_extract.diagrams.rendering.tile_renderer import render_tile

_COLOURS = {"junction": (220, 0, 0), "edge": (230, 120, 0), "dash-end": (160, 0, 200), "free-end": (120, 80, 0),
            "invariant": (0, 70, 230),
            "ring": (0, 150, 0), "corner": (0, 160, 170), "user": (0x43, 0x25, 0x5B), "arrow": (235, 0, 140)}
_LEGEND = {"user": "Points added by hand (name left of the dot)", "corner": "V  Triangle corners", "invariant": "I  Invariants from the system file", "junction": "X  Line crossings",
           "edge": "E  Crossings on the triangle edge", "dash-end": "D  Dashed-line ends",
           "free-end": "F  Free line ends", "ring": "C  Compound rings",
           "arrow": "Stored arrows (towards falling temperature)"}
_FADE = 0.55
_ARROW_LENGTH_PX = 20
_ARROW_HALF_WIDTH_PX = 8
_ARROW_SPAN_PX = 10


def render_node_map(
    image: np.ndarray,
    nodes: list[DiagramNode],
    box: tuple[int, int, int, int],
    scale: float = 1.0,
    pixel_origin: tuple[float, float] = (0.0, 0.0),
    labels: bool = True,
    legend: bool = False,
    font_px: int = 15,
    arrows: list[tuple[list[tuple[float, float]], str]] | None = None,
) -> Image.Image:
    """``box`` in page pixels; the scan is faded so labels stay readable; rulers in page pixels.

    ``labels=False`` draws the markers only; ``legend`` adds a key of the kinds present (top left).
    ``arrows`` (page-pixel boundary pieces with their stored arrow, ``boundary_arrow_segments``)
    are drawn under the markers as magenta arrowheads (20 × 16 page px), ``?`` as a magenta ``?``.
    Each label takes the first of eight positions around its marker that overlaps no
    marker or label drawn before it. Hand-added points (kind ``user``, label ``name•``)
    show the name left of the dot first, as drawn by hand, without the bullet.
    """
    gray = image if image.ndim == 2 else np.asarray(Image.fromarray(image).convert("L"))
    faded = (255 - (255 - gray.astype(np.float32)) * _FADE).astype(np.uint8)
    tile = render_tile(faded, box, scale)
    x0, y0, x1, y1 = box
    offset_x = tile.width - int((x1 - x0) * scale)
    offset_y = tile.height - int((y1 - y0) * scale)
    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default(size=font_px)
    dot = max(4, font_px // 4)
    ring = max(9, font_px // 2 + 2)
    arrow_colour = _COLOURS["arrow"]
    for pixels, arrow in arrows or []:
        local = [(offset_x + (px - x0) * scale, offset_y + (py - y0) * scale) for px, py in pixels]
        if arrow == "?":
            middle = local[len(local) // 2]
            draw.text(middle, "?", fill=arrow_colour, font=font, anchor="mm", stroke_width=max(2, font_px // 7), stroke_fill="white")
        for head in arrowheads(local, arrow, _ARROW_LENGTH_PX * scale, _ARROW_HALF_WIDTH_PX * scale, _ARROW_SPAN_PX * scale):
            draw.polygon(head, fill=arrow_colour, outline="white")
    markers = []
    for node in nodes:
        px, py = node.pixel[0] + pixel_origin[0], node.pixel[1] + pixel_origin[1]
        if x0 <= px < x1 and y0 <= py < y1:
            markers.append((node, offset_x + (px - x0) * scale, offset_y + (py - y0) * scale))
    taken = [(sx - dot, sy - dot, sx + dot, sy + dot) for _, sx, sy in markers]
    for node, sx, sy in markers:
        colour = _COLOURS[node.kind]
        if node.kind == "ring":
            draw.ellipse([sx - ring, sy - ring, sx + ring, sy + ring], outline=colour, width=max(2, font_px // 8))
        else:
            draw.ellipse([sx - dot, sy - dot, sx + dot, sy + dot], fill=colour)
    if labels:
        for node, sx, sy in markers:
            text = node.label.rstrip("•")
            box_w = draw.textlength(text, font=font) + 4
            box_h = font_px + 4
            gap = dot + 2
            options = [(sx + gap, sy - box_h - 1), (sx + gap, sy + 1), (sx - gap - box_w, sy - box_h - 1),
                       (sx - gap - box_w, sy + 1), (sx - box_w / 2, sy - gap - box_h), (sx - box_w / 2, sy + gap),
                       (sx + gap, sy - box_h / 2), (sx - gap - box_w, sy - box_h / 2)]
            if node.kind == "user":
                options.insert(0, (sx - gap - box_w, sy - box_h / 2))
            place = next((o for o in options if not any(_overlap((o[0], o[1], o[0] + box_w, o[1] + box_h), t) for t in taken)),
                         options[0])
            taken.append((place[0], place[1], place[0] + box_w, place[1] + box_h))
            draw.text((place[0] + 2, place[1] + 2), text, fill=_COLOURS[node.kind], font=font,
                      stroke_width=max(2, font_px // 7), stroke_fill="white")
    if legend:
        _draw_legend(draw, nodes, font_px, bool(arrows))
    return tile


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _draw_legend(draw: ImageDraw.ImageDraw, nodes: list[DiagramNode], font_px: int, with_arrows: bool) -> None:
    size = max(26, int(font_px * 1.5))
    font = ImageFont.load_default(size=size)
    entries = [(kind, text) for kind, text in _LEGEND.items()
               if any(n.kind == kind for n in nodes) or (kind == "arrow" and with_arrows)]
    line = int(size * 1.6)
    text_width = max(draw.textlength(text, font=font) for _, text in entries)
    x0, y0 = 80, 60
    x1 = int(x0 + text_width + 3 * size)
    draw.rectangle([x0, y0, x1, y0 + line * len(entries) + size], fill="white", outline=(80, 80, 80), width=2)
    for row, (kind, text) in enumerate(entries):
        cx, cy = x0 + size, y0 + size + row * line
        colour = _COLOURS[kind]
        r = size // 3
        if kind == "ring":
            draw.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], outline=colour, width=3)
        elif kind == "arrow":
            draw.polygon([(cx + r, cy), (cx - r, cy - r), (cx - r, cy + r)], fill=colour)
        else:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)
        draw.text((cx + size, cy), text, fill=(30, 30, 30), font=font, anchor="lm")
