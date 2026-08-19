"""A deterministic, short-lived centroid tracker.

This is deliberately not a re-identification system. IDs are process-local counters,
expire within seconds, and are never included in exported observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import hypot
from typing import Iterable

from .detector import Detection


@dataclass(frozen=True, slots=True)
class TrackedDetection:
    track_id: int
    object_class: str
    x: float
    y: float
    confidence: float
    observed_at: datetime


@dataclass(slots=True)
class _TransientTrack:
    track_id: int
    object_class: str
    x: float
    y: float
    last_seen: datetime


class CentroidTracker:
    def __init__(self, *, max_distance_px: float = 80.0, ttl_seconds: float = 2.0) -> None:
        if max_distance_px <= 0 or ttl_seconds <= 0:
            raise ValueError("tracker distance and TTL must be positive")
        self._max_distance = max_distance_px
        self._ttl_seconds = ttl_seconds
        self._next_id = 1
        self._tracks: dict[int, _TransientTrack] = {}

    def update(
        self, detections: Iterable[Detection], observed_at: datetime
    ) -> tuple[TrackedDetection, ...]:
        self._expire(observed_at)
        ordered = sorted(
            detections, key=lambda value: (value.object_class, value.center, value.bbox_xyxy)
        )
        available = set(self._tracks)
        output: list[TrackedDetection] = []
        for detection in ordered:
            x, y = detection.center
            candidates = [
                (
                    hypot(track.x - x, track.y - y),
                    track_id,
                )
                for track_id, track in self._tracks.items()
                if track_id in available and track.object_class == detection.object_class
            ]
            candidates.sort()
            if candidates and candidates[0][0] <= self._max_distance:
                track_id = candidates[0][1]
                available.remove(track_id)
                track = self._tracks[track_id]
                track.x, track.y, track.last_seen = x, y, observed_at
            else:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = _TransientTrack(
                    track_id, detection.object_class, x, y, observed_at
                )
            output.append(
                TrackedDetection(
                    track_id,
                    detection.object_class,
                    x,
                    y,
                    detection.confidence,
                    observed_at,
                )
            )
        return tuple(output)

    def _expire(self, observed_at: datetime) -> None:
        expired = [
            track_id
            for track_id, track in self._tracks.items()
            if (observed_at - track.last_seen).total_seconds() > self._ttl_seconds
        ]
        for track_id in expired:
            del self._tracks[track_id]
