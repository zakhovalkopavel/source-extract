"""
source_extract.diagrams.models.compound_point — A compound ring of a ternary figure with its compound and temperature.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompoundPoint:
    """``pixel`` is a page pixel; ``wt`` follows the system ``components``.

    ``tag`` is written next to the ring: the compound ``notation``, else the node label.
    ``temperature_C`` is that of the system invariant on the ring (``invariant``), else the
    compound's melting point (``behaviour`` congruent / incongruent), else None.
    """

    tag: str
    pixel: tuple[float, float]
    wt: list[float]
    compound: str | None = None
    formula: str | None = None
    temperature_C: float | None = None
    behaviour: str | None = None
    invariant: str | None = None

    def legend(self) -> str:
        """``NS  Na2O·SiO2, sodium-metasilicate (1088 °C)``; the composition when no compound matches."""
        composition = " / ".join(f"{max(v, 0.0):.1f}" for v in self.wt) + " wt%"
        if self.compound:
            name = f"{self.formula}, {self.compound}" if self.formula else self.compound
        elif self.invariant:
            return f"{self.tag}  point {self.invariant}, {composition} ({self.temperature_C:g} °C)"
        else:
            name = f"{composition}, no compound of the system"
        if self.temperature_C is None:
            return f"{self.tag}  {name} (no temperature)"
        extra = f", {self.invariant}" if self.invariant else (f", {self.behaviour}" if self.behaviour == "incongruent" else "")
        return f"{self.tag}  {name} ({self.temperature_C:g} °C{extra})"
