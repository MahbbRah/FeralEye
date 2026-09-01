"""Asynchronous Event Video Clip Recorder with Pre/Post Rolling Buffer."""

import os
import time
import logging
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict
import cv2
import numpy as np

from events.models import ConfirmedAlertEvent
from camera.base import BaseStreamReader

logger = logging.getLogger("camera_guard.recorder")


class EventVideoRecorder:
    """
    Records an event video clip surrounding a confirmed detection:
    - Pre-detection seconds (from stream rolling pre-buffer)
    - Post-detection seconds (recorded live from stream)

    Clip length is configurable per class via `clip_lengths` (e.g.
    {"cat": 10, "person": 30}); any class not present falls back to the
    global pre/post buffer durations.

    Encoding is done asynchronously in a background thread to prevent
    blocking the main AI detection loop.
    """

    def __init__(
        self,
        evidence_directory: Path = Path("./evidence_storage"),
        pre_buffer_sec: float = 10.0,
        post_buffer_sec: float = 10.0,
        target_fps: float = 10.0,
        enabled: bool = True,
        clip_lengths: Optional[Dict[str, float]] = None
    ):
        self.evidence_directory = Path(evidence_directory)
        self.pre_buffer_sec = pre_buffer_sec
        self.post_buffer_sec = post_buffer_sec
        self.target_fps = target_fps
        self.enabled = enabled
        self.clip_lengths = clip_lengths or {}

    def _durations_for_event(self, event: ConfirmedAlertEvent) -> Tuple[float, float]:
        """Returns (pre_sec, post_sec) for the event's class, honoring per-class overrides."""
        best_det = event.best_result.best_detection if event.best_result else None
        class_name = best_det.class_name.lower() if best_det else ""
        override = self.clip_lengths.get(class_name)
        if override is None or override <= 0:
            return self.pre_buffer_sec, self.post_buffer_sec
        # Keep the configured pre/post ratio, scaled to the per-class total length.
        total_default = max(0.1, self.pre_buffer_sec + self.post_buffer_sec)
        ratio = self.pre_buffer_sec / total_default
        pre = override * ratio
        post = override - pre
        return pre, post

    def record_event_clip_async(
        self,
        event: ConfirmedAlertEvent,
        stream: BaseStreamReader,
        on_complete_callback: Optional[Callable[[ConfirmedAlertEvent], None]] = None
    ) -> None:
        """
        Spawns an asynchronous worker thread to record and encode the event clip.
        """
        if not self.enabled:
            return

        pre_sec, post_sec = self._durations_for_event(event)

        # Grab pre-roll frames immediately at trigger time
        pre_frames = stream.get_recent_frames(duration_sec=pre_sec)
        
        thread = threading.Thread(
            target=self._recording_worker,
            args=(event, stream, pre_frames, on_complete_callback, pre_sec, post_sec),
            name=f"ClipRecorder-{event.event_id}",
            daemon=True
        )
        thread.start()
        logger.info(
            f"Started event video clip recorder for Event ID: {event.event_id} "
            f"({len(pre_frames)} pre-frames, {pre_sec:.0f}s pre + {post_sec:.0f}s post)."
        )

    def _recording_worker(
        self,
        event: ConfirmedAlertEvent,
        stream: BaseStreamReader,
        pre_frames: List[Tuple[float, np.ndarray]],
        on_complete_callback: Optional[Callable[[ConfirmedAlertEvent], None]],
        pre_sec: float,
        post_sec: float
    ) -> None:
        try:
            # 1. Collect post-trigger frames for post_sec
            post_frames: List[Tuple[float, np.ndarray]] = []
            start_time = time.time()
            frame_interval = 1.0 / max(1.0, self.target_fps)

            while (time.time() - start_time) < post_sec:
                loop_t0 = time.perf_counter()
                has_frame, frame = stream.get_latest_frame()
                if has_frame and frame is not None:
                    post_frames.append((time.time(), frame))

                # Throttle collection rate
                elapsed = time.perf_counter() - loop_t0
                to_sleep = frame_interval - elapsed
                if to_sleep > 0:
                    time.sleep(to_sleep)
                else:
                    time.sleep(0.01)

            # 2. Combine and sort frames chronologically
            all_frames_data = pre_frames + post_frames
            if not all_frames_data:
                logger.warning(f"No frames available to compile video for event {event.event_id}.")
                return

            # Deduplicate by timestamp and sort
            all_frames_data.sort(key=lambda x: x[0])
            frames_to_write = [f for ts, f in all_frames_data if f is not None]

            if not frames_to_write:
                logger.warning(f"Empty frame list for event {event.event_id}.")
                return

            # 3. Determine output file path
            date_dir_name = event.triggered_at.strftime("%Y-%m-%d")
            out_dir = self.evidence_directory / date_dir_name
            out_dir.mkdir(parents=True, exist_ok=True)

            best_det = event.best_result.best_detection
            class_name = best_det.class_name.lower() if best_det else "target"
            conf_pct = int(best_det.confidence * 100) if best_det else 0
            time_str = event.triggered_at.strftime("%Y%m%d_%H%M%S")

            filename = f"clip_{class_name}_{time_str}_conf{conf_pct}pct_{event.event_id}.mp4"
            output_path = out_dir / filename

            # 4. Initialize OpenCV VideoWriter
            h, w = frames_to_write[0].shape[:2]
            
            # Calculate effective FPS: total frames / total duration
            total_duration = pre_sec + post_sec
            calc_fps = max(5.0, min(30.0, len(frames_to_write) / total_duration))

            # Try MP4V codec (cross-platform, built into all OpenCV installations)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(output_path), fourcc, calc_fps, (w, h))

            if not writer.isOpened():
                # Fallback to AVI / XVID if MP4V is unavailable
                logger.warning("MP4V codec failed to open. Trying XVID fallback.")
                output_path = out_dir / f"{output_path.stem}.avi"
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                writer = cv2.VideoWriter(str(output_path), fourcc, calc_fps, (w, h))

            # 5. Write frames with timestamp watermark
            watermark_text = f"FeralEye | {event.triggered_at.strftime('%Y-%m-%d %H:%M:%S')} | {class_name.upper()} ({conf_pct}%)"
            for frame in frames_to_write:
                # Add subtle watermark
                annotated = frame.copy()
                cv2.putText(
                    annotated,
                    watermark_text,
                    (20, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA
                )
                writer.write(annotated)

            writer.release()
            event.evidence_video_path = str(output_path)
            logger.info(f"✅ Event video clip saved: {output_path} ({len(frames_to_write)} frames, {calc_fps:.1f} FPS)")

            # 6. Notify completion callback (e.g. for Google Drive sync)
            if on_complete_callback:
                try:
                    on_complete_callback(event)
                except Exception as cb_err:
                    logger.error(f"Error in on_complete_callback for video clip: {cb_err}")

        except Exception as e:
            logger.exception(f"Failed to record event video clip for {event.event_id}: {e}")
