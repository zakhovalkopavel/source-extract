"""
source_extract.diagrams.config.invariant_spec — One invariant point in a binary config.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InvariantSpec:
    """Printed values and seed pixels of an invariant.

    ``label_composition`` is wt% of the x component; ``None`` = not printed
    (digitized value used and flagged; for ``compound-melting`` a stoichiometric
    composition supplied by the host catalog is used).
    ``label_temperature`` ``None`` = not printed: the detected invariant line,
    else the junction pixel, gives the temperature (flagged). Not allowed for
    ``compound-melting``.
    ``external_ids`` are optional host cross-check entry ids (e.g. a bibliography
    index); the library does not interpret them.
    """

    id: str
    type: str
    reaction: str | None
    phases: list[str]
    label_temperature: float | None
    label_composition: float | None
    seed_pixel: tuple[float, float]
    external_ids: list[int] = field(default_factory=list)
    notes: str | None = None
    label_second_composition: float | None = None
    second_seed_pixel: tuple[float, float] | None = None
    label_box: tuple[int, int, int, int] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "InvariantSpec":
        label = data["label"]
        seed = data["seedPixel"]
        second = data.get("secondSeedPixel")
        box = data.get("labelBox")
        external = data.get(
            "externalIds",
            data.get("external_ids", data.get("nbs", [])),
        )
        return cls(
            id=data["id"],
            type=data["type"],
            reaction=data.get("reaction"),
            phases=list(data["phases"]),
            label_temperature=label.get("temperature"),
            label_composition=label.get("composition"),
            seed_pixel=(float(seed[0]), float(seed[1])),
            external_ids=[int(n) for n in external],
            notes=data.get("notes"),
            label_second_composition=label.get("secondComposition"),
            second_seed_pixel=(float(second[0]), float(second[1])) if second else None,
            label_box=tuple(int(v) for v in box) if box else None,
        )
