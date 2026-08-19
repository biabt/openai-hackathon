#!/usr/bin/env python3
"""Rebuild the deterministic two-district Developer A acceptance fixture."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from build_flow_artifacts import build_flow_artifacts
from city_os.spatial import normalize_osm_graph, write_spatial_artifacts


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell_polygon(cell: str):
    import h3
    from shapely.geometry import Polygon

    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(cell)])


def _write_observations(path: Path, forward_edge: str) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = [
        {
            "camera_id": "fixture-camera-west-east",
            "edge_id": forward_edge,
            "bucket_start": datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
            "object_class": "car",
            "direction": "a_to_b",
            "count": 30,
            "confidence": 0.95,
        },
        {
            "camera_id": "fixture-camera-west-east",
            "edge_id": forward_edge,
            "bucket_start": datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
            "object_class": "bus",
            "direction": "a_to_b",
            "count": 3,
            "confidence": 0.90,
        },
        {
            "camera_id": "fixture-camera-west-east",
            "edge_id": forward_edge,
            "bucket_start": datetime(2026, 8, 19, 12, 5, tzinfo=timezone.utc),
            "object_class": "car",
            "direction": "a_to_b",
            "count": 36,
            "confidence": 0.92,
        },
    ]
    schema = pa.schema(
        [
            ("camera_id", pa.string()),
            ("edge_id", pa.string()),
            ("bucket_start", pa.timestamp("us", tz="UTC")),
            ("object_class", pa.string()),
            ("direction", pa.string()),
            ("count", pa.int64()),
            ("confidence", pa.float64()),
        ],
        metadata={b"city_os_privacy": b"aggregate_only_no_track_identifiers_no_frames"},
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")
    return len(rows)


def _artifact_rows(path: Path) -> int:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        return pq.read_metadata(path).num_rows
    if path.suffix == ".geojson":
        return len(json.loads(path.read_text(encoding="utf-8"))["features"])
    return 0


def build_fixture(output: Path) -> dict[str, object]:
    import geopandas as gpd
    import h3
    import networkx as nx

    graph = nx.MultiDiGraph()
    coordinates = {
        "west-1": (-46.6500, -23.5600),
        "west-2": (-46.6475, -23.5585),
        "east-1": (-46.6350, -23.5510),
        "east-2": (-46.6325, -23.5495),
    }
    for node_id, (x, y) in coordinates.items():
        graph.add_node(node_id, x=x, y=y)
    arcs = [
        ("west-1", "west-2", "west-forward", "residential", 30),
        ("west-2", "west-1", "west-reverse", "residential", 30),
        ("west-2", "east-1", "connector-forward", "primary", 50),
        ("east-1", "west-2", "connector-reverse", "primary", 50),
        ("east-1", "east-2", "east-forward", "secondary", 40),
        ("east-2", "east-1", "east-reverse", "secondary", 40),
    ]
    for u, v, key, highway, speed in arcs:
        graph.add_edge(u, v, key=key, highway=highway, maxspeed=speed, osmid=key)

    nodes, edges = normalize_osm_graph(graph, resolution=8)
    cells = sorted({node.h3_cell for node in nodes})
    if len(cells) != 2:
        raise RuntimeError(f"fixture coordinates must produce exactly two H3 cells, got {cells}")
    cell_frame = gpd.GeoDataFrame(
        [{"cell": cell, "geometry": _cell_polygon(cell)} for cell in cells],
        geometry="geometry",
        crs="EPSG:4326",
    )
    forward = next(edge for edge in edges if edge.u == "west-2" and edge.v == "east-1")
    reverse = next(edge for edge in edges if edge.u == "east-1" and edge.v == "west-2")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="city-os-flow-fixture-", dir=output.parent) as temp_name:
        temp = Path(temp_name)
        spatial = temp / "spatial"
        derived = temp / "derived"
        spatial.mkdir()
        derived.mkdir()
        write_spatial_artifacts(
            spatial,
            nodes,
            edges,
            cell_frame,
            source="repository-authored two-district topology",
            source_date="2026-08-19",
            license="Repository fixture; not an OpenStreetMap extract",
        )
        observation_path = temp / "camera_observations.parquet"
        observation_rows = _write_observations(observation_path, forward.edge_id)
        build_flow_artifacts(spatial / "manifest.json", observation_path, derived)

        artifact_paths = sorted(
            list(spatial.iterdir())
            + [observation_path]
            + list(derived.iterdir()),
            key=lambda path: path.relative_to(temp).as_posix(),
        )
        artifacts = [
            {
                "path": path.relative_to(temp).as_posix(),
                "rows": observation_rows if path == observation_path else _artifact_rows(path),
                "sha256": _sha256(path),
            }
            for path in artifact_paths
        ]
        manifest: dict[str, object] = {
            "schema_version": "1.0.0",
            "fixture_id": "two-district-directed-flow-v1",
            "fixture_type": "synthetic_acceptance_fixture",
            "production_artifacts": False,
            "build_command": "python3 scripts/build_flow_fixture.py --output data/fixtures/flow",
            "privacy": "Aggregate object counts only; no frames or persistent track identifiers.",
            "district_cells": {"east": cells[0], "west": cells[1]},
            "directed_observation": {
                "observed_edge_id": forward.edge_id,
                "reverse_edge_id": reverse.edge_id,
                "direction": "a_to_b",
            },
            "artifacts": artifacts,
            "component_manifests": {
                "spatial": "spatial/manifest.json",
                "flow": "derived/manifest.json",
            },
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        if output.exists():
            for child in sorted(output.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        else:
            output.mkdir()
        for child in sorted(temp.iterdir()):
            shutil.move(str(child), output / child.name)
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data" / "fixtures" / "flow")
    args = parser.parse_args()
    manifest = build_fixture(args.output.resolve())
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
