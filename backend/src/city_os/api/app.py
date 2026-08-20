"""FastAPI surface for bootstrap, scenario parsing, jobs, and frame replay."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
from .artifact_loader import load_world

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
            code="scenario_not_recognized",
            message="Text was not recognized; deterministic offline rules were used.",
        ),
    )


def _parse_scenario(text: str) -> ScenarioParseResponse:
    normalized = text.casefold()
    for scenario in built_in_scenarios():
        recognized = (
            scenario.id.casefold() in normalized
            or (scenario.type is ScenarioType.FLOOD and "alag" in normalized)
            or (scenario.type is ScenarioType.EVENT and "evento" in normalized)
        )
        if recognized:
            return ScenarioParseResponse(
                observation=scenario, used_fallback=False, error=None
            )
    return _fallback_parse(text)


def create_app() -> FastAPI:
    api = FastAPI(title="City OS Simulation API", version="1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"http://(?:127\.0\.0\.1|localhost):\d+",
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    repository = Path(__file__).resolve().parents[4]
    spatial_manifest = repository / "data" / "demo" / "spatial" / "artifacts" / "manifest.json"
    world = load_world(spatial_manifest)
    registry = JobRegistry()
    xs = [float(node["x"]) for node in world.nodes]
    ys = [float(node["y"]) for node in world.nodes]

    def layer(name: str, data: tuple[dict[str, object], ...]) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "provenance": {
                "source_manifest": "data/demo/spatial/artifacts/manifest.json",
                "simulated": False,
                "layer": name,
            },
            "data": data,
        }

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
                min_longitude=min(xs), min_latitude=min(ys),
                max_longitude=max(xs), max_latitude=max(ys),
            ),
            fleet_size_bounds=FleetSizeBounds(minimum=1, maximum=120, default=12),
            scenarios=built_in_scenarios(),
            layer_urls={
                "roads": "/map/sao-paulo.pmtiles",
                "nodes": "/api/layers/nodes",
                "edges": "/api/layers/edges",
                "h3_cells": "/api/layers/h3-cells",
            },
        )

    @api.get("/api/layers/nodes")
    def nodes() -> dict[str, object]:
        return layer("nodes", world.nodes)

    @api.get("/api/layers/edges")
    def edges() -> dict[str, object]:
        return layer("edges", world.edges)

    @api.get("/api/layers/h3-cells")
    def h3_cells() -> dict[str, object]:
        return layer("h3_cells", world.h3_cells)

    @api.get("/map/sao-paulo.pmtiles")
    def map_tiles() -> FileResponse:
        return FileResponse(
            repository / "data" / "demo" / "map" / "sao-paulo.pmtiles",
            media_type="application/vnd.pmtiles",
        )

    @api.post("/api/scenario-cards/parse", response_model=ScenarioParseResponse)
    def parse_scenario(request: ScenarioParseRequest) -> ScenarioParseResponse:
        return _parse_scenario(request.text)

    @api.post("/api/simulations", response_model=SimulationCreatedResponse, status_code=202)
    def create_simulation(request: SimulationRequest) -> SimulationCreatedResponse:
        accepted_scenarios = {item.id for item in built_in_scenarios()} | {
            "flood-aricanduva-1730",
            "event-allianz-1800",
        }
        if request.scenario_id not in accepted_scenarios:
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
