from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data" / "fixtures" / "flow"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))


def test_fixture_manifest_checksums_and_frozen_schemas() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["fixture_type"] == "synthetic_acceptance_fixture"
    assert manifest["production_artifacts"] is False
    for entry in manifest["artifacts"]:
        path = FIXTURE / entry["path"]
        assert path.is_file()
        assert _sha256(path) == entry["sha256"]
        if path.suffix == ".parquet":
            assert pq.read_metadata(path).num_rows == entry["rows"]

    expected = {
        "spatial/nodes.parquet": ["node_id", "x", "y", "h3_cell"],
        "spatial/edges.parquet": [
            "edge_id", "u", "v", "length_m", "free_flow_seconds", "capacity_vph", "geometry_wkb"
        ],
        "camera_observations.parquet": [
            "camera_id", "edge_id", "bucket_start", "object_class", "direction", "count", "confidence"
        ],
        "derived/edge_state.parquet": [
            "edge_id", "bucket_start", "flow_vph", "speed_kph", "travel_seconds", "occupancy_people", "confidence"
        ],
        "derived/h3_density.parquet": [
            "cell", "bucket_start", "density_people_km2", "emergency_intensity_hour", "confidence"
        ],
    }
    for relative, names in expected.items():
        assert pq.read_schema(FIXTURE / relative).names == names


def test_graph_h3_and_edge_references_are_complete() -> None:
    nodes = pq.read_table(FIXTURE / "spatial" / "nodes.parquet").to_pylist()
    edges = pq.read_table(FIXTURE / "spatial" / "edges.parquet").to_pylist()
    edge_states = pq.read_table(FIXTURE / "derived" / "edge_state.parquet").to_pylist()
    density = pq.read_table(FIXTURE / "derived" / "h3_density.parquet").to_pylist()
    node_cells = {row["h3_cell"] for row in nodes}
    density_cells = {row["cell"] for row in density}
    assert density_cells <= node_cells
    assert all(any(node["h3_cell"] == cell for node in nodes) for cell in density_cells)
    edge_ids = {row["edge_id"] for row in edges}
    assert {row["edge_id"] for row in edge_states} <= edge_ids


def test_observed_direction_influences_matching_arc_more_than_reverse() -> None:
    directed = _manifest()["directed_observation"]
    observations = pq.read_table(FIXTURE / "camera_observations.parquet").to_pylist()
    assert {row["edge_id"] for row in observations} == {directed["observed_edge_id"]}
    states = pq.read_table(FIXTURE / "derived" / "edge_state.parquet").to_pylist()
    by_bucket = {}
    for row in states:
        by_bucket.setdefault(row["bucket_start"], {})[row["edge_id"]] = row["flow_vph"]
    assert all(
        values[directed["observed_edge_id"]] > values[directed["reverse_edge_id"]]
        for values in by_bucket.values()
    )


def test_shared_contracts_validate_fixture_when_developer_b_is_present() -> None:
    try:
        contracts = importlib.import_module("city_os.contracts.artifacts")
    except ImportError:
        # C0 is owned by Developer B and is not present in this repository yet.
        return
    mappings = [
        ("RoadNode", FIXTURE / "spatial" / "nodes.parquet"),
        ("RoadEdge", FIXTURE / "spatial" / "edges.parquet"),
        ("CameraObservation", FIXTURE / "camera_observations.parquet"),
        ("EdgeState", FIXTURE / "derived" / "edge_state.parquet"),
        ("H3Density", FIXTURE / "derived" / "h3_density.parquet"),
    ]
    for model_name, path in mappings:
        model = getattr(contracts, model_name)
        for row in pq.read_table(path).to_pylist():
            model.model_validate(row)
