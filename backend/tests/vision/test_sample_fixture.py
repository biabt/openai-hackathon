from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from city_os.vision.camera_config import load_camera_config
from city_os.vision.detector import Detection
from city_os.vision.line_counter import DirectionalLineCounter
from city_os.vision.tracks import CentroidTracker


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data" / "fixtures" / "vision"


def test_synthetic_fixture_matches_manual_aggregate_counts_and_provenance() -> None:
    config = load_camera_config(FIXTURE / "camera_config.json")
    payload_path = FIXTURE / "synthetic_detections.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    provenance = json.loads((FIXTURE / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["fixture_type"] == "synthetic_cached_detections"
    assert provenance["source_url"] is None
    assert provenance["sha256"] == hashlib.sha256(payload_path.read_bytes()).hexdigest()

    tracker = CentroidTracker(
        max_distance_px=config.max_track_distance_px,
        ttl_seconds=config.track_ttl_seconds,
    )
    counter = DirectionalLineCounter(config)
    for frame in payload["frames"]:
        observed_at = config.starts_at + timedelta(seconds=frame["offset_seconds"])
        detections = [
            Detection(
                row["object_class"], row["confidence"], tuple(row["bbox_xyxy"])
            )
            for row in frame["detections"]
        ]
        counter.update_many(tracker.update(detections, observed_at))

    actual = {
        (row.object_class, row.direction): row.count for row in counter.observations()
    }
    expected = {
        (row["object_class"], row["direction"]): row["count"]
        for row in payload["manual_counts"]
    }
    tolerance = payload["mvp_absolute_count_tolerance"]
    assert set(actual) == set(expected)
    assert all(abs(actual[key] - count) <= tolerance for key, count in expected.items())


def test_authorized_real_sample_retains_only_provenance_and_aggregate_annotation() -> None:
    provenance = json.loads((FIXTURE / "provenance.json").read_text(encoding="utf-8"))
    reference = provenance["authorized_real_sample"]
    annotation = json.loads((FIXTURE / reference["annotation_file"]).read_text(encoding="utf-8"))

    assert reference["media_persisted"] is False
    assert annotation["camera_location"]["municipality"] == "São Paulo"
    assert annotation["license"] == "CC BY-SA 4.0"
    assert annotation["author"] == "Sintegrity"
    assert len(annotation["source_media"]["sha256"]) == 64
    assert annotation["source_media"]["persisted_in_repository"] is False
    assert annotation["manual_annotation"]["counts"] == [
        {"object_class": "car", "direction": "right_to_left", "count": 2}
    ]
    assert not any(path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webm", ".mp4"} for path in FIXTURE.iterdir())


def test_parquet_output_schema_contains_aggregates_only(tmp_path) -> None:
    import importlib.util

    import pyarrow.parquet as pq

    script_path = ROOT / "scripts" / "process_camera_frames.py"
    spec = importlib.util.spec_from_file_location("process_camera_frames", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    config = load_camera_config(FIXTURE / "camera_config.json")
    counter = DirectionalLineCounter(config)
    output = tmp_path / "observations.parquet"
    module._write_parquet(output, counter.observations())
    schema = pq.read_schema(output)

    assert schema.names == [
        "camera_id",
        "edge_id",
        "bucket_start",
        "object_class",
        "direction",
        "count",
        "confidence",
    ]
    assert not any("track" in name or "bbox" in name or "frame" in name for name in schema.names)
    assert schema.metadata[b"city_os_privacy"] == b"aggregate_only_no_track_identifiers_no_frames"
