"""
source_extract.diagrams.builders.node_map_builder — Numbered points of a ternary diagram for topology hints.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from scipy import ndimage

from source_extract.diagrams.detection.dash_end_detector import detect_line_ends
from source_extract.diagrams.detection.junction_detector import detect_junctions
from source_extract.diagrams.detection.ring_detector import detect_rings
from source_extract.diagrams.detection.text_detector import detect_text_boxes
from source_extract.diagrams.models.diagram_node import DiagramNode
from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.ternary_calibration import TernaryCalibration

_MARGIN_PX = 8
_INVARIANT_PX = 12.0
_EDGE_PX = 10.0
_ROW_BAND_PX = 50
_DASH_END_PX = 10.0
_TEXT_PAD_PX = 6
_FRAME_WIDTH_PX = 3
_FRAME_BAND_PX = 6.0
_STROKE_REACH_PX = 14
_SOLID_PX = 60.0
_STRAIGHT_SD_PX = 2.5
_LONG_STRAIGHT_PX = 100.0
_CONTINUE_PX = (3, 25)
_CONTINUE_SIDE_PX = 4
_ALIGNED_COS = 0.94
_MIN_DASH_PX = 12.0
_DASH_ELONGATION = 2.0
_CORNER_PX = 12.0
_RING_PAD_PX = 6.0
_PREFIX = {"corner": "V", "invariant": "I", "junction": "X", "edge": "E", "dash-end": "D", "free-end": "F", "ring": "C"}


def _source_pixel(sources: list[dict], source_ref: str | None) -> list | tuple | None:
    """Return the pixel from ``sources`` matching ``source_ref``, or the first pixel present."""
    for entry in sources:
        if not entry.get("pixel"):
            continue
        if source_ref is None or entry.get("ref") == source_ref:
            return entry["pixel"]
    return None


def build_node_map(
    system: dict,
    mask: np.ndarray,
    pixel_origin: tuple[float, float] = (0.0, 0.0),
    scale: LineScale | None = None,
    *,
    source_ref: str | None = None,
) -> list[DiagramNode]:
    """Triangle corners, invariants, junctions, edge points, dash ends, free line ends and rings.

    Labels have one letter per kind (V corner, I invariant, X crossing, E edge
    point, D dash end, F free line end, C ring) and run in reading order (bands of 50 px, then x).
    Corners are the calibration corners (``invariant`` = the component); other
    points within 12 px of a corner, except invariants, are dropped.
    Detected junctions within 12 px of an invariant of the system file are
    replaced by the invariant (its stored source pixel); junctions on a ring are
    dropped. Rings are searched in the crop before it is cut to the triangle (a
    ring drawn on an edge stays closed) and kept when their centre lies within
    the triangle + 8 px. Junctions and dash ends inside label boxes (padded 6 px) and rings
    inside unpadded label boxes are dropped. Edge points lie on the edge line and
    are kept only when a line leads inside from them (``_Strokes.leads_inside``):
    ruler ticks and label leaders ending freely inside the triangle are dropped.
    Dash ends and free ends within 10 px of another node are dropped. Pixel sizes
    are for the reference line width, scaled by ``scale``.
    ``source_ref`` selects which ``sources[].ref`` supplies invariant pixels
    (``None`` = first source that has a pixel).
    """
    s = scale or LineScale()
    margin, pad = s.count(_MARGIN_PX), s.count(_TEXT_PAD_PX)
    calibration = TernaryCalibration.from_system(system, pixel_origin)
    components = list(system["components"])
    corners = np.array([calibration.stored_to_page(*calibration.corners[c]) for c in components])
    x0, y0 = (np.floor(corners.min(axis=0)) - 3 * margin).astype(int)
    x1, y1 = (np.ceil(corners.max(axis=0)) + 3 * margin).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, mask.shape[1]), min(y1, mask.shape[0])
    region = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(region, [np.round(corners - [x0, y0]).astype(np.int32)], 1)
    region = ndimage.binary_dilation(region.astype(bool), iterations=margin)
    local = mask[y0:y1, x0:x1] & region
    frame = np.zeros(local.shape, np.uint8)
    cv2.polylines(frame, [np.round(corners - [x0, y0]).astype(np.int32)], True, 1, s.count(_FRAME_WIDTH_PX))
    found_rings = [(x, y, d) for x, y, d in detect_rings(mask[y0:y1, x0:x1], scale=s)
                   if region[min(int(round(y)), region.shape[0] - 1), min(int(round(x)), region.shape[1] - 1)]]
    text_boxes = detect_text_boxes(local, exclude=[(x, y) for x, y, _ in found_rings], scale=s)
    blocked = np.zeros(local.shape, bool)
    for bx0, by0, bx1, by1 in text_boxes:
        blocked[max(by0 - pad, 0):by1 + pad, max(bx0 - pad, 0):bx1 + pad] = True

    def in_text(page: tuple[float, float], pad: bool) -> bool:
        lx, ly = int(round(page[0] - x0)), int(round(page[1] - y0))
        if pad:
            return 0 <= ly < blocked.shape[0] and 0 <= lx < blocked.shape[1] and bool(blocked[ly, lx])
        return any(bx0 <= lx <= bx1 and by0 <= ly <= by1 for bx0, by0, bx1, by1 in text_boxes)

    rings = [(x + x0, y + y0, d) for x, y, d in found_rings if not in_text((x + x0, y + y0), False)]
    triangle = np.zeros(local.shape, np.uint8)
    cv2.fillPoly(triangle, [np.round(corners - [x0, y0]).astype(np.int32)], 1)
    frame_distance = ndimage.distance_transform_edt(~frame.astype(bool))
    inner = local & triangle.astype(bool) & (frame_distance > s.length(_FRAME_BAND_PX))
    strokes = _Strokes(inner, frame_distance, blocked, s)
    invariants = []
    for point in system.get("invariantPoints", []):
        pixel = _source_pixel(point.get("sources") or [], source_ref)
        if pixel is not None:
            invariants.append((point["id"], calibration.stored_to_page(float(pixel[0]), float(pixel[1]))))

    candidates: list[tuple[str, tuple[float, float], str | None]] = [("invariant", p, i) for i, p in invariants]
    for jx, jy in detect_junctions(local, scale=s):
        page = (jx + x0, jy + y0)
        if any(math.dist(page, p) <= s.length(_INVARIANT_PX) for _, p in invariants):
            continue
        if any(math.dist(page, (rx, ry)) <= d / 2.0 + s.length(_RING_PAD_PX) for rx, ry, d in rings) or in_text(page, True):
            continue
        if _edge_distance(page, corners) <= s.length(_EDGE_PX):
            page = _onto_edge(page, corners)
            if not strokes.leads_inside((page[0] - x0, page[1] - y0)):
                continue
            candidates.append(("edge", page, None))
        else:
            candidates.append(("junction", page, None))
    hits, free = detect_line_ends(local, frame=frame.astype(bool), blocked=blocked, scale=s)
    for kind, points in (("dash-end", hits), ("free-end", free)):
        for ex, ey in points:
            page = (ex + x0, ey + y0)
            if in_text(page, True) or any(math.dist(page, p) <= s.length(_DASH_END_PX) for _, p, _ in candidates):
                continue
            candidates.append((kind, page, None))
    candidates += [("ring", (x, y), None) for x, y, _ in rings]
    candidates = [c for c in candidates
                  if c[0] == "invariant" or all(math.dist(c[1], corner) > s.length(_CORNER_PX) for corner in corners)]
    candidates += [("corner", (float(x), float(y)), c) for c, (x, y) in zip(components, corners)]
    band = s.count(_ROW_BAND_PX)
    candidates.sort(key=lambda c: (int(c[1][1] // band), c[1][0]))

    numbers = dict.fromkeys(_PREFIX, 0)
    nodes = []
    for kind, page, invariant in candidates:
        numbers[kind] += 1
        wt = calibration.to_wt(*page)
        nodes.append(DiagramNode(f"{_PREFIX[kind]}{numbers[kind]}", kind, calibration.page_to_stored(*page),
                                 [wt[c] for c in components], invariant))
    return nodes


def _edges(corners: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    return [(corners[0], corners[1]), (corners[1], corners[2]), (corners[2], corners[0])]


def _foot(point: tuple[float, float], a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    segment = b - a
    t = float(np.clip((np.array(point) - a) @ segment / (segment @ segment), 0.0, 1.0))
    return a + t * segment, t


def _edge_distance(point: tuple[float, float], corners: np.ndarray) -> float:
    return min(float(np.linalg.norm(np.array(point) - _foot(point, a, b)[0])) for a, b in _edges(corners))


def _onto_edge(point: tuple[float, float], corners: np.ndarray) -> tuple[float, float]:
    foot = min((_foot(point, a, b)[0] for a, b in _edges(corners)), key=lambda f: float(np.linalg.norm(np.array(point) - f)))
    return float(foot[0]), float(foot[1])


class _Strokes:
    """Ink inside the triangle with the frame band removed, split into strokes (8-connected components)."""

    def __init__(self, inner: np.ndarray, frame_distance: np.ndarray, blocked: np.ndarray, scale: LineScale):
        self.labels, _ = ndimage.label(inner, structure=np.ones((3, 3), bool))
        self.boxes = ndimage.find_objects(self.labels)
        self.frame_distance = frame_distance
        self.blocked = blocked
        self.scale = scale
        self._shapes: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, float]] = {}

    def leads_inside(self, point: tuple[float, float]) -> bool:
        """True if a stroke starting within 14 px of ``point`` is a curve or a line network (≥ 60 px, not
        straight), a straight line of ≥ 100 px (ruler ticks are shorter), or a straight stroke whose far end is back at the frame
        (an isotherm across a corner), at or pointing into a label box within 25 px (an isotherm broken
        by its temperature), or continued by a dash on its axis (a dashed line)."""
        s = self.scale
        reach = s.count(_STROKE_REACH_PX)
        x, y = int(round(point[0])), int(round(point[1]))
        window = self.labels[max(0, y - reach):y + reach + 1, max(0, x - reach):x + reach + 1]
        for label in np.unique(window[window > 0]):
            points, centre, axis, minor = self._shape(int(label))
            along = (points - centre) @ axis
            extent = float(along.max() - along.min())
            if extent >= s.length(_LONG_STRAIGHT_PX):
                return True
            if extent >= s.length(_SOLID_PX) and minor > s.length(_STRAIGHT_SD_PX):
                return True
            far = points[int(np.argmax(np.linalg.norm(points - np.array(point), axis=1)))]
            if math.dist(far, point) >= s.length(_SOLID_PX) and self._at(self.frame_distance, far) <= s.length(_FRAME_BAND_PX + 4):
                return True
            direction = axis if (far - centre) @ axis >= 0 else -axis
            if self._continued(far, direction, int(label)):
                return True
        return False

    @staticmethod
    def _at(image: np.ndarray, point: np.ndarray):
        x, y = int(round(point[0])), int(round(point[1]))
        return image[min(max(y, 0), image.shape[0] - 1), min(max(x, 0), image.shape[1] - 1)]

    def _shape(self, label: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        if label not in self._shapes:
            box = self.boxes[label - 1]
            ys, xs = np.nonzero(self.labels[box] == label)
            points = np.column_stack([xs + box[1].start, ys + box[0].start]).astype(float)
            centre = points.mean(axis=0)
            if len(points) < 3:
                self._shapes[label] = (points, centre, np.array([1.0, 0.0]), 0.0)
            else:
                values, vectors = np.linalg.eigh(np.cov((points - centre).T))
                self._shapes[label] = (points, centre, vectors[:, 1], float(np.sqrt(max(values[0], 0.0))))
        return self._shapes[label]

    def _continued(self, end: np.ndarray, direction: np.ndarray, own: int) -> bool:
        """A label box at or ahead of ``end``, or a dash (12–59 px, length ≥ 2× its width) ahead, aligned with the
        stroke and whose own axis passes within 4 px of ``end``."""
        s = self.scale
        if self._at(self.blocked, end):
            return True
        normal = np.array([-direction[1], direction[0]])
        side = s.count(_CONTINUE_SIDE_PX)
        for step in range(s.count(_CONTINUE_PX[0]), s.count(_CONTINUE_PX[1]) + 1):
            for offset in range(-side, side + 1):
                x, y = np.round(end + direction * step + normal * offset).astype(int)
                if not (0 <= y < self.labels.shape[0] and 0 <= x < self.labels.shape[1]):
                    continue
                if self.blocked[y, x]:
                    return True
                label = int(self.labels[y, x])
                if not label or label == own:
                    continue
                points, centre, axis, minor = self._shape(label)
                along = (points - centre) @ axis
                extent = float(along.max() - along.min())
                if (s.length(_MIN_DASH_PX) <= extent < s.length(_SOLID_PX) and extent >= _DASH_ELONGATION * math.sqrt(12) * minor
                        and abs(float(axis @ direction)) >= _ALIGNED_COS
                        and abs(float((end - centre) @ np.array([-axis[1], axis[0]]))) <= s.length(_CONTINUE_SIDE_PX)):
                    return True
        return False
