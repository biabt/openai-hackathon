from fastapi.testclient import TestClient

from city_os.api.app import app
from city_os.contracts import SimulationRequest
from city_os.simulation import run_paired_simulation


def test_seeded_vertical_slice_uses_identical_call_ids() -> None:
    client = TestClient(app)
    scenario = client.get("/api/bootstrap").json()["scenarios"][0]["id"]
    created = client.post(
        "/api/simulations", json={"scenario_id": scenario, "fleet_size": 3, "seed": 42}
    )
    assert created.status_code == 202
    simulation_id = created.json()["simulation_id"]
    assert client.get(f"/api/simulations/{simulation_id}").json()["status"] == "completed"
    with client.websocket_connect(f"/api/simulations/{simulation_id}/stream") as socket:
        frames = [socket.receive_json() for _ in range(146)]
    terminal = [frame for frame in frames if frame["minute"] == 360]
    assert [call["id"] for call in terminal[0]["calls"]] == [
        call["id"] for call in terminal[1]["calls"]
    ]
    assert terminal[1]["metrics"]["p90_seconds"] <= terminal[0]["metrics"]["p90_seconds"]


def test_same_request_is_byte_deterministic() -> None:
    client = TestClient(app)
    request = {"scenario_id": "flood-aricanduva-1730", "fleet_size": 2, "seed": 42}
    ids = [client.post("/api/simulations", json=request).json()["simulation_id"] for _ in range(2)]
    assert ids[0] == ids[1]


def test_healthz_and_scenario_parser_use_contract_wrappers() -> None:
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    parsed = client.post("/api/scenario-cards/parse", json={"text": "alagamento"}).json()
    assert parsed["observation"]["type"] == "flood"
    assert parsed["used_fallback"] is False
    assert parsed["error"] is None

    fallback = client.post("/api/scenario-cards/parse", json={"text": "texto desconhecido"}).json()
    assert fallback["used_fallback"] is True
    assert fallback["error"]["code"] == "scenario_not_recognized"


def test_paired_simulation_serialization_is_replayable() -> None:
    request = SimulationRequest(
        scenario_id="flood-aricanduva-1730", fleet_size=3, seed=42
    )
    first = run_paired_simulation(request)
    second = run_paired_simulation(request)
    assert [frame.model_dump_json() for frame in first.frames] == [
        frame.model_dump_json() for frame in second.frames
    ]
