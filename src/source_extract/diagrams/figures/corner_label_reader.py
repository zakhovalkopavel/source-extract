"""
source_extract.diagrams.figures.corner_label_reader — Tesseract reading of the text at the three corners of a ternary triangle.

OCR results only choose the corner components; they are logged and never written as data.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_BOXES = {
    "top": (-0.12, -0.13, 0.12, -0.005),
    "left": (-0.12, 0.005, 0.06, 0.12),
    "right": (-0.06, 0.005, 0.12, 0.12),
}


def read_corner_labels(image: np.ndarray, corners: dict[str, tuple[float, float]]) -> dict[str, dict]:
    """``{corner: {"text", "box"}}``: the text read above the top corner and below the left and right corners.

    Each box (page pixels x0, y0, x1, y1) spans fixed fractions of the base length
    around its corner, where the figure prints the component and its melting point.
    """
    import pytesseract

    page = Image.fromarray(image).convert("L")
    base = corners["right"][0] - corners["left"][0]
    out = {}
    for name, (a, b, c, d) in _BOXES.items():
        x, y = corners[name]
        box = (max(0, int(x + a * base)), max(0, int(y + b * base)),
               min(page.width, int(x + c * base)), min(page.height, int(y + d * base)))
        crop = page.crop(box)
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        out[name] = {"text": pytesseract.image_to_string(crop, config="--psm 6").strip(), "box": box}
    return out
