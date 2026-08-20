#!/usr/bin/env python3
"""Build a privacy-safe H3 demand profile from the official CET accident layer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import h3
import pandas as pd

SOURCE_URL = (
    "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=geoportal%3Aacidente_cet"
    "&outputFormat=application%2Fjson&srsName=EPSG%3A4326"
)
METADATA_URL = (
    "https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/resources/"
    "datasets/597833ac-aa90-4b4b-8a48-3be0a9a8c009"
)
LICENSE_URL = (
    "https://prefeitura.sp.gov.br/web/licenciamento/w/"
    "licen%C3%A7a-para-uso-de-dados-do-geosampa"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_source(path: Path | None) -> tuple[dict[str, Any], bytes]:
    if path is None:
        with urllib.request.urlopen(SOURCE_URL, timeout=120) as response:  # noqa: S310
            payload = response.read()
    else:
        payload = path.read_bytes()
    return json.loads(payload.decode("utf-8")), payload


def _distance_sq(lon: float, lat: float, center_lon: float, center_lat: float) -> float:
    longitude_scale = math.cos(math.radians(center_lat))
    return ((lon - center_lon) * longitude_scale) ** 2 + (lat - center_lat) ** 2


def build_profile(
    source: Path | None,
    nodes_path: Path,
    cells_path: Path,
    output: Path,
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    document, source_bytes = _load_source(source)
    features = document.get("features")
    if not isinstance(features, list):
        raise ValueError("CET source must be a GeoJSON FeatureCollection")

    cells_document = json.loads(cells_path.read_text(encoding="utf-8"))
    eligible_cells = {
        str(feature["properties"]["cell"])
        for feature in cells_document.get("features", [])
    }
    if not eligible_cells:
        raise ValueError("spatial H3 artifact is empty")

    nodes = pd.read_parquet(nodes_path)
    nodes_by_cell: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for row in nodes.to_dict(orient="records"):
        cell = str(row["h3_cell"])
        if cell in eligible_cells:
            nodes_by_cell[cell].append((int(row["node_id"]), float(row["x"]), float(row["y"])))

    aggregate: dict[str, dict[str, Any]] = {}
    dates: list[str] = []
    retained = 0
    for feature in features:
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        longitude, latitude = float(coordinates[0]), float(coordinates[1])
        cell = h3.latlng_to_cell(latitude, longitude, 8)
        if cell not in eligible_cells or cell not in nodes_by_cell:
            continue
        properties = feature.get("properties") or {}
        hour_value = str(properties.get("ho_acidente", ""))
        try:
            hour = int(hour_value[11:13])
        except (TypeError, ValueError):
            hour = 0
        date = str(properties.get("dt_acidente", ""))[:10]
        if date:
            dates.append(date)
        row = aggregate.setdefault(
            cell,
            {
                "historical_occurrences": 0,
                "injured": 0,
                "fatalities": 0,
                "hourly_occurrences": [0] * 24,
            },
        )
        row["historical_occurrences"] += 1
        row["injured"] += max(0, int(properties.get("qt_ferido") or 0))
        row["fatalities"] += max(0, int(properties.get("qt_fatal") or 0))
        row["hourly_occurrences"][hour] += 1
        retained += 1

    if not aggregate:
        raise ValueError("no CET occurrences overlap the routable H3 coverage")

    total_weight = sum(row["historical_occurrences"] for row in aggregate.values())
    points: list[dict[str, Any]] = []
    hourly_totals = [0] * 24
    for cell in sorted(aggregate):
        center_lat, center_lon = h3.cell_to_latlng(cell)
        node_id, longitude, latitude = min(
            nodes_by_cell[cell],
            key=lambda node: (_distance_sq(node[1], node[2], center_lon, center_lat), node[0]),
        )
        row = aggregate[cell]
        for hour, count in enumerate(row["hourly_occurrences"]):
            hourly_totals[hour] += count
        points.append(
            {
                "id": f"demand:{cell}",
                "node_id": node_id,
                "h3_cell": cell,
                "longitude": longitude,
                "latitude": latitude,
                "historical_occurrences": row["historical_occurrences"],
                "injured": row["injured"],
                "fatalities": row["fatalities"],
                "hourly_occurrences": row["hourly_occurrences"],
                "weight": row["historical_occurrences"] / total_weight,
            }
        )

    profile = {
        "schema_version": "1.0",
        "data_class": "observed_aggregate_proxy",
        "label": "Proxy agregado de demanda pré-hospitalar baseado em acidentes CET",
        "source": {
            "publisher": "CET/GeoSampa, Prefeitura de São Paulo",
            "dataset": "Acidentes de trânsito com vítimas (INFOCRIM/RDO)",
            "url": SOURCE_URL,
            "metadata_url": METADATA_URL,
            "license": "CC BY-SA 4.0",
            "license_url": LICENSE_URL,
            "retrieved_at": retrieved_at,
            "sha256": _sha256(source_bytes),
            "observed_from": min(dates) if dates else None,
            "observed_to": max(dates) if dates else None,
        },
        "coverage": {
            "source_occurrences": len(features),
            "retained_occurrences": retained,
            "routable_h3_cells": len(eligible_cells),
            "covered_h3_cells": len(points),
            "h3_resolution": 8,
        },
        "modeling": {
            "use": "relative spatial and hourly weights only",
            "runtime_calls": "synthetic seeded draws",
            "absolute_volume": "simulated calibration, not a measured SAMU call rate",
            "privacy": "incident identifiers, addresses, exact coordinates and exact timestamps removed",
        },
        "hourly_occurrences": hourly_totals,
        "points": points,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--nodes", required=True, type=Path)
    parser.add_argument("--cells", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()
    profile = build_profile(
        args.source,
        args.nodes,
        args.cells,
        args.output,
        retrieved_at=args.retrieved_at,
    )
    print(
        f"wrote {len(profile['points'])} aggregate demand points from "
        f"{profile['coverage']['retained_occurrences']} retained occurrences"
    )


if __name__ == "__main__":
    main()
