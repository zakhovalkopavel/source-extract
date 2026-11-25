"""Validate resolved parameter dicts against ParamSpec lists."""

from __future__ import annotations

from typing import Any

from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType


class ParamValidator:
    """Stateless validation of command parameter payloads."""

    @staticmethod
    def validate(specs: list[ParamSpec], values: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        by_name = {s.name: s for s in specs}
        for name, value in values.items():
            if name not in by_name:
                raise ValueError(f"Unknown parameter: {name}")
            resolved[name] = ParamValidator._coerce(by_name[name], value)
        for spec in specs:
            if spec.name in resolved:
                continue
            if spec.required and spec.default is None:
                raise ValueError(f"Missing required parameter: {spec.name}")
            if spec.default is not None:
                resolved[spec.name] = spec.default
        return resolved

    @staticmethod
    def _coerce(spec: ParamSpec, value: Any) -> Any:
        if value is None:
            return None
        if spec.param_type == ParamType.BOOLEAN:
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"1", "true", "yes", "on"}
        if spec.param_type == ParamType.INTEGER:
            return int(value)
        if spec.param_type == ParamType.NUMBER:
            return float(value)
        if spec.param_type == ParamType.ENUM and spec.choices is not None:
            if value not in spec.choices:
                raise ValueError(f"{spec.name} must be one of {spec.choices}")
            return value
        if spec.param_type == ParamType.INTEGER_LIST:
            if isinstance(value, str):
                return [int(x) for x in value.replace(",", " ").split()]
            return [int(x) for x in value]
        if spec.param_type == ParamType.STRING_LIST:
            if isinstance(value, str):
                return value.split()
            return list(value)
        return value
