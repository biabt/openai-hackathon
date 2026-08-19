from __future__ import annotations

import math

import pytest

from city_os.optimization import (
    AmbulanceSnapshot,
    DemandPoint,
    FleetSnapshot,
    OptimizationConfig,
    optimize_positions,
    static_p_median,
)


def travel(a: int, b: int) -> float:
    if a == 99:
        return math.inf
    return abs(a - b)


def test_static_baseline_is_deterministic_and_preserves_multiplicity() -> None:
    demand = [(0, 10.0), (10, 1.0)]
    one = static_p_median([99, 10, 0], demand, 3, travel)
    two = static_p_median([0, 10, 99], demand, 3, travel)
    assert one == two
    assert one.fleet_size == 3
    assert sum(one.counts.values()) == 3
    assert 99 not in one.positions


def test_optimizer_reduces_tail_risk_and_filters_unreachable_candidates() -> None:
    snapshot = FleetSnapshot((AmbulanceSnapshot("a", 0, dwell_minutes=30),))
    result = optimize_positions(
        snapshot,
        [DemandPoint(10, 1), DemandPoint(9, 1)],
        [99, 0, 10],
        OptimizationConfig(travel=travel, minimum_dwell_minutes=0),
    )
    assert result.positions == (10,)
    assert result.moved == ("a",)


@pytest.mark.parametrize(
    "unit",
    [
        AmbulanceSnapshot("a", 0, available=False, dwell_minutes=30),
        AmbulanceSnapshot("a", 0, dispatched=True, dwell_minutes=30),
        AmbulanceSnapshot("a", 0, dwell_minutes=2),
    ],
)
def test_anti_thrashing_excludes_units(unit: AmbulanceSnapshot) -> None:
    result = optimize_positions(
        FleetSnapshot((unit,)),
        [(10, 1)],
        [0, 10],
        OptimizationConfig(travel=travel, minimum_dwell_minutes=15),
    )
    assert result.positions == (0,)
    assert not result.moved


def test_move_limit_and_improvement_threshold_prevent_small_repositions() -> None:
    snapshot = FleetSnapshot((AmbulanceSnapshot("a", 0, dwell_minutes=30),))
    limited = optimize_positions(
        snapshot,
        [(10, 1)],
        [0, 10],
        OptimizationConfig(travel=travel, maximum_move_distance=5),
    )
    threshold = optimize_positions(
        snapshot,
        [(10, 1)],
        [0, 10],
        OptimizationConfig(travel=travel, improvement_threshold=10),
    )
    assert limited.positions == threshold.positions == (0,)


def test_equity_and_reposition_penalties_are_in_objective() -> None:
    snapshot = FleetSnapshot((AmbulanceSnapshot("a", 0, dwell_minutes=30),))
    result = optimize_positions(
        snapshot,
        [DemandPoint(0, 1, "west"), DemandPoint(10, 1, "east")],
        [0, 5, 10],
        OptimizationConfig(travel=travel, alpha=0, equity_penalty=2, reposition_penalty=0.1),
    )
    assert result.positions == (5,)
    assert result.objective == pytest.approx(5.5)
