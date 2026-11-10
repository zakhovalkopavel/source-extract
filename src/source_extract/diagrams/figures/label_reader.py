"""
source_extract.diagrams.figures.label_reader — Tesseract reading of a printed number (suggestion only).

OCR results go to the review list, never into the system JSON.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def read_label(image: np.ndarray, box: tuple[int, int, int, int], whitelist: str = "0123456789.") -> tuple[str, float]:
    """Text and mean confidence (0–100) of the label inside ``box`` (x0, y0, x1, y1)."""
    import pytesseract

    x0, y0, x1, y1 = box
    crop = Image.fromarray(image[y0:y1, x0:x1]).convert("L")
    crop = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
    config = f"--psm 7 -c tessedit_char_whitelist={whitelist}"
    data = pytesseract.image_to_data(crop, config=config, output_type=pytesseract.Output.DICT)
    words = [(w, float(c)) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
    if not words:
        return "", 0.0
    text = "".join(w for w, _ in words)
    confidence = sum(c for _, c in words) / len(words)
    return text, confidence
