"""Local Speaker Audio Deterrent Alert Provider."""

import shutil
import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.audio")


class AudioDeterrentAlertHandler(BaseAlertHandler):
    """
    Plays a local audio deterrent sound (siren, dog bark, or predator alarm)
    via the device speaker (Mac afplay, Linux aplay/paplay).
    """

    def __init__(self, sound_file: Optional[str] = None):
        self.sound_file = sound_file

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        # Spawn audio player in non-blocking background thread
        thread = threading.Thread(target=self._play_sound, daemon=True)
        thread.start()
        return True

    def _play_sound(self) -> None:
        try:
            # Check for macOS afplay
            if shutil.which("afplay"):
                if self.sound_file and Path(self.sound_file).exists():
                    subprocess.run(["afplay", self.sound_file], timeout=5.0)
                else:
                    # Built-in macOS system alarm sound
                    subprocess.run(["afplay", "/System/Library/Sounds/Sosumi.aiff"], timeout=3.0)
                logger.info("🔊 Local audio deterrent played.")
            # Check for Linux aplay/paplay
            elif shutil.which("aplay"):
                if self.sound_file and Path(self.sound_file).exists():
                    subprocess.run(["aplay", self.sound_file], timeout=5.0)
            elif shutil.which("paplay"):
                if self.sound_file and Path(self.sound_file).exists():
                    subprocess.run(["paplay", self.sound_file], timeout=5.0)
            else:
                logger.warning("No audio playback utility found (afplay/aplay/paplay).")
        except Exception as e:
            logger.error(f"Failed to play audio alert: {e}")
