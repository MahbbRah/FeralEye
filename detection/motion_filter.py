"""Optional lightweight frame-differencing motion filter."""

import logging
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("camera_guard.motion")


class MotionFilter:
    """
    Lightweight, low-overhead motion filter using grayscale downscaling and delta thresholding.
    Used to skip AI inference when there is zero movement in the frame.
    """

    def __init__(self, min_contour_area: int = 500, threshold_delta: int = 25, sample_width: int = 320):
        self.min_contour_area = min_contour_area
        self.threshold_delta = threshold_delta
        self.sample_width = sample_width
        self._prev_gray: Optional[np.ndarray] = None

    def check_motion(self, frame: np.ndarray) -> Tuple[bool, int]:
        """
        Calculates if meaningful motion occurred relative to the previous frame.
        
        Returns:
            (has_motion: bool, motion_pixels_area: int)
        """
        # Downscale frame for ultra-low CPU motion checking
        h, w = frame.shape[:2]
        scale = self.sample_width / float(w)
        resized = cv2.resize(frame, (self.sample_width, int(h * scale)), interpolation=cv2.INTER_AREA)

        # Convert to grayscale and apply Gaussian blur to smooth sensor noise
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return True, self.min_contour_area  # Initial frame always passes

        # Compute absolute difference
        frame_delta = cv2.absdiff(self._prev_gray, gray)
        thresh = cv2.threshold(frame_delta, self.threshold_delta, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours of moving regions
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        total_motion_area = 0
        motion_detected = False

        for c in contours:
            area = cv2.contourArea(c)
            if area >= self.min_contour_area:
                total_motion_area += int(area)
                motion_detected = True

        self._prev_gray = gray
        return motion_detected, total_motion_area

    def reset(self) -> None:
        """Resets the reference background frame."""
        self._prev_gray = None
