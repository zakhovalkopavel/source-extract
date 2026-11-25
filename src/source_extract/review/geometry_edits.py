"""Geometry edit operations applied to a draft dict (points / polylines)."""

from __future__ import annotations

import copy
from typing import Any


class GeometryEdits:
    """Pure transforms used by the review API."""

    @staticmethod
    def move_point(draft: dict[str, Any], path: list[Any], new_xy: Any) -> dict[str, Any]:
        out = copy.deepcopy(draft)
        node: Any = out
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = new_xy
        return out

    @staticmethod
    def undo_stack_push(stack: list[dict[str, Any]], snapshot: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        next_stack = [*stack, snapshot]
        return next_stack[-limit:]
