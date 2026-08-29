"""Detection State Machine with Sliding Window Confirmation and Cooldown."""

import uuid
import time
import logging
from enum import Enum
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from events.models import FrameDetectionResult, ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.state_engine")


class State(str, Enum):
    IDLE = "IDLE"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    COOLDOWN = "COOLDOWN"


class DetectionStateEngine:
    """
    Manages detection state transitions to prevent false positives and alert flooding.
    
    Logic:
    1. Single detection -> CANDIDATE state, records candidate frame.
    2. If >= `confirmation_count` detections occur within `window_sec` -> Triggers CONFIRMED alert.
    3. After alert -> enters COOLDOWN for `cooldown_sec` suppressing new alerts.
    4. When window expires without meeting count -> resets to IDLE.
    """

    def __init__(
        self,
        confirmation_count: int = 2,
        confirmation_window_sec: float = 4.0,
        cooldown_sec: float = 300.0,
    ):
        self.confirmation_count = confirmation_count
        self.confirmation_window_sec = confirmation_window_sec
        self.cooldown_sec = cooldown_sec

        self.current_state = State.IDLE
        self._history: List[FrameDetectionResult] = []
        self._cooldown_start_time: Optional[datetime] = None

    def process_result(self, result: FrameDetectionResult) -> Tuple[State, Optional[ConfirmedAlertEvent]]:
        """
        Ingests a frame detection result and updates the state machine.
        
        Returns:
            (current_state, alert_event_or_None)
        """
        now = result.timestamp

        # Check if currently in cooldown
        if self.current_state == State.COOLDOWN:
            elapsed = (now - self._cooldown_start_time).total_seconds()
            if elapsed < self.cooldown_sec:
                # Still cooling down
                if result.has_targets:
                    logger.debug(f"[COOLDOWN] Cat still in view ({elapsed:.0f}s / {self.cooldown_sec:.0f}s elapsed). Alert suppressed.")
                return State.COOLDOWN, None
            else:
                logger.info(f"Cooldown period ({self.cooldown_sec}s) ended. Returning to IDLE.")
                self.current_state = State.IDLE
                self._history.clear()
                self._cooldown_start_time = None

        # Clean history older than confirmation window
        cutoff_time = now - timedelta(seconds=self.confirmation_window_sec)
        self._history = [r for r in self._history if r.timestamp >= cutoff_time]

        if result.has_targets:
            self._history.append(result)
            count = len(self._history)
            best_det = result.best_detection
            logger.info(f"Target candidate '{best_det.class_name}' detected with conf={best_det.confidence:.2f} (Window count: {count}/{self.confirmation_count})")

            if count >= self.confirmation_count:
                # CONFIRMED!
                self.current_state = State.CONFIRMED
                event_id = str(uuid.uuid4())[:8]
                best_overall_result = max(self._history, key=lambda r: r.best_detection.confidence if r.best_detection else 0.0)

                event = ConfirmedAlertEvent(
                    event_id=event_id,
                    triggered_at=now,
                    confirmed_detections=list(self._history),
                    best_result=best_overall_result,
                )

                logger.warning(
                    f"*** ALERT CONFIRMED! [{event.event_id}] Target '{best_overall_result.best_detection.class_name}' "
                    f"confirmed with {count} detections in {self.confirmation_window_sec:.1f}s window! "
                    f"Peak confidence: {best_overall_result.best_detection.confidence:.2%} ***"
                )

                # Enter Cooldown immediately
                self.current_state = State.COOLDOWN
                self._cooldown_start_time = now
                self._history.clear()

                return State.CONFIRMED, event
            else:
                self.current_state = State.CANDIDATE
                return State.CANDIDATE, None
        else:
            if not self._history:
                self.current_state = State.IDLE
            else:
                self.current_state = State.CANDIDATE
            return self.current_state, None
