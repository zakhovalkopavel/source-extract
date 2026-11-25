"""Parameter type enumeration for ParamSpec."""

from __future__ import annotations

from enum import Enum


class ParamType(str, Enum):
    """Supported ParamSpec value types (CLI / OpenAPI / GUI)."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    PATH = "path"
    ENUM = "enum"
    STRING_LIST = "string_list"
    INTEGER_LIST = "integer_list"
