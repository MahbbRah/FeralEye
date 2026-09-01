"""Unit test for 20-second Event Video Clip Recorder."""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from events.models import ConfirmedAlertEvent, FrameDetectionResult, Detection, BoundingBox
from evidence.clip_recorder import EventVideoRecorder
from camera.base import BaseStreamReader


class MockStream(BaseStreamReader):
    def __init__(self):
        self._connected = True
        self._frames = []

    def start(self): pass
    def stop(self): pass

    def get_latest_frame(self):
        # Generate color gradient frame
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, :, 1] = 200
        return True, frame

    def get_recent_frames(self, duration_sec=10.0):
        frames = []
        now = time.time()
        for i in range(20):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:, :, 2] = 200
            frames.append((now - (20 - i) * 0.5, frame))
        return frames

    @property
    def is_connected(self): return True


def test_event_video_recording():
    print("Testing EventVideoRecorder...")
    out_dir = Path("tests/test_evidence")
    out_dir.mkdir(parents=True, exist_ok=True)

    stream = MockStream()
    recorder = EventVideoRecorder(
        evidence_directory=out_dir,
        pre_buffer_sec=2.0,
        post_buffer_sec=2.0,
        target_fps=10.0,
        enabled=True
    )

    det = Detection(class_name="cat", confidence=0.88, bbox=BoundingBox(10, 10, 50, 50))
    res = FrameDetectionResult(timestamp=datetime.now(), detections=[det], frame=np.zeros((240, 320, 3), dtype=np.uint8), inference_time_ms=10.0)
    event = ConfirmedAlertEvent(
        event_id="TESTVID99",
        triggered_at=datetime.now(),
        confirmed_detections=[res, res],
        best_result=res
    )

    done_flag = {"done": False}
    def on_complete(ev):
        done_flag["done"] = True

    recorder.record_event_clip_async(event, stream, on_complete_callback=on_complete)

    # Wait for recorder worker to finish
    time.sleep(3.0)

    assert event.evidence_video_path is not None, "Video path was not set!"
    video_path = Path(event.evidence_video_path)
    assert video_path.exists(), f"Video file does not exist: {video_path}"
    assert video_path.stat().st_size > 1000, f"Video file is too small ({video_path.stat().st_size} bytes)"

    # Verify OpenCV can read the output video
    cap = cv2.VideoCapture(str(video_path))
    assert cap.isOpened(), "Generated video could not be opened by cv2.VideoCapture!"
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    print(f"✅ Video recorded successfully: {video_path} ({frame_count} frames, {video_path.stat().st_size} bytes)")


if __name__ == "__main__":
    test_event_video_recording()
