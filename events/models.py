"""Data Models for Detections, Events, and Telemetry."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import numpy as np


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        return int(round(self.x1)), int(round(self.y1)), int(round(self.x2)), int(round(self.y2))


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: Optional[int] = None


@dataclass
class FrameDetectionResult:
    timestamp: datetime
    detections: List[Detection]
    frame: np.ndarray  # Raw original frame
    inference_time_ms: float
    motion_detected: bool = True

    @property
    def has_targets(self) -> bool:
        return len(self.detections) > 0

    @property
    def best_detection(self) -> Optional[Detection]:
        if not self.detections:
            return None
        return max(self.detections, key=lambda d: d.confidence)


@dataclass
class ConfirmedAlertEvent:
    event_id: str
    triggered_at: datetime
    confirmed_detections: List[FrameDetectionResult]
    best_result: FrameDetectionResult
    evidence_image_path: Optional[str] = None
    evidence_video_path: Optional[str] = None
