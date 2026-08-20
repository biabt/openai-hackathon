"""Validated, privacy-safe demand profile used by the local API."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h3  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class DemandProfilePoint:
    id: str
    node_id: int
    h3_cell: str
    longitude: float
    latitude: float
    historical_occurrences: int
    injured: int
    fatalities: int
    hourly_occurrences: tuple[int, ...]
    weight: float

    def layer_record(self) -> dict[str, object]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "h3_cell": self.h3_cell,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "historical_occurrences": self.historical_occurrences,
            "injured": self.injured,
            "fatalities": self.fatalities,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class DemandProfile:
    points: tuple[DemandProfilePoint, ...]
    hourly_occurrences: tuple[int, ...]
    source: dict[str, object]
    coverage: dict[str, object]
    modeling: dict[str, object]
    checksum: str
    label: str

    @property
    def point_by_node(self) -> dict[int, DemandProfilePoint]:
        return {point.node_id: point for point in self.points}

    def layer_records(self) -> tuple[dict[str, object], ...]:
        return tuple(point.layer_record() for point in self.points)


def default_profile_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "demo" / "demand" / "demand_profile.json"


def load_demand_profile(path: Path | None = None) -> DemandProfile:
    profile_path = (path or default_profile_path()).resolve()
    payload = profile_path.read_bytes()
    document: dict[str, Any] = json.loads(payload.decode("utf-8"))
    if document.get("schema_version") != "1.0":
        raise ValueError("unsupported demand profile schema")
    if document.get("data_class") != "observed_aggregate_proxy":
        raise ValueError("demand profile must remain an observed aggregate proxy")

    raw_points = document.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("demand profile has no points")
    points: list[DemandProfilePoint] = []
    seen_ids: set[str] = set()
    seen_cells: set[str] = set()
    for raw in raw_points:
        cell = str(raw["h3_cell"])
        if not h3.is_valid_cell(cell) or h3.get_resolution(cell) != 8:
            raise ValueError(f"invalid demand H3 cell: {cell}")
        point_id = str(raw["id"])
        if point_id in seen_ids or cell in seen_cells:
            raise ValueError("demand profile point IDs and cells must be unique")
        hourly = tuple(int(value) for value in raw["hourly_occurrences"])
        if len(hourly) != 24 or any(value < 0 for value in hourly):
            raise ValueError("demand hourly occurrence vectors must contain 24 non-negative values")
        point = DemandProfilePoint(
            id=point_id,
            node_id=int(raw["node_id"]),
            h3_cell=cell,
            longitude=float(raw["longitude"]),
            latitude=float(raw["latitude"]),
            historical_occurrences=int(raw["historical_occurrences"]),
            injured=int(raw["injured"]),
            fatalities=int(raw["fatalities"]),
            hourly_occurrences=hourly,
            weight=float(raw["weight"]),
        )
        if point.node_id < 0 or point.historical_occurrences <= 0:
            raise ValueError("demand points require a real node and positive aggregate count")
        if not all(math.isfinite(value) for value in (point.longitude, point.latitude, point.weight)):
            raise ValueError("demand point coordinates and weights must be finite")
        if point.weight <= 0 or point.injured < 0 or point.fatalities < 0:
            raise ValueError("demand point weights and aggregate casualties are invalid")
        points.append(point)
        seen_ids.add(point_id)
        seen_cells.add(cell)

    if not math.isclose(sum(point.weight for point in points), 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("demand profile weights must sum to one")
    hourly_occurrences = tuple(int(value) for value in document["hourly_occurrences"])
    if len(hourly_occurrences) != 24 or sum(hourly_occurrences) <= 0:
        raise ValueError("demand profile requires a non-empty 24-hour distribution")
    return DemandProfile(
        points=tuple(points),
        hourly_occurrences=hourly_occurrences,
        source=dict(document["source"]),
        coverage=dict(document["coverage"]),
        modeling=dict(document["modeling"]),
        checksum=hashlib.sha256(payload).hexdigest(),
        label=str(document["label"]),
    )
