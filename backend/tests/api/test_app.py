from fastapi.testclient import TestClient

from city_os.api import create_app


def test_vertical_slice_and_websocket_replay() -> None:
    client = TestClient(create_app())
    assert client.get("/healthz").json() == {"status": "ok"}
    bootstrap = client.get("/api/bootstrap")
    assert bootstrap.status_code == 200
    created = client.post(
        "/api/simulations",
        json={"scenario_id": "flood-aricanduva", "fleet_size": 4, "seed": 42},
    )
    assert created.status_code == 202
    simulation_id = created.json()["simulation_id"]
    status = client.get(f"/api/simulations/{simulation_id}")
    assert status.json()["status"] == "completed"
    metrics = status.json()["metrics"]
    assert metrics["optimized"]["p90_seconds"] <= metrics["baseline"]["p90_seconds"]
    with client.websocket_connect(f"/api/simulations/{simulation_id}/stream") as websocket:
        frames = [websocket.receive_json() for _ in range(4)]
    assert {frame["policy"] for frame in frames} == {"baseline", "optimized"}


def test_validation_unknowns_and_offline_parser() -> None:
    client = TestClient(create_app())
    assert client.get("/api/simulations/sim-missing").status_code == 404
    invalid = client.post(
        "/api/simulations", json={"scenario_id": "bad", "fleet_size": 1, "seed": 1}
    )
    assert invalid.status_code == 422
    parsed = client.post("/api/scenario-cards/parse", json={"text": "Flood in Aricanduva"})
    assert parsed.status_code == 200
    assert parsed.json()["observation"]["type"] == "flood"
    assert parsed.json()["used_fallback"] is True
