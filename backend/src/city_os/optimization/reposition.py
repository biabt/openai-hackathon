"""Small, simulator-independent value objects for placement decisions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

Node = Hashable


@dataclass(frozen=True, slots=True)
class DemandPoint:
    node: Node
    weight: float = 1.0
    district: str = ""

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("demand weight must be non-negative")


@dataclass(frozen=True, slots=True)
class AmbulanceSnapshot:
    ambulance_id: str
    node: Node
    available: bool = True
    dispatched: bool = False
    dwell_minutes: float = 0.0


@dataclass(frozen=True, slots=True)
class FleetSnapshot:
    ambulances: tuple[AmbulanceSnapshot, ...]


@dataclass(frozen=True, slots=True)
class Allocation:
    """One target node per ambulance; duplicates represent fleet multiplicity."""

    positions: tuple[Node, ...]
    objective: float = 0.0
    moved: tuple[str, ...] = ()

    @property
    def counts(self) -> dict[Node, int]:
        return dict(Counter(self.positions))

    @property
    def fleet_size(self) -> int:
        return len(self.positions)


def normalized_demand(
    demand: Iterable[DemandPoint | tuple[Node, float]],
) -> tuple[DemandPoint, ...]:
    points = tuple(
        item if isinstance(item, DemandPoint) else DemandPoint(node=item[0], weight=float(item[1]))
        for item in demand
    )
    if not points:
        raise ValueError("demand must not be empty")
    return points
