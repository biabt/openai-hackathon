"""Detector boundary with optional, lazily imported Ultralytics support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

ALLOWED_OBJECT_CLASSES = frozenset(
    {"person", "bicycle", "motorcycle", "car", "bus", "truck"}
)


@dataclass(frozen=True, slots=True)
class Detection:
    """One detector result used only during the current processing run."""

    object_class: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _rows(value: Any) -> list[Any]:
    """Convert tensors, NumPy arrays, and simple test doubles to Python rows."""

    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return list(value.tolist())
    return list(value)


class YoloDetector:
    """Small adapter around an injected or local Ultralytics YOLO model.

    Passing ``model`` keeps tests independent of Ultralytics and model weights.
    Without an injected model, ``model_path`` must point at a local file; this
    adapter never requests or downloads a model.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        model: Any | None = None,
        confidence_threshold: float = 0.25,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if model is None:
            if model_path is None:
                raise ValueError("a local model_path or injected model is required")
            local_path = Path(model_path)
            if not local_path.is_file():
                raise FileNotFoundError(f"local model does not exist: {local_path}")
            try:
                from ultralytics import YOLO  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "Ultralytics is required to process frames; install the vision extra"
                ) from exc
            model = YOLO(str(local_path))
        self._model = model
        self._confidence_threshold = confidence_threshold

    def detect(self, frame: Any) -> tuple[Detection, ...]:
        try:
            raw_results = self._model.predict(
                source=frame, verbose=False, conf=self._confidence_threshold
            )
        except TypeError:
            # Lightweight injected doubles need not accept Ultralytics keywords.
            raw_results = self._model.predict(frame)

        detections: list[Detection] = []
        for result in raw_results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names: Mapping[int, str] | Sequence[str] = getattr(
                result, "names", getattr(self._model, "names", {})
            )
            classes = _rows(boxes.cls)
            confidences = _rows(boxes.conf)
            coordinates = _rows(boxes.xyxy)
            if not (len(classes) == len(confidences) == len(coordinates)):
                raise ValueError("detector returned inconsistent box arrays")
            for class_id, confidence, xyxy in zip(classes, confidences, coordinates):
                index = int(class_id)
                try:
                    label = names[index]
                except (KeyError, IndexError, TypeError) as exc:
                    raise ValueError(f"detector has no label for class {index}") from exc
                score = float(confidence)
                if label not in ALLOWED_OBJECT_CLASSES or score < self._confidence_threshold:
                    continue
                values = tuple(float(value) for value in xyxy)
                if len(values) != 4:
                    raise ValueError("detector box must contain exactly four coordinates")
                x1, y1, x2, y2 = values
                if x2 < x1 or y2 < y1:
                    raise ValueError("detector box coordinates are inverted")
                detections.append(Detection(label, score, (x1, y1, x2, y2)))

        return tuple(
            sorted(
                detections,
                key=lambda item: (item.object_class, item.bbox_xyxy, -item.confidence),
            )
        )
