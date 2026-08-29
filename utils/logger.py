"""Structured and Clean Logging Setup."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "camera_guard", log_file: Path | str = None, level: str = "INFO") -> logging.Logger:
    """Configures an application logger with console and optional rotating file output."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # If handlers already exist on this specific logger, clear them to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.propagate = False

    # Log format: [2026-08-29 10:30:15] [INFO] [camera.cv_stream] Message
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,              # Keep up to 5 rolled log files
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
