"""
Live Stream Simulator from Recorded Video.

Feeds a recorded video file through the entire Camera Guard pipeline
(Sampling -> Motion Filter -> YOLO11n -> StateEngine -> Evidence -> Alerts)
in real-time to simulate live camera behavior.
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from utils.logger import setup_logger
from detection.yolo_detector import YOLODetector
from detection.motion_filter import MotionFilter
from events.state_engine import DetectionStateEngine
from evidence.storage import EvidenceStorage
from alerts.console_alert import ConsoleAlertHandler


def simulate_stream(video_path: str):
    logger = setup_logger(name="simulator", level="INFO")
    logger.info("=" * 60)
    logger.info(" 🎬 Starting Real-Time Video Stream Simulation")
    logger.info(f" Video Source:       {video_path}")
    logger.info(f" Model:              {config.MODEL_NAME}")
    logger.info(f" Target Classes:     {config.TARGET_CLASSES}")
    logger.info(f" Sampling FPS:       {config.DETECTION_FPS:.1f}")
    logger.info("=" * 60)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video file: {video_path}")
        return

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(round(video_fps / config.DETECTION_FPS)))

    detector = YOLODetector(
        model_name=config.MODEL_NAME,
        target_classes=config.TARGET_CLASSES,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
        imgsz=config.INFERENCE_IMAGE_SIZE
    )

    motion_filter = MotionFilter(
        min_contour_area=config.MOTION_MIN_AREA,
        threshold_delta=config.MOTION_THRESHOLD
    ) if config.ENABLE_MOTION_FILTER else None

    state_engine = DetectionStateEngine(
        confirmation_count=config.CONFIRMATION_COUNT,
        confirmation_window_sec=config.CONFIRMATION_WINDOW_SEC,
        cooldown_sec=config.ALERT_COOLDOWN_SEC
    )

    evidence_storage = EvidenceStorage(
        base_dir=config.EVIDENCE_DIRECTORY,
        save_annotated=True
    )

    alert_handler = ConsoleAlertHandler()

    frame_idx = 0
    simulated_start_time = time.time()
    sample_interval_sec = 1.0 / config.DETECTION_FPS

    logger.info("Beginning simulated playback...")

    try:
        while True:
            loop_start = time.perf_counter()
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.info("End of video file reached.")
                break

            if frame_idx % frame_interval == 0:
                now = datetime.now()

                # 1. Motion Filter
                should_run_ai = True
                if motion_filter:
                    has_motion, _ = motion_filter.check_motion(frame)
                    if not has_motion:
                        should_run_ai = False

                # 2. AI Detection
                if should_run_ai:
                    result = detector.detect(frame)
                    result.timestamp = now

                    # 3. State Engine
                    state, alert_event = state_engine.process_result(result)

                    # 4. Confirmed Alert
                    if alert_event:
                        saved_path = evidence_storage.save_event_evidence(alert_event)
                        alert_handler.send_alert(alert_event)

                # Maintain realistic 1 FPS clock cadence
                elapsed = time.perf_counter() - loop_start
                sleep_time = sample_interval_sec - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            frame_idx += 1

    finally:
        cap.release()
        logger.info("Simulation finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Stream Simulator")
    parser.add_argument("video_file", type=str, help="Path to video file (MP4, MKV, AVI)")
    args = parser.parse_args()
    simulate_stream(args.video_file)
