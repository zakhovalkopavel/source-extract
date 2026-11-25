"""Single tunable parameter declaration shared by CLI, API, and GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_extract.params.param_type import ParamType


@dataclass(frozen=True)
class ParamSpec:
    """One command parameter with metadata for forms and OpenAPI."""

    name: str
    param_type: ParamType
    description: str = ""
    default: Any = None
    required: bool = False
    choices: tuple[Any, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    group: str = "basic"
    advanced: bool = False
    positional: bool = False
    cli_flags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.param_type.value,
            "description": self.description,
            "default": self.default,
            "required": self.required,
            "choices": list(self.choices) if self.choices else None,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "group": self.group,
            "advanced": self.advanced,
            "positional": self.positional,
            "cliFlags": list(self.cli_flags),
        }
