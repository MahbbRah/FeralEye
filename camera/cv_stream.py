"""Threaded OpenCV RTSP Stream Reader with Auto-Reconnect."""

import os
import time
import logging
import threading
from typing import Optional, Tuple
import cv2
import numpy as np

from collections import deque
from camera.base import BaseStreamReader

logger = logging.getLogger("camera_guard.stream")


class OpenCVRTSPStream(BaseStreamReader):
    """
    High-reliability threaded RTSP Stream Reader using OpenCV.
    
    Features:
    - Dedicated daemon grabber thread drops stale buffer frames so the consumer always gets real-time frames.
    - Maintains a rolling circular pre-buffer of past frames for event video clip generation.
    - Forces RTSP over TCP for stream stability and artifact reduction.
    - Automatic exponential backoff reconnection logic on stream drop or network glitch.
    - Thread-safe frame retrieval and graceful shutdown.
    """

    def __init__(
        self,
        rtsp_url: str,
        connect_timeout_sec: float = 10.0,
        reconnect_initial_delay_sec: float = 2.0,
        reconnect_max_delay_sec: float = 30.0,
        pre_buffer_max_frames: int = 300,
    ):
        self.rtsp_url = rtsp_url
        self.connect_timeout_sec = connect_timeout_sec
        self.reconnect_initial_delay = reconnect_initial_delay_sec
        self.reconnect_max_delay = reconnect_max_delay_sec

        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._latest_frame: Optional[np.ndarray] = None
        self._frame_timestamp: float = 0.0
        self._last_retrieved_timestamp: float = 0.0
        self._pre_buffer = deque(maxlen=pre_buffer_max_frames)

        # Enforce TCP transport with a 5-second socket timeout (stimeout in microseconds)
        # Prevents timeout=0 instant drop when camera is negotiating handshake
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"
        # Filter libavcodec decode noise (e.g. "Could not find ref with POC") that appears
        # at startup while the 4K pre-buffer fills and the reader momentarily stalls.
        # 8 = AV_LOG_FATAL: ERROR-level decoder chatter is dropped, real failures surface.
        os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "8"

    def start(self) -> None:
        """Starts the background frame capture thread."""
        if self._running:
            logger.warning("Stream reader already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name="RTSPStreamWorker", daemon=True)
        self._thread.start()
        logger.info(f"Stream reader started for: {self._sanitize_url(self.rtsp_url)}")

    def stop(self) -> None:
        """Stops the capture thread and cleans up."""
        logger.info("Stopping RTSP stream reader...")
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._connected = False
        with self._lock:
            self._latest_frame = None
            self._pre_buffer.clear()
        logger.info("RTSP stream reader stopped.")

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Retrieves the latest available frame.
        Returns:
            (has_new_frame: bool, frame: np.ndarray | None)
        """
        with self._lock:
            if self._latest_frame is None:
                return False, None

            if self._frame_timestamp > self._last_retrieved_timestamp:
                self._last_retrieved_timestamp = self._frame_timestamp
                # Return a copy or direct reference (numpy arrays are fast to copy if needed)
                return True, self._latest_frame.copy()
            else:
                return False, None

    def get_recent_frames(self, duration_sec: float = 10.0):
        """
        Extracts all frames stored in the pre-buffer from the last `duration_sec` seconds.
        Returns a list of (timestamp, frame_array).
        """
        cutoff = time.time() - duration_sec
        with self._lock:
            # Shallow list copy of relevant items
            return [(ts, f.copy()) for ts, f in self._pre_buffer if ts >= cutoff]

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _capture_loop(self) -> None:
        """Main background loop handling connection, grabbing, and auto-reconnect."""
        backoff_delay = self.reconnect_initial_delay

        while self._running:
            cap: Optional[cv2.VideoCapture] = None
            try:
                logger.info(f"Connecting to RTSP stream: {self._sanitize_url(self.rtsp_url)}...")
                cap = cv2.VideoCapture(self.rtsp_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    raise RuntimeError("Failed to open RTSP stream.")

                self._connected = True
                backoff_delay = self.reconnect_initial_delay  # Reset backoff on successful connection
                logger.info("RTSP stream connected successfully.")

                # Read properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                logger.info(f"Stream parameters: {width}x{height} @ {fps:.1f} FPS")

                consecutive_failures = 0
                while self._running:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        consecutive_failures += 1
                        if consecutive_failures >= 5:
                            logger.warning("Multiple consecutive frame read failures. Reconnecting...")
                            break
                        time.sleep(0.05)
                        continue

                    consecutive_failures = 0
                    now = time.time()
                    with self._lock:
                        self._latest_frame = frame
                        self._frame_timestamp = now
                        self._pre_buffer.append((now, frame))

            except Exception as e:
                logger.error(f"RTSP stream error: {e}")
            finally:
                self._connected = False
                if cap is not None:
                    cap.release()

            if self._running:
                logger.info(f"Waiting {backoff_delay:.1f}s before attempting reconnection...")
                time.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2, self.reconnect_max_delay)

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Sanitizes sensitive RTSP credentials in logs if present."""
        if "@" in url:
            prefix, rest = url.split("@", 1)
            scheme = prefix.split("//")[0]
            return f"{scheme}//***:***@{rest}"
        return url
