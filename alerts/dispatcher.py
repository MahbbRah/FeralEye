"""Concurrent Alert Dispatcher for Multi-Channel Notifications."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.dispatcher")


class AlertDispatcher:
    """
    Manages and dispatches confirmed alert events to all registered handlers
    concurrently in background worker threads without blocking the video pipeline.
    """

    def __init__(self, handlers: List[BaseAlertHandler], max_workers: int = 4):
        self.handlers = handlers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AlertWorker")

    def dispatch(self, event: ConfirmedAlertEvent) -> None:
        """Dispatches the event to all handlers asynchronously."""
        if not self.handlers:
            logger.warning("No alert handlers configured.")
            return

        logger.info(f"Dispatching alert event {event.event_id} to {len(self.handlers)} handler(s)...")

        for handler in self.handlers:
            self._executor.submit(self._safe_send, handler, event)

    def _safe_send(self, handler: BaseAlertHandler, event: ConfirmedAlertEvent) -> None:
        handler_name = handler.__class__.__name__
        try:
            handler.send_alert(event)
        except Exception as e:
            logger.exception(f"Unhandled error in alert handler '{handler_name}': {e}")

    def shutdown(self, wait: bool = True) -> None:
        """Shuts down the worker pool cleanly."""
        self._executor.shutdown(wait=wait)
