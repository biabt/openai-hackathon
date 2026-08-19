"""Environment-level dependency contract tests."""

from importlib import import_module, metadata

import pytest


def test_environment_uses_only_opencv_python_4() -> None:
    """The supported OpenCV distribution must be the sole owner of ``cv2``."""
    cv2 = import_module("cv2")

    assert cv2.__version__.split(".", maxsplit=1)[0] == "4"
    assert metadata.version("opencv-python").split(".", maxsplit=1)[0] == "4"
    with pytest.raises(metadata.PackageNotFoundError):
        metadata.version("opencv-python-headless")
