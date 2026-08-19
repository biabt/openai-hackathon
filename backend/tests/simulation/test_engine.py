from city_os.contracts import SimulationPolicy, SimulationRequest
from city_os.simulation import run_paired_simulation


def test_paired_simulation_is_deterministic_and_uses_same_tape() -> None:
    request = SimulationRequest(scenario_id="flood-aricanduva", fleet_size=6, seed=42)
    first = run_paired_simulation(request)
    second = run_paired_simulation(request)
    assert first.call_tape == second.call_tape
    first_frames = [frame.model_dump() for frame in first.frames]
    second_frames = [frame.model_dump() for frame in second.frames]
    assert first_frames == second_frames
    assert len(first.frames) == 146
    assert first.metrics.baseline.policy is SimulationPolicy.BASELINE
    assert first.metrics.optimized.policy is SimulationPolicy.OPTIMIZED
    assert first.metrics.optimized.p90_seconds <= first.metrics.baseline.p90_seconds


def test_fleet_size_is_exact_in_every_frame() -> None:
    result = run_paired_simulation(SimulationRequest(scenario_id="normal", fleet_size=3, seed=7))
    assert all(len(frame.ambulances) == 3 for frame in result.frames)
