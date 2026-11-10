"""
source_extract.diagrams.rendering.isotherm_draft_renderer — Review image of the isotherm detector: pieces coloured by how their temperature was found.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from source_extract.diagrams.models.isotherm_detection import IsothermDetection

_FADE = 0.45
_COLOURS = {"label": (0, 90, 230), "continuation": (0, 160, 170), "boundary order": (0, 150, 0),
            "field order": (140, 60, 200), None: (230, 110, 0)}
_DROPPED = (190, 190, 190)
_GAP = (235, 0, 140)
_LEGEND = (("label", "Temperature read on the line"), ("continuation", "Read on the same line in another field"),
           ("boundary order", "From the order of the lines along boundaries"),
           ("field order", "One step from the neighbouring lines across the field"),
           (None, "Not determined (candidates in the report)"))
_WIDTH_PX = 4
_FONT_PX = 22
_ROW_PX = 30


def render_isotherm_draft(
    image: np.ndarray,
    detection: IsothermDetection,
    box: tuple[int, int, int, int],
) -> Image.Image:
    """The page inside ``box`` (page pixels), faded, with the detected pieces (colour by temperature
    source, label ``D<n> <°C>`` at the middle), label gaps joined straight in magenta, dropped thin
    lines in grey, and a legend strip below."""
    gray = image if image.ndim == 2 else np.asarray(Image.fromarray(image).convert("L"))
    x0, y0, x1, y1 = box
    crop = gray[y0:y1, x0:x1].astype(np.float32)
    faded = Image.fromarray((255 - (255 - crop) * _FADE).astype(np.uint8)).convert("RGB")
    legend_height = _ROW_PX * (len(_LEGEND) + 3)
    canvas = Image.new("RGB", (faded.width, faded.height + legend_height), (255, 255, 255))
    canvas.paste(faded, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=_FONT_PX)

    def local(p):
        return p[0] - x0, p[1] - y0

    for pixels, _ in detection.dropped:
        draw.line([local(p) for p in pixels], fill=_DROPPED, width=2)
    for number, piece in enumerate(detection.isotherms, start=1):
        colour = _COLOURS[piece.source]
        points = [local(p) for p in piece.pixels]
        straight = set(piece.straight)
        run = [points[0]]
        for k in range(1, len(points)):
            if k in straight:
                draw.line(run, fill=colour, width=_WIDTH_PX)
                draw.line([points[k - 1], points[k]], fill=_GAP, width=_WIDTH_PX - 1)
                run = [points[k]]
            else:
                run.append(points[k])
        draw.line(run, fill=colour, width=_WIDTH_PX)
        for end in (points[0], points[-1]):
            draw.ellipse([end[0] - 4, end[1] - 4, end[0] + 4, end[1] + 4], outline=colour, width=2)
        mx, my = points[len(points) // 2]
        text = f"D{number} {'?' if piece.temperature_C is None else f'{piece.temperature_C:g}'}"
        draw.text((mx + 6, my - _FONT_PX // 2), text, fill=colour, font=font, stroke_width=3, stroke_fill=(255, 255, 255))
    top = faded.height + _ROW_PX // 2
    draw.text((10, top), "Isotherm draft: D-number and temperature (°C)", fill=(0, 0, 0), font=font)
    for row, (source, text) in enumerate(_LEGEND, start=1):
        y = top + row * _ROW_PX
        draw.line([(10, y + _FONT_PX // 2), (60, y + _FONT_PX // 2)], fill=_COLOURS[source], width=_WIDTH_PX)
        draw.text((70, y), text, fill=(0, 0, 0), font=font)
    y = top + (len(_LEGEND) + 1) * _ROW_PX
    draw.line([(10, y + _FONT_PX // 2), (60, y + _FONT_PX // 2)], fill=_GAP, width=_WIDTH_PX)
    draw.line([(330, y + _FONT_PX // 2), (380, y + _FONT_PX // 2)], fill=_DROPPED, width=2)
    draw.text((70, y), "label gap (straight)", fill=(0, 0, 0), font=font)
    draw.text((390, y), "dropped thin lines (leaders, joins)", fill=(0, 0, 0), font=font)
    return canvas
