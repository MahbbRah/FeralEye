"""Evidence Retention & Cleanup Module.

Handles automatic deletion of local evidence files older than the configured
retention window. The cleanup runs on an interval (default hourly) from a
background thread so the main detection loop is never blocked.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("camera_guard.retention")


class EvidenceRetention:
    """Periodically prunes old evidence files (annotated images, raw images, clips)."""

    def __init__(
        self,
        base_dir: Path | str = "./evidence_storage",
        retention_days: int = 10,
        check_interval_sec: float = 3600.0,
        enabled: bool = True,
    ):
        self.base_dir = Path(base_dir)
        self.retention_days = max(1, int(retention_days))
        self.check_interval_sec = max(1.0, check_interval_sec)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_cleanup_summary = ""

    def start(self) -> None:
        """Starts the background retention thread (idempotent)."""
        if not self.enabled:
            logger.info("Evidence retention disabled. Skipping periodic cleanup.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="EvidenceRetention",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Evidence retention started: deleting files older than "
            f"{self.retention_days}d in {self.base_dir} every {self.check_interval_sec:.0f}s"
        )

    def stop(self) -> None:
        """Signals the retention thread to stop and waits briefly for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def cleanup_once(self) -> int:
        """
        Deletes evidence files older than `retention_days` (by modification time).
        Returns the number of files deleted.
        """
        if not self.base_dir.exists():
            return 0

        cutoff = time.time() - (self.retention_days * 86400)
        deleted = 0

        for item in sorted(self.base_dir.rglob("*")):
            if not item.is_file():
                continue
            try:
                if item.stat().st_mtime < cutoff:
                    item.unlink()
                    deleted += 1
                    logger.info(f"Retention: deleted expired evidence file: {item}")
            except FileNotFoundError:
                pass
            except PermissionError as e:
                logger.warning(f"Retention: could not delete {item}: {e}")

        if deleted:
            self.last_cleanup_summary = (
                f"Deleted {deleted} expired evidence file(s) older than {self.retention_days}d "
                f"from {self.base_dir}"
            )
            logger.info(self.last_cleanup_summary)
        return deleted

    def _run_loop(self) -> None:
        """Background loop: run cleanup immediately, then on interval."""
        try:
            self.cleanup_once()
        except Exception:
            logger.exception("Retention: initial cleanup failed")

        while not self._stop_event.wait(self.check_interval_sec):
            try:
                self.cleanup_once()
            except Exception:
                logger.exception("Retention: periodic cleanup failed")
