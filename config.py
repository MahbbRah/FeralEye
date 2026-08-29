"""Central Configuration Module for Predator & Cat Detection System."""

from typing import List, Optional
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General metadata
    CAMERA_NAME: str = Field(default="Poultry Pen", description="Friendly name of monitored location")

    # Camera settings
    CAMERA_RTSP_URL: str = Field(
        default="rtsp://192.168.1.233/live/ch00_0",
        description="Full RTSP URL of the IP camera stream"
    )
    STREAM_BACKEND: str = Field(default="opencv", description="Stream backend: 'opencv' or 'ffmpeg'")
    CAMERA_CONNECT_TIMEOUT_SEC: float = Field(default=10.0, description="RTSP connect timeout in seconds")
    CAMERA_RECONNECT_INITIAL_DELAY_SEC: float = Field(default=2.0, description="Initial reconnect backoff delay")
    CAMERA_RECONNECT_MAX_DELAY_SEC: float = Field(default=30.0, description="Max reconnect backoff delay")

    # Detection & AI settings
    DETECTION_FPS: float = Field(default=1.0, description="Number of frames per second to sample for AI detection")
    MODEL_NAME: str = Field(default="yolo11s.pt", description="YOLO model path or name")
    TARGET_CLASSES: List[str] = Field(default=["cat", "dog"], description="List of target classes to monitor")
    CONFIDENCE_THRESHOLD: float = Field(default=0.25, description="Minimum detection confidence score (0.0 to 1.0)")
    INFERENCE_IMAGE_SIZE: int = Field(default=640, description="YOLO inference image size (640 is standard)")

    # Motion Filtering (Optional pre-filter)
    ENABLE_MOTION_FILTER: bool = Field(default=False, description="Enable cheap motion filtering before AI inference")
    MOTION_MIN_AREA: int = Field(default=500, description="Minimum contour area in pixels to register motion")
    MOTION_THRESHOLD: int = Field(default=25, description="Pixel intensity delta threshold for motion")

    # Confirmation & Cooldown state machine
    CONFIRMATION_COUNT: int = Field(default=2, description="Consecutive or window detections required to trigger alert")
    CONFIRMATION_WINDOW_SEC: float = Field(default=4.0, description="Sliding window time in seconds for confirmation")
    ALERT_COOLDOWN_SEC: float = Field(default=180.0, description="Cooldown period after confirmed alert before new alerts")

    # Evidence Storage
    EVIDENCE_DIRECTORY: Path = Field(default=Path("./evidence_storage"), description="Directory to store evidence photos")
    SAVE_ANNOTATED_IMAGE: bool = Field(default=True, description="Save frame with bounding boxes and timestamps")
    SAVE_RAW_IMAGE: bool = Field(default=False, description="Save unmodified raw frame")

    # --- ALERT INTEGRATIONS ---
    # Telegram Bot
    TELEGRAM_ENABLED: bool = Field(default=False, description="Enable Telegram bot photo alerts")
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot API Token (from @BotFather)")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram Chat ID or Group ID")
    TELEGRAM_PROXY_URL: Optional[str] = Field(default=None, description="Optional HTTP/SOCKS5 proxy (e.g. http://127.0.0.1:7890)")

    # Ntfy.sh (Instant Push Alarms)
    NTFY_ENABLED: bool = Field(default=False, description="Enable Ntfy smartphone push alerts")
    NTFY_TOPIC: str = Field(default="", description="Ntfy topic name (e.g. my_predator_guard_123)")
    NTFY_SERVER_URL: str = Field(default="https://ntfy.sh", description="Ntfy server URL")
    NTFY_PRIORITY: str = Field(default="urgent", description="Ntfy priority: min, low, default, high, urgent")

    # Discord Webhook
    DISCORD_ENABLED: bool = Field(default=False, description="Enable Discord Webhook notifications")
    DISCORD_WEBHOOK_URL: str = Field(default="", description="Discord channel webhook URL")

    # SMTP Email
    EMAIL_ENABLED: bool = Field(default=False, description="Enable SMTP email alerts with photo attachment")
    SMTP_SERVER: str = Field(default="smtp.gmail.com", description="SMTP server address")
    SMTP_PORT: int = Field(default=587, description="SMTP port (587 for TLS, 465 for SSL)")
    EMAIL_SENDER: str = Field(default="", description="Sender email address")
    EMAIL_PASSWORD: str = Field(default="", description="Sender email password / App password")
    EMAIL_RECIPIENTS: List[str] = Field(default=[], description="List of recipient email addresses")
    EMAIL_USE_TLS: bool = Field(default=True, description="Use STARTTLS (True) or SSL (False)")

    # Generic Webhook (Home Assistant / MQTT bridge)
    WEBHOOK_ENABLED: bool = Field(default=False, description="Enable generic JSON webhook POST")
    WEBHOOK_URL: str = Field(default="", description="Destination webhook URL")

    # Local Audio Alarm
    AUDIO_ALARM_ENABLED: bool = Field(default=False, description="Enable local speaker alarm/deterrent sound")
    AUDIO_ALARM_FILE: Optional[str] = Field(default=None, description="Path to custom .wav/.mp3 alarm sound file")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    LOG_FILE: Path = Field(default=Path("./logs/camera_guard.log"), description="File path for application logs")
    METRICS_LOG_INTERVAL_SEC: float = Field(default=60.0, description="Interval in seconds to report CPU/FPS metrics")


# Global singleton configuration instance
config = AppConfig()
