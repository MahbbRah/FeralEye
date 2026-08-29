"""Unit test for sliding-window detection state engine."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from events.models import BoundingBox, Detection, FrameDetectionResult
from events.state_engine import DetectionStateEngine, State


def run_state_engine_tests():
    print("Testing DetectionStateEngine...")
    engine = DetectionStateEngine(
        confirmation_count=2,
        confirmation_window_sec=4.0,
        cooldown_sec=10.0
    )

    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    cat_det = [Detection(class_name="cat", confidence=0.88, bbox=BoundingBox(10, 10, 50, 50))]
    
    t0 = datetime(2026, 8, 29, 10, 0, 0)

    # 1. Negative Frame -> IDLE
    res1 = FrameDetectionResult(timestamp=t0, detections=[], frame=dummy_frame, inference_time_ms=10.0)
    state, alert = engine.process_result(res1)
    assert state == State.IDLE, f"Expected IDLE, got {state}"
    assert alert is None
    print("  [Pass] Initial negative frame -> IDLE")

    # 2. Single Cat Detection -> CANDIDATE
    t1 = t0 + timedelta(seconds=1)
    res2 = FrameDetectionResult(timestamp=t1, detections=cat_det, frame=dummy_frame, inference_time_ms=10.0)
    state, alert = engine.process_result(res2)
    assert state == State.CANDIDATE, f"Expected CANDIDATE, got {state}"
    assert alert is None
    print("  [Pass] Single cat detection -> CANDIDATE")

    # 3. Second Cat Detection within 4s -> CONFIRMED & enters COOLDOWN
    t2 = t1 + timedelta(seconds=1)
    res3 = FrameDetectionResult(timestamp=t2, detections=cat_det, frame=dummy_frame, inference_time_ms=10.0)
    state, alert = engine.process_result(res3)
    assert state == State.CONFIRMED, f"Expected CONFIRMED, got {state}"
    assert alert is not None
    assert alert.best_result.best_detection.confidence == 0.88
    print("  [Pass] Second detection within window -> CONFIRMED (Alert emitted)")

    # 4. Third Cat Detection during cooldown -> COOLDOWN (suppressed)
    t3 = t2 + timedelta(seconds=2)
    res4 = FrameDetectionResult(timestamp=t3, detections=cat_det, frame=dummy_frame, inference_time_ms=10.0)
    state, alert = engine.process_result(res4)
    assert state == State.COOLDOWN, f"Expected COOLDOWN, got {state}"
    assert alert is None, "Expected alert to be suppressed during cooldown"
    print("  [Pass] Detection during cooldown -> COOLDOWN (Suppressed)")

    # 5. After cooldown expires -> IDLE
    t4 = t2 + timedelta(seconds=11)
    res5 = FrameDetectionResult(timestamp=t4, detections=[], frame=dummy_frame, inference_time_ms=10.0)
    state, alert = engine.process_result(res5)
    assert state == State.IDLE, f"Expected IDLE, got {state}"
    assert alert is None
    print("  [Pass] After cooldown elapses -> IDLE")

    print("\n✅ All StateEngine tests passed successfully!")


if __name__ == "__main__":
    run_state_engine_tests()
