#!/usr/bin/env python3
"""Build the reproducible central Sao Paulo MVP graph/H3 artifact bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphml", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subset-boundary-output", type=Path, required=True)
    args = parser.parse_args()

    import geopandas as gpd
    import h3
    import osmnx as ox
    from shapely import wkb
    from shapely.geometry import LineString, box

    from city_os.spatial import build_h3_grid, write_spatial_artifacts

    graph = ox.load_graphml(args.graphml)
    official = gpd.read_file(args.boundary).to_crs("EPSG:4326")
    extent = box(-46.67, -23.585, -46.60, -23.515)
    boundary_geometry = official.geometry.union_all().intersection(extent)
    subset = gpd.GeoDataFrame(
        {"name": ["Sao Paulo central demo subset"], "geometry": [boundary_geometry]},
        crs="EPSG:4326",
    )
    args.subset_boundary_output.parent.mkdir(parents=True, exist_ok=True)
    subset.to_file(args.subset_boundary_output, driver="GeoJSON")
    nodes = [
        {"node_id": str(node), "x": float(data["x"]), "y": float(data["y"]),
         "h3_cell": h3.latlng_to_cell(float(data["y"]), float(data["x"]), 8)}
        for node, data in graph.nodes(data=True)
    ]
    edges = []
    ordered_edges = sorted(
        graph.edges(keys=True, data=True), key=lambda row: (int(row[0]), int(row[1]), str(row[2]))
    )
    for edge_id, (u, v, _key, data) in enumerate(ordered_edges):
        geometry = data.get("geometry") or LineString([
            (float(graph.nodes[u]["x"]), float(graph.nodes[u]["y"])),
            (float(graph.nodes[v]["x"]), float(graph.nodes[v]["y"])),
        ])
        length = max(0.01, float(data["length"]))
        match = re.search(r"\d+(?:\.\d+)?", str(data.get("maxspeed", "")))
        speed_kph = max(5.0, float(match.group())) if match else 30.0
        edges.append({
            "edge_id": str(edge_id), "u": str(u), "v": str(v), "length_m": length,
            "free_flow_seconds": length / (speed_kph * 1000 / 3600), "capacity_vph": 600.0,
            "geometry_wkb": bytes(wkb.dumps(geometry, hex=False, output_dimension=2, byte_order=1)),
        })
    cells = build_h3_grid(boundary_geometry, resolution=8)
    manifest = write_spatial_artifacts(
        args.output, nodes, edges, cells,
        source="OpenStreetMap live Overpass extract, fixed central Sao Paulo extent",
        source_date="2026-08-19",
    )
    print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
