"""Generic Webhook Alert Notification Provider (Home Assistant, MQTT Bridge, IFTTT)."""

import logging
from typing import Optional, Dict, Any
import requests

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.webhook")


class WebhookAlertHandler(BaseAlertHandler):
    """
    Dispatches JSON event payload to custom webhooks (e.g. Home Assistant, Node-RED).
    """

    def __init__(self, webhook_url: str, custom_headers: Optional[Dict[str, str]] = None, camera_name: str = "Poultry Pen"):
        self.webhook_url = webhook_url.strip()
        self.headers = custom_headers or {"Content-Type": "application/json"}
        self.camera_name = camera_name

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        if not self.webhook_url:
            logger.warning("Webhook alert skipped: missing URL.")
            return False

        best_det = event.best_result.best_detection
        payload: Dict[str, Any] = {
            "event": "predator_alert",
            "event_id": event.event_id,
            "location": self.camera_name,
            "target": best_det.class_name if best_det else "target",
            "confidence": best_det.confidence if best_det else 0.0,
            "timestamp": event.triggered_at.isoformat(),
            "evidence_path": event.evidence_image_path,
            "total_detections": len(event.confirmed_detections)
        }

        try:
            res = requests.post(self.webhook_url, json=payload, headers=self.headers, timeout=5.0)
            if res.status_code in (200, 201, 202, 204):
                logger.info(f"✅ Webhook alert posted successfully to {self.webhook_url}.")
                return True
            else:
                logger.error(f"Webhook returned status {res.status_code}: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to post webhook alert: {e}")
            return False
