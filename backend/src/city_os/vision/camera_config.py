"""Strict local configuration for a single camera counting line."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

DIRECTIONS = ("a_to_b", "b_to_a")


def _point(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-number array")
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a two-number array") from exc


@dataclass(frozen=True, slots=True)
class CameraConfig:
    camera_id: str
    edge_id: str
    line_a: tuple[float, float]
    line_b: tuple[float, float]
    edge_ids: Mapping[str, str] | None = None
    roi: tuple[tuple[float, float], ...] = ()
    bucket_seconds: int = 300
    hysteresis_px: float = 3.0
    min_track_age_seconds: float = 0.1
    min_track_observations: int = 2
    track_ttl_seconds: float = 2.0
    max_track_distance_px: float = 80.0
    starts_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.camera_id or not self.edge_id:
            raise ValueError("camera_id and edge_id must be non-empty")
        if self.line_a == self.line_b:
            raise ValueError("counting-line endpoints must differ")
        if self.bucket_seconds <= 0 or self.hysteresis_px < 0:
            raise ValueError("bucket_seconds must be positive and hysteresis non-negative")
        if self.min_track_age_seconds < 0 or self.min_track_observations < 2:
            raise ValueError("track age must be non-negative and observations at least two")
        if self.track_ttl_seconds <= 0 or self.max_track_distance_px <= 0:
            raise ValueError("track TTL and match distance must be positive")
        if self.edge_ids is not None:
            unknown = set(self.edge_ids) - set(DIRECTIONS)
            if unknown or any(not value for value in self.edge_ids.values()):
                raise ValueError("edge_ids may contain only non-empty a_to_b/b_to_a values")

    def edge_for(self, direction: str) -> str:
        if direction not in DIRECTIONS:
            raise ValueError(f"unknown direction: {direction}")
        return (self.edge_ids or {}).get(direction, self.edge_id)


def load_camera_config(path: str | Path) -> CameraConfig:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("camera config must be a JSON object")
    allowed = {
        "camera_id", "edge_id", "edge_ids", "line", "roi", "bucket_seconds",
        "hysteresis_px", "min_track_age_seconds", "min_track_observations",
        "track_ttl_seconds", "max_track_distance_px", "starts_at",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown camera config fields: {sorted(unknown)}")
    line = raw.get("line")
    if not isinstance(line, dict) or set(line) != {"a", "b"}:
        raise ValueError("line must contain exactly endpoints a and b")
    roi_raw = raw.get("roi", [])
    if not isinstance(roi_raw, list):
        raise ValueError("roi must be an array of points")
    starts_at_raw = raw.get("starts_at")
    starts_at = datetime.fromisoformat(starts_at_raw) if starts_at_raw else None
    if starts_at is not None and starts_at.tzinfo is None:
        raise ValueError("starts_at must include a timezone")
    edge_ids_raw = raw.get("edge_ids")
    if edge_ids_raw is not None and not isinstance(edge_ids_raw, dict):
        raise ValueError("edge_ids must be an object")
    return CameraConfig(
        camera_id=str(raw["camera_id"]),
        edge_id=str(raw["edge_id"]),
        line_a=_point(line["a"], "line.a"),
        line_b=_point(line["b"], "line.b"),
        edge_ids={str(key): str(value) for key, value in edge_ids_raw.items()}
        if edge_ids_raw is not None else None,
        roi=tuple(_point(value, "roi point") for value in roi_raw),
        bucket_seconds=int(raw.get("bucket_seconds", 300)),
        hysteresis_px=float(raw.get("hysteresis_px", 3.0)),
        min_track_age_seconds=float(raw.get("min_track_age_seconds", 0.1)),
        min_track_observations=int(raw.get("min_track_observations", 2)),
        track_ttl_seconds=float(raw.get("track_ttl_seconds", 2.0)),
        max_track_distance_px=float(raw.get("max_track_distance_px", 80.0)),
        starts_at=starts_at,
    )
