"""Direct FFmpeg Subprocess Stream Reader (Identical decoding stack to VLC)."""

import time
import logging
import subprocess
import threading
from typing import Optional, Tuple
from collections import deque
import numpy as np

from camera.base import BaseStreamReader

logger = logging.getLogger("camera_guard.ffmpeg_stream")


class FFmpegRTSPStream(BaseStreamReader):
    """
    Direct FFmpeg subprocess RTSP reader.
    Spawns ffmpeg to ingest H.265/H.264 RTSP stream and outputs raw BGR24 frames via stdout pipe.
    Provides identical networking and decoding behavior to VLC.
    """

    def __init__(
        self,
        rtsp_url: str,
        target_fps: float = 1.0,
        output_width: int = 1280,
        output_height: int = 720,
        reconnect_initial_delay_sec: float = 2.0,
        reconnect_max_delay_sec: float = 30.0,
        pre_buffer_max_frames: int = 300,
    ):
        self.rtsp_url = rtsp_url
        self.target_fps = target_fps
        self.width = output_width
        self.height = output_height
        self.frame_size_bytes = self.width * self.height * 3  # BGR24

        self.reconnect_initial_delay = reconnect_initial_delay_sec
        self.reconnect_max_delay = reconnect_max_delay_sec

        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None

        self._latest_frame: Optional[np.ndarray] = None
        self._frame_timestamp: float = 0.0
        self._last_retrieved_timestamp: float = 0.0
        # Rolling pre-buffer so event clips can include pre-detection footage.
        self._pre_buffer = deque(maxlen=pre_buffer_max_frames)
        # stderr must be drained continuously: a full stderr pipe blocks the
        # ffmpeg process mid-decode, which stalls frames and corrupts the GOP.
        self._recent_stderr: deque = deque(maxlen=30)
        self._stderr_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name="FFmpegWorker", daemon=True)
        self._thread.start()
        logger.info(f"FFmpeg stream reader started for: {self._sanitize_url(self.rtsp_url)}")

    def stop(self) -> None:
        logger.info("Stopping FFmpeg stream reader...")
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._connected = False
        with self._lock:
            self._latest_frame = None
            self._pre_buffer.clear()
        logger.info("FFmpeg stream reader stopped.")

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            if self._latest_frame is None:
                return False, None
            if self._frame_timestamp > self._last_retrieved_timestamp:
                self._last_retrieved_timestamp = self._frame_timestamp
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
            return [(ts, f.copy()) for ts, f in self._pre_buffer if ts >= cutoff]

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _capture_loop(self) -> None:
        backoff = self.reconnect_initial_delay

        while self._running:
            # Build FFmpeg command with RTSP TCP transport, low latency, and scaling
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-i", self.rtsp_url,
                "-vf", f"fps={self.target_fps},scale={self.width}:{self.height}",
                "-f", "rawvideo",
                "-pix_fmt", "bgr24",
                "pipe:1"
            ]

            try:
                logger.info(f"Launching FFmpeg subprocess for {self._sanitize_url(self.rtsp_url)}...")
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=self.frame_size_bytes * 4
                )

                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr, name="FFmpegStderrDrain", daemon=True
                )
                self._stderr_thread.start()

                backoff = self.reconnect_initial_delay

                while self._running:
                    # Read exact chunk of bytes for one frame
                    raw_frame = self._proc.stdout.read(self.frame_size_bytes)
                    if not raw_frame or len(raw_frame) != self.frame_size_bytes:
                        recent_errors = list(self._recent_stderr)
                        if recent_errors:
                            logger.warning(f"FFmpeg error details: {' | '.join(recent_errors[-5:])}")
                        else:
                            logger.warning("FFmpeg frame read incomplete or stream ended.")
                        break

                    self._connected = True
                    frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((self.height, self.width, 3))
                    now = time.time()
                    with self._lock:
                        self._latest_frame = frame
                        self._frame_timestamp = now
                        self._pre_buffer.append((now, frame))

            except Exception as e:
                logger.error(f"FFmpeg error: {e}")
            finally:
                self._connected = False
                if self._proc:
                    try:
                        self._proc.terminate()
                        self._proc.wait(timeout=1.0)
                    except Exception:
                        pass
                    self._proc = None
                if self._stderr_thread and self._stderr_thread.is_alive():
                    self._stderr_thread.join(timeout=2.0)
                self._stderr_thread = None

            if self._running:
                logger.info(f"FFmpeg stream disconnected. Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, self.reconnect_max_delay)

    def _drain_stderr(self) -> None:
        """Continuously consumes ffmpeg stderr so the pipe never fills and blocks the decoder."""
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for raw_line in iter(proc.stderr.readline, b""):
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                self._recent_stderr.append(line)
                logger.debug(f"FFmpeg: {line}")
        except Exception:
            pass

    @staticmethod
    def _sanitize_url(url: str) -> str:
        if "@" in url:
            prefix, rest = url.split("@", 1)
            scheme = prefix.split("//")[0]
            return f"{scheme}//***:***@{rest}"
        return url
