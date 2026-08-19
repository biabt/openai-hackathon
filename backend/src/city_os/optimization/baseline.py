"""Competent deterministic static weighted p-median baseline."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable, Sequence

from .reposition import Allocation, DemandPoint, Node, normalized_demand

Travel = Callable[[Node, Node], float]


def _key(value: Hashable) -> str:
    return repr(value)


def static_p_median(
    candidates: Sequence[Node],
    demand: Iterable[DemandPoint | tuple[Node, float]],
    fleet_size: int,
    travel: Travel,
) -> Allocation:
    """Greedily minimize weighted nearest-unit travel time.

    Repeated nodes are intentionally allowed: they encode multiple ambulances at a
    strong demand center and make the result exactly match the requested fleet.
    """
    if fleet_size <= 0:
        raise ValueError("fleet_size must be positive")
    points = normalized_demand(demand)
    eligible = tuple(
        sorted(
            {
                candidate
                for candidate in candidates
                if any(math.isfinite(travel(candidate, point.node)) for point in points)
            },
            key=_key,
        )
    )
    if not eligible:
        raise ValueError("no candidate can reach forecast demand")

    def cost(positions: tuple[Node, ...]) -> float:
        return sum(
            point.weight * min(travel(position, point.node) for position in positions)
            for point in points
        )

    positions: tuple[Node, ...] = ()
    for _ in range(fleet_size):
        positions += (
            min(eligible, key=lambda candidate: (cost(positions + (candidate,)), _key(candidate))),
        )
    return Allocation(positions=positions, objective=cost(positions))
