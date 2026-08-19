from __future__ import annotations

from math import inf, nan

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from city_os.contracts.api import (
    AmbulanceSnapshot,
    AmbulanceStatus,
    ApiError,
    BootstrapResponse,
    CallPriority,
    CallSnapshot,
    CallStatus,
    FleetSizeBounds,
    MethodologyMetadata,
    PairedMetrics,
    ScenarioObservation,
    ScenarioParseRequest,
    ScenarioParseResponse,
    ScenarioSource,
    ScenarioType,
    SimulationCreatedResponse,
    SimulationFrame,
    SimulationJobResponse,
    SimulationJobStatus,
    SimulationMetrics,
    SimulationPolicy,
    SimulationRequest,
)

H3_R8 = "8828308281fffff"


def valid_scenario(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "scenario-1",
        "type": "event",
        "starts_at": "17:30",
        "ends_at": "19:00",
        "affected_h3": [H3_R8],
        "demand_multiplier": 1.5,
        "travel_penalty": 1.0,
        "blocked_edges": [1, 2],
        "confidence": 0.9,
        "source": "simulated",
    }
    value.update(overrides)
    return value


def valid_metrics(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "policy": "baseline",
        "mean_seconds": 900.0,
        "p50_seconds": 800.0,
        "p90_seconds": 1000.0,
        "p95_seconds": 1100.0,
        "within_8m_pct": 50.0,
        "within_12m_pct": 70.0,
        "within_20m_pct": 90.0,
        "worst_district_p90_seconds": 1200.0,
        "queued_calls": 0,
        "unserved_calls": 0,
        "reposition_km": 0.0,
    }
    value.update(overrides)
    return value


def valid_ambulance(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "amb-1",
        "status": "available",
        "node_id": 1,
        "target_node_id": None,
        "call_id": None,
    }
    value.update(overrides)
    return value


def valid_call(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "call-1",
        "h3_cell": H3_R8,
        "node_id": 2,
        "priority": 1,
        "status": "pending",
        "occurred_at_minute": 0,
        "response_seconds": None,
    }
    value.update(overrides)
    return value


def valid_frame(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "minute": 0,
        "policy": "baseline",
        "ambulances": [valid_ambulance()],
        "calls": [valid_call()],
        "metrics": valid_metrics(),
        "active_scenario_ids": ["scenario-1"],
    }
    value.update(overrides)
    return value


def valid_bootstrap(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "api_version": "1.0",
        "city": "São Paulo",
        "h3_resolution": 8,
        "simulation_duration_minutes": 360,
        "frame_interval_minutes": 5,
        "optimization_cadence_minutes": 15,
        "forecast_horizon_minutes": 60,
        "default_seed": 0,
        "fleet_size_bounds": {"minimum": 1, "maximum": 120, "default": 1},
        "scenarios": [valid_scenario()],
        "layer_urls": {"roads": "/layers/roads.geojson"},
    }
    value.update(overrides)
    return value


def valid_paired_metrics() -> PairedMetrics:
    return PairedMetrics(
        baseline=SimulationMetrics.model_validate(valid_metrics()),
        optimized=SimulationMetrics.model_validate(valid_metrics(policy="optimized")),
    )


def valid_methodology() -> MethodologyMetadata:
    return MethodologyMetadata(
        call_tape_seed=0,
        calibration_target_seconds=1260,
        calibration_description="Calibrated simulation",
        data_label="simulated",
    )


@pytest.mark.parametrize(
    ("type_", "value"),
    [
        (AmbulanceStatus, "available"),
        (ScenarioType, "transit_disruption"),
        (ScenarioSource, "simulated"),
        (SimulationPolicy, "optimized"),
        (CallStatus, "unserved"),
        (SimulationJobStatus, "completed"),
        (CallPriority, 3),
    ],
)
def test_frozen_enums_serialize_to_their_wire_values(type_: type[object], value: object) -> None:
    """A renamed or non-lowercase enum member breaks generated clients."""
    assert type_(value).value == value  # type: ignore[operator,union-attr]


