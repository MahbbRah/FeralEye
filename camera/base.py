"""Abstract base class for video streams."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np


class BaseStreamReader(ABC):
    """Abstract interface for video/RTSP frame readers."""

    @abstractmethod
    def start(self) -> None:
        """Start reading stream in background."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop background reader and release resources."""
        pass

    @abstractmethod
    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Returns (has_new_frame, frame).
        If connected but no new frame since last call, returns (False, None).
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if the stream is currently connected and healthy."""
        pass
