"""
source_extract.diagrams.builders.isotherm_temperature_solver — Isotherm temperatures from read labels, the order of the lines along boundaries and their order across fields.
"""
from __future__ import annotations

import math

_MAX_C = 4000.0


def solve_isotherm_temperatures(
    group_count: int,
    labels: dict[int, float],
    ladders: list[tuple[list[int], float, float]],
    step_C: float,
    chains: list[list[int]] | None = None,
) -> tuple[list[list[float]], list[int], list[int]]:
    """Possible temperatures of each isotherm group (lines continuing across boundaries share a group).

    Every group starts with the multiples of ``step_C`` up to 4000 °C, a group in ``labels`` with
    its read value. A ladder ``(groups, low, high)`` lists the groups crossing one boundary stretch
    between two points of known temperature, in order from the ``low`` end to the ``high`` end
    (the liquidus rises monotonically along the stretch): each lies strictly between ``low`` and
    ``high`` and strictly above the previous one. Ladders are added one at a time, longest first,
    each propagated with the ones already accepted until nothing changes; a ladder that leaves a
    group without any temperature (a line crossing the stretch twice, or one end of a line put on
    the wrong boundary) is rejected.
    ``chains`` (neighbouring lines in order across a field) are added after the ladders, longest
    first, in the same way: each line one ``step_C`` from the previous one, all rising or all falling.
    Returns the sorted options per group (one = determined), the indices of the rejected ladders and
    of the rejected chains.
    """
    every = [step_C * k for k in range(1, int(_MAX_C // step_C) + 1)]
    domains: list[set[float]] = [{labels[g]} if g in labels else set(every) for g in range(group_count)]
    accepted: list[tuple[list[int], float, float]] = []
    rejected: list[int] = []
    for index in sorted(range(len(ladders)), key=lambda k: -len(ladders[k][0])):
        groups = ladders[index][0]
        if len(set(groups)) != len(groups):
            rejected.append(index)
            continue
        trial = _propagate([set(d) for d in domains], accepted + [ladders[index]], [], step_C)
        if any(not d for d in trial):
            rejected.append(index)
            continue
        accepted.append(ladders[index])
        domains = trial
    chains = chains or []
    kept: list[list[int]] = []
    dropped: list[int] = []
    for index in sorted(range(len(chains)), key=lambda k: -len(chains[k])):
        trial = _propagate([set(d) for d in domains], accepted, kept + [chains[index]], step_C)
        if any(not d for d in trial):
            dropped.append(index)
            continue
        kept.append(chains[index])
        domains = trial
    return [sorted(d) for d in domains], sorted(rejected), sorted(dropped)


def _propagate(domains: list[set[float]], ladders: list[tuple[list[int], float, float]],
               chains: list[list[int]], step_C: float) -> list[set[float]]:
    changed = True
    while changed:
        changed = False
        for groups, low, high in ladders:
            previous = -math.inf
            for g in groups:
                kept = {t for t in domains[g] if low < t < high and t > previous}
                if kept != domains[g]:
                    domains[g], changed = kept, True
                previous = min(kept, default=math.inf)
            following = math.inf
            for g in reversed(groups):
                kept = {t for t in domains[g] if t < following}
                if kept != domains[g]:
                    domains[g], changed = kept, True
                following = max(kept, default=-math.inf)
            if any(not domains[g] for g in groups):
                return domains
        for groups in chains:
            feasible: dict[int, set[float]] = {g: set() for g in groups}
            for delta in (step_C, -step_C):
                base: set[float] | None = None
                for k, g in enumerate(groups):
                    shifted = {t - k * delta for t in domains[g]}
                    base = shifted if base is None else base & shifted
                for t0 in base or set():
                    for k, g in enumerate(groups):
                        feasible[g].add(t0 + k * delta)
            for g in groups:
                kept = domains[g] & feasible[g]
                if kept != domains[g]:
                    domains[g], changed = kept, True
            if any(not domains[g] for g in groups):
                return domains
    return domains
