"""
Test Utility for Verifying Alert Handlers.

Allows manual and synthetic testing of Telegram, Ntfy, Discord, Email,
Webhooks, and Audio without requiring a live cat detection.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from utils.logger import setup_logger
from events.models import ConfirmedAlertEvent, FrameDetectionResult, Detection, BoundingBox
from evidence.storage import EvidenceStorage
from alerts.console_alert import ConsoleAlertHandler
from alerts.telegram_alert import TelegramAlertHandler
from alerts.ntfy_alert import NtfyAlertHandler
from alerts.discord_alert import DiscordAlertHandler
from alerts.email_alert import EmailAlertHandler
from alerts.webhook_alert import WebhookAlertHandler
from alerts.audio_alert import AudioDeterrentAlertHandler


def create_synthetic_alert_event() -> ConfirmedAlertEvent:
    """Creates a mock confirmed alert event with a drawn test image."""
    h, w = 720, 1280
    frame = np.full((h, w, 3), 40, dtype=np.uint8)

    # Draw simulated background pattern
    cv2.rectangle(frame, (100, 100), (w - 100, h - 100), (60, 60, 60), -1)
    cv2.putText(
        frame,
        "PREDATOR GUARD TEST PATTERN",
        (150, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 255),
        2,
        cv2.LINE_AA
    )

    mock_det = Detection(
        class_name="cat",
        confidence=0.94,
        bbox=BoundingBox(x1=300, y1=200, x2=700, y2=550)
    )

    result = FrameDetectionResult(
        timestamp=datetime.now(),
        detections=[mock_det],
        frame=frame,
        inference_time_ms=12.5
    )

    event = ConfirmedAlertEvent(
        event_id="TEST999",
        triggered_at=datetime.now(),
        confirmed_detections=[result, result],
        best_result=result
    )

    # Save mock evidence image
    storage = EvidenceStorage(base_dir="./tests/test_evidence", save_annotated=True)
    storage.save_event_evidence(event)
    return event


def test_channel(channel: str):
    logger = setup_logger(name="test_alerts", level="INFO")
    logger.info("=" * 60)
    logger.info(f" 🧪 Testing Alert Channel: {channel.upper()}")
    logger.info("=" * 60)

    event = create_synthetic_alert_event()
    logger.info(f"Generated test event: {event.event_id}")
    logger.info(f"Evidence photo: {event.evidence_image_path}")

    if channel in ("console", "all"):
        logger.info("\n--- Testing Console Alert ---")
        ConsoleAlertHandler().send_alert(event)

    if channel in ("telegram", "all"):
        logger.info("\n--- Testing Telegram Alert ---")
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            logger.warning("⚠️ Telegram settings missing in .env (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        else:
            handler = TelegramAlertHandler(
                bot_token=config.TELEGRAM_BOT_TOKEN,
                chat_id=config.TELEGRAM_CHAT_ID,
                camera_name=config.CAMERA_NAME,
                proxy_url=config.TELEGRAM_PROXY_URL
            )
            success = handler.send_alert(event)
            logger.info(f"Telegram alert result: {'SUCCESS ✅' if success else 'FAILED ❌'}")

    if channel in ("ntfy", "all"):
        logger.info("\n--- Testing Ntfy.sh Alert ---")
        if not config.NTFY_TOPIC:
            logger.warning("⚠️ Ntfy topic missing in .env (NTFY_TOPIC).")
        else:
            handler = NtfyAlertHandler(
                topic=config.NTFY_TOPIC,
                server_url=config.NTFY_SERVER_URL,
                priority=config.NTFY_PRIORITY,
                camera_name=config.CAMERA_NAME
            )
            success = handler.send_alert(event)
            logger.info(f"Ntfy alert result: {'SUCCESS ✅' if success else 'FAILED ❌'}")

    if channel in ("discord", "all"):
        logger.info("\n--- Testing Discord Alert ---")
        if not config.DISCORD_WEBHOOK_URL:
            logger.warning("⚠️ Discord webhook URL missing in .env (DISCORD_WEBHOOK_URL).")
        else:
            handler = DiscordAlertHandler(
                webhook_url=config.DISCORD_WEBHOOK_URL,
                camera_name=config.CAMERA_NAME
            )
            success = handler.send_alert(event)
            logger.info(f"Discord alert result: {'SUCCESS ✅' if success else 'FAILED ❌'}")

    if channel in ("email", "all"):
        logger.info("\n--- Testing Email Alert ---")
        if not config.SMTP_SERVER or not config.EMAIL_SENDER or not config.EMAIL_RECIPIENTS:
            logger.warning("⚠️ Email SMTP settings incomplete in .env.")
        else:
            handler = EmailAlertHandler(
                smtp_server=config.SMTP_SERVER,
                smtp_port=config.SMTP_PORT,
                sender_email=config.EMAIL_SENDER,
                sender_password=config.EMAIL_PASSWORD,
                recipient_emails=config.EMAIL_RECIPIENTS,
                use_tls=config.EMAIL_USE_TLS,
                camera_name=config.CAMERA_NAME
            )
            success = handler.send_alert(event)
            logger.info(f"Email alert result: {'SUCCESS ✅' if success else 'FAILED ❌'}")

    if channel in ("webhook", "all"):
        logger.info("\n--- Testing Webhook Alert ---")
        if not config.WEBHOOK_URL:
            logger.warning("⚠️ Webhook URL missing in .env (WEBHOOK_URL).")
        else:
            handler = WebhookAlertHandler(
                webhook_url=config.WEBHOOK_URL,
                camera_name=config.CAMERA_NAME
            )
            success = handler.send_alert(event)
            logger.info(f"Webhook alert result: {'SUCCESS ✅' if success else 'FAILED ❌'}")

    if channel in ("audio", "all"):
        logger.info("\n--- Testing Audio Deterrent Alarm ---")
        handler = AudioDeterrentAlertHandler(sound_file=config.AUDIO_ALARM_FILE)
        handler.send_alert(event)
        logger.info("Audio deterrent triggered.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Predator Guard Alert Handlers")
    parser.add_argument(
        "--channel",
        type=str,
        choices=["telegram", "ntfy", "discord", "email", "webhook", "audio", "console", "all"],
        default="all",
        help="The specific alert channel to test (default: all enabled)"
    )
    args = parser.parse_args()
    test_channel(args.channel)
