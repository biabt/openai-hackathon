"""Deterministic schema and canonical fixture export contract."""

from __future__ import annotations

import json
from pathlib import Path

from city_os.contracts.api import BootstrapResponse, SimulationFrame
from city_os.contracts.export_schema import export_contracts

BACKEND_ROOT = Path(__file__).parents[2]
ARTIFACT_PATHS = (
    Path("schema/city-os.schema.json"),
    Path("tests/fixtures/contracts/bootstrap.json"),
    Path("tests/fixtures/contracts/stream.jsonl"),
)
EXPECTED_MODEL_DEFINITIONS = {
    "AmbulanceSnapshot",
    "ApiError",
    "ArtifactChecksum",
    "ArtifactEntry",
    "ArtifactManifest",
    "BootstrapResponse",
    "CallSnapshot",
    "CameraObservation",
    "EdgeState",
    "FleetSizeBounds",
    "H3Density",
    "MethodologyMetadata",
    "PairedMetrics",
    "RoadEdge",
    "RoadNode",
    "ScenarioObservation",
    "ScenarioParseRequest",
    "ScenarioParseResponse",
    "SimulationCreatedResponse",
    "SimulationFrame",
    "SimulationJobResponse",
    "SimulationMetrics",
    "SimulationRequest",
}


def _assert_recursively_sorted_keys(value: object) -> None:
    if isinstance(value, dict):
        assert list(value) == sorted(value)
        for nested in value.values():
            _assert_recursively_sorted_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_recursively_sorted_keys(nested)


def _read_export(root: Path, relative_path: Path) -> bytes:
    return (root / relative_path).read_bytes()


def test_export_is_byte_stable_and_matches_committed_contracts(tmp_path: Path) -> None:
    """Introducing clock, environment, hash-order, or random input changes exported bytes."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    export_contracts(first_root)
    export_contracts(second_root)

    for relative_path in ARTIFACT_PATHS:
        first = _read_export(first_root, relative_path)
        second = _read_export(second_root, relative_path)
        committed = _read_export(BACKEND_ROOT, relative_path)
        assert first == second == committed
        assert first.endswith(b"\n")
        assert b"\r" not in first


def test_schema_reaches_every_frozen_model_and_is_canonical(tmp_path: Path) -> None:
    """Omitting a public API or artifact model leaves generated consumers incomplete."""
    export_contracts(tmp_path)
    schema_bytes = _read_export(tmp_path, ARTIFACT_PATHS[0])
    schema = json.loads(schema_bytes)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "https://city-os.local/schema/city-os/v1"
    assert schema["title"] == "City OS C0 API Contract"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["oneOf"] == [
        {"$ref": "#/$defs/BootstrapResponse"},
        {"$ref": "#/$defs/SimulationFrame"},
    ]
    assert EXPECTED_MODEL_DEFINITIONS <= schema["$defs"].keys()
    _assert_recursively_sorted_keys(schema)
    expected = (
        json.dumps(schema, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    assert schema_bytes == expected


def test_bootstrap_round_trips_through_pydantic_and_is_canonical(tmp_path: Path) -> None:
    """A hand-shaped or noncanonical bootstrap can drift from its Pydantic contract."""
    export_contracts(tmp_path)
    bootstrap_bytes = _read_export(tmp_path, ARTIFACT_PATHS[1])
    bootstrap = BootstrapResponse.model_validate_json(bootstrap_bytes)
    payload = json.loads(bootstrap_bytes)

    assert bootstrap.api_version == "1.0"
    assert bootstrap.city == "São Paulo"
    assert bootstrap.h3_resolution == 8
    assert bootstrap.simulation_duration_minutes == 360
    assert bootstrap.frame_interval_minutes == 5
    assert bootstrap.optimization_cadence_minutes == 15
    assert bootstrap.forecast_horizon_minutes == 60
    assert bootstrap.default_seed == 42
    assert bootstrap.fleet_size_bounds.default == 3
    assert [scenario.id for scenario in bootstrap.scenarios] == [
        "flood-aricanduva-1730",
        "event-allianz-1800",
    ]
    assert all(scenario.source.value == "simulated" for scenario in bootstrap.scenarios)
    _assert_recursively_sorted_keys(payload)
    expected = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    assert bootstrap_bytes == expected


def test_stream_round_trips_and_preserves_paired_call_tape(tmp_path: Path) -> None:
    """Reordering frames or changing paired call identity invalidates policy comparison."""
    export_contracts(tmp_path)
    stream_bytes = _read_export(tmp_path, ARTIFACT_PATHS[2])
    lines = stream_bytes.decode("utf-8").splitlines()
    frames = [SimulationFrame.model_validate_json(line) for line in lines]

    assert [(frame.minute, frame.policy.value) for frame in frames] == [
        (0, "baseline"),
        (0, "optimized"),
        (5, "baseline"),
        (5, "optimized"),
        (10, "baseline"),
        (10, "optimized"),
    ]
    assert all(len(frame.ambulances) == 3 for frame in frames)
    assert all(frame.metrics.policy is frame.policy for frame in frames)
    assert any(call.response_seconds is None for frame in frames for call in frame.calls)
    assert any(call.response_seconds is not None for frame in frames for call in frame.calls)

    scenario_ids = {
        scenario.id
        for scenario in BootstrapResponse.model_validate_json(
            _read_export(tmp_path, ARTIFACT_PATHS[1])
        ).scenarios
    }
    assert all(set(frame.active_scenario_ids) <= scenario_ids for frame in frames)

    for baseline, optimized in zip(frames[::2], frames[1::2], strict=True):
        assert baseline.minute == optimized.minute
        assert len(baseline.calls) == len(optimized.calls)
        for baseline_call, optimized_call in zip(
            baseline.calls, optimized.calls, strict=True
        ):
            assert (
                baseline_call.id,
                baseline_call.h3_cell,
                baseline_call.node_id,
                baseline_call.priority,
                baseline_call.occurred_at_minute,
            ) == (
                optimized_call.id,
                optimized_call.h3_cell,
                optimized_call.node_id,
                optimized_call.priority,
                optimized_call.occurred_at_minute,
            )

    for line in lines:
        payload = json.loads(line)
        _assert_recursively_sorted_keys(payload)
        assert line == json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    assert stream_bytes.endswith(b"\n")
