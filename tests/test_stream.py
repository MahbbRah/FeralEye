"""Standalone test script to verify RTSP stream connectivity."""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from camera.cv_stream import OpenCVRTSPStream
from utils.logger import setup_logger

logger = setup_logger(name="test_stream", level="DEBUG")


def test_rtsp_stream():
    url = config.CAMERA_RTSP_URL
    logger.info(f"Testing RTSP stream connection to: {url}")

    stream = OpenCVRTSPStream(
        rtsp_url=url,
        connect_timeout_sec=5.0,
        reconnect_initial_delay_sec=1.0,
        reconnect_max_delay_sec=5.0
    )

    try:
        stream.start()
        logger.info("Waiting for stream to connect and receive initial frames...")

        frames_received = 0
        timeout_start = time.time()
        max_wait_seconds = 15.0

        while frames_received < 10 and (time.time() - timeout_start) < max_wait_seconds:
            has_frame, frame = stream.get_latest_frame()
            if has_frame and frame is not None:
                frames_received += 1
                h, w, c = frame.shape
                logger.info(f"Received frame #{frames_received}: shape={w}x{h}, channels={c}, dtype={frame.dtype}")
            time.sleep(0.5)

        if frames_received >= 10:
            logger.info("✅ SUCCESS: RTSP stream is healthy and frames are being decoded properly!")
        else:
            logger.warning(f"⚠️ Received only {frames_received} frames before timeout ({max_wait_seconds}s).")

    finally:
        stream.stop()


if __name__ == "__main__":
    test_rtsp_stream()
