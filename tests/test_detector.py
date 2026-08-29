"""Test YOLO detector and synthetic image evidence generation."""

import sys
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from detection.yolo_detector import YOLODetector
from evidence.storage import EvidenceStorage
from events.models import ConfirmedAlertEvent, FrameDetectionResult, Detection, BoundingBox
from datetime import datetime


def test_detector():
    print(f"Testing YOLODetector with model '{config.MODEL_NAME}' and Evidence Storage...")
    detector = YOLODetector(model_name=config.MODEL_NAME, target_classes=["cat"], confidence_threshold=0.3)

    # Create synthetic test frame with a drawn rectangle simulating an image
    frame = np.full((720, 1280, 3), 180, dtype=np.uint8)
    cv2.putText(frame, "Synthetic Test Canvas", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)

    # Run detection on synthetic frame
    result = detector.detect(frame)
    print(f"Inference latency: {result.inference_time_ms:.2f} ms")
    print(f"Detections found: {len(result.detections)}")

    # Test Evidence saving with mock detection
    storage = EvidenceStorage(base_dir="./tests/test_evidence", save_annotated=True)
    mock_detection = Detection(
        class_name="cat",
        confidence=0.92,
        bbox=BoundingBox(x1=200, y1=200, x2=500, y2=500)
    )
    mock_result = FrameDetectionResult(
        timestamp=datetime.now(),
        detections=[mock_detection],
        frame=frame,
        inference_time_ms=15.0
    )
    mock_event = ConfirmedAlertEvent(
        event_id="test1234",
        triggered_at=datetime.now(),
        confirmed_detections=[mock_result],
        best_result=mock_result
    )

    saved_path = storage.save_event_evidence(mock_event)
    print(f"Saved test evidence to: {saved_path}")
    assert saved_path is not None and Path(saved_path).exists(), "Evidence file was not saved!"
    print("✅ Detector & Evidence storage verified successfully!")


if __name__ == "__main__":
    test_detector()
