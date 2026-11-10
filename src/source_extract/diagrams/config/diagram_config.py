"""
source_extract.diagrams.config.diagram_config — Binary diagram config (configs/<system>.config.json).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.config.invariant_spec import InvariantSpec
from source_extract.diagrams.config.liquidus_branch_spec import LiquidusBranchSpec


@dataclass
class DiagramConfig:
    """Everything a person reads or decides for one binary diagram."""

    system: str
    components: list[str]
    output: str
    id_prefix: str
    source: dict
    frame_search_box: tuple[int, int, int, int]
    x_component: str
    x_ticks: list[float]
    y_ticks: list[float]
    phases: list[str]
    end_members: dict[str, tuple[float, float]]
    invariants: list[InvariantSpec]
    liquidus: list[LiquidusBranchSpec]
    x_tick_pixels: list[float] | None = None
    y_tick_pixels: list[float] | None = None
    liquid_immiscibility: dict | None = None
    junction_tolerance_wt: float = 1.5
    stroke_width_px: tuple[float, float] | None = None
    verbatim: dict = field(default_factory=dict)
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict, name: str = "") -> "DiagramConfig":
        axes = data["axes"]
        return cls(
            system=data["system"],
            components=list(data["components"]),
            output=data["output"],
            id_prefix=data["idPrefix"],
            source=dict(data["source"]),
            frame_search_box=tuple(int(v) for v in data["frameSearchBox"]),
            x_component=axes["x"]["component"],
            x_ticks=list(axes["x"]["ticks"]),
            y_ticks=list(axes["y"]["ticks"]),
            x_tick_pixels=axes["x"].get("tickPixels"),
            y_tick_pixels=axes["y"].get("tickPixels"),
            phases=list(data["phases"]),
            end_members={
                phase: (value["x"], value["labelTemperature"]) for phase, value in data["endMembers"].items()
            },
            invariants=[InvariantSpec.from_dict(i) for i in data["invariants"]],
            liquidus=[LiquidusBranchSpec.from_dict(b) for b in data["liquidus"]],
            liquid_immiscibility=data.get("liquidImmiscibility"),
            junction_tolerance_wt=float(data.get("junctionTolerance_wt", 1.5)),
            stroke_width_px=(
                (float(data["strokeWidth_px"][0]), float(data["strokeWidth_px"][1]))
                if data.get("strokeWidth_px") else None
            ),
            verbatim=dict(data.get("verbatim", {})),
            name=name,
        )

    @property
    def pdf_page(self) -> int:
        return int(self.source["pdfPage"])

    @property
    def ref(self) -> str:
        return self.source["ref"]

    @property
    def other_component(self) -> str:
        return next(c for c in self.components if c != self.x_component)

    def invariant(self, invariant_id: str) -> InvariantSpec:
        for spec in self.invariants:
            if spec.id == invariant_id:
                return spec
        raise KeyError(f"unknown invariant '{invariant_id}'")
