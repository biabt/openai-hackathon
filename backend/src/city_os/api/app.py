"""FastAPI surface for bootstrap, scenario parsing, jobs, and frame replay."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from city_os.contracts import (
    ApiError,
    BootstrapResponse,
    FleetSizeBounds,
    GeographicBounds,
    ScenarioObservation,
    ScenarioParseRequest,
    ScenarioParseResponse,
    ScenarioSource,
    ScenarioType,
    SimulationCreatedResponse,
    SimulationJobResponse,
    SimulationJobStatus,
    SimulationRequest,
)
from city_os.scenarios import parse_scenario_card

from .jobs import JobRegistry

DEFAULT_CELL = "88a8100c05fffff"


def built_in_scenarios() -> tuple[ScenarioObservation, ...]:
    return (
        ScenarioObservation(
            id="normal",
            type=ScenarioType.EVENT,
            starts_at="12:00",
            ends_at="12:01",
            affected_h3=(DEFAULT_CELL,),
            demand_multiplier=1.0,
            travel_penalty=1.0,
            blocked_edges=(),
            confidence=1.0,
            source=ScenarioSource.SIMULATED,
        ),
        ScenarioObservation(
            id="flood-aricanduva",
            type=ScenarioType.FLOOD,
            starts_at="14:00",
            ends_at="16:00",
            affected_h3=(DEFAULT_CELL,),
            demand_multiplier=1.35,
            travel_penalty=1.8,
            blocked_edges=(12345,),
            confidence=0.85,
            source=ScenarioSource.SIMULATED,
        ),
        ScenarioObservation(
            id="event-allianz",
            type=ScenarioType.EVENT,
            starts_at="18:00",
            ends_at="21:00",
            affected_h3=(DEFAULT_CELL,),
            demand_multiplier=1.5,
            travel_penalty=1.2,
            blocked_edges=(),
            confidence=0.9,
            source=ScenarioSource.SIMULATED,
        ),
    )


def _fallback_parse(text: str) -> ScenarioParseResponse:
    selected = parse_scenario_card(text)
    return ScenarioParseResponse(
        observation=selected,
        used_fallback=True,
        error=ApiError(
            code="offline_fallback", message="Parsed with deterministic offline rules."
        ),
    )


def create_app() -> FastAPI:
    api = FastAPI(title="City OS Simulation API", version="1.0")
    registry = JobRegistry()

    @api.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/bootstrap", response_model=BootstrapResponse)
    def bootstrap() -> BootstrapResponse:
        return BootstrapResponse(
            api_version="1.0",
            city="São Paulo",
            h3_resolution=8,
            simulation_duration_minutes=360,
            frame_interval_minutes=5,
            optimization_cadence_minutes=15,
            forecast_horizon_minutes=60,
            default_seed=42,
            bounds=GeographicBounds(
                min_longitude=-46.85,
                min_latitude=-24.0,
                max_longitude=-46.35,
                max_latitude=-23.35,
            ),
            fleet_size_bounds=FleetSizeBounds(minimum=1, maximum=120, default=12),
            scenarios=built_in_scenarios(),
            layer_urls={
                "roads": "/assets/map/sao-paulo.pmtiles",
                "h3_density": "/api/layers/h3-density",
                "edge_flow": "/api/layers/edge-flow",
            },
        )

    @api.post("/api/scenario-cards/parse", response_model=ScenarioParseResponse)
    def parse_scenario(request: ScenarioParseRequest) -> ScenarioParseResponse:
        return _fallback_parse(request.text)

    @api.post("/api/simulations", response_model=SimulationCreatedResponse, status_code=202)
    def create_simulation(request: SimulationRequest) -> SimulationCreatedResponse:
        if request.scenario_id not in {item.id for item in built_in_scenarios()}:
            raise HTTPException(status_code=422, detail="unknown scenario_id")
        job = registry.create(request)
        return SimulationCreatedResponse(
            simulation_id=job.response.simulation_id,
            status=SimulationJobStatus.QUEUED,
        )

    @api.get("/api/simulations/{simulation_id}", response_model=SimulationJobResponse)
    def simulation_status(simulation_id: str) -> SimulationJobResponse:
        job = registry.get(simulation_id)
        if job is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        return job.response

    @api.websocket("/api/simulations/{simulation_id}/stream")
    async def stream(websocket: WebSocket, simulation_id: str) -> None:
        await websocket.accept()
        job = registry.get(simulation_id)
        if job is None:
            await websocket.close(code=4404, reason="simulation not found")
            return
        try:
            for frame in job.frames:
                await websocket.send_text(frame.model_dump_json())
            await websocket.close(code=1000)
        except WebSocketDisconnect:
            return

    return api


app = create_app()
