"""
source_extract.diagrams.validation.inferred_temperature_check — Arithmetic check of an isotherm temperature inferred from labelled neighbours or from bounds.
"""
from __future__ import annotations

_TOLERANCE = 1e-6


def inferred_temperature_problem(temperature, inferred) -> str | None:
    """Why ``inferred`` does not give ``temperature``, or None.

    ``{"from": [anchor °C, …], "step": °C}``: ``from`` holds one or two labelled isotherm
    temperatures of the same field and ``step`` the interval between neighbouring lines: the
    temperature is a whole, non-zero number of steps from each anchor and, with two anchors,
    strictly between them (which then are a whole number of steps apart).

    ``{"between": [low °C, high °C], "step": °C}`` (no labelled isotherm in the field, the
    order of the lines along boundaries gives the bounds, usually invariant temperatures):
    the temperature is a whole number of steps and strictly between ``low`` and ``high``.
    """
    if not isinstance(inferred, dict):
        return "inferred must be an object with from (or between) and step"
    anchors, bounds, step = inferred.get("from"), inferred.get("between"), inferred.get("step")
    if not isinstance(temperature, (int, float)):
        return "an inferred isotherm needs a numeric temperature_C"
    if not isinstance(step, (int, float)) or step <= 0:
        return "inferred.step must be a positive number"
    if (anchors is None) == (bounds is None):
        return "inferred needs exactly one of from and between"
    if bounds is not None:
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(b, (int, float)) for b in bounds) or bounds[0] >= bounds[1]):
            return "inferred.between must be [low, high] with low < high"
        steps = temperature / step
        if abs(steps - round(steps)) > _TOLERANCE:
            return f"{temperature:g} °C is not a whole number of {step:g} °C steps"
        if not bounds[0] < temperature < bounds[1]:
            return f"{temperature:g} °C is not between {bounds[0]:g} and {bounds[1]:g} °C"
        return None
    if (not isinstance(anchors, list) or len(anchors) not in (1, 2)
            or any(not isinstance(a, (int, float)) for a in anchors)):
        return "inferred.from must list one or two labelled temperatures"
    for anchor in anchors:
        steps = (temperature - anchor) / step
        if abs(steps - round(steps)) > _TOLERANCE or round(steps) == 0:
            return f"{temperature:g} °C is not a whole, non-zero number of {step:g} °C steps from {anchor:g} °C"
    if len(anchors) == 2 and not min(anchors) < temperature < max(anchors):
        return f"{temperature:g} °C is not between {anchors[0]:g} and {anchors[1]:g} °C"
    return None
