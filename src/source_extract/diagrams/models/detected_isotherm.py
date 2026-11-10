"""
source_extract.diagrams.models.detected_isotherm — An isotherm found on the page by the isotherm detector, with its evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.models.review_item import ReviewItem

_WAYPOINT_PX = 60.0
_END_CLEARANCE_PX = 15.0


@dataclass
class DetectedIsotherm:
    """One isotherm piece inside one field (page pixels).

    ``pixels`` run from ``start`` to ``end`` (ends moved onto the boundary or edge they meet);
    ``straight`` holds the indices ``k`` where ``pixels[k - 1] → pixels[k]`` crosses a label
    printed in the line. ``ends`` describe each end (``boundary <fields>``, ``edge``, ``label``,
    ``free``). ``group`` is shared by the pieces of one line continuing across boundaries.
    ``temperature_C`` comes from ``source``: ``label`` (read on this piece), ``continuation``
    (read on a piece of the same group), ``boundary order`` (the order of the crossings along
    boundaries between invariants of known temperature), or None with ``candidates``.
    ``inferred`` is the config ``inferred`` object of a temperature that is not printed on the line.
    """

    field: str
    pixels: list[tuple[float, float]]
    straight: list[int] = field(default_factory=list)
    ends: tuple[str, str] = ("free", "free")
    dashed: bool = False
    group: int = 0
    temperature_C: float | None = None
    source: str | None = None
    label: str | None = None
    candidates: list[float] = field(default_factory=list)
    inferred: dict | None = None
    evidence: list[str] = field(default_factory=list)

    @property
    def start(self) -> tuple[float, float]:
        return self.pixels[0]

    @property
    def end(self) -> tuple[float, float]:
        return self.pixels[-1]

    def config_entry(self, origin: tuple[float, float] = (0.0, 0.0)) -> dict:
        """Isotherm entry of a curves config (stored pixels: page pixels − ``origin``), waypoints every
        ~60 px of line and at both sides of each label gap (the far side ``straight``)."""
        def stored(p) -> list[int]:
            return [int(round(p[0] - origin[0])), int(round(p[1] - origin[1]))]

        waypoints: list = []
        travelled = 0.0
        last = self.pixels[0]
        straight = set(self.straight)
        for k in range(1, len(self.pixels) - 1):
            p = self.pixels[k]
            travelled += ((p[0] - self.pixels[k - 1][0]) ** 2 + (p[1] - self.pixels[k - 1][1]) ** 2) ** 0.5
            clear = min(_distance(p, self.pixels[0]), _distance(p, self.pixels[-1])) >= _END_CLEARANCE_PX
            if k + 1 in straight and clear:
                waypoints.append(stored(p))
                travelled, last = 0.0, p
            elif k in straight:
                waypoints.append({"pixel": stored(p), "straight": True})
                travelled, last = 0.0, p
            elif travelled >= _WAYPOINT_PX and clear and _distance(p, last) >= _END_CLEARANCE_PX:
                waypoints.append(stored(p))
                travelled, last = 0.0, p
        entry: dict = {"field": self.field, "temperature_C": self.temperature_C, "new": True}
        if self.inferred is not None:
            entry["inferred"] = self.inferred
        if self.dashed:
            entry["dashed"] = True
        entry["startPixel"] = stored(self.start)
        entry["endPixel"] = stored(self.end)
        if waypoints:
            entry["waypoints"] = waypoints
        entry["notes"] = "; ".join(self.evidence)
        return entry

    def review_items(self) -> list[ReviewItem]:
        name = f"isotherm {self.field} {_temperature(self)}"
        if self.temperature_C is None:
            options = ", ".join(f"{t:g}" for t in self.candidates) or "no candidate"
            return [ReviewItem("isotherm-temperature", name, f"temperature not determined ({options}); "
                                                             f"{_px(self.start)}→{_px(self.end)}")]
        return []


def _temperature(item: DetectedIsotherm) -> str:
    return "?" if item.temperature_C is None else f"{item.temperature_C:g}"


def _distance(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _px(p) -> str:
    return f"({p[0]:.0f}, {p[1]:.0f})"
