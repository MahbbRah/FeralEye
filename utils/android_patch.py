"""Android / Termux compatibility patch for Ultralytics."""

import platform
import os
from pathlib import Path

# Fix: On Termux/Android, platform.system() returns "Android",
# which causes Ultralytics to throw "ValueError: Unsupported operating system: Android".
if "android" in platform.system().lower():
    platform.system = lambda: "Linux"
    config_dir = Path.home() / ".config" / "Ultralytics"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(config_dir)
