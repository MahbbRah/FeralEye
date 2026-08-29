"""Telegram Bot Alert Notification Provider."""

import logging
from pathlib import Path
from typing import Optional
import requests

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.telegram")


class TelegramAlertHandler(BaseAlertHandler):
    """
    Sends instant push notifications with annotated evidence photo
    to a Telegram chat or group. Supports HTTP/SOCKS5 proxies.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        camera_name: str = "Poultry Pen",
        proxy_url: Optional[str] = None
    ):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()
        self.camera_name = camera_name
        self.proxy_url = proxy_url.strip() if proxy_url else None
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        self._proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram alert skipped: missing bot token or chat ID.")
            return False

        best_det = event.best_result.best_detection
        class_name = best_det.class_name.upper() if best_det else "PREDATOR"
        conf_pct = best_det.confidence * 100 if best_det else 0.0
        time_str = event.triggered_at.strftime("%Y-%m-%d %H:%M:%S")

        caption = (
            f"🚨 *PREDATOR ALERT DETECTED* 🚨\n\n"
            f"📍 *Location:* {self.camera_name}\n"
            f"🐾 *Target:* `{class_name}`\n"
            f"🎯 *Confidence:* `{conf_pct:.1f}%`\n"
            f"⏱️ *Timestamp:* `{time_str}`\n"
            f"🆔 *Event ID:* `{event.event_id}`\n"
        )

        photo_path = event.evidence_image_path
        if not photo_path or not Path(photo_path).exists():
            # Fallback to text message if photo file is missing
            return self._send_text_message(caption)

        try:
            with open(photo_path, "rb") as photo_file:
                payload = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown",
                }
                files = {"photo": photo_file}
                response = requests.post(
                    self.api_url,
                    data=payload,
                    files=files,
                    proxies=self._proxies,
                    timeout=15.0
                )

            if response.status_code == 200:
                logger.info(f"✅ Telegram photo alert sent successfully for event {event.event_id}.")
                return True
            else:
                logger.error(f"Telegram API returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    def _send_text_message(self, text: str) -> bool:
        """Fallback to sendMessage if no photo is available."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            res = requests.post(url, json=payload, timeout=8.0)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Telegram text message fallback failed: {e}")
            return False
