"""Central Configuration Module for Predator & Cat Detection System.

Pure Python implementation without C/Rust dependencies (like Pydantic/Maturin)
for seamless cross-platform execution on Android/Termux, Linux, and macOS.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _get_list(key: str, default: List[str]) -> List[str]:
    val = os.getenv(key)
    if val is None:
        return default
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed]
        except Exception:
            pass
    # Fallback to comma-separated
    return [x.strip() for x in val.split(",") if x.strip()]


@dataclass
class AppConfig:
    # General metadata
    CAMERA_NAME: str = os.getenv("CAMERA_NAME", "Poultry Pen")

    # Camera settings
    CAMERA_RTSP_URL: str = os.getenv("CAMERA_RTSP_URL", "rtsp://192.168.1.233/live/ch00_0")
    STREAM_BACKEND: str = os.getenv("STREAM_BACKEND", "opencv")
    CAMERA_CONNECT_TIMEOUT_SEC: float = _get_float("CAMERA_CONNECT_TIMEOUT_SEC", 10.0)
    CAMERA_RECONNECT_INITIAL_DELAY_SEC: float = _get_float("CAMERA_RECONNECT_INITIAL_DELAY_SEC", 2.0)
    CAMERA_RECONNECT_MAX_DELAY_SEC: float = _get_float("CAMERA_RECONNECT_MAX_DELAY_SEC", 30.0)

    # Detection & AI settings
    DETECTION_FPS: float = _get_float("DETECTION_FPS", 1.0)
    MODEL_NAME: str = os.getenv("MODEL_NAME", "yolo11s.pt")
    TARGET_CLASSES: List[str] = field(default_factory=lambda: _get_list("TARGET_CLASSES", ["cat", "dog"]))
    CONFIDENCE_THRESHOLD: float = _get_float("CONFIDENCE_THRESHOLD", 0.25)
    INFERENCE_IMAGE_SIZE: int = _get_int("INFERENCE_IMAGE_SIZE", 640)

    # Motion Filtering (Optional pre-filter)
    ENABLE_MOTION_FILTER: bool = _get_bool("ENABLE_MOTION_FILTER", False)
    MOTION_MIN_AREA: int = _get_int("MOTION_MIN_AREA", 500)
    MOTION_THRESHOLD: int = _get_int("MOTION_THRESHOLD", 25)

    # Confirmation & Cooldown state machine
    CONFIRMATION_COUNT: int = _get_int("CONFIRMATION_COUNT", 2)
    CONFIRMATION_WINDOW_SEC: float = _get_float("CONFIRMATION_WINDOW_SEC", 4.0)
    ALERT_COOLDOWN_SEC: float = _get_float("ALERT_COOLDOWN_SEC", 180.0)

    # Evidence Storage
    EVIDENCE_DIRECTORY: Path = field(default_factory=lambda: Path(os.getenv("EVIDENCE_DIRECTORY", "./evidence_storage")))
    SAVE_ANNOTATED_IMAGE: bool = _get_bool("SAVE_ANNOTATED_IMAGE", True)
    SAVE_RAW_IMAGE: bool = _get_bool("SAVE_RAW_IMAGE", False)

    # --- ALERT INTEGRATIONS ---
    # Telegram Bot
    TELEGRAM_ENABLED: bool = _get_bool("TELEGRAM_ENABLED", False)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_PROXY_URL: Optional[str] = os.getenv("TELEGRAM_PROXY_URL", None)

    # Ntfy.sh (Instant Push Alarms)
    NTFY_ENABLED: bool = _get_bool("NTFY_ENABLED", True)
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC", "Predator_alert_fast")
    NTFY_SERVER_URL: str = os.getenv("NTFY_SERVER_URL", "https://ntfy.sh")
    NTFY_PRIORITY: str = os.getenv("NTFY_PRIORITY", "urgent")

    # Discord Webhook
    DISCORD_ENABLED: bool = _get_bool("DISCORD_ENABLED", False)
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # SMTP Email
    EMAIL_ENABLED: bool = _get_bool("EMAIL_ENABLED", False)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = _get_int("SMTP_PORT", 587)
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_RECIPIENTS: List[str] = field(default_factory=lambda: _get_list("EMAIL_RECIPIENTS", []))
    EMAIL_USE_TLS: bool = _get_bool("EMAIL_USE_TLS", True)

    # Generic Webhook (Home Assistant / MQTT bridge)
    WEBHOOK_ENABLED: bool = _get_bool("WEBHOOK_ENABLED", False)
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")

    # Local Audio Alarm
    AUDIO_ALARM_ENABLED: bool = _get_bool("AUDIO_ALARM_ENABLED", False)
    AUDIO_ALARM_FILE: Optional[str] = os.getenv("AUDIO_ALARM_FILE", None)

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = field(default_factory=lambda: Path(os.getenv("LOG_FILE", "./logs/camera_guard.log")))
    METRICS_LOG_INTERVAL_SEC: float = _get_float("METRICS_LOG_INTERVAL_SEC", 60.0)


# Global singleton configuration instance
config = AppConfig()
