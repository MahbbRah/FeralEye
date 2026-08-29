"""Discord Webhook Alert Notification Provider."""

import json
import logging
from pathlib import Path
from typing import Optional
import requests

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.discord")


class DiscordAlertHandler(BaseAlertHandler):
    """
    Sends rich embedded notifications with evidence photo attachments
    to a Discord channel via Webhook.
    """

    def __init__(self, webhook_url: str, camera_name: str = "Poultry Pen"):
        self.webhook_url = webhook_url.strip()
        self.camera_name = camera_name

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        if not self.webhook_url:
            logger.warning("Discord alert skipped: missing webhook URL.")
            return False

        best_det = event.best_result.best_detection
        class_name = best_det.class_name.upper() if best_det else "PREDATOR"
        conf_pct = best_det.confidence * 100 if best_det else 0.0
        time_str = event.triggered_at.strftime("%Y-%m-%d %H:%M:%S")

        embed = {
            "title": "🚨 Predator Detection Alert!",
            "description": f"A **{class_name}** has been confirmed by the camera guard.",
            "color": 16724736,  # Orange-Red
            "fields": [
                {"name": "📍 Location", "value": self.camera_name, "inline": True},
                {"name": "🐾 Target", "value": class_name, "inline": True},
                {"name": "🎯 Confidence", "value": f"{conf_pct:.1f}%", "inline": True},
                {"name": "⏱️ Timestamp", "value": time_str, "inline": True},
                {"name": "🆔 Event ID", "value": event.event_id, "inline": True},
            ],
            "footer": {"text": "Predator Camera Guard Service"},
            "timestamp": event.triggered_at.isoformat()
        }

        photo_path = event.evidence_image_path
        try:
            if photo_path and Path(photo_path).exists():
                embed["image"] = {"url": f"attachment://{Path(photo_path).name}"}
                payload = {"embeds": [embed]}

                with open(photo_path, "rb") as f:
                    files = {
                        "payload_json": (None, json.dumps(payload)),
                        "file": (Path(photo_path).name, f, "image/jpeg")
                    }
                    response = requests.post(self.webhook_url, files=files, timeout=10.0)
            else:
                payload = {"embeds": [embed]}
                response = requests.post(self.webhook_url, json=payload, timeout=8.0)

            if response.status_code in (200, 204):
                logger.info(f"✅ Discord webhook alert sent successfully for event {event.event_id}.")
                return True
            else:
                logger.error(f"Discord webhook returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
