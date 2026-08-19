#!/usr/bin/env python3
"""Build spatial artifacts from explicit local PBF and boundary inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True, help="Local, clipped OSM PBF; no download is attempted")
    parser.add_argument("--boundary", type=Path, required=True, help="Local municipal boundary GeoJSON")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=8, choices=range(16))
    return parser.parse_args()


def _graph_from_pbf(path: Path):
    try:
        import networkx as nx
        from pyrosm import OSM
    except ImportError as exc:
        raise SystemExit("building from PBF requires the pyrosm and networkx build dependencies") from exc
    osm = OSM(str(path))
    nodes_frame, edges_frame = osm.get_network(network_type="driving", nodes=True)
    graph = nx.MultiDiGraph()
    for row in nodes_frame.itertuples():
        graph.add_node(row.id, x=float(row.lon), y=float(row.lat))
    for index, row in enumerate(edges_frame.itertuples()):
        graph.add_edge(
            row.u,
            row.v,
            key=getattr(row, "id", index),
            osmid=getattr(row, "id", index),
            highway=getattr(row, "highway", "unclassified"),
            maxspeed=getattr(row, "maxspeed", None),
            lanes=getattr(row, "lanes", None),
            length=float(row.length),
            geometry=row.geometry,
        )
    return graph


def main() -> None:
    args = parse_args()
    for label, path in (("PBF", args.pbf), ("boundary", args.boundary)):
        if not path.is_file():
            raise SystemExit(f"{label} input does not exist: {path}; this command never downloads inputs")
    import geopandas as gpd
    from city_os.spatial import build_h3_grid, normalize_osm_graph, write_spatial_artifacts

    boundary = gpd.read_file(args.boundary)
    if boundary.empty:
        raise SystemExit("municipal boundary contains no features")
    graph = _graph_from_pbf(args.pbf)
    nodes, edges = normalize_osm_graph(graph, resolution=args.resolution)
    cells = build_h3_grid(boundary, resolution=args.resolution)
    source_metadata_path = args.pbf.with_suffix(args.pbf.suffix + ".source.json")
    source_metadata = json.loads(source_metadata_path.read_text()) if source_metadata_path.is_file() else {}
    manifest = write_spatial_artifacts(
        args.output,
        nodes,
        edges,
        cells,
        source=f"OpenStreetMap extract {args.pbf.name}",
        source_date=source_metadata.get("source_date", "not-recorded"),
    )
    print(json.dumps(manifest.model_dump(mode="json"), sort_keys=True))


if __name__ == "__main__":
    main()
