from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose

from city_os.vision.camera_config import CameraConfig
from city_os.vision.line_counter import DirectionalLineCounter
from city_os.vision.tracks import TrackedDetection


START = datetime(2026, 8, 19, 12, 1, tzinfo=timezone.utc)


def _track(track_id, object_class, y, seconds, confidence=0.8):
    return TrackedDetection(
        track_id=track_id,
        object_class=object_class,
        x=50,
        y=y,
        confidence=confidence,
        observed_at=START + timedelta(seconds=seconds),
    )


def test_counts_two_stable_crossings_but_not_jitter_or_expired_track() -> None:
    config = CameraConfig(
        camera_id="camera-1",
        edge_id="fallback",
        edge_ids={"a_to_b": "edge-forward", "b_to_a": "edge-reverse"},
        line_a=(0, 50),
        line_b=(100, 50),
        hysteresis_px=3,
        min_track_age_seconds=0.2,
        min_track_observations=2,
        track_ttl_seconds=1,
    )
    counter = DirectionalLineCounter(config)
    counter.update_many(
        [
            _track(1, "car", 40, 0, 0.9),
            _track(2, "person", 60, 0, 0.6),
            _track(3, "bicycle", 48, 0),
            _track(4, "truck", 40, 0),
            _track(1, "car", 49, 0.25, 0.8),
            _track(2, "person", 51, 0.25, 0.8),
            _track(3, "bicycle", 52, 0.25),
            _track(1, "car", 60, 0.5, 0.7),
            _track(2, "person", 40, 0.5, 0.7),
            _track(3, "bicycle", 49, 0.5),
            _track(4, "truck", 60, 2.0),
        ]
    )

    observations = counter.observations()
    assert [(row.object_class, row.direction, row.count) for row in observations] == [
        ("car", "a_to_b", 1),
        ("person", "b_to_a", 1),
    ]
    assert observations[0].edge_id == "edge-forward"
    assert observations[1].edge_id == "edge-reverse"
    assert observations[0].bucket_start == datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert isclose(observations[0].confidence, 0.8)
    assert isclose(observations[1].confidence, 0.7)
    assert counter.active_track_count == 1
