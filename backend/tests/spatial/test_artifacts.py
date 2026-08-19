from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Polygon

from city_os.spatial.artifacts import validate_manifest, write_spatial_artifacts
from city_os.spatial.h3_grid import build_h3_grid
from city_os.spatial.osm_graph import normalize_osm_graph


def toy_world():
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-46.65, y=-23.56)
    graph.add_node(2, x=-46.64, y=-23.55)
    graph.add_node(3, x=-46.63, y=-23.54)
    graph.add_edge(1, 2, key=0, length=1_500, highway="primary", maxspeed=50)
    graph.add_edge(2, 1, key=0, length=1_500, highway="primary", maxspeed=50)
    graph.add_edge(2, 3, key=0, length=1_500, highway="secondary", maxspeed=40)
    boundary = Polygon([(-46.67, -23.58), (-46.61, -23.58), (-46.61, -23.52), (-46.67, -23.52)])
    nodes, edges = normalize_osm_graph(graph)
    return nodes, edges, build_h3_grid(boundary)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_artifact_round_trip_checksums_crs_and_weights(tmp_path: Path) -> None:
    nodes, edges, cells = toy_world()
    manifest = write_spatial_artifacts(tmp_path, nodes, edges, cells, source_date="2026-08-19")
    loaded = validate_manifest(tmp_path / "manifest.json")

    assert manifest.schema_version == "1.0.0"
    assert loaded["crs"] == "EPSG:4326"
    assert gpd.read_file(tmp_path / "h3_cells.geojson").crs.to_epsg() == 4326
    assert pq.read_table(tmp_path / "nodes.parquet").schema.metadata[b"geo_crs"] == b"EPSG:4326"
    assert pq.read_table(tmp_path / "edges.parquet").column("geometry_wkb").type.__str__() == "string"
    weights = pq.read_table(tmp_path / "edge_h3_weights.parquet").to_pandas()
    assert weights.groupby("edge_id")["weight"].sum().tolist() == pytest.approx([1.0] * len(edges), abs=1e-6)
    assert {entry["sha256"] for entry in loaded["artifacts"]} == {
        digest(tmp_path / entry["path"]) for entry in loaded["artifacts"]
    }


def test_artifacts_are_deterministic_and_mutation_is_rejected(tmp_path: Path) -> None:
    nodes, edges, cells = toy_world()
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_spatial_artifacts(first, reversed(nodes), reversed(edges), cells.iloc[::-1], source_date="2026-08-19")
    write_spatial_artifacts(second, nodes, edges, cells, source_date="2026-08-19")
    for name in ("nodes.parquet", "edges.parquet", "h3_cells.geojson", "edge_h3_weights.parquet", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    artifact = first / "nodes.parquet"
    artifact.write_bytes(artifact.read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        validate_manifest(first / "manifest.json")


def test_manifest_is_complete_json(tmp_path: Path) -> None:
    nodes, edges, cells = toy_world()
    write_spatial_artifacts(tmp_path, nodes, edges, cells, source_date="2026-08-19")
    data = json.loads((tmp_path / "manifest.json").read_text())
    assert data["bounds"][0] < -46.6
    assert data["source"] == "OpenStreetMap"
    assert data["license"].startswith("OpenStreetMap contributors")
    assert {item["path"] for item in data["artifacts"]} == {
        "nodes.parquet", "edges.parquet", "h3_cells.geojson", "edge_h3_weights.parquet"
    }
