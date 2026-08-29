"""Abstract base class for Alert Notification Providers."""

from abc import ABC, abstractmethod
from events.models import ConfirmedAlertEvent


class BaseAlertHandler(ABC):
    """Abstract interface for all notification dispatchers."""

    @abstractmethod
    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        """
        Dispatches an alert for a confirmed predator detection.
        
        Args:
            event: The ConfirmedAlertEvent containing timestamp, best detection, and evidence path.
        Returns:
            True if sent successfully, False otherwise.
        """
        pass