@pytest.mark.parametrize(
    "field,value",
    [
        ("fleet_size", 0),
        ("fleet_size", True),
        ("fleet_size", 1.0),
        ("seed", -1),
        ("seed", "1"),
    ],
)
def test_simulation_request_rejects_non_strict_or_out_of_range_numbers(
    field: str, value: object
) -> None:
    """Accepting coerced, zero, or negative inputs makes runs non-deterministic."""
    request = {"scenario_id": "scenario-1", "fleet_size": 1, "seed": 0}
    request[field] = value

    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(request)


def test_simulation_request_accepts_unbounded_positive_fleet_and_seed() -> None:
    """The C0 controller deliberately has no arbitrary fleet or seed ceiling."""
    request = SimulationRequest(scenario_id=" scenario-1 ", fleet_size=101, seed=2**63)

    assert request.scenario_id == "scenario-1"
    assert request.fleet_size == 101
    assert request.seed == 2**63


@pytest.mark.parametrize("cell", ["8828308281ffffF", "8828308281ffffe", "not-a-cell"])
def test_scenario_rejects_malformed_or_non_resolution_8_h3_cells(cell: str) -> None:
    """A syntactically H3-like string must not leak into map rendering."""
    with pytest.raises(ValidationError):
        ScenarioObservation.model_validate(valid_scenario(affected_h3=[cell]))


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [("19:00", "19:00"), ("19:00", "17:30"), ("24:00", "25:00")],
)
def test_scenario_requires_same_day_increasing_hh_mm_times(starts_at: str, ends_at: str) -> None:
    """Equal, reverse, and non-clock times cannot form an active scenario interval."""
    with pytest.raises(ValidationError):
        ScenarioObservation.model_validate(valid_scenario(starts_at=starts_at, ends_at=ends_at))


@pytest.mark.parametrize(
    "overrides",
    [
        {"blocked_edges": [1, 1]},
        {"affected_h3": [H3_R8, H3_R8]},
        {"demand_multiplier": inf},
        {"confidence": nan},
        {"source": "llm"},
        {"unexpected": "field"},
    ],
)
def test_scenario_rejects_invalid_collections_finite_values_and_extra_fields(
    overrides: dict[str, object]
) -> None:
    """Contract input must be finite, deduplicated, and closed to unknown fields."""
    with pytest.raises(ValidationError):
        ScenarioObservation.model_validate(valid_scenario(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "repositioning", "target_node_id": None},
        {"status": "available", "target_node_id": 4},
        {"status": "dispatched", "call_id": None},
        {"status": "available", "call_id": "call-1"},
        {"node_id": -1},
        {"target_node_id": -1},
    ],
)
def test_ambulance_snapshot_enforces_status_dependent_references(
    overrides: dict[str, object]
) -> None:
    """Impossible ambulance state combinations would produce contradictory map markers."""
    with pytest.raises(ValidationError):
        AmbulanceSnapshot.model_validate(valid_ambulance(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "on_scene", "response_seconds": None},
        {"status": "queued", "response_seconds": 10.0},
        {"status": "unserved", "response_seconds": 10.0},
        {"occurred_at_minute": 361},
        {"response_seconds": -0.1},
    ],
)
def test_call_snapshot_enforces_response_lifecycle(overrides: dict[str, object]) -> None:
    """A null response means genuinely not answered, never a fabricated zero."""
    with pytest.raises(ValidationError):
        CallSnapshot.model_validate(valid_call(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"p90_seconds": 700.0},
        {"within_12m_pct": 40.0},
        {"within_20m_pct": 101.0},
        {"mean_seconds": inf},
        {"queued_calls": -1},
    ],
)
def test_metrics_enforce_ordered_percentiles_and_finite_bounds(
    overrides: dict[str, object]
) -> None:
    """An invalid performance summary must be rejected before charting."""
    with pytest.raises(ValidationError):
        SimulationMetrics.model_validate(valid_metrics(**overrides))


def test_metrics_allow_an_empty_response_population_but_not_partial_percentiles() -> None:
    """No calls has no response distribution; a partial distribution is misleading."""
    empty = SimulationMetrics.model_validate(
        valid_metrics(
            mean_seconds=None,
            p50_seconds=None,
            p90_seconds=None,
            p95_seconds=None,
            within_8m_pct=None,
            within_12m_pct=None,
            within_20m_pct=None,
            worst_district_p90_seconds=None,
        )
    )
    assert empty.mean_seconds is None

    with pytest.raises(ValidationError):
        SimulationMetrics.model_validate(valid_metrics(mean_seconds=None))


