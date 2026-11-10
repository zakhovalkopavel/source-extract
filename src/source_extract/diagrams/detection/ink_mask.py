"""
source_extract.diagrams.detection.ink_mask — Binary ink mask of a grey page image.
"""
from __future__ import annotations

import numpy as np


def ink_mask(image: np.ndarray, threshold: int = 128) -> np.ndarray:
    """True where the grey value is below ``threshold``."""
    if image.ndim == 3:
        image = image.mean(axis=2)
    return image < threshold
