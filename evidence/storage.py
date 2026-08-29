"""Evidence Storage & Frame Annotation Module."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import cv2
import numpy as np

from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.evidence")


class EvidenceStorage:
    """
    Handles saving annotated and raw evidence images when detections are confirmed.
    Organizes files into daily folders with timestamps and confidence scores in the filename.
    """

    def __init__(
        self,
        base_dir: Path | str = "./evidence_storage",
        save_annotated: bool = True,
        save_raw: bool = False
    ):
        self.base_dir = Path(base_dir)
        self.save_annotated = save_annotated
        self.save_raw = save_raw
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_event_evidence(self, event: ConfirmedAlertEvent) -> Optional[str]:
        """
        Annotates and saves the best frame from a confirmed alert event.
        
        Returns:
            Path string of saved annotated image, or None.
        """
        best_result = event.best_result
        if best_result is None or best_result.frame is None:
            logger.error("Cannot save evidence: missing frame in event.")
            return None

        now = event.triggered_at
        date_folder = self.base_dir / now.strftime("%Y-%m-%d")
        date_folder.mkdir(parents=True, exist_ok=True)

        best_det = best_result.best_detection
        class_name = best_det.class_name if best_det else "target"
        conf_pct = int(round(best_det.confidence * 100)) if best_det else 0

        time_str = now.strftime("%Y%m%d_%H%M%S")
        filename_base = f"{class_name}_{time_str}_conf{conf_pct}pct_{event.event_id}"

        saved_path_str: Optional[str] = None

        # 1. Save Annotated Frame
        if self.save_annotated:
            annotated_frame = self._annotate_frame(best_result.frame, best_result, now)
            annotated_path = date_folder / f"{filename_base}_annotated.jpg"
            success = cv2.imwrite(str(annotated_path), annotated_frame)
            if success:
                logger.info(f"Evidence photo saved: {annotated_path}")
                saved_path_str = str(annotated_path)
                event.evidence_image_path = saved_path_str
            else:
                logger.error(f"Failed to write evidence image to {annotated_path}")

        # 2. Save Raw Frame (optional)
        if self.save_raw:
            raw_path = date_folder / f"{filename_base}_raw.jpg"
            cv2.imwrite(str(raw_path), best_result.frame)

        return saved_path_str

    def _annotate_frame(self, frame: np.ndarray, result, timestamp: datetime) -> np.ndarray:
        """Draws bounding boxes, labels, confidence, and timestamp banner onto the frame."""
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Draw top banner for timestamp and event info
        banner_height = max(40, int(h * 0.05))
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_height), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, annotated, 0.3, 0, annotated)

        banner_text = f"PREDATOR GUARD | {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Detections: {len(result.detections)}"
        cv2.putText(
            annotated,
            banner_text,
            (15, int(banner_height * 0.65)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7 * (banner_height / 40),
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # Draw bounding boxes for all detections in the frame
        for det in result.detections:
            x1, y1, x2, y2 = det.bbox.to_int_tuple()
            # Bounding box color: Red/Orange for alerts (BGR format)
            color = (0, 69, 255)  # Bright orange-red
            thickness = max(2, int(min(w, h) * 0.003))

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

            # Label badge above box
            label = f"{det.class_name.upper()} {det.confidence:.1%}"
            (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            badge_y1 = max(0, y1 - text_h - 10)
            badge_y2 = y1

            cv2.rectangle(annotated, (x1, badge_y1), (x1 + text_w + 10, badge_y2), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )

        return annotated
