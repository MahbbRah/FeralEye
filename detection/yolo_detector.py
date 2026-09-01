import time
import logging
from typing import List, Optional, Set
import numpy as np
import torch

# Ensure Android/Termux compatibility before importing Ultralytics
import utils.android_patch  # noqa: F401
from ultralytics import YOLO

from events.models import BoundingBox, Detection, FrameDetectionResult

logger = logging.getLogger("camera_guard.detector")


class YOLODetector:
    """
    Lightweight YOLO object detector wrapper.
    Keeps model loaded in memory, selects optimal compute device, and filters target classes.
    """

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        target_classes: Optional[List[str]] = None,
        confidence_threshold: float = 0.45,
        imgsz: int = 640
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz

        # Class aliases for user convenience
        aliases = {
            "human": "person",
            "people": "person",
            "feline": "cat",
            "canine": "dog",
        }
        normalized_targets = []
        for c in (target_classes or ["cat"]):
            c_clean = c.lower().strip()
            normalized_targets.append(aliases.get(c_clean, c_clean))

        self.target_classes = normalized_targets

        self._device = self._select_device()
        logger.info(f"Loading YOLO model '{self.model_name}' on device '{self._device}'...")
        start_time = time.time()
        self.model = YOLO(self.model_name)
        load_time = time.time() - start_time
        logger.info(f"Model loaded in {load_time:.2f}s. Monitoring target classes: {self.target_classes}")

        # Resolve COCO class IDs for target names
        self.class_names = self.model.names  # dict: {0: 'person', 15: 'cat', ...}
        self.target_class_ids: Set[int] = {
            cls_id for cls_id, name in self.class_names.items()
            if name.lower() in self.target_classes
        }
        logger.info(f"Mapped target classes {self.target_classes} -> COCO class IDs: {self.target_class_ids}")

        # Class-specific confidence thresholds (e.g. higher for person to avoid chicken false positives)
        self.class_thresholds = {
            "person": 0.65,
            "human": 0.65,
            "cat": self.confidence_threshold,
            "dog": self.confidence_threshold,
        }

    def _select_device(self) -> str:
        """Selects the best available hardware acceleration device and optimizes CPU threads."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        
        # On multi-core mobile CPUs (Android / ARM), utilize all cores
        try:
            num_cores = os.cpu_count() or 4
            torch.set_num_threads(max(1, min(num_cores, 4)))
            logger.info(f"Configured PyTorch CPU with {torch.get_num_threads()} worker threads.")
        except Exception:
            pass

        return "cpu"

    def detect(self, frame: np.ndarray) -> FrameDetectionResult:
        """
        Runs object detection inference on a single frame.
        
        Returns:
            FrameDetectionResult containing timestamp, detections, and inference latency.
        """
        from datetime import datetime

        timestamp = datetime.now()
        t0 = time.perf_counter()

        # Run inference across all classes without restricting 'classes=...'
        # This allows chickens/roosters to be correctly classified as 'bird' (class 14)
        # rather than being forced into 'person' (class 0) by class filtering!
        min_conf = min(self.confidence_threshold, 0.20)
        results = self.model.predict(
            source=frame,
            conf=min_conf,
            imgsz=self.imgsz,
            device=self._device,
            verbose=False,
        )

        inference_time_ms = (time.perf_counter() - t0) * 1000.0
        detections: List[Detection] = []

        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                class_name = self.class_names.get(cls_id, f"class_{cls_id}").lower()

                # Discard chickens/birds immediately
                if class_name in ("bird", "chicken"):
                    continue

                # Only evaluate target classes configured by user
                if class_name not in self.target_classes and cls_id not in self.target_class_ids:
                    continue

                # Get class-specific threshold (e.g. 0.65 for person, 0.25 for cat/dog)
                required_conf = self.class_thresholds.get(class_name, self.confidence_threshold)

                if conf >= required_conf:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    box_h = abs(y2 - y1)
                    box_w = abs(x2 - x1)

                    # Physical sanity check: A real human cannot be a tiny 40px box
                    if class_name == "person" and box_h < 80:
                        # Too small to be a human in view (likely small animal/bird artifact)
                        continue

                    detections.append(
                        Detection(
                            class_name=class_name,
                            confidence=conf,
                            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                        )
                    )

        return FrameDetectionResult(
            timestamp=timestamp,
            detections=detections,
            frame=frame,
            inference_time_ms=inference_time_ms
        )
