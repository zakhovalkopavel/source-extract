"""CommandSpec — one operation with ParamSpecs and a runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_validator import ParamValidator

CommandRunner = Callable[[dict[str, Any]], int]


@dataclass
class CommandSpec:
    """One SE command; CLI flags, OpenAPI, and GUI forms share ``params``."""

    command_id: str
    title: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    adapter_id: str | None = None
    family: str = "general"
    run: CommandRunner | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.command_id,
            "title": self.title,
            "description": self.description,
            "family": self.family,
            "adapterId": self.adapter_id,
            "params": [p.to_dict() for p in self.params],
        }

    def execute(self, raw_params: dict[str, Any]) -> int:
        resolved = ParamValidator.validate(self.params, raw_params)
        if self.run is None:
            raise RuntimeError(f"Command {self.command_id!r} has no runner")
        return self.run(resolved)
