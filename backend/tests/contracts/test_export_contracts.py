"""Deterministic schema and canonical fixture export contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

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


def _committed_schema() -> dict[str, object]:
    return json.loads(_read_export(BACKEND_ROOT, ARTIFACT_PATHS[0]))


def _definition_validator(
    schema: dict[str, object], definition_name: str
) -> Draft202012Validator:
    definition_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition_name}",
    }
    Draft202012Validator.check_schema(definition_schema)
    return Draft202012Validator(definition_schema)


def _scenario_payload() -> dict[str, object]:
    return {
        "affected_h3": ["88a8100c05fffff"],
        "blocked_edges": [],
        "confidence": 0.9,
        "demand_multiplier": 1.5,
        "ends_at": "19:00",
        "id": "scenario-1",
        "source": "simulated",
        "starts_at": "17:30",
        "travel_penalty": 1.25,
        "type": "event",
    }


def _metrics_payload(policy: str) -> dict[str, object]:
    return {
        "mean_seconds": 600.0,
        "p50_seconds": 600.0,
        "p90_seconds": 600.0,
        "p95_seconds": 600.0,
        "policy": policy,
        "queued_calls": 0,
        "reposition_km": 0.0,
        "unserved_calls": 0,
        "within_12m_pct": 100.0,
        "within_20m_pct": 100.0,
        "within_8m_pct": 0.0,
        "worst_district_p90_seconds": 600.0,
    }


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
    assert "type" not in schema
    assert "additionalProperties" not in schema
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


def test_committed_fixtures_validate_against_matching_schema_definitions() -> None:
    """A schema weaker or incompatible with committed payloads breaks non-Python consumers."""
    schema = _committed_schema()
    Draft202012Validator.check_schema(schema)
    bootstrap_validator = _definition_validator(schema, "BootstrapResponse")
    frame_validator = _definition_validator(schema, "SimulationFrame")

    bootstrap_validator.validate(
        json.loads(_read_export(BACKEND_ROOT, ARTIFACT_PATHS[1]))
    )
    for line in _read_export(BACKEND_ROOT, ARTIFACT_PATHS[2]).decode("utf-8").splitlines():
        frame_validator.validate(json.loads(line))


def test_committed_fixtures_validate_against_full_root_schema() -> None:
    """Root-level siblings must not reject payloads accepted by a referenced model."""
    validator = Draft202012Validator(_committed_schema())

    validator.validate(json.loads(_read_export(BACKEND_ROOT, ARTIFACT_PATHS[1])))
    for line in _read_export(BACKEND_ROOT, ARTIFACT_PATHS[2]).decode("utf-8").splitlines():
        validator.validate(json.loads(line))


def test_full_root_schema_rejects_an_object_matching_no_frozen_model() -> None:
    """Removing incompatible root strictness must not make the contract root permissive."""
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(_committed_schema()).validate({"unknown_contract": True})


@pytest.mark.parametrize(
    "internal_payload",
    [
        {"h3_cell": "88a8100c05fffff", "node_id": 1, "x": -46.63, "y": -23.55},
        {"fleet_size": 3, "scenario_id": "scenario-1", "seed": 42},
    ],
)
def test_full_root_schema_rejects_valid_internal_models(
    internal_payload: dict[str, object],
) -> None:
    """Internal definitions remain addressable without becoming root documents."""
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(_committed_schema()).validate(internal_payload)


@pytest.mark.parametrize(
    "definition_name,field_name", [("RoadNode", "h3_cell"), ("H3Density", "cell")]
)
def test_artifact_schema_rejects_malformed_h3_syntax(
    definition_name: str, field_name: str
) -> None:
    """Dropping declarative H3 syntax lets schema-only producers emit invalid cells."""
    schema = _committed_schema()
    payloads: dict[str, dict[str, object]] = {
        "RoadNode": {
            "h3_cell": "not-an-h3-cell",
            "node_id": 1,
            "x": -46.63,
            "y": -23.55,
        },
        "H3Density": {
            "bucket_start": "2026-08-19T12:05:00Z",
            "cell": "not-an-h3-cell",
            "confidence": 0.9,
            "density_people_km2": 1000.0,
            "emergency_intensity_hour": 1.0,
        },
    }

    with pytest.raises(JsonSchemaValidationError):
        _definition_validator(schema, definition_name).validate(payloads[definition_name])
    assert schema["$defs"][definition_name]["properties"][field_name]["pattern"] == (  # type: ignore[index]
        "^[0-9a-f]{15}$"
    )


def test_road_edge_schema_publishes_base64_metadata_and_rejects_empty_shape() -> None:
    """Losing WKB wire metadata makes generated artifact clients accept arbitrary text."""
    schema = _committed_schema()
    geometry_schema = schema["$defs"]["RoadEdge"]["properties"]["geometry_wkb"]  # type: ignore[index]
    payload = {
        "capacity_vph": 900.0,
        "edge_id": 1,
        "free_flow_seconds": 5.0,
        "geometry_wkb": "",
        "length_m": 42.5,
        "u": 1,
        "v": 2,
    }

    assert geometry_schema["contentEncoding"] == "base64"
    with pytest.raises(JsonSchemaValidationError):
        _definition_validator(schema, "RoadEdge").validate(payload)


@pytest.mark.parametrize(
    ("definition_name", "payload"),
    [
        (
            "CameraObservation",
            {
                "bucket_start": "2026-08-19T12:05:00Z",
                "camera_id": "",
                "confidence": 0.9,
                "count": 1,
                "direction": "northbound",
                "edge_id": 1,
                "object_class": "bus",
            },
        ),
        (
            "ArtifactEntry",
            {
                "checksum": {"algorithm": "sha256", "value": "a" * 64},
                "media_type": "application/octet-stream",
                "name": "",
                "path": "roads/nodes.parquet",
            },
        ),
    ],
)
def test_artifact_schema_rejects_empty_frozen_strings(
    definition_name: str, payload: dict[str, object]
) -> None:
    """Missing minLength metadata permits values rejected by artifact ingestion."""
    with pytest.raises(JsonSchemaValidationError):
        _definition_validator(_committed_schema(), definition_name).validate(payload)


@pytest.mark.parametrize(
    "path", ["/roads.parquet", "roads\\nodes.parquet", "roads/../nodes.parquet"]
)
def test_artifact_entry_schema_rejects_unsafe_relative_paths(path: str) -> None:
    """Dropping the safe relative-path shape lets generated manifests escape their root."""
    payload = {
        "checksum": {"algorithm": "sha256", "value": "a" * 64},
        "media_type": "application/octet-stream",
        "name": "roads",
        "path": path,
    }

    with pytest.raises(JsonSchemaValidationError):
        _definition_validator(_committed_schema(), "ArtifactEntry").validate(payload)


def test_parse_response_schema_matches_fallback_error_branches() -> None:
    """Independent fallback/error fields admit states the runtime contract rejects."""
    validator = _definition_validator(_committed_schema(), "ScenarioParseResponse")
    error = {"code": "fallback", "message": "Unable to parse"}
    observation = _scenario_payload()

    validator.validate({"error": None, "observation": observation, "used_fallback": False})
    validator.validate({"error": error, "observation": observation, "used_fallback": True})
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({"error": error, "observation": observation, "used_fallback": False})
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({"error": None, "observation": observation, "used_fallback": True})


def test_job_response_schema_matches_terminal_status_payload_branches() -> None:
    """Independent job fields let generated clients accept contradictory terminal states."""
    validator = _definition_validator(_committed_schema(), "SimulationJobResponse")
    request = {"fleet_size": 3, "scenario_id": "scenario-1", "seed": 42}
    empty = {
        "error": None,
        "methodology": None,
        "metrics": None,
        "request": request,
        "simulation_id": "sim-run-1",
        "status": "running",
    }
    completed = empty | {
        "methodology": {
            "calibration_description": "Calibrated simulation",
            "calibration_target_seconds": 1260,
            "call_tape_seed": 42,
            "data_label": "simulated",
        },
        "metrics": {
            "baseline": _metrics_payload("baseline"),
            "optimized": _metrics_payload("optimized"),
        },
        "status": "completed",
    }
    failed = empty | {
        "error": {"code": "failed", "message": "Simulation failed"},
        "status": "failed",
    }

    validator.validate(empty)
    validator.validate(completed)
    validator.validate(failed)
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(empty | {"status": "completed"})
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(empty | {"status": "failed"})
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(
            empty
            | {
                "error": {"code": "failed", "message": "Simulation failed"},
                "status": "running",
            }
        )
