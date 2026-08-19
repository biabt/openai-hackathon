"""Strict, versioned request and response contracts for the City OS API."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, IntEnum
from typing import Annotated, Literal, Self

import h3  # type: ignore[import-untyped]
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)


class StrictModel(BaseModel):
    """Base contract model: no coercion, no unknown fields, no hidden defaults."""

    model_config = ConfigDict(extra="forbid", strict=True)


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, pattern=r"\S"),
]
NodeId = Annotated[int, Field(strict=True, ge=0)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, ge=1)]
PortableSeed = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFinite = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Percentage = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
HHMM = Annotated[
    str,
    StringConstraints(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$", strict=True),
]
SimulationId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^sim-[A-Za-z0-9_-]+$", strict=True),
]


def _validate_local_asset_url(value: str) -> str:
    if value.startswith("//"):
        raise ValueError("must be an origin-relative path")
    return value


LocalAssetUrl = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^/\S+$", strict=True),
    AfterValidator(_validate_local_asset_url),
]


def _validate_h3_resolution_8(value: str) -> str:
    if not h3.is_valid_cell(value) or h3.get_resolution(value) != 8:
        raise ValueError("must be a valid H3 resolution-8 cell")
    return value


H3Cell = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{15}$", strict=True),
    AfterValidator(_validate_h3_resolution_8),
]


class AmbulanceStatus(str, Enum):  # noqa: UP042 - frozen public base classes
    AVAILABLE = "available"
    REPOSITIONING = "repositioning"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    TRANSPORTING = "transporting"
    HANDOFF = "handoff"
    RELEASED = "released"


class ScenarioType(str, Enum):  # noqa: UP042 - frozen public base classes
    EVENT = "event"
    FLOOD = "flood"
    DEMONSTRATION = "demonstration"
    TRANSIT_DISRUPTION = "transit_disruption"


class ScenarioSource(str, Enum):  # noqa: UP042 - frozen public base classes
    SIMULATED = "simulated"


class SimulationPolicy(str, Enum):  # noqa: UP042 - frozen public base classes
    BASELINE = "baseline"
    OPTIMIZED = "optimized"


class CallPriority(IntEnum):
    P1 = 1
    P2 = 2
    P3 = 3


class CallStatus(str, Enum):  # noqa: UP042 - frozen public base classes
    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    TRANSPORTING = "transporting"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    UNSERVED = "unserved"


class SimulationJobStatus(str, Enum):  # noqa: UP042 - frozen public base classes
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _parse_wire_enum(enum_type: type[Enum]) -> Callable[[object], Enum]:
    def parse(value: object) -> Enum:
        if isinstance(value, enum_type):
            return value
        is_string_enum = issubclass(enum_type, str) and type(value) is str
        is_integer_enum = issubclass(enum_type, IntEnum) and type(value) is int
        if is_string_enum or is_integer_enum:
            try:
                return enum_type(value)
            except ValueError as error:
                raise ValueError(f"unsupported {enum_type.__name__} value") from error
        raise ValueError(f"{enum_type.__name__} must use its JSON wire value")

    return parse


WireAmbulanceStatus = Annotated[
    AmbulanceStatus, BeforeValidator(_parse_wire_enum(AmbulanceStatus))
]
WireScenarioType = Annotated[ScenarioType, BeforeValidator(_parse_wire_enum(ScenarioType))]
WireScenarioSource = Annotated[ScenarioSource, BeforeValidator(_parse_wire_enum(ScenarioSource))]
WireSimulationPolicy = Annotated[
    SimulationPolicy, BeforeValidator(_parse_wire_enum(SimulationPolicy))
]
WireCallPriority = Annotated[CallPriority, BeforeValidator(_parse_wire_enum(CallPriority))]
WireCallStatus = Annotated[CallStatus, BeforeValidator(_parse_wire_enum(CallStatus))]
WireSimulationJobStatus = Annotated[
    SimulationJobStatus, BeforeValidator(_parse_wire_enum(SimulationJobStatus))
]


class ScenarioObservation(StrictModel):
    id: NonEmptyString
    type: WireScenarioType
    starts_at: HHMM
    ends_at: HHMM
    affected_h3: Annotated[tuple[H3Cell, ...], Field(strict=False, min_length=1)]
    demand_multiplier: Annotated[FiniteNumber, Field(ge=0.5, le=5.0)]
    travel_penalty: Annotated[FiniteNumber, Field(ge=1.0, le=10.0)]
    blocked_edges: Annotated[tuple[NodeId, ...], Field(strict=False)]
    confidence: Annotated[FiniteNumber, Field(ge=0.0, le=1.0)]
    source: WireScenarioSource

    @model_validator(mode="after")
    def _validate_interval_and_unique_members(self) -> Self:
        if self.starts_at >= self.ends_at:
            raise ValueError("ends_at must be later than starts_at")
        if len(self.affected_h3) != len(set(self.affected_h3)):
            raise ValueError("affected_h3 must contain unique cells")
        if len(self.blocked_edges) != len(set(self.blocked_edges)):
            raise ValueError("blocked_edges must contain unique edge IDs")
        return self


class SimulationRequest(StrictModel):
    scenario_id: NonEmptyString
    fleet_size: PositiveInt
    seed: PortableSeed


class AmbulanceSnapshot(StrictModel):
    id: NonEmptyString
    status: WireAmbulanceStatus
    node_id: NodeId
    target_node_id: NodeId | None
    call_id: NonEmptyString | None

    @model_validator(mode="after")
    def _validate_references_for_status(self) -> Self:
        stationary_statuses = {
            AmbulanceStatus.AVAILABLE,
            AmbulanceStatus.ON_SCENE,
            AmbulanceStatus.HANDOFF,
            AmbulanceStatus.RELEASED,
        }
        call_statuses = {
            AmbulanceStatus.DISPATCHED,
            AmbulanceStatus.ON_SCENE,
            AmbulanceStatus.TRANSPORTING,
            AmbulanceStatus.HANDOFF,
        }
        if self.status is AmbulanceStatus.REPOSITIONING and self.target_node_id is None:
            raise ValueError("repositioning ambulances require target_node_id")
        if self.status in stationary_statuses and self.target_node_id is not None:
            raise ValueError("stationary ambulances must not have target_node_id")
        if (self.status in call_statuses) != (self.call_id is not None):
            raise ValueError("call_id must be present exactly for call-active ambulance states")
        return self


class CallSnapshot(StrictModel):
    id: NonEmptyString
    h3_cell: H3Cell
    node_id: NodeId
    priority: WireCallPriority
    status: WireCallStatus
    occurred_at_minute: Annotated[int, Field(strict=True, ge=0, le=360)]
    response_seconds: NonNegativeFinite | None

    @model_validator(mode="after")
    def _validate_response_lifecycle(self) -> Self:
        answered_statuses = {
            CallStatus.ON_SCENE,
            CallStatus.TRANSPORTING,
            CallStatus.HANDOFF,
            CallStatus.COMPLETED,
        }
        if (self.status in answered_statuses) != (self.response_seconds is not None):
            raise ValueError("response_seconds must be present exactly once a call is on scene")
        return self


class SimulationMetrics(StrictModel):
    policy: WireSimulationPolicy
    mean_seconds: NonNegativeFinite | None
    p50_seconds: NonNegativeFinite | None
    p90_seconds: NonNegativeFinite | None
    p95_seconds: NonNegativeFinite | None
    within_8m_pct: Percentage | None
    within_12m_pct: Percentage | None
    within_20m_pct: Percentage | None
    worst_district_p90_seconds: NonNegativeFinite | None
    queued_calls: NonNegativeInt
    unserved_calls: NonNegativeInt
    reposition_km: NonNegativeFinite

    @model_validator(mode="after")
    def _validate_response_distribution(self) -> Self:
        response_fields = (
            self.mean_seconds,
            self.p50_seconds,
            self.p90_seconds,
            self.p95_seconds,
            self.within_8m_pct,
            self.within_12m_pct,
            self.within_20m_pct,
            self.worst_district_p90_seconds,
        )
        if any(value is None for value in response_fields):
            if not all(value is None for value in response_fields):
                raise ValueError("response-derived metrics must be all null or all present")
            return self
        assert self.p50_seconds is not None
        assert self.p90_seconds is not None
        assert self.p95_seconds is not None
        assert self.within_8m_pct is not None
        assert self.within_12m_pct is not None
        assert self.within_20m_pct is not None
        if not self.p50_seconds <= self.p90_seconds <= self.p95_seconds:
            raise ValueError("response percentiles must be ordered")
        if not self.within_8m_pct <= self.within_12m_pct <= self.within_20m_pct:
            raise ValueError("within-threshold percentages must be ordered")
        return self


class SimulationFrame(StrictModel):
    minute: Annotated[int, Field(strict=True, ge=0, le=360, multiple_of=5)]
    policy: WireSimulationPolicy
    ambulances: Annotated[tuple[AmbulanceSnapshot, ...], Field(strict=False)]
    calls: Annotated[tuple[CallSnapshot, ...], Field(strict=False)]
    metrics: SimulationMetrics
    active_scenario_ids: Annotated[tuple[NonEmptyString, ...], Field(strict=False)]

    @model_validator(mode="after")
    def _validate_policy_and_scenarios(self) -> Self:
        if self.metrics.policy is not self.policy:
            raise ValueError("metrics.policy must equal frame policy")
        ambulance_ids = [ambulance.id for ambulance in self.ambulances]
        if len(ambulance_ids) != len(set(ambulance_ids)):
            raise ValueError("ambulances must have unique IDs")
        call_ids = [call.id for call in self.calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("calls must have unique IDs")
        if len(self.active_scenario_ids) != len(set(self.active_scenario_ids)):
            raise ValueError("active_scenario_ids must contain unique values")
        return self


class FleetSizeBounds(StrictModel):
    minimum: PositiveInt
    maximum: PositiveInt
    default: PositiveInt

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if not self.minimum <= self.default <= self.maximum:
            raise ValueError("default must be within fleet size bounds")
        return self


class GeographicBounds(StrictModel):
    min_longitude: Annotated[FiniteNumber, Field(ge=-180, le=180)]
    min_latitude: Annotated[FiniteNumber, Field(ge=-90, le=90)]
    max_longitude: Annotated[FiniteNumber, Field(ge=-180, le=180)]
    max_latitude: Annotated[FiniteNumber, Field(ge=-90, le=90)]

    @model_validator(mode="after")
    def _validate_axis_order(self) -> Self:
        if self.min_longitude >= self.max_longitude:
            raise ValueError("min_longitude must be less than max_longitude")
        if self.min_latitude >= self.max_latitude:
            raise ValueError("min_latitude must be less than max_latitude")
        return self


class BootstrapResponse(StrictModel):
    api_version: Literal["1.0"]
    city: Literal["São Paulo"]
    h3_resolution: Literal[8]
    simulation_duration_minutes: Literal[360]
    frame_interval_minutes: Literal[5]
    optimization_cadence_minutes: Literal[15]
    forecast_horizon_minutes: Literal[60]
    default_seed: PortableSeed
    bounds: GeographicBounds
    fleet_size_bounds: FleetSizeBounds
    scenarios: Annotated[tuple[ScenarioObservation, ...], Field(strict=False)]
    layer_urls: Annotated[
        dict[NonEmptyString, LocalAssetUrl],
        Field(
            strict=False,
            json_schema_extra={"propertyNames": {"minLength": 1, "pattern": r"\S"}},
        ),
    ]

    @model_validator(mode="after")
    def _validate_scenario_ids(self) -> Self:
        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenarios must have unique IDs")
        return self


class ScenarioParseRequest(StrictModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ApiError(StrictModel):
    code: NonEmptyString
    message: NonEmptyString


class ScenarioParseResponse(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"used_fallback": {"const": True}},
                        "required": ["used_fallback"],
                    },
                    "then": {"properties": {"error": {"not": {"type": "null"}}}},
                    "else": {"properties": {"error": {"type": "null"}}},
                }
            ]
        }
    )

    observation: ScenarioObservation
    used_fallback: StrictBool
    error: ApiError | None

    @model_validator(mode="after")
    def _validate_fallback_error(self) -> Self:
        if self.used_fallback != (self.error is not None):
            raise ValueError("error must be present exactly when fallback is used")
        return self


class SimulationCreatedResponse(StrictModel):
    simulation_id: SimulationId
    status: Literal[SimulationJobStatus.QUEUED]


class PairedMetrics(StrictModel):
    baseline: SimulationMetrics
    optimized: SimulationMetrics

    @model_validator(mode="after")
    def _validate_policies(self) -> Self:
        if self.baseline.policy is not SimulationPolicy.BASELINE:
            raise ValueError("baseline metrics must use baseline policy")
        if self.optimized.policy is not SimulationPolicy.OPTIMIZED:
            raise ValueError("optimized metrics must use optimized policy")
        return self


class MethodologyMetadata(StrictModel):
    call_tape_seed: PortableSeed
    calibration_target_seconds: Literal[1260]
    calibration_description: NonEmptyString
    data_label: Literal["simulated"]


class SimulationJobResponse(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
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
        }
    )

    simulation_id: SimulationId
    request: SimulationRequest
    status: WireSimulationJobStatus
    metrics: PairedMetrics | None
    methodology: MethodologyMetadata | None
    error: ApiError | None

    @model_validator(mode="after")
    def _validate_terminal_payloads(self) -> Self:
        is_completed = self.status is SimulationJobStatus.COMPLETED
        is_failed = self.status is SimulationJobStatus.FAILED
        if is_completed != (self.metrics is not None):
            raise ValueError("metrics must be present exactly for completed jobs")
        if is_completed != (self.methodology is not None):
            raise ValueError("methodology must be present exactly for completed jobs")
        if is_failed != (self.error is not None):
            raise ValueError("error must be present exactly for failed jobs")
        if (
            is_completed
            and self.methodology is not None
            and self.methodology.call_tape_seed != self.request.seed
        ):
            raise ValueError("methodology call_tape_seed must equal request seed")
        return self
