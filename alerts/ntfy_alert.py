"""Ntfy.sh Instant Push Alarm Notification Provider."""

import logging
from pathlib import Path
from typing import Optional
import requests

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.ntfy")


class NtfyAlertHandler(BaseAlertHandler):
    """
    Sends smartphone push alarms via ntfy.sh (or self-hosted ntfy server).
    Supports urgent priority, custom alarm sounds, and attached photos.
    """

    def __init__(
        self,
        topic: str,
        server_url: str = "https://ntfy.sh",
        priority: str = "urgent",
        camera_name: str = "Poultry Pen"
    ):
        self.topic = topic.strip()
        self.server_url = server_url.rstrip("/")
        self.priority = priority
        self.camera_name = camera_name
        self.post_url = f"{self.server_url}/{self.topic}"

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        if not self.topic:
            logger.warning("Ntfy alert skipped: missing topic.")
            return False

        best_det = event.best_result.best_detection
        class_name = best_det.class_name.upper() if best_det else "PREDATOR"
        conf_pct = best_det.confidence * 100 if best_det else 0.0
        time_str = event.triggered_at.strftime("%Y-%m-%d %H:%M:%S")

        title = f"{class_name} Detected at {self.camera_name}!"
        message = f"Confirmed {class_name} ({conf_pct:.1f}% confidence) at {time_str}. Event ID: {event.event_id}"

        headers = {
            "Title": title,
            "Priority": self.priority,
            "Tags": "rotating_light,warning,cat",
            "Message": message,
        }

        photo_path = event.evidence_image_path
        try:
            if photo_path and Path(photo_path).exists():
                with open(photo_path, "rb") as f:
                    headers["Filename"] = Path(photo_path).name
                    response = requests.post(
                        self.post_url,
                        data=f,
                        headers=headers,
                        timeout=15.0
                    )
            else:
                response = requests.post(
                    self.post_url,
                    data=message.encode("utf-8"),
                    headers=headers,
                    timeout=8.0
                )

            if response.status_code == 200:
                logger.info(f"✅ Ntfy push alarm sent successfully to topic '{self.topic}'.")
                return True
            else:
                logger.error(f"Ntfy returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Ntfy alert: {e}")
            return False