@pytest.mark.parametrize(
    "overrides",
    [
        {"minute": 1},
        {"minute": 365},
        {"metrics": valid_metrics(policy="optimized")},
        {"active_scenario_ids": ["scenario-1", "scenario-1"]},
    ],
)
def test_frame_enforces_schedule_policy_and_identifier_invariants(
    overrides: dict[str, object]
) -> None:
    """A frame must be a coherent, regularly sampled policy snapshot."""
    with pytest.raises(ValidationError):
        SimulationFrame.model_validate(valid_frame(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "ambulances": [
                valid_ambulance(id="amb-1", node_id=1),
                valid_ambulance(id="amb-1", node_id=2),
            ]
        },
        {
            "calls": [
                valid_call(id="call-1", node_id=1),
                valid_call(id="call-1", node_id=2),
            ]
        },
    ],
)
def test_frame_rejects_duplicate_snapshot_ids(overrides: dict[str, object]) -> None:
    """Duplicate entity IDs make a frame ambiguous to keyed frontend state."""
    with pytest.raises(ValidationError):
        SimulationFrame.model_validate(valid_frame(**overrides))


def test_bootstrap_rejects_duplicate_scenario_ids() -> None:
    """Scenario IDs are stable control identifiers and must not collide."""
    scenarios = [valid_scenario(id="scenario-1"), valid_scenario(id="scenario-1")]

    with pytest.raises(ValidationError):
        BootstrapResponse.model_validate(valid_bootstrap(scenarios=scenarios))


def test_parse_response_requires_error_exactly_for_fallback() -> None:
    """Clients need an error whenever the parsing result is a fallback, and never otherwise."""
    observation = ScenarioObservation.model_validate(valid_scenario())
    error = ApiError(code="fallback", message="Unable to parse")

    fallback = ScenarioParseResponse(observation=observation, used_fallback=True, error=error)
    parsed = ScenarioParseResponse(observation=observation, used_fallback=False, error=None)
    assert fallback.error == error
    assert parsed.error is None
    with pytest.raises(ValidationError):
        ScenarioParseResponse(observation=observation, used_fallback=True, error=None)
    with pytest.raises(ValidationError):
        ScenarioParseResponse(observation=observation, used_fallback=False, error=error)


def test_parse_response_schema_exposes_the_runtime_fallback_condition() -> None:
    """Schema-only clients must see the same fallback/error branches as Pydantic."""
    schema = ScenarioParseResponse.model_json_schema()

    assert schema["allOf"] == [
        {
            "if": {
                "properties": {"used_fallback": {"const": True}},
                "required": ["used_fallback"],
            },
            "then": {"properties": {"error": {"not": {"type": "null"}}}},
            "else": {"properties": {"error": {"type": "null"}}},
        }
    ]


@pytest.mark.parametrize(
    ("used_fallback", "error", "is_valid"),
    [
        (False, None, True),
        (True, "present", True),
        (False, "present", False),
        (True, None, False),
    ],
)
def test_parse_response_schema_and_runtime_accept_the_same_branches(
    used_fallback: bool, error: str | None, is_valid: bool
) -> None:
    """Draft 2020-12 validation must agree with runtime fallback validation."""
    payload = {
        "observation": valid_scenario(),
        "used_fallback": used_fallback,
        "error": {"code": "fallback", "message": "Unable to parse"} if error else None,
    }
    schema_accepts = Draft202012Validator(ScenarioParseResponse.model_json_schema()).is_valid(
        payload
    )
    try:
        ScenarioParseResponse.model_validate(payload)
        runtime_accepts = True
    except ValidationError:
        runtime_accepts = False

    assert schema_accepts is is_valid
    assert runtime_accepts is is_valid


