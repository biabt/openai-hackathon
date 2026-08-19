#!/usr/bin/env python3
"""Build deterministic edge-state and H3-density artifacts from observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from city_os.flow import aggregate_h3_density, bpr_travel_seconds, estimate_edge_flows


DEFAULT_OCCUPANCY_PRIORS = {
    "bicycle": 1.0,
    "bus": 25.0,
    "car": 1.5,
    "default": 1.5,
    "motorcycle": 1.0,
    "truck": 1.2,
}
DEFAULT_ESTIMATOR_PARAMETERS = {
    "lambda_spatial": 0.25,
    "lambda_temporal": 1.0,
    "lambda_conservation": 0.5,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_source_path(path: Path, output: Path) -> str:
    """Return a relocatable source path instead of leaking a checkout path."""
    return Path(os.path.relpath(path, output)).as_posix()


def _artifact_candidates(manifest: dict[str, Any]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    artifacts = manifest.get("artifacts", manifest.get("files", {}))
    if isinstance(artifacts, dict):
        for name, value in artifacts.items():
            if isinstance(value, str):
                candidates[str(name)] = value
            elif isinstance(value, dict) and (path := value.get("path") or value.get("file")):
                candidates[str(name)] = str(path)
    elif isinstance(artifacts, list):
        for value in artifacts:
            if isinstance(value, dict) and (path := value.get("path") or value.get("file")):
                candidates[str(value.get("name", Path(str(path)).stem))] = str(path)
    return candidates


def _resolve_source(manifest_path: Path, manifest: dict[str, Any], names: tuple[str, ...]) -> Path:
    candidates = _artifact_candidates(manifest)
    for name in names:
        for key, value in candidates.items():
            if key == name or Path(value).name == name:
                path = (manifest_path.parent / value).resolve()
                if path.is_file():
                    return path
        path = (manifest_path.parent / name).resolve()
        if path.is_file():
            return path
    raise FileNotFoundError(f"spatial manifest does not reference any of: {', '.join(names)}")


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise ImportError("build_flow_artifacts requires pyarrow") from exc
    return parquet.read_table(path).to_pylist()


def _read_cells(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".parquet":
        return _read_parquet(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection":
        raise ValueError("H3 GeoJSON must be a FeatureCollection")
    try:
        from pyproj import Geod
    except ImportError as exc:  # pragma: no cover - part of the spatial build dependencies
        raise ImportError("reading H3 GeoJSON areas requires pyproj") from exc
    geod = Geod(ellps="WGS84")

    def polygon_area(rings: list[list[list[float]]]) -> float:
        if not rings:
            return 0.0
        exterior = abs(geod.polygon_area_perimeter(*zip(*rings[0]))[0])
        holes = sum(abs(geod.polygon_area_perimeter(*zip(*ring))[0]) for ring in rings[1:])
        return max(exterior - holes, 0.0)

    result: list[dict[str, Any]] = []
    for feature in document.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "Polygon":
            area_m2 = polygon_area(geometry.get("coordinates", []))
        elif geometry.get("type") == "MultiPolygon":
            area_m2 = sum(polygon_area(polygon) for polygon in geometry.get("coordinates", []))
        else:
            raise ValueError("H3 GeoJSON features must be Polygon or MultiPolygon")
        result.append(
            {
                "cell": feature.get("properties", {}).get("cell", feature.get("id")),
                "area_km2": area_m2 / 1_000_000.0,
            }
        )
    return result


def _write_parquet(path: Path, rows: list[dict[str, Any]], schema: Any) -> None:
    import pyarrow as pa
    import pyarrow.parquet as parquet

    temporary = path.with_name(f".{path.name}.tmp")
    table = pa.Table.from_pylist(rows, schema=schema)
    parquet.write_table(table, temporary, compression="zstd", write_statistics=True)
    os.replace(temporary, path)


def _bucket(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_matrices(edges: list[dict[str, Any]]) -> tuple[Any, Any]:
    from scipy import sparse

    nodes = sorted({str(edge[endpoint]) for edge in edges for endpoint in ("u", "v")})
    node_index = {node: index for index, node in enumerate(nodes)}
    row: list[int] = []
    column: list[int] = []
    data: list[float] = []
    for index, edge in enumerate(edges):
        row.extend((node_index[str(edge["u"])], node_index[str(edge["v"])]))
        column.extend((index, index))
        data.extend((-1.0, 1.0))
    incidence = sparse.coo_matrix((data, (row, column)), shape=(len(nodes), len(edges))).tocsr()
    shared = (abs(incidence).T @ abs(incidence)).tocsr()
    shared.setdiag(0.0)
    shared.eliminate_zeros()
    shared.data[:] = 1.0
    laplacian = sparse.diags(np.asarray(shared.sum(axis=1)).ravel()) - shared
    return incidence, laplacian


def _cell_areas(rows: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        cell = str(row.get("cell", row.get("h3_cell")))
        area = row.get("area_km2")
        if area is None:
            try:
                import h3
            except ImportError as exc:  # pragma: no cover - only for older spatial artifacts
                raise ValueError("h3_cells must contain area_km2 when h3 is unavailable") from exc
            area = h3.cell_area(cell, unit="km^2")
        result[cell] = float(area)
    return result


def build_flow_artifacts(
    spatial_manifest: Path,
    observations: Path,
    output: Path,
    *,
    estimator_parameters: dict[str, float] | None = None,
    occupancy_priors: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build both flow artifacts and return their written manifest."""
    spatial_manifest = Path(spatial_manifest).resolve()
    observations = Path(observations).resolve()
    output = Path(output).resolve()
    if not spatial_manifest.is_file() or not observations.is_file():
        raise FileNotFoundError("spatial manifest and observations must be existing local files")
    spatial = json.loads(spatial_manifest.read_text(encoding="utf-8"))
    edge_path = _resolve_source(spatial_manifest, spatial, ("road_edges.parquet", "edges.parquet"))
    weight_path = _resolve_source(spatial_manifest, spatial, ("edge_h3_weights.parquet",))
    cell_path = _resolve_source(spatial_manifest, spatial, ("h3_cells.parquet", "h3_cells.geojson"))

    edges = sorted(_read_parquet(edge_path), key=lambda row: str(row["edge_id"]))
    if not edges:
        raise ValueError("road edge artifact is empty")
    edge_index = {str(edge["edge_id"]): index for index, edge in enumerate(edges)}
    weights = _read_parquet(weight_path)
    areas = _cell_areas(_read_cells(cell_path))
    observations_rows = _read_parquet(observations)
    unknown = sorted({str(row["edge_id"]) for row in observations_rows} - set(edge_index))
    if unknown:
        raise ValueError(f"observations reference unknown edge IDs: {unknown}")

    parameters = dict(DEFAULT_ESTIMATOR_PARAMETERS)
    parameters.update(estimator_parameters or {})
    priors = dict(DEFAULT_OCCUPANCY_PRIORS)
    priors.update(occupancy_priors or {})
    incidence, laplacian = _build_matrices(edges)
    grouped: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in observations_rows:
        grouped[_bucket(row["bucket_start"])].append(row)

    previous = np.zeros(len(edges), dtype=float)
    edge_states: list[dict[str, Any]] = []
    for bucket in sorted(grouped):
        by_edge: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in grouped[bucket]:
            if str(row.get("object_class", "")) != "person":
                by_edge[str(row["edge_id"])].append(row)
        observed_edges = sorted(by_edge)
        from scipy import sparse

        H = sparse.coo_matrix(
            (np.ones(len(observed_edges)), (np.arange(len(observed_edges)), [edge_index[e] for e in observed_edges])),
            shape=(len(observed_edges), len(edges)),
        ).tocsr()
        values = np.asarray([sum(float(row["count"]) for row in by_edge[edge]) * 12.0 for edge in observed_edges])
        confidences = np.asarray(
            [
                sum(float(row["confidence"]) * float(row["count"]) for row in by_edge[edge])
                / max(sum(float(row["count"]) for row in by_edge[edge]), 1.0)
                for edge in observed_edges
            ]
        )
        flow = estimate_edge_flows(
            incidence,
            laplacian,
            H,
            values,
            previous,
            weights=confidences,
            **parameters,
        )
        observed_confidence = {edge: float(confidences[i]) for i, edge in enumerate(observed_edges)}
        network_confidence = float(np.mean(confidences)) * 0.5 if len(confidences) else 0.0
        for index, edge in enumerate(edges):
            edge_id = str(edge["edge_id"])
            travel = float(
                bpr_travel_seconds(
                    edge["free_flow_seconds"], flow[index], edge["capacity_vph"]
                )
            )
            speed = float(edge["length_m"]) / travel * 3.6 if travel > 0 else 0.0
            class_counts: dict[str, float] = defaultdict(float)
            for row in by_edge.get(edge_id, []):
                class_counts[str(row["object_class"])] += float(row["count"])
            count_total = sum(class_counts.values())
            occupancy_factor = (
                sum(priors.get(kind, priors["default"]) * count for kind, count in class_counts.items()) / count_total
                if count_total
                else priors["default"]
            )
            edge_states.append(
                {
                    "edge_id": edge_id,
                    "bucket_start": bucket,
                    "flow_vph": float(flow[index]),
                    "speed_kph": speed,
                    "travel_seconds": travel,
                    "occupancy_people": float(flow[index] * travel / 3600.0 * occupancy_factor),
                    "confidence": observed_confidence.get(edge_id, network_confidence),
                }
            )
        previous = flow

    densities = aggregate_h3_density(edge_states, weights, areas, priors)
    density_rows = [
        dict(row) if isinstance(row, dict) else row.model_dump(mode="python")
        for row in densities
    ]
    edge_states.sort(key=lambda row: (row["bucket_start"], row["edge_id"]))
    density_rows.sort(key=lambda row: (row["bucket_start"], row["cell"]))

    import pyarrow as pa

    output.mkdir(parents=True, exist_ok=True)
    edge_output = output / "edge_state.parquet"
    density_output = output / "h3_density.parquet"
    _write_parquet(
        edge_output,
        edge_states,
        pa.schema(
            [
                ("edge_id", pa.string()),
                ("bucket_start", pa.timestamp("us", tz="UTC")),
                ("flow_vph", pa.float64()),
                ("speed_kph", pa.float64()),
                ("travel_seconds", pa.float64()),
                ("occupancy_people", pa.float64()),
                ("confidence", pa.float64()),
            ]
        ),
    )
    _write_parquet(
        density_output,
        density_rows,
        pa.schema(
            [
                ("cell", pa.string()),
                ("bucket_start", pa.timestamp("us", tz="UTC")),
                ("density_people_km2", pa.float64()),
                ("emergency_intensity_hour", pa.float64()),
                ("confidence", pa.float64()),
            ]
        ),
    )
    manifest = {
        "schema_version": "1.0.0",
        "sources": {
            "spatial_manifest": {
                "path": _manifest_source_path(spatial_manifest, output),
                "sha256": _sha256(spatial_manifest),
            },
            "observations": {
                "path": _manifest_source_path(observations, output),
                "sha256": _sha256(observations),
            },
        },
        "estimator_parameters": {key: parameters[key] for key in sorted(parameters)},
        "occupancy_priors": {key: priors[key] for key in sorted(priors)},
        "artifacts": {
            "edge_state": {"path": edge_output.name, "rows": len(edge_states), "sha256": _sha256(edge_output)},
            "h3_density": {"path": density_output.name, "rows": len(density_rows), "sha256": _sha256(density_output)},
        },
    }
    manifest_path = output / "manifest.json"
    temporary_manifest = output / ".manifest.json.tmp"
    temporary_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary_manifest, manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spatial-manifest", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build_flow_artifacts(args.spatial_manifest, args.observations, args.output)


if __name__ == "__main__":
    main()
