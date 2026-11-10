"""
source_extract.diagrams.builders.boundary_graph_builder — Boundary curves of a ternary read from the page: heavy strokes, their junctions (invariant points), edge points and open ends.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

from source_extract.diagrams.detection.skeleton_branches import skeleton_branches
from source_extract.diagrams.detection.skeletonizer import skeletonize
from source_extract.diagrams.detection.text_detector import detect_text_boxes
from source_extract.diagrams.models.boundary_graph import BoundaryEdge, BoundaryGraph, BoundaryNode
from source_extract.diagrams.models.line_scale import LineScale

_HEAVY_LINES = 1.3
_BRANCH_LINES = 1.5
_MAX_LINES = 10.0
_FRAME_LINES = 3.0
_SPUR_LINES = 4.0
_MARGIN_PX = 4
_TEXT_MARGIN_PX = 6
_TEXT_DROP_SHARE = 0.5
_TEXT_DROP_PX = 60.0
_DIRECTION_PX = 10
_TAIL_PX = 30.0
_TURN_COS = 0.5
_HOOK_PX = 40.0
_ATTACH_PX = 10.0
_CONE_PX = 25.0
_CONE_COS = 0.8
_AHEAD_PX = 40.0
_EDGE_AHEAD_PX = 60.0
_TRIM_KEEP_PX = 10.0
_HIT_PX = 2.5
_HIT_SHARE = 0.08
_ON_NODE_PX = 8.0
_INK_GAP_PX = 14.0
_DASH_GAP_PX = 40.0
_DASH_MAX_PX = 70.0
_TEXT_GAP_PX = 130.0
_TEXT_SHARE = 0.3
_HIDDEN_MIN_PX = 60.0
_HIDDEN_COS = 0.97
_HIDDEN_AHEAD_PX = 160.0
_LATERAL_PX = 6.0
_LATERAL_SHARE = 0.25
_EDGE_PX = 14.0
_MIN_LOOSE_PX = 80.0
_DASHED_SHARE = 0.25
_ROUNDS = 3


def detect_boundary_graph(
    mask: np.ndarray,
    corners: list[tuple[float, float]],
    scale: LineScale | None = None,
) -> BoundaryGraph:
    """Boundary curves inside the triangle ``corners`` (page pixels) of the page ``mask``.

    Heavy strokes: ink around ridge pixels 1.3–10 line widths wide (each ridge pixel keeps the ink
    within its own half width; isotherms are drawn about one line width), inside the triangle without
    a band of three line widths along its edges. Their skeleton is split into branches
    (``skeleton_branches``, spurs up to four line widths pruned); a branch is kept when its median
    stroke width is at least 1.5 line widths and it is not a short piece (< 60 px) lying mostly on a
    printed label (``detect_text_boxes``, grown by 6 px). Branch ends on a label are cut back, and a
    sharp hook (≤ 40 px) at an open end is dropped. The branches form a graph: a node joining two
    curves is passed through, and a stub up to 30 px from a junction to a free end (an arrowhead, an
    isotherm crossing) is dropped. Free ends continue across a gap to another free end when each lies
    ahead of the other (within 6 px or a quarter of the gap of the other's direction): up to 14 px (a
    break), up to 40 px when one side is a dash (≤ 70 px), up to 130 px when ≥ 30 % of the gap lies
    on a label, up to 160 px between two pieces of at least 60 px pointing at each other (a label
    printed over the curve); cheapest first. A free end within 10 px of another curve, within 25 px
    of it ahead, or whose direction hits it within 40 px (130 px across a label, 160 px from a curve
    of at least 60 px) meets it (a junction drawn with a gap); a free end whose direction hits a
    triangle edge within 130 px (60 px from a curve under 60 px), or within 14 px of an edge, is an
    edge point (moved onto the edge). Curves with two open
    ends shorter than 80 px are dropped. Nodes where three or more curves meet are ``junction``; a
    curve is ``dashed`` when ≥ 25 % of its length is dash gaps. Pixel sizes are for the reference line
    width, scaled by ``scale``; the width limits are in measured line widths (``scale.line_px``).
    """
    s = scale or LineScale()
    line = s.line_px
    corners_arr = np.asarray(corners, float)
    x0, y0 = np.maximum(np.floor(corners_arr.min(axis=0)) - _MARGIN_PX, 0).astype(int)
    x1 = int(min(mask.shape[1], math.ceil(corners_arr[:, 0].max()) + _MARGIN_PX))
    y1 = int(min(mask.shape[0], math.ceil(corners_arr[:, 1].max()) + _MARGIN_PX))
    origin = np.array([x0, y0], float)
    local = mask[y0:y1, x0:x1].astype(bool)
    tri = corners_arr - origin
    inside = _polygon(local.shape, tri) & ~_frame(local.shape, tri, max(1, round(_FRAME_LINES * line)))
    distance = ndimage.distance_transform_edt(local)
    heavy = _heavy_strokes(local, distance, _HEAVY_LINES * line, _MAX_LINES * line) & inside
    text = np.zeros(local.shape, bool)
    m = s.count(_TEXT_MARGIN_PX)
    for bx0, by0, bx1, by1 in detect_text_boxes(local, scale=s):
        text[max(0, by0 - m):by1 + m, max(0, bx0 - m):bx1 + m] = True
    branches, junctions = skeleton_branches(skeletonize(heavy), min_pixels=3, spur_pixels=round(_SPUR_LINES * line))
    log: list[str] = []
    kept: list[tuple[np.ndarray, tuple[int, int]]] = []
    for branch, ends in zip(branches, junctions):
        at = branch.astype(int)
        width = float(np.median(2.0 * distance[at[:, 1], at[:, 0]]))
        if width < _BRANCH_LINES * line:
            continue
        if _length(branch) < s.length(_TEXT_DROP_PX) and text[at[:, 1], at[:, 0]].mean() >= _TEXT_DROP_SHARE:
            continue
        kept.append((branch, ends))
    log.append(f"{len(branches)} skeleton branches of heavy strokes, {len(kept)} heavy")
    graph = _Graph(kept, s)
    graph.trim_text_ends(text, s.length(_TRIM_KEEP_PX))
    graph.trim_hooks(s.length(_HOOK_PX))
    for _ in range(_ROUNDS):
        graph.simplify(s.length(_TAIL_PX))
        graph.link_gaps(text, s)
        graph.simplify(s.length(_TAIL_PX))
        graph.trim_hooks(s.length(_HOOK_PX))
        graph.attach(text, s)
        graph.simplify(s.length(_TAIL_PX))
    graph.to_frame(tri, s)
    graph.drop_loose(s.length(_MIN_LOOSE_PX))
    graph.simplify(s.length(_TAIL_PX))
    result = graph.result(origin, tri)
    counts = {k: sum(1 for n in result.nodes if n.kind == k) for k in ("junction", "edge", "end")}
    log.append(f"{len(result.edges)} boundary curves; nodes: {counts['junction']} junctions, {counts['edge']} edge points, "
               f"{counts['end']} open ends")
    result.log = log + graph.log
    return result


class _Graph:
    """Mutable curve graph in crop pixels: ``nodes`` (pixel arrays), ``edges`` (dicts or None when removed)."""

    def __init__(self, kept: list[tuple[np.ndarray, tuple[int, int]]], s: LineScale):
        self.log: list[str] = []
        self.nodes: list[np.ndarray] = []
        self.kinds: dict[int, tuple[str, int | None]] = {}
        self.edges: list[dict | None] = []
        cluster_ends: dict[int, list[np.ndarray]] = {}
        for branch, ends in kept:
            for end, cluster in ((branch[0], ends[0]), (branch[-1], ends[1])):
                if cluster:
                    cluster_ends.setdefault(cluster, []).append(end)
        cluster_node = {}
        for cluster, points in cluster_ends.items():
            cluster_node[cluster] = len(self.nodes)
            self.nodes.append(np.mean(points, axis=0))
        for branch, ends in kept:
            ids = []
            for end, cluster in ((branch[0], ends[0]), (branch[-1], ends[1])):
                if cluster:
                    ids.append(cluster_node[cluster])
                else:
                    ids.append(len(self.nodes))
                    self.nodes.append(end.astype(float))
            pixels = np.vstack([self.nodes[ids[0]], branch, self.nodes[ids[1]]])
            self.edges.append({"pixels": pixels, "a": ids[0], "b": ids[1], "gaps": [], "ink": _length(branch), "gap": 0.0})
        self.step = s.count(_DIRECTION_PX)

    def live(self) -> list[int]:
        return [k for k, e in enumerate(self.edges) if e is not None]

    def incident(self, node: int) -> list[tuple[int, int]]:
        """``(edge, end)`` pairs at ``node`` (end 0: the edge starts there); a loop appears twice."""
        out = []
        for k in self.live():
            e = self.edges[k]
            if e["a"] == node:
                out.append((k, 0))
            if e["b"] == node:
                out.append((k, 1))
        return out

    def degree(self) -> dict[int, int]:
        count: dict[int, int] = {}
        for k in self.live():
            for n in (self.edges[k]["a"], self.edges[k]["b"]):
                count[n] = count.get(n, 0) + 1
        return count

    def end(self, edge: int, end: int) -> tuple[np.ndarray, np.ndarray]:
        """Node pixel and outward unit direction of ``edge`` at its start (0) or end (1)."""
        pixels = self.edges[edge]["pixels"]
        k = min(self.step, len(pixels) - 1)
        p = pixels[0] if end == 0 else pixels[-1]
        q = pixels[k] if end == 0 else pixels[-1 - k]
        u = p - q
        n = float(np.linalg.norm(u))
        return p, (u / n if n > 0 else np.zeros(2))

    def oriented(self, edge: int, start_node: int) -> np.ndarray:
        e = self.edges[edge]
        return e["pixels"] if e["a"] == start_node else e["pixels"][::-1]

    def join(self, first: int, second: int, node: int, gap_kind: str | None = None) -> None:
        """Replace the edges ``first`` and ``second`` meeting at ``node`` by one edge through it."""
        e1, e2 = self.edges[first], self.edges[second]
        p1 = self.oriented(first, e1["a"] if e1["b"] == node else e1["b"])
        p2 = self.oriented(second, node)
        a = e1["a"] if e1["b"] == node else e1["b"]
        b = e2["b"] if e2["a"] == node else e2["a"]
        gaps = _oriented_gaps(e1, p1 is not e1["pixels"]) + [(len(p1) + i, kind) for i, kind in
                                                              _oriented_gaps(e2, p2 is not e2["pixels"])]
        if gap_kind is not None:
            gaps.append((len(p1), gap_kind))
            gaps.sort()
        self.edges[first] = {"pixels": np.vstack([p1, p2]), "a": a, "b": b, "gaps": gaps,
                             "ink": e1["ink"] + e2["ink"], "gap": e1["gap"] + e2["gap"]}
        self.edges[second] = None

    def simplify(self, tail_px: float) -> None:
        """Pass through nodes joining two curves, drop short stubs from junctions, until nothing changes."""
        changed = True
        while changed:
            changed = False
            degree = self.degree()
            for k in self.live():
                e = self.edges[k]
                for free, other in ((e["a"], e["b"]), (e["b"], e["a"])):
                    if (degree.get(free) == 1 and degree.get(other, 0) >= 3 and free not in self.kinds
                            and _length(e["pixels"]) < tail_px):
                        self.edges[k] = None
                        changed = True
                        break
                if changed:
                    break
            if changed:
                continue
            for node, count in self.degree().items():
                if count != 2 or node in self.kinds:
                    continue
                pair = self.incident(node)
                if pair[0][0] == pair[1][0]:
                    continue
                self.join(pair[0][0], pair[1][0], node)
                changed = True
                break

    def free_ends(self) -> list[tuple[int, int, int]]:
        """``(node, edge, end)`` of every open end."""
        degree = self.degree()
        return [(n, k, end) for k in self.live() for end, n in ((0, self.edges[k]["a"]), (1, self.edges[k]["b"]))
                if degree.get(n) == 1 and n not in self.kinds]

    def link_gaps(self, text: np.ndarray, s: LineScale) -> None:
        free = self.free_ends()
        if len(free) < 2:
            return
        points = [self.end(k, end) for _, k, end in free]
        tree = cKDTree(np.array([p for p, _ in points]))
        options = []
        for i, j in tree.query_pairs(r=s.length(_TEXT_GAP_PX)):
            if free[i][1] == free[j][1]:
                continue
            (p1, u1), (p2, u2) = points[i], points[j]
            kind = _gap_kind(p1, u1, p2, u2, _length(self.edges[free[i][1]]["pixels"]),
                             _length(self.edges[free[j][1]]["pixels"]), text, s)
            if kind is None:
                continue
            gap = float(np.linalg.norm(p2 - p1))
            v = (p2 - p1) / max(gap, 1e-9)
            options.append((gap / s.length(_TEXT_GAP_PX) + (1.0 - float(u1 @ v)) + (1.0 - float(-u2 @ v)), i, j, kind, gap))
        used: set[int] = set()
        for _, i, j, kind, gap in sorted(options):
            if i in used or j in used:
                continue
            (n1, k1, _), (n2, k2, _) = free[i], free[j]
            if self.edges[k1] is None or self.edges[k2] is None or k1 == k2:
                continue
            used.update((i, j))
            e2 = self.edges[k2]
            if e2["a"] == n2:
                e2["a"] = n1
            else:
                e2["b"] = n1
            self.edges[k2]["gap"] += gap
            self.join(k1, k2, n1, kind)

    def trim_text_ends(self, text: np.ndarray, keep_px: float) -> None:
        """Cut the pixels lying on a label off every open end (strokes of the letters), keeping ``keep_px``."""
        for node, edge, end in self.free_ends():
            e = self.edges[edge]
            pixels = e["pixels"] if end == 1 else e["pixels"][::-1]
            at = np.round(pixels).astype(int)
            on = text[at[:, 1], at[:, 0]]
            cut = len(pixels)
            while cut > 1 and on[cut - 1]:
                cut -= 1
            if cut == len(pixels) or _length(pixels[:cut]) < keep_px:
                continue
            self.nodes[node] = pixels[cut - 1].astype(float)
            e["ink"] = max(0.0, e["ink"] - _length(pixels[cut - 1:]))
            if end == 1:
                e["pixels"] = e["pixels"][:cut]
                e["gaps"] = [(i, kind) for i, kind in e["gaps"] if i < cut]
            else:
                removed = len(pixels) - cut
                e["pixels"] = e["pixels"][removed:]
                e["gaps"] = [(i - removed, kind) for i, kind in e["gaps"] if i > removed]

    def trim_hooks(self, hook_px: float) -> None:
        """Cut an open end at a sharp turn (> 60°) within its last ``hook_px`` (a dash touching a letter or another line)."""
        for node, edge, end in self.free_ends():
            e = self.edges[edge]
            pixels = e["pixels"] if end == 1 else e["pixels"][::-1]
            n = len(pixels)
            step = self.step
            tail = np.cumsum(np.r_[0.0, np.linalg.norm(np.diff(pixels[::-1], axis=0), axis=1)])
            cut = None
            for k in range(step, n - step):
                if tail[n - 1 - k] > hook_px:
                    continue
                before, after = pixels[k] - pixels[k - step], pixels[k + step] - pixels[k]
                cos = float(before @ after) / max(float(np.linalg.norm(before) * np.linalg.norm(after)), 1e-9)
                if cos < _TURN_COS:
                    cut = k
                    break
            if cut is None:
                continue
            self.nodes[node] = pixels[cut].astype(float)
            e["ink"] = max(0.0, e["ink"] - _length(pixels[cut:]))
            if end == 1:
                e["pixels"] = e["pixels"][:cut + 1]
                e["gaps"] = [(i, kind) for i, kind in e["gaps"] if i <= cut]
            else:
                removed = n - 1 - cut
                e["pixels"] = e["pixels"][removed:]
                e["gaps"] = [(i - removed, kind) for i, kind in e["gaps"] if i > removed]

    def attach(self, text: np.ndarray, s: LineScale) -> None:
        """Free ends meeting another curve (or pointing at it, also across a label) become junctions on it."""
        for node, edge, end in self.free_ends():
            if self.edges[edge] is None or self.degree().get(node) != 1:
                continue
            p, u = self.end(edge, end)
            hit = self._hit(edge, p, u, text, s)
            if hit is None:
                continue
            other, index, q = hit
            target = self._split(other, index, s)
            e = self.edges[edge]
            pixels = e["pixels"]
            if end == 0:
                e["pixels"] = np.vstack([self.nodes[target], pixels])
                e["a"] = target
                e["gaps"] = [(0 if i == 0 else i + 1, kind) for i, kind in e["gaps"]] + [(1, "ink")]
            else:
                e["pixels"] = np.vstack([pixels, self.nodes[target]])
                e["b"] = target
                e["gaps"] = e["gaps"] + [(len(pixels), "ink")]
            e["gaps"].sort()
            e["gap"] += float(np.linalg.norm(self.nodes[target] - p))
            self.log.append(f"open end ({p[0]:.0f}, {p[1]:.0f}) meets a curve at ({q[0]:.0f}, {q[1]:.0f})")

    def _hit(self, edge: int, p: np.ndarray, u: np.ndarray, text: np.ndarray, s: LineScale):
        best = None
        attach_px, hit_px, cone_px = s.length(_ATTACH_PX), s.length(_HIT_PX), s.length(_CONE_PX)
        long_line = _length(self.edges[edge]["pixels"]) >= s.length(_HIDDEN_MIN_PX)
        ahead_px = s.length(_HIDDEN_AHEAD_PX) if long_line else s.length(_TEXT_GAP_PX) if _text_share(p, p + u * s.length(_TEXT_GAP_PX) * 0.5, text) >= _TEXT_SHARE \
            else s.length(_AHEAD_PX)
        own = self.edges[edge]["pixels"]
        for k in self.live():
            if k == edge:
                continue
            pixels = self.edges[k]["pixels"]
            d = np.linalg.norm(pixels - p, axis=1)
            i = int(np.argmin(d))
            if d[i] <= attach_px and (best is None or d[i] < best[0]):
                best = (float(d[i]), k, i)
            rel = pixels - p
            along = rel @ u
            cone = np.nonzero((d <= cone_px) & (along >= _CONE_COS * d))[0]
            if cone.size:
                j = int(cone[np.argmin(d[cone])])
                if best is None or d[j] < best[0]:
                    best = (float(d[j]), k, j)
            across = np.abs(rel[:, 0] * u[1] - rel[:, 1] * u[0])
            ok = np.nonzero((along > 0) & (along <= ahead_px) & (across <= np.maximum(hit_px, _HIT_SHARE * along)))[0]
            if ok.size:
                j = int(ok[np.argmin(along[ok])])
                if best is None or along[j] < best[0]:
                    best = (float(along[j]), k, j)
        if best is None:
            return None
        if len(own) > 1 and float(np.linalg.norm(own - self.edges[best[1]]["pixels"][best[2]], axis=1).min()) < 1.0:
            return None
        return best[1], best[2], self.edges[best[1]]["pixels"][best[2]]

    def _split(self, edge: int, index: int, s: LineScale) -> int:
        """Node at pixel ``index`` of ``edge``: an end node within 8 px, else a new node splitting the edge."""
        e = self.edges[edge]
        pixels = e["pixels"]
        q = pixels[index]
        on_node = s.length(_ON_NODE_PX)
        for node in (e["a"], e["b"]):
            if float(np.linalg.norm(self.nodes[node] - q)) <= on_node:
                return node
        node = len(self.nodes)
        self.nodes.append(q.astype(float))
        first, second = pixels[:index + 1], pixels[index:]
        gaps1 = [(i, kind) for i, kind in e["gaps"] if i <= index]
        gaps2 = [(i - index, kind) for i, kind in e["gaps"] if i > index]
        share = _length(first) / max(_length(pixels), 1e-9)
        self.edges[edge] = {"pixels": first, "a": e["a"], "b": node, "gaps": gaps1,
                            "ink": e["ink"] * share, "gap": e["gap"] * share}
        self.edges.append({"pixels": second, "a": node, "b": e["b"], "gaps": gaps2,
                           "ink": e["ink"] * (1 - share), "gap": e["gap"] * (1 - share)})
        return node

    def to_frame(self, tri: np.ndarray, s: LineScale) -> None:
        """Free ends at (or pointing at) a triangle edge become edge points on it."""
        sides = [(tri[i], tri[(i + 1) % 3]) for i in range(3)]
        near = s.length(_EDGE_PX)
        for node, edge, end in self.free_ends():
            p, u = self.end(edge, end)
            long_line = _length(self.edges[edge]["pixels"]) >= s.length(_HIDDEN_MIN_PX)
            ahead = s.length(_TEXT_GAP_PX if long_line else _EDGE_AHEAD_PX)
            ray = near_side = None
            for side, (a, b) in enumerate(sides):
                foot, d = _foot(p, a, b)
                if d <= near and (near_side is None or d < near_side[0]):
                    near_side = (d, side, foot)
                cos = float(u @ (foot - p)) / d if d > 0 else 0.0
                if cos > 0:
                    t = d / cos
                    if t <= ahead and (ray is None or t < ray[0]):
                        ray = (t, side, _foot(p + u * t, a, b)[0])
            best = ray or near_side
            if best is None:
                continue
            _, side, foot = best
            e = self.edges[edge]
            new = len(self.nodes)
            self.nodes.append(foot.astype(float))
            self.kinds[new] = ("edge", side)
            if end == 0:
                e["pixels"] = np.vstack([foot, e["pixels"]])
                e["a"] = new
                e["gaps"] = [(i + 1, kind) for i, kind in e["gaps"]]
            else:
                e["pixels"] = np.vstack([e["pixels"], foot])
                e["b"] = new

    def drop_loose(self, min_px: float) -> None:
        degree = self.degree()
        for k in self.live():
            e = self.edges[k]
            loose = all(degree.get(n, 0) <= 2 and n not in self.kinds for n in (e["a"], e["b"])) and \
                (e["a"] == e["b"] or all(degree.get(n) == 1 for n in (e["a"], e["b"])))
            if loose and _length(e["pixels"]) < min_px:
                self.edges[k] = None

    def result(self, origin: np.ndarray, tri: np.ndarray) -> BoundaryGraph:
        degree = self.degree()
        used = sorted({n for k in self.live() for n in (self.edges[k]["a"], self.edges[k]["b"])})
        index = {n: i for i, n in enumerate(used)}
        nodes = []
        for n in used:
            kind, side = self.kinds.get(n, ("junction" if degree[n] >= 3 else "end", None))
            p = self.nodes[n] + origin
            nodes.append(BoundaryNode((float(p[0]), float(p[1])), kind, side))
        edges = []
        for k in self.live():
            e = self.edges[k]
            dash = sum(1 for _, kind in e["gaps"] if kind == "dash")
            length = e["ink"] + e["gap"]
            dashed = dash >= 2 and e["gap"] >= _DASHED_SHARE * length
            edges.append(BoundaryEdge(e["pixels"] + origin, (index[e["a"]], index[e["b"]]), list(e["gaps"]),
                                      float(e["ink"]), float(e["gap"]), dashed))
        return BoundaryGraph(nodes, edges)


def _oriented_gaps(edge: dict, reversed_: bool) -> list[tuple[int, str]]:
    if not reversed_:
        return list(edge["gaps"])
    n = len(edge["pixels"])
    return sorted((n - i, kind) for i, kind in edge["gaps"])


def _gap_kind(p1, u1, p2, u2, length1, length2, text, s: LineScale) -> str | None:
    delta = p2 - p1
    gap = float(np.linalg.norm(delta))
    if gap == 0:
        return "ink"
    lateral = max(s.length(_LATERAL_PX), _LATERAL_SHARE * gap)
    for p, u, q in ((p1, u1, p2), (p2, u2, p1)):
        d = q - p
        if float(u @ d) <= 0 or abs(float(u[0] * d[1] - u[1] * d[0])) > lateral:
            return None
    if gap <= s.length(_INK_GAP_PX):
        return "ink"
    if gap <= s.length(_DASH_GAP_PX) and min(length1, length2) <= s.length(_DASH_MAX_PX):
        return "dash"
    if _text_share(p1, p2, text) >= _TEXT_SHARE:
        return "text"
    v = delta / gap
    if min(length1, length2) >= s.length(_HIDDEN_MIN_PX) and min(float(u1 @ v), float(-u2 @ v)) >= _HIDDEN_COS:
        return "hidden"
    return None


def _heavy_strokes(mask: np.ndarray, distance: np.ndarray, low: float, high: float) -> np.ndarray:
    """Ink of the strokes whose ridge width (2 × distance to the background) lies in ``[low, high]``:
    each such ridge pixel claims the ink within its own half width (plus 1.5 px), so a thin line beside
    a heavy one stays out."""
    ridge = mask & (distance >= ndimage.maximum_filter(distance, size=3))
    keep = ridge & (2.0 * distance >= low) & (2.0 * distance <= high)
    away, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
    return mask & (away <= distance[iy, ix] + 1.5)


def _text_share(a: np.ndarray, b: np.ndarray, text: np.ndarray) -> float:
    n = max(2, int(float(np.linalg.norm(b - a)) / 2.0))
    samples = np.round(a + np.linspace(0.0, 1.0, n)[:, None] * (b - a)).astype(int)
    ok = (samples[:, 1] >= 0) & (samples[:, 1] < text.shape[0]) & (samples[:, 0] >= 0) & (samples[:, 0] < text.shape[1])
    samples = samples[ok]
    return float(text[samples[:, 1], samples[:, 0]].mean()) if samples.size else 0.0


def _foot(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    seg = b - a
    t = float(np.clip((p - a) @ seg / max(float(seg @ seg), 1e-12), 0.0, 1.0))
    foot = a + t * seg
    return foot, float(np.linalg.norm(p - foot))


def _length(pixels: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(pixels, axis=0), axis=1).sum()) if len(pixels) > 1 else 0.0


def _polygon(shape: tuple[int, ...], tri: np.ndarray) -> np.ndarray:
    image = Image.new("1", (shape[1], shape[0]), 0)
    ImageDraw.Draw(image).polygon([tuple(p) for p in tri], fill=1)
    return np.array(image, dtype=bool)


def _frame(shape: tuple[int, ...], tri: np.ndarray, width: int) -> np.ndarray:
    image = Image.new("1", (shape[1], shape[0]), 0)
    ImageDraw.Draw(image).line([*(tuple(p) for p in tri), tuple(tri[0])], fill=1, width=width)
    return np.array(image, dtype=bool)