def test_job_response_requires_completed_payloads_and_failed_error() -> None:
    """Polling clients can rely on terminal states to decide which payload to render."""
    request = SimulationRequest(scenario_id="scenario-1", fleet_size=1, seed=0)
    paired = valid_paired_metrics()
    methodology = valid_methodology()
    completed = SimulationJobResponse(
        simulation_id="sim-run_1",
        request=request,
        status="completed",
        metrics=paired,
        methodology=methodology,
        error=None,
    )
    assert completed.metrics == paired

    failed = SimulationJobResponse(
        simulation_id="sim-run_1",
        request=request,
        status="failed",
        metrics=None,
        methodology=None,
        error=ApiError(code="failed", message="Simulation failed"),
    )
    assert failed.error is not None
    with pytest.raises(ValidationError):
        SimulationJobResponse(
            simulation_id="sim-run_1",
            request=request,
            status="completed",
            metrics=None,
            methodology=None,
            error=None,
        )
    with pytest.raises(ValidationError):
        SimulationJobResponse(
            simulation_id="sim-run_1",
            request=request,
            status="failed",
            metrics=None,
            methodology=None,
            error=None,
        )


def test_job_response_schema_exposes_the_runtime_terminal_conditions() -> None:
    """Schema-only clients must see completed, failed, and in-progress payload rules."""
    schema = SimulationJobResponse.model_json_schema()

    assert schema["allOf"] == [
        {
            "if": {
                "properties": {"status": {"const": "completed"}},
                "required": ["status"],
            },
            "then": {
                "properties": {
                    "metrics": {"not": {"type": "null"}},
                    "methodology": {"not": {"type": "null"}},
                }
            },
            "else": {
                "properties": {
                    "metrics": {"type": "null"},
                    "methodology": {"type": "null"},
                }
            },
        },
        {
            "if": {
                "properties": {"status": {"const": "failed"}},
                "required": ["status"],
            },
            "then": {"properties": {"error": {"not": {"type": "null"}}}},
            "else": {"properties": {"error": {"type": "null"}}},
        },
    ]


@pytest.mark.parametrize(
    ("status", "metrics", "methodology", "error", "is_valid"),
    [
        ("queued", None, None, None, True),
        ("running", None, None, None, True),
        ("completed", "present", "present", None, True),
        ("failed", None, None, "present", True),
        ("completed", None, None, None, False),
        ("failed", None, None, None, False),
        ("queued", "present", "present", None, False),
        ("running", None, None, "present", False),
    ],
)
def test_job_response_runtime_acceptance_matches_schema_status_branches(
    status: str,
    metrics: str | None,
    methodology: str | None,
    error: str | None,
    is_valid: bool,
) -> None:
    """Every schema status branch must agree with runtime payload validation."""
    payload = {
        "simulation_id": "sim-run_1",
        "request": {"scenario_id": "scenario-1", "fleet_size": 120, "seed": 0},
        "status": status,
        "metrics": valid_paired_metrics().model_dump(mode="json") if metrics else None,
        "methodology": valid_methodology().model_dump(mode="json") if methodology else None,
        "error": {"code": "failed", "message": "Simulation failed"} if error else None,
    }

    schema_accepts = Draft202012Validator(SimulationJobResponse.model_json_schema()).is_valid(
        payload
    )
    try:
        SimulationJobResponse.model_validate(payload)
        runtime_accepts = True
    except ValidationError:
        runtime_accepts = False

    assert schema_accepts is is_valid
    assert runtime_accepts is is_valid


def test_bootstrap_and_created_wrappers_validate_their_fixed_surface() -> None:
    """Controls and creation polling depend on immutable bootstrap and queued shapes."""
    bootstrap = BootstrapResponse.model_validate(valid_bootstrap())
    created = SimulationCreatedResponse(simulation_id="sim-abc_1", status="queued")

    assert bootstrap.layer_urls["roads"] == "/layers/roads.geojson"
    assert created.status == SimulationJobStatus.QUEUED
    with pytest.raises(ValidationError):
        FleetSizeBounds(minimum=2, maximum=1, default=1)
    with pytest.raises(ValidationError):
        ScenarioParseRequest(text="   ")
    with pytest.raises(ValidationError):
        SimulationCreatedResponse(simulation_id="not-a-simulation", status="queued")
