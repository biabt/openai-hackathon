#!/usr/bin/env python3
"""Process a local recording into privacy-safe five-minute aggregates.

This command never opens a camera device, makes a network request, or writes source/
annotated frames. Its only output is a Parquet table without track identifiers.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from city_os.vision.camera_config import CameraConfig, load_camera_config
from city_os.vision.detector import YoloDetector
from city_os.vision.line_counter import AggregateObservation, DirectionalLineCounter
from city_os.vision.tracks import CentroidTracker

IMAGE_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".ppm", ".tif", ".tiff"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="local video or image directory")
    parser.add_argument("--model", type=Path, required=True, help="local YOLO weights")
    parser.add_argument("--camera-config", type=Path, required=True, help="local camera JSON")
    parser.add_argument("--output", type=Path, required=True, help="output .parquet path")
    parser.add_argument("--fps", type=float, help="required sampling rate for an image directory")
    parser.add_argument(
        "--starts-at",
        type=datetime.fromisoformat,
        help="timezone-aware recording start; overrides camera config starts_at",
    )
    parser.add_argument("--confidence", type=float, default=0.25)
    return parser


def _inside_roi(x: float, y: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    if not polygon:
        return True
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        intersects = (current_y > y) != (previous_y > y) and x < (
            (previous_x - current_x) * (y - current_y) / (previous_y - current_y)
            + current_x
        )
        if intersects:
            inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _local_frames(source: Path, configured_fps: float | None) -> tuple[Iterator[Any], float]:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("OpenCV is required to decode local frames") from exc

    if source.is_dir():
        if configured_fps is None or configured_fps <= 0:
            raise ValueError("--fps must be positive for an image directory")
        paths = sorted(
            path
            for path in source.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        if not paths:
            raise ValueError(f"image directory contains no supported images: {source}")

        def image_iterator() -> Iterator[Any]:
            for path in paths:
                frame = cv2.imread(str(path))
                if frame is None:
                    raise ValueError(f"could not decode image: {path}")
                yield frame

        return image_iterator(), configured_fps

    if not source.is_file():
        raise FileNotFoundError(f"local input does not exist: {source}")
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"could not open local video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        capture.release()
        raise ValueError("video does not report a positive frame rate")

    def video_iterator() -> Iterator[Any]:
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    return
                yield frame
        finally:
            capture.release()

    return video_iterator(), fps


def _write_parquet(
    path: Path,
    observations: tuple[AggregateObservation, ...],
    *,
    bucket_seconds: int = 300,
) -> None:
    try:
        import pyarrow as pa  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PyArrow is required to write aggregate Parquet output") from exc

    schema = pa.schema(
        [
            ("camera_id", pa.string()),
            ("edge_id", pa.string()),
            ("bucket_start", pa.timestamp("us", tz="UTC")),
            ("object_class", pa.string()),
            ("direction", pa.string()),
            ("count", pa.int64()),
            ("confidence", pa.float64()),
        ],
        metadata={
            b"city_os_privacy": b"aggregate_only_no_track_identifiers_no_frames",
            b"bucket_seconds": str(bucket_seconds).encode("ascii"),
        },
    )
    table = pa.Table.from_pylist([item.as_dict() for item in observations], schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        pq.write_table(table, temporary, compression="zstd")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def process(args: argparse.Namespace) -> tuple[AggregateObservation, ...]:
    config: CameraConfig = load_camera_config(args.camera_config)
    starts_at = args.starts_at or config.starts_at
    if starts_at is None or starts_at.tzinfo is None:
        raise ValueError("a timezone-aware --starts-at or camera config starts_at is required")
    detector = YoloDetector(args.model, confidence_threshold=args.confidence)
    tracker = CentroidTracker(
        max_distance_px=config.max_track_distance_px,
        ttl_seconds=config.track_ttl_seconds,
    )
    counter = DirectionalLineCounter(config)
    frames, fps = _local_frames(args.input, args.fps)
    for frame_index, frame in enumerate(frames):
        observed_at = starts_at + timedelta(seconds=frame_index / fps)
        detections = [
            detection
            for detection in detector.detect(frame)
            if _inside_roi(*detection.center, config.roi)
        ]
        counter.update_many(tracker.update(detections, observed_at))
    observations = counter.observations()
    _write_parquet(args.output, observations, bucket_seconds=config.bucket_seconds)
    return observations


def main() -> int:
    args = _parser().parse_args()
    process(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
