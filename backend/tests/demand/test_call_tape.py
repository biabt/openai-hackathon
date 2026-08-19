from datetime import UTC, datetime

from city_os.contracts.api import ScenarioObservation, ScenarioSource, ScenarioType
from city_os.demand import generate_call_tape

CELL_A = "88a8100c05fffff"
CELL_B = "88a8100c07fffff"


def _density(intensity: float = 24.0) -> list[dict[str, object]]:
    start = datetime(2026, 8, 19, 17, 0, tzinfo=UTC)
    return [
        {"cell": CELL_A, "bucket_start": start, "emergency_intensity_hour": intensity},
        {"cell": CELL_B, "bucket_start": start, "emergency_intensity_hour": intensity},
    ]


def _flood(multiplier: float) -> ScenarioObservation:
    return ScenarioObservation(
        id="flood-test",
        type=ScenarioType.FLOOD,
        starts_at="17:00",
        ends_at="18:00",
        affected_h3=(CELL_A,),
        demand_multiplier=multiplier,
        travel_penalty=2.0,
        blocked_edges=(),
        confidence=0.9,
        source=ScenarioSource.SIMULATED,
    )


def test_tape_is_immutable_seeded_and_stably_ordered() -> None:
    first = generate_call_tape(_density(), (), 42, 60, node_by_h3={CELL_A: 8, CELL_B: 9})
    second = generate_call_tape(_density(), (), 42, 60, node_by_h3={CELL_A: 8, CELL_B: 9})
    assert first == second
    assert tuple(call.id for call in first) == tuple(
        f"call-{index:06d}" for index in range(1, len(first) + 1)
    )
    assert tuple(call.occurred_at_second for call in first) == tuple(
        sorted(call.occurred_at_second for call in first)
    )
    assert {call.node_id for call in first} == {8, 9}


def test_scenario_only_elevates_affected_cell_in_active_window() -> None:
    baseline_a = []
    baseline_b = []
    flood_a = []
    flood_b = []
    for seed in range(100):
        baseline = generate_call_tape(_density(12), (), seed, 60)
        flood = generate_call_tape(_density(12), (_flood(3.0),), seed, 60)
        baseline_a.append(sum(call.h3_cell == CELL_A for call in baseline))
        baseline_b.append(sum(call.h3_cell == CELL_B for call in baseline))
        flood_a.append(sum(call.h3_cell == CELL_A for call in flood))
        flood_b.append(sum(call.h3_cell == CELL_B for call in flood))
    assert sum(flood_a) > 2 * sum(baseline_a)
    # Independent RNG consumption can shift exact B draws, but its expected rate is unchanged.
    assert abs(sum(flood_b) - sum(baseline_b)) < 0.2 * sum(baseline_b)


def test_zero_density_and_empty_input_produce_no_calls() -> None:
    assert generate_call_tape([], (), 1) == ()
    assert generate_call_tape(_density(0), (), 1) == ()
