"""Export the deterministic C0 JSON Schema and canonical contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

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
    SimulationMetrics,
    SimulationPolicy,
    SimulationRequest,
)
from city_os.contracts.artifacts import (
    ArtifactChecksum,
    ArtifactEntry,
    ArtifactManifest,
    CameraObservation,
    EdgeState,
    H3Density,
    RoadEdge,
    RoadNode,
)

SCHEMA_RELATIVE_PATH = Path("schema/city-os.schema.json")
BOOTSTRAP_RELATIVE_PATH = Path("tests/fixtures/contracts/bootstrap.json")
STREAM_RELATIVE_PATH = Path("tests/fixtures/contracts/stream.jsonl")
H3_SAO_PAULO_R8 = "88a8100c05fffff"

FROZEN_MODELS: tuple[type[BaseModel], ...] = (
    AmbulanceSnapshot,
    ApiError,
    ArtifactChecksum,
    ArtifactEntry,
    ArtifactManifest,
    BootstrapResponse,
    CallSnapshot,
    CameraObservation,
    EdgeState,
    FleetSizeBounds,
    H3Density,
    MethodologyMetadata,
    PairedMetrics,
    RoadEdge,
    RoadNode,
    ScenarioObservation,
    ScenarioParseRequest,
    ScenarioParseResponse,
    SimulationCreatedResponse,
    SimulationFrame,
    SimulationJobResponse,
    SimulationMetrics,
    SimulationRequest,
)


def _schema_document() -> dict[str, Any]:
    _, shared_schema = models_json_schema(
        [(model, "validation") for model in FROZEN_MODELS],
        ref_template="#/$defs/{model}",
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://city-os.local/schema/city-os/v1",
        "title": "City OS C0 API Contract",
        "$defs": shared_schema["$defs"],
        "oneOf": [
            {"$ref": "#/$defs/BootstrapResponse"},
            {"$ref": "#/$defs/SimulationFrame"},
        ],
    }


def _scenarios() -> tuple[ScenarioObservation, ...]:
    scenarios = (
        ScenarioObservation(
            id="flood-aricanduva-1730",
            type=ScenarioType.FLOOD,
            starts_at="17:30",
            ends_at="19:00",
            affected_h3=(H3_SAO_PAULO_R8,),
            demand_multiplier=1.25,
            travel_penalty=2.0,
            blocked_edges=(12345, 12346),
            confidence=0.9,
            source=ScenarioSource.SIMULATED,
        ),
        ScenarioObservation(
            id="event-allianz-1800",
            type=ScenarioType.EVENT,
            starts_at="18:00",
            ends_at="21:00",
            affected_h3=(H3_SAO_PAULO_R8,),
            demand_multiplier=1.5,
            travel_penalty=1.25,
            blocked_edges=(),
            confidence=0.9,
            source=ScenarioSource.SIMULATED,
        ),
    )
    return tuple(sorted(scenarios, key=lambda scenario: (scenario.starts_at, scenario.id)))


def _bootstrap() -> BootstrapResponse:
    return BootstrapResponse(
        api_version="1.0",
        city="São Paulo",
        h3_resolution=8,
        simulation_duration_minutes=360,
        frame_interval_minutes=5,
        optimization_cadence_minutes=15,
        forecast_horizon_minutes=60,
        default_seed=42,
        fleet_size_bounds=FleetSizeBounds(minimum=1, maximum=120, default=3),
        scenarios=_scenarios(),
        layer_urls={
            "camera_locations": "/api/layers/camera-locations",
            "edge_flow": "/api/layers/edge-flow",
            "h3_density": "/api/layers/h3-density",
            "roads": "/assets/map/sao-paulo.pmtiles",
        },
    )


def _ambulance(
    ambulance_id: str,
    *,
    status: AmbulanceStatus,
    node_id: int,
    target_node_id: int | None = None,
    call_id: str | None = None,
) -> AmbulanceSnapshot:
    return AmbulanceSnapshot(
        id=ambulance_id,
        status=status,
        node_id=node_id,
        target_node_id=target_node_id,
        call_id=call_id,
    )


def _fleet(first: AmbulanceSnapshot) -> tuple[AmbulanceSnapshot, ...]:
    return (
        first,
        _ambulance("amb-002", status=AmbulanceStatus.AVAILABLE, node_id=2),
        _ambulance("amb-003", status=AmbulanceStatus.AVAILABLE, node_id=3),
    )


def _metrics(
    policy: SimulationPolicy,
    *,
    response_seconds: float | None,
    reposition_km: float,
) -> SimulationMetrics:
    if response_seconds is None:
        response_values: dict[str, float | None] = {
            "mean_seconds": None,
            "p50_seconds": None,
            "p90_seconds": None,
            "p95_seconds": None,
            "within_8m_pct": None,
            "within_12m_pct": None,
            "within_20m_pct": None,
            "worst_district_p90_seconds": None,
        }
    else:
        within_8m = 100.0 if response_seconds <= 480.0 else 0.0
        response_values = {
            "mean_seconds": response_seconds,
            "p50_seconds": response_seconds,
            "p90_seconds": response_seconds,
            "p95_seconds": response_seconds,
            "within_8m_pct": within_8m,
            "within_12m_pct": 100.0,
            "within_20m_pct": 100.0,
            "worst_district_p90_seconds": response_seconds,
        }
    return SimulationMetrics(
        policy=policy,
        **response_values,
        queued_calls=0,
        unserved_calls=0,
        reposition_km=reposition_km,
    )


def _zero_metrics(policy: SimulationPolicy, *, reposition_km: float) -> SimulationMetrics:
    return SimulationMetrics(
        policy=policy,
        mean_seconds=0.0,
        p50_seconds=0.0,
        p90_seconds=0.0,
        p95_seconds=0.0,
        within_8m_pct=0.0,
        within_12m_pct=0.0,
        within_20m_pct=0.0,
        worst_district_p90_seconds=0.0,
        queued_calls=0,
        unserved_calls=0,
        reposition_km=reposition_km,
    )


def _call(*, status: CallStatus, response_seconds: float | None) -> CallSnapshot:
    return CallSnapshot(
        id="call-0001",
        h3_cell=H3_SAO_PAULO_R8,
        node_id=20,
        priority=CallPriority.P1,
        status=status,
        occurred_at_minute=5,
        response_seconds=response_seconds,
    )


def _frames() -> tuple[SimulationFrame, ...]:
    baseline = SimulationPolicy.BASELINE
    optimized = SimulationPolicy.OPTIMIZED
    return (
        SimulationFrame(
            minute=0,
            policy=baseline,
            ambulances=_fleet(
                _ambulance("amb-001", status=AmbulanceStatus.AVAILABLE, node_id=1)
            ),
            calls=(),
            metrics=_zero_metrics(baseline, reposition_km=0.0),
            active_scenario_ids=(),
        ),
        SimulationFrame(
            minute=0,
            policy=optimized,
            ambulances=_fleet(
                _ambulance(
                    "amb-001",
                    status=AmbulanceStatus.REPOSITIONING,
                    node_id=1,
                    target_node_id=10,
                )
            ),
            calls=(),
            metrics=_zero_metrics(optimized, reposition_km=1.2),
            active_scenario_ids=(),
        ),
        SimulationFrame(
            minute=5,
            policy=baseline,
            ambulances=_fleet(
                _ambulance(
                    "amb-001",
                    status=AmbulanceStatus.DISPATCHED,
                    node_id=1,
                    target_node_id=20,
                    call_id="call-0001",
                )
            ),
            calls=(_call(status=CallStatus.DISPATCHED, response_seconds=None),),
            metrics=_metrics(baseline, response_seconds=None, reposition_km=0.0),
            active_scenario_ids=(),
        ),
        SimulationFrame(
            minute=5,
            policy=optimized,
            ambulances=_fleet(
                _ambulance(
                    "amb-001",
                    status=AmbulanceStatus.DISPATCHED,
                    node_id=10,
                    target_node_id=20,
                    call_id="call-0001",
                )
            ),
            calls=(_call(status=CallStatus.DISPATCHED, response_seconds=None),),
            metrics=_metrics(optimized, response_seconds=None, reposition_km=1.2),
            active_scenario_ids=(),
        ),
        SimulationFrame(
            minute=10,
            policy=baseline,
            ambulances=_fleet(
                _ambulance(
                    "amb-001",
                    status=AmbulanceStatus.ON_SCENE,
                    node_id=20,
                    call_id="call-0001",
                )
            ),
            calls=(_call(status=CallStatus.ON_SCENE, response_seconds=540.0),),
            metrics=_metrics(baseline, response_seconds=540.0, reposition_km=0.0),
            active_scenario_ids=(),
        ),
        SimulationFrame(
            minute=10,
            policy=optimized,
            ambulances=_fleet(
                _ambulance(
                    "amb-001",
                    status=AmbulanceStatus.ON_SCENE,
                    node_id=20,
                    call_id="call-0001",
                )
            ),
            calls=(_call(status=CallStatus.ON_SCENE, response_seconds=360.0),),
            metrics=_metrics(optimized, response_seconds=360.0, reposition_km=1.2),
            active_scenario_ids=(),
        ),
    )


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_jsonl(values: tuple[SimulationFrame, ...]) -> bytes:
    lines = (
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for value in values
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write(root: Path, relative_path: Path, content: bytes) -> None:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def export_contracts(output_root: str | Path) -> None:
    """Write the schema and fixtures under an explicit backend output root."""
    root = Path(output_root)
    _write(root, SCHEMA_RELATIVE_PATH, _canonical_json(_schema_document()))
    _write(
        root,
        BOOTSTRAP_RELATIVE_PATH,
        _canonical_json(_bootstrap().model_dump(mode="json")),
    )
    _write(root, STREAM_RELATIVE_PATH, _canonical_jsonl(_frames()))


if __name__ == "__main__":
    export_contracts(Path(__file__).parents[3])
