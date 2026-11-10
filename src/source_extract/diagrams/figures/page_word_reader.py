"""
source_extract.diagrams.figures.page_word_reader — Every word printed in a part of a page (field names, temperatures), by Tesseract.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from PIL import Image
from scipy import ndimage

from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.page_word import PageWord

WordOcr = Callable[[np.ndarray], list[tuple[str, float, int, int, int, int]]]

_GLYPH_MAX_PX = 70
_SAME_WORD = 0.5


def read_page_words(
    image: np.ndarray,
    mask: np.ndarray,
    box: tuple[int, int, int, int],
    ocr: WordOcr | None = None,
    scale: LineScale | None = None,
) -> list[PageWord]:
    """Words inside ``box`` (x0, y0, x1, y1; page pixels) of the page ``image``, two readings merged.

    ``ocr`` reads a grey crop (uint8, white paper) and returns ``(text, confidence, left, top,
    width, height)`` per word (default: Tesseract, sparse text, ``--psm 11``). It reads the crop
    as printed and once more with only glyph-sized ink (connected components of ``mask`` at most
    70 px in both directions), where words crossed by lines come out; of two words whose boxes
    overlap by half of the smaller one, the more confident is kept.
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    read = ocr or _tesseract_words
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(image.shape[1], int(box[2])), min(image.shape[0], int(box[3]))
    crop = image[y0:y1, x0:x1]
    if crop.ndim == 3:
        crop = np.asarray(Image.fromarray(crop).convert("L"))
    ink = mask[y0:y1, x0:x1].astype(bool)
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3), bool))
    limit = s.length(_GLYPH_MAX_PX)
    small = np.zeros(int(labels.max()) + 1, bool)
    for index, found in enumerate(ndimage.find_objects(labels), start=1):
        if found is not None:
            small[index] = max(found[0].stop - found[0].start, found[1].stop - found[1].start) <= limit
    glyphs = np.where(small[labels], 0, 255).astype(np.uint8)
    words: list[PageWord] = []
    for picture in (crop.astype(np.uint8), glyphs):
        for text, confidence, left, top, width, height in read(picture):
            text = text.strip()
            if text:
                words.append(PageWord(text, float(confidence), (x0 + left, y0 + top, x0 + left + width, y0 + top + height)))
    kept: list[PageWord] = []
    for word in sorted(words, key=lambda w: -w.confidence):
        if not any(_overlap(word.box, other.box) >= _SAME_WORD for other in kept):
            kept.append(word)
    return sorted(kept, key=lambda w: (w.box[1], w.box[0]))


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Intersection area over the smaller box area."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / max(smaller, 1)


def _tesseract_words(picture: np.ndarray) -> list[tuple[str, float, int, int, int, int]]:
    import pytesseract

    data = pytesseract.image_to_data(Image.fromarray(picture), config="--psm 11", output_type=pytesseract.Output.DICT)
    return [(data["text"][i], float(data["conf"][i]), int(data["left"][i]), int(data["top"][i]),
             int(data["width"][i]), int(data["height"][i]))
            for i in range(len(data["text"])) if data["text"][i].strip() and float(data["conf"][i]) >= 0]
