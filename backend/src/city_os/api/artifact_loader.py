"""Validated, checksum-first loading of local simulation artifacts."""

from __future__ import annotations

import hashlib
import json
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from city_os.contracts import ArtifactManifest


@dataclass(frozen=True)
class SimulationWorld:
    """Validated spatial inputs loaded independently from the simulation engine."""

    nodes: tuple[dict[str, Any], ...] = ()
    edges: tuple[dict[str, Any], ...] = ()
    edge_states: tuple[dict[str, Any], ...] = ()
    densities: tuple[dict[str, Any], ...] = ()
    h3_cells: tuple[dict[str, Any], ...] = ()
    artifacts: dict[str, bytes] = field(default_factory=dict)


class ArtifactLoadError(ValueError):
    """An artifact set is absent, corrupt, unsafe, or unsupported."""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ArtifactLoadError(f"artifact manifest is missing: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactLoadError(f"artifact manifest is invalid: {path}") from error


def _entries(document: dict[str, Any]) -> list[tuple[str, str]]:
    version = document.get("schema_version")
    if version == "1.0":
        try:
            # JSON arrays are the wire representation of the contract's immutable tuples.
            manifest = ArtifactManifest.model_validate_json(json.dumps(document))
        except ValidationError as error:
            raise ArtifactLoadError(f"artifact manifest does not match schema: {error}") from error
        return [(entry.path, entry.checksum.value) for entry in manifest.artifacts]
    if version == "1.0.0" and isinstance(document.get("artifacts"), list):
        entries = []
        for entry in document["artifacts"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ArtifactLoadError("artifact manifest contains an invalid entry")
            checksum = entry.get("sha256")
            if not isinstance(checksum, str) or len(checksum) != 64:
                raise ArtifactLoadError(f"artifact checksum is invalid: {entry.get('path')}")
            entries.append((entry["path"], checksum))
        return entries
    raise ArtifactLoadError(f"unsupported artifact schema version: {version!r}")


def load_world(manifest_path: Path) -> SimulationWorld:
    """Verify all bytes in a manifest, then deserialize known simulation tables."""

    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    document = _read_manifest(manifest_path)
    blobs: dict[str, bytes] = {}
    for relative, expected in _entries(document):
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ArtifactLoadError(f"artifact path escapes manifest directory: {relative}")
        try:
            payload = candidate.read_bytes()
        except FileNotFoundError as error:
            raise ArtifactLoadError(f"artifact is missing: {relative}") from error
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ArtifactLoadError(
                f"artifact checksum mismatch for {relative}: expected {expected}, got {actual}"
            )
        blobs[relative] = payload

    def records(suffix: str) -> tuple[dict[str, Any], ...]:
        paths = [root / path for path in blobs if path.endswith(suffix)]
        if not paths:
            return ()
        try:
            return tuple(pd.read_parquet(paths[0]).to_dict(orient="records"))
        except Exception as error:
            raise ArtifactLoadError(f"unsupported or unreadable artifact: {suffix}") from error

    raw_nodes = records("nodes.parquet")
    original_ids = sorted({str(row["node_id"]) for row in raw_nodes})
    used: set[int] = set()
    node_ids: dict[str, int] = {}
    for original in original_ids:
        candidate = int(original) if original.isdecimal() else int(
            hashlib.sha256(original.encode("utf-8")).hexdigest()[:15], 16
        )
        while candidate in used:
            candidate += 1
        used.add(candidate)
        node_ids[original] = candidate
    nodes = tuple({**row, "node_id": node_ids[str(row["node_id"])]} for row in raw_nodes)

    raw_edges = records("edges.parquet")
    edges = []
    for index, row in enumerate(raw_edges):
        original_edge = str(row["edge_id"])
        edge_id = int(original_edge) if original_edge.isdecimal() else index
        geometry = row.get("geometry_wkb")
        edges.append({
            **row,
            "edge_id": edge_id,
            "u": node_ids[str(row["u"])],
            "v": node_ids[str(row["v"])],
            "geometry_wkb": base64.b64encode(geometry).decode("ascii")
            if isinstance(geometry, bytes) else geometry,
        })

    h3_cells: tuple[dict[str, Any], ...] = ()
    geojson_paths = [root / path for path in blobs if path.endswith("h3_cells.geojson")]
    if geojson_paths:
        try:
            document = json.loads(geojson_paths[0].read_text(encoding="utf-8"))
            h3_cells = tuple(
                {"cell": feature["properties"]["cell"], "geometry": feature["geometry"]}
                for feature in document["features"]
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ArtifactLoadError("unsupported or unreadable artifact: h3_cells.geojson") from error

    return SimulationWorld(
        nodes=nodes, edges=tuple(edges), h3_cells=h3_cells,
        edge_states=records("edge_state.parquet"), densities=records("h3_density.parquet"),
        artifacts=blobs,
    )
