"""
source_extract.diagrams.builders.node_label_resolver — Replace node-map labels in config text by invariant ids or stored pixels.
"""
from __future__ import annotations

import math
import re

_LABEL = re.compile(r"(?<![0-9A-Za-z])[VIXEDFC][0-9]+•?(?![0-9A-Za-z•])")
_SAME_PIXEL_PX = 2.0


def resolve_node_labels(
    value,
    nodes: dict[str, tuple[float, float]],
    invariants: dict[str, tuple[float, float]],
    where: str,
    log: list[str] | None = None,
):
    """``value`` with every node label in its strings (nested lists and dicts too) replaced.

    Node labels (``X23``, ``I2•``, ``D101•``: a kind letter V, I, X, E, D or C,
    a number and an optional •) are working names of the node map and of the
    config ``nodes``; the dataset keeps stable references instead. A label whose
    pixel lies within 2 px of an invariant's source pixel (``invariants``: id →
    stored pixel) becomes the nearest such id, any other its stored pixel ``[x, y]``.
    Resolved labels are logged once per ``where``. Raises ValueError for a
    label that is not in ``nodes``.
    """
    seen: dict[str, str] = {}

    def replace(match: re.Match) -> str:
        label = match.group(0)
        if label not in nodes:
            raise ValueError(f"{where}: node label '{label}' is not in the config nodes; add it there or write the pixel")
        if label not in seen:
            pixel = nodes[label]
            distance, nearest = min(((math.dist(p, pixel), i) for i, p in invariants.items()), default=(math.inf, None))
            seen[label] = nearest if distance <= _SAME_PIXEL_PX else f"[{pixel[0]:g}, {pixel[1]:g}]"
        return seen[label]

    def walk(item):
        if isinstance(item, str):
            return _LABEL.sub(replace, item)
        if isinstance(item, list):
            return [walk(v) for v in item]
        if isinstance(item, dict):
            return {k: walk(v) for k, v in item.items()}
        return item

    out = walk(value)
    if seen and log is not None:
        log.append(f"{where}: node labels " + ", ".join(f"{k} → {v}" for k, v in seen.items()))
    return out
