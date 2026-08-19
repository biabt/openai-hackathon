"""Privacy-preserving camera crossing aggregation.

Track identifiers are deliberately confined to this package's in-memory processing
path.  The public output contains only five-minute aggregate observations.
"""

from .camera_config import CameraConfig, load_camera_config
from .detector import ALLOWED_OBJECT_CLASSES, Detection, YoloDetector
from .line_counter import AggregateObservation, DirectionalLineCounter
from .tracks import CentroidTracker, TrackedDetection

__all__ = [
    "ALLOWED_OBJECT_CLASSES",
    "AggregateObservation",
    "CameraConfig",
    "CentroidTracker",
    "Detection",
    "DirectionalLineCounter",
    "TrackedDetection",
    "YoloDetector",
    "load_camera_config",
]
