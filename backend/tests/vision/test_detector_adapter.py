from __future__ import annotations

from city_os.vision.detector import ALLOWED_OBJECT_CLASSES, YoloDetector


class _Values:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _Boxes:
    cls = _Values([0, 1, 2, 3, 4, 5, 6])
    conf = _Values([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.99])
    xyxy = _Values([[i, 1, i + 1, 2] for i in range(7)])


class _Result:
    boxes = _Boxes()
    names = {
        0: "person",
        1: "bicycle",
        2: "motorcycle",
        3: "car",
        4: "bus",
        5: "truck",
        6: "dog",
    }


class _FakeModel:
    def predict(self, source, verbose=False, conf=0.25):
        assert source == "frame"
        assert verbose is False
        assert conf == 0.25
        return [_Result()]


def test_detector_keeps_only_transport_classes() -> None:
    detections = YoloDetector(model=_FakeModel()).detect("frame")

    assert {item.object_class for item in detections} == ALLOWED_OBJECT_CLASSES
    assert all(0.0 <= item.confidence <= 1.0 for item in detections)
    assert "dog" not in {item.object_class for item in detections}
