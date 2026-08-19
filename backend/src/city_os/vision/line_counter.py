"""Directional line crossing logic with aggregate-only public output."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import import_module
from math import hypot
from typing import Any, Iterable

from .camera_config import CameraConfig
from .detector import ALLOWED_OBJECT_CLASSES
from .tracks import TrackedDetection


@dataclass(frozen=True, slots=True)
class AggregateObservation:
    """Contract-shaped fallback used until the shared Pydantic model is installed."""

    camera_id: str
    edge_id: str
    bucket_start: datetime
    object_class: str
    direction: str
    count: int
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_contract(self) -> Any:
        """Materialize Developer B's frozen model when that package is present."""

        try:
            module = import_module("city_os.contracts.artifacts")
            contract_type = getattr(module, "CameraObservation")
        except (ImportError, AttributeError) as exc:
            raise RuntimeError("shared CameraObservation contract is not installed") from exc
        return contract_type(**self.as_dict())


@dataclass(slots=True)
class _TrackState:
    object_class: str
    first_seen: datetime
    last_seen: datetime
    observations: int
    stable_side: int | None
    confidence_sum: float
    counted: bool = False


class DirectionalLineCounter:
    """Count stable side changes and immediately discard expired track state.

    Relative to directed line ``a -> b``, negative signed distance is side A and
    positive signed distance is side B. Therefore ``-1 -> +1`` is ``a_to_b``.
    The hysteresis dead band prevents a track that merely touches or jitters along
    the line from changing its stable side.
    """

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        ax, ay = config.line_a
        bx, by = config.line_b
        self._ax, self._ay = ax, ay
        self._dx, self._dy = bx - ax, by - ay
        self._line_length = hypot(self._dx, self._dy)
        self._tracks: dict[int, _TrackState] = {}
        self._crossings: dict[tuple[datetime, str, str, str], list[float]] = defaultdict(list)

    @property
    def active_track_count(self) -> int:
        return len(self._tracks)

    def update(self, observation: TrackedDetection) -> None:
        if observation.observed_at.tzinfo is None:
            raise ValueError("observation timestamps must include a timezone")
        if observation.object_class not in ALLOWED_OBJECT_CLASSES:
            return
        if not 0.0 <= observation.confidence <= 1.0:
            raise ValueError("detection confidence must be between 0 and 1")
        self.expire(observation.observed_at)
        side = self._stable_side(observation.x, observation.y)
        state = self._tracks.get(observation.track_id)
        if state is None:
            self._tracks[observation.track_id] = _TrackState(
                observation.object_class,
                observation.observed_at,
                observation.observed_at,
                1,
                side,
                observation.confidence,
            )
            return
        if observation.observed_at < state.last_seen:
            raise ValueError("track observations must be chronological")
        if state.object_class != observation.object_class:
            raise ValueError("a transient track cannot change object class")

        previous_side = state.stable_side
        state.last_seen = observation.observed_at
        state.observations += 1
        state.confidence_sum += observation.confidence
        if side is None:
            return
        state.stable_side = side
        age = (state.last_seen - state.first_seen).total_seconds()
        eligible = (
            not state.counted
            and previous_side is not None
            and side != previous_side
            and state.observations >= self.config.min_track_observations
            and age >= self.config.min_track_age_seconds
        )
        if not eligible:
            return
        direction = "a_to_b" if previous_side < side else "b_to_a"
        bucket = _bucket_start(observation.observed_at, self.config.bucket_seconds)
        edge_id = self.config.edge_for(direction)
        mean_confidence = state.confidence_sum / state.observations
        self._crossings[(bucket, observation.object_class, direction, edge_id)].append(
            mean_confidence
        )
        state.counted = True

    def update_many(self, observations: Iterable[TrackedDetection]) -> None:
        for observation in sorted(
            observations, key=lambda item: (item.observed_at, item.track_id)
        ):
            self.update(observation)

    def expire(self, now: datetime) -> None:
        expired = [
            track_id
            for track_id, state in self._tracks.items()
            if (now - state.last_seen).total_seconds() > self.config.track_ttl_seconds
        ]
        for track_id in expired:
            del self._tracks[track_id]

    def observations(self) -> tuple[AggregateObservation, ...]:
        records = [
            AggregateObservation(
                camera_id=self.config.camera_id,
                edge_id=edge_id,
                bucket_start=bucket,
                object_class=object_class,
                direction=direction,
                count=len(confidences),
                confidence=sum(confidences) / len(confidences),
            )
            for (bucket, object_class, direction, edge_id), confidences in self._crossings.items()
        ]
        return tuple(
            sorted(
                records,
                key=lambda item: (
                    item.bucket_start,
                    item.camera_id,
                    item.edge_id,
                    item.object_class,
                    item.direction,
                ),
            )
        )

    def _stable_side(self, x: float, y: float) -> int | None:
        signed_distance = (
            self._dx * (y - self._ay) - self._dy * (x - self._ax)
        ) / self._line_length
        if signed_distance > self.config.hysteresis_px:
            return 1
        if signed_distance < -self.config.hysteresis_px:
            return -1
        return None


def _bucket_start(value: datetime, bucket_seconds: int) -> datetime:
    utc_value = value.astimezone(timezone.utc)
    epoch = int(utc_value.timestamp())
    floored = epoch - epoch % bucket_seconds
    return datetime.fromtimestamp(floored, tz=timezone.utc)
