"""
source_extract.diagrams.rendering.tile_renderer — Zoom tile of a page region with pixel rulers.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

_RULER = 40


def render_tile(image: np.ndarray, box: tuple[int, int, int, int], scale: float = 1.0) -> Image.Image:
    """Crop ``box`` (x0, y0, x1, y1, page pixels), scale it and add rulers in page pixels.

    Minor marks every 10 px, labelled marks every 50 px (every 100 px when the
    tile is wider than 1500 page pixels).
    """
    x0, y0, x1, y1 = (int(v) for v in box)
    crop = Image.fromarray(image[y0:y1, x0:x1]).convert("RGB")
    if scale != 1.0:
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.NEAREST)
    tile = Image.new("RGB", (crop.width + _RULER, crop.height + _RULER), "white")
    tile.paste(crop, (_RULER, _RULER))
    draw = ImageDraw.Draw(tile)
    label_step = 100 if (x1 - x0) > 1500 else 50
    for px in range((x0 // 10) * 10, x1 + 1, 10):
        if px < x0:
            continue
        sx = _RULER + (px - x0) * scale
        length = 12 if px % label_step == 0 else 5
        draw.line([(sx, _RULER - length), (sx, _RULER - 1)], fill="red")
        if px % label_step == 0:
            draw.text((sx + 2, 2), str(px), fill="red")
    for py in range((y0 // 10) * 10, y1 + 1, 10):
        if py < y0:
            continue
        sy = _RULER + (py - y0) * scale
        length = 12 if py % label_step == 0 else 5
        draw.line([(_RULER - length, sy), (_RULER - 1, sy)], fill="red")
        if py % label_step == 0:
            draw.text((2, sy + 2), str(py), fill="red")
    return tile
