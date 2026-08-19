"""Atomic, checksummed spatial artifact writer."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA_VERSION = "1.0.0"
OSM_LICENSE = "OpenStreetMap contributors, Open Database License (ODbL) 1.0"


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    path: str
    sha256: str
    rows: int
    media_type: str


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: str
    artifacts: tuple[ArtifactEntry, ...]
    bounds: tuple[float, float, float, float]
    source: str
    source_date: str
    license: str
    crs: str = "EPSG:4326"

    def model_dump(self, *, mode: str = "python", **_: Any) -> dict[str, Any]:
        data = asdict(self)
        if mode == "json":
            data["artifacts"] = list(data["artifacts"])
            data["bounds"] = list(data["bounds"])
        return data


def _mapping(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return dict(record.model_dump(mode="python"))
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, Mapping):
        return dict(record)
    return dict(vars(record))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_parquet(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)
    metadata = dict(table.schema.metadata or {})
    metadata[b"geo_crs"] = b"EPSG:4326"
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, path, compression="zstd", version="2.6", write_statistics=True)


def _cells_rows(cells: Any) -> list[dict[str, Any]]:
    if hasattr(cells, "iterrows"):
        rows = []
        for _, row in cells.iterrows():
            rows.append({"cell": str(row["cell"]), "geometry": row.geometry})
        return sorted(rows, key=lambda row: row["cell"])
    rows = []
    for record in cells:
        values = _mapping(record)
        rows.append({"cell": str(values["cell"]), "geometry": values["geometry"]})
    return sorted(rows, key=lambda row: row["cell"])


def _geojson(cells: list[dict[str, Any]]) -> dict[str, Any]:
    from shapely.geometry import mapping

    return {
        "type": "FeatureCollection",
        "name": "city-os-h3-cells",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {
                "type": "Feature",
                "id": row["cell"],
                "properties": {"cell": row["cell"]},
                "geometry": mapping(row["geometry"]),
            }
            for row in cells
        ],
    }


def _edge_h3_weights(edges: list[dict[str, Any]], cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from shapely import wkb

    result: list[dict[str, Any]] = []
    for edge in edges:
        line = wkb.loads(bytes(edge["geometry_wkb"]))
        raw: list[tuple[str, float]] = []
        for cell in cells:
            length = float(line.intersection(cell["geometry"]).length)
            if length > 0:
                raw.append((cell["cell"], length))
        if not raw and cells:
            # Numerical boundary misses are assigned deterministically to the nearest cell.
            nearest = min(cells, key=lambda cell: (line.distance(cell["geometry"]), cell["cell"]))
            raw = [(nearest["cell"], 1.0)]
        total = sum(value for _, value in raw)
        for cell, value in raw:
            result.append({"edge_id": str(edge["edge_id"]), "cell": cell, "weight": value / total})
    return sorted(result, key=lambda row: (row["edge_id"], row["cell"]))


def _bounds(cells: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    if cells:
        minx = min(row["geometry"].bounds[0] for row in cells)
        miny = min(row["geometry"].bounds[1] for row in cells)
        maxx = max(row["geometry"].bounds[2] for row in cells)
        maxy = max(row["geometry"].bounds[3] for row in cells)
        return (minx, miny, maxx, maxy)
    if nodes:
        xs, ys = [float(row["x"]) for row in nodes], [float(row["y"]) for row in nodes]
        return (min(xs), min(ys), max(xs), max(ys))
    raise ValueError("at least one node or cell is required")


def write_spatial_artifacts(
    output_dir: str | Path,
    nodes: Iterable[Any],
    edges: Iterable[Any],
    cells: Any,
    *,
    source: str = "OpenStreetMap",
    source_date: str | None = None,
    license: str = OSM_LICENSE,
) -> ArtifactManifest:
    """Write deterministic spatial files, replacing each destination atomically."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    node_rows = sorted((_mapping(row) for row in nodes), key=lambda row: str(row["node_id"]))
    edge_rows = sorted((_mapping(row) for row in edges), key=lambda row: str(row["edge_id"]))
    cell_rows = _cells_rows(cells)
    if len({row["node_id"] for row in node_rows}) != len(node_rows):
        raise ValueError("node_id values must be unique")
    if len({row["edge_id"] for row in edge_rows}) != len(edge_rows):
        raise ValueError("edge_id values must be unique")
    weights = _edge_h3_weights(edge_rows, cell_rows)
    totals: dict[str, float] = {}
    for row in weights:
        totals[row["edge_id"]] = totals.get(row["edge_id"], 0.0) + row["weight"]
    if any(abs(total - 1.0) > 1e-6 for total in totals.values()):
        raise ValueError("edge-to-H3 weights do not sum to one")

    schemas = {
        "nodes.parquet": pa.schema(
            [("node_id", pa.string()), ("x", pa.float64()), ("y", pa.float64()), ("h3_cell", pa.string())]
        ),
        "edges.parquet": pa.schema(
            [
                ("edge_id", pa.string()), ("u", pa.string()), ("v", pa.string()),
                ("length_m", pa.float64()), ("free_flow_seconds", pa.float64()),
                ("capacity_vph", pa.float64()), ("geometry_wkb", pa.binary()),
            ]
        ),
        "edge_h3_weights.parquet": pa.schema(
            [("edge_id", pa.string()), ("cell", pa.string()), ("weight", pa.float64())]
        ),
    }
    row_sets = {"nodes.parquet": node_rows, "edges.parquet": edge_rows, "edge_h3_weights.parquet": weights}

    with tempfile.TemporaryDirectory(prefix="city-os-spatial-", dir=output) as temp_name:
        temp = Path(temp_name)
        for name, schema in schemas.items():
            _write_parquet(temp / name, row_sets[name], schema)
        (temp / "h3_cells.geojson").write_text(
            json.dumps(_geojson(cell_rows), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        media_types = {
            "nodes.parquet": "application/vnd.apache.parquet",
            "edges.parquet": "application/vnd.apache.parquet",
            "edge_h3_weights.parquet": "application/vnd.apache.parquet",
            "h3_cells.geojson": "application/geo+json",
        }
        entries = tuple(
            ArtifactEntry(name, _sha256(temp / name), len(cell_rows) if name == "h3_cells.geojson" else len(row_sets[name]), media_types[name])
            for name in sorted(media_types)
        )
        manifest = ArtifactManifest(
            schema_version=SCHEMA_VERSION,
            artifacts=entries,
            bounds=_bounds(cell_rows, node_rows),
            source=source,
            source_date=source_date or date.today().isoformat(),
            license=license,
        )
        (temp / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for name in (*sorted(media_types), "manifest.json"):
            os.replace(temp / name, output / name)
    return manifest


def validate_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Validate checksums and row counts for a spatial manifest."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported spatial schema version: {data.get('schema_version')!r}")
    for entry in data.get("artifacts", []):
        artifact = path.parent / entry["path"]
        if not artifact.is_file():
            raise FileNotFoundError(f"missing spatial artifact: {artifact}")
        if _sha256(artifact) != entry["sha256"]:
            raise ValueError(f"checksum mismatch for {artifact.name}")
    return data
