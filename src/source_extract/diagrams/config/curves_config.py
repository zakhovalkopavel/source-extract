"""
source_extract.diagrams.config.curves_config — Ternary curves config (configs/<system>.curves.config.json).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.constants.boundary_arrows import BOUNDARY_ARROWS
from source_extract.diagrams.validation.inferred_temperature_check import inferred_temperature_problem

def _pixel(value, nodes: dict[str, tuple[float, float]] | None = None) -> tuple[float, float]:
    if isinstance(value, str):
        if not nodes or value not in nodes:
            raise ValueError(f"unknown node label '{value}'")
        return nodes[value]
    return float(value[0]), float(value[1])


def _waypoint(value, nodes: dict[str, tuple[float, float]]) -> dict:
    if isinstance(value, dict):
        return {"pixel": _pixel(value["pixel"], nodes), "straight": bool(value.get("straight", False)),
                "split": bool(value.get("split", False))}
    return {"pixel": _pixel(value, nodes), "straight": False, "split": False}


def _width(value) -> tuple[float, float] | None:
    return None if value is None else (float(value[0]), float(value[1]))


def _arrows(entry: dict) -> list[str] | None:
    value = entry.get("arrows")
    if value is None:
        return None
    segments = len(entry["path"]) - 1 + (1 if entry.get("endPixel") else 0)
    if not isinstance(value, list) or len(value) != segments or any(v not in BOUNDARY_ARROWS for v in value):
        raise ValueError(f"curve {entry['fields']} {entry['path']}: arrows must give one of "
                         f"{' '.join(BOUNDARY_ARROWS)} per segment ({segments})")
    return list(value)


def _inferred(entry: dict) -> dict | None:
    value = entry.get("inferred")
    if value is None:
        return None
    problem = inferred_temperature_problem(entry["temperature_C"], value)
    if problem:
        raise ValueError(f"isotherm {entry['field']} {entry['temperature_C']}: {problem}")
    key = "from" if "from" in value else "between"
    return {key: list(value[key]), "step": value["step"]}


def _invariant(entry: dict, nodes: dict[str, tuple[float, float]]) -> dict:
    if not entry.get("new"):
        raise ValueError(f"invariant {entry.get('id')}: config invariants are only appended (set \"new\": true); "
                         "change an existing point with edits")
    return {
        "id": entry["id"],
        "type": entry["type"],
        "reaction": entry.get("reaction"),
        "phases": list(entry["phases"]),
        "temperature_C": entry.get("temperature_C"),
        "pixel": _pixel(entry["pixel"], nodes),
        "temperature": entry.get("temperature", "not printed"),
        "composition": entry.get("composition", "digitized"),
        "new": True,
        "notes": entry.get("notes"),
    }


@dataclass
class CurvesConfig:
    """Tracing hints for the boundary curves, isotherms, inversion curves and liquid-immiscibility branches of one ternary file.

    Each entry carries ``strokeWidth_px``: its own width range, or the config
    default (``strokeWidth_px`` for curves, inversions and immiscibility branches,
    ``isothermStrokeWidth_px`` for isotherms). A curve ``endPixel`` (or ``None``)
    is an open end after the last path point, where the curve leaves the figure.
    Isotherms, inversions and immiscibility branches run from ``startPixel`` to
    ``endPixel``. Waypoints are
    ``{"pixel": (x, y), "straight": bool, "split": bool}``; a straight waypoint is joined to the
    previous point by a straight line (stroke hidden by a label) instead of traced;
    an isotherm is split at a ``split`` waypoint (a field edge the detector misses).
    Any pixel may be given as a label of the ``nodes`` map (node-map labels).
    Entries with ``new`` (and ``notes``; inversions also ``temperature_C`` and
    ``source``) are appended to the system file; ``edits`` are
    ``{"path", "pixel" or None, "set", "remove" or None}`` structure edits applied before tracing
    (``remove``: the keys an element of the list at ``path`` must have to be removed).
    ``frame_mask_px`` > 0 erases a band of that width along the triangle edges
    from the tracing mask. ``line_width_px`` (``lineWidth_px``) replaces the measured
    line width of the page (pixel scale); None = measure it. Any entry may set ``dashed``: traced on the dashes only.
    An isotherm drawn as several pieces in one field sets ``part`` (2, 3, …; default 1)
    on every piece after the first; the system file entry carries the same ``part``.
    ``fields`` (review overlay only) are ``{"name", "legend", "ring": [pixels], "seed": pixel or None}``;
    ``name`` is drawn in the field, ``legend`` (default: the name) in the legend.
    A curve ``arrows`` (or None) gives the printed arrow of each path segment, plus
    one for an open end: ``>`` towards the next path point, ``<`` towards the previous
    one, ``<>`` pointing away from a maximum inside the segment, ``?`` not readable;
    it is written to the boundary curve of the system file.
    An isotherm without a printed temperature sets ``inferred``
    ``{"from": [labelled °C, …], "step": °C}`` (one or two labelled isotherms of the field
    and the interval between lines; checked by ``inferred_temperature_problem``), or
    ``{"between": [low °C, high °C], "step": °C}`` when only the order of the lines along
    boundaries bounds it (``detect-isotherms``); a ``new`` entry carries it into the system file.
    ``invariants`` are new invariant points (``new`` required): ``id``, ``type``,
    ``reaction``, ``phases``, ``temperature_C`` (None when not printed), ``pixel``
    and the source reading texts ``temperature`` and ``composition``; the
    composition is computed from the pixel when the point is appended.
    """

    system_file: str
    pdf_page: int
    pixel_origin: tuple[float, float]
    stroke_width_px: tuple[float, float]
    endpoint_pixels: dict[str, tuple[float, float]]
    curves: list[dict] = field(default_factory=list)
    isotherms: list[dict] = field(default_factory=list)
    inversions: list[dict] = field(default_factory=list)
    invariants: list[dict] = field(default_factory=list)
    liquid_immiscibility: list[dict] = field(default_factory=list)
    edits: list[dict] = field(default_factory=list)
    fields: list[dict] = field(default_factory=list)
    nodes: dict[str, tuple[float, float]] = field(default_factory=dict)
    frame_mask_px: float = 0.0
    line_width_px: float | None = None
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict, name: str = "") -> "CurvesConfig":
        width = _width(data.get("strokeWidth_px", [3.5, 9]))
        isotherm_width = _width(data.get("isothermStrokeWidth_px")) or width
        nodes = {k: _pixel(v) for k, v in data.get("nodes", {}).items()}

        def pixel(value) -> tuple[float, float]:
            return _pixel(value, nodes)

        def waypoints(entry: dict) -> list[dict]:
            return [_waypoint(p, nodes) for p in entry.get("waypoints", [])]

        curves = [
            {
                "fields": list(c["fields"]),
                "path": list(c["path"]),
                "waypoints": waypoints(c),
                "endPixel": pixel(c["endPixel"]) if c.get("endPixel") else None,
                "arrows": _arrows(c),
                "strokeWidth_px": _width(c.get("strokeWidth_px")) or width,
                "dashed": bool(c.get("dashed", False)),
                "new": bool(c.get("new", False)),
                "notes": c.get("notes"),
            }
            for c in data.get("curves", [])
        ]
        isotherms = [
            {
                "field": i["field"],
                "temperature_C": i["temperature_C"],
                "inferred": _inferred(i),
                "part": int(i.get("part", 1)),
                "startPixel": pixel(i["startPixel"]),
                "endPixel": pixel(i["endPixel"]),
                "waypoints": waypoints(i),
                "strokeWidth_px": _width(i.get("strokeWidth_px")) or isotherm_width,
                "dashed": bool(i.get("dashed", False)),
                "new": bool(i.get("new", False)),
                "notes": i.get("notes"),
            }
            for i in data.get("isotherms", [])
        ]
        inversions = [
            {
                "phase": v["phase"],
                "change": v["change"],
                "startPixel": pixel(v["startPixel"]),
                "endPixel": pixel(v["endPixel"]),
                "waypoints": waypoints(v),
                "strokeWidth_px": _width(v.get("strokeWidth_px")) or width,
                "dashed": bool(v.get("dashed", False)),
                "new": bool(v.get("new", False)),
                "notes": v.get("notes"),
                "temperature_C": v.get("temperature_C"),
                "source": v.get("source"),
            }
            for v in data.get("inversions", [])
        ]
        fields = [
            {"name": f["name"], "legend": f.get("legend") or f["name"], "ring": [pixel(p) for p in f.get("ring", [])],
             "seed": pixel(f["seed"]) if f.get("seed") is not None else None}
            for f in data.get("fields", [])
        ]
        edits = [
            {"path": e["path"], "pixel": pixel(e["pixel"]) if e.get("pixel") is not None else None, "set": dict(e.get("set", {})),
             "remove": dict(e["remove"]) if e.get("remove") is not None else None}
            for e in data.get("edits", [])
        ]
        for edit in edits:
            if edit["remove"] is not None and (edit["set"] or edit["pixel"] is not None or not edit["remove"]):
                raise ValueError(f"{name}: edit {edit['path']}: 'remove' takes the keys to match and no 'set' or 'pixel'")
        liquid_immiscibility = [
            {
                "startPixel": pixel(b["startPixel"]),
                "endPixel": pixel(b["endPixel"]),
                "waypoints": waypoints(b),
                "strokeWidth_px": _width(b.get("strokeWidth_px")) or width,
                "dashed": bool(b.get("dashed", False)),
            }
            for b in data.get("liquidImmiscibility", [])
        ]
        return cls(
            system_file=data["systemFile"],
            pdf_page=int(data["pdfPage"]),
            pixel_origin=_pixel(data.get("pixelOrigin", [0, 0])),
            stroke_width_px=width,
            endpoint_pixels={k: pixel(v) for k, v in data.get("endpointPixels", {}).items()},
            curves=curves,
            isotherms=isotherms,
            inversions=inversions,
            invariants=[_invariant(v, nodes) for v in data.get("invariants", [])],
            liquid_immiscibility=liquid_immiscibility,
            edits=edits,
            fields=fields,
            nodes=nodes,
            frame_mask_px=float(data.get("frameMask_px", 0)),
            line_width_px=float(data["lineWidth_px"]) if data.get("lineWidth_px") is not None else None,
            name=name,
        )
