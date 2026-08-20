from fastapi.testclient import TestClient

from city_os.api import create_app


def test_bootstrap_announces_only_real_map_layers() -> None:
    client = TestClient(create_app())
    urls = client.get("/api/bootstrap").json()["layer_urls"]
    assert urls == {
        "roads": "/map/sao-paulo.pmtiles",
        "nodes": "/api/layers/nodes",
        "edges": "/api/layers/edges",
        "h3_cells": "/api/layers/h3-cells",
    }


def test_spatial_layers_use_verified_real_artifacts() -> None:
    client = TestClient(create_app())
    nodes = client.get("/api/layers/nodes").json()
    edges = client.get("/api/layers/edges").json()
    cells = client.get("/api/layers/h3-cells").json()
    for name, payload in (("nodes", nodes), ("edges", edges), ("h3_cells", cells)):
        assert payload["schema_version"] == "1.0"
        assert payload["provenance"]["layer"] == name
        assert payload["provenance"]["simulated"] is False
        assert payload["data"]
    node_ids = {row["node_id"] for row in nodes["data"]}
    assert all(type(node_id) is int for node_id in node_ids)
    assert all(edge["u"] in node_ids and edge["v"] in node_ids for edge in edges["data"])
    assert all(type(edge["edge_id"]) is int for edge in edges["data"])


def test_pmtiles_is_served_from_local_bundle() -> None:
    response = TestClient(create_app()).get("/map/sao-paulo.pmtiles", headers={"Range": "bytes=0-15"})
    assert response.status_code in {200, 206}
    assert response.content
