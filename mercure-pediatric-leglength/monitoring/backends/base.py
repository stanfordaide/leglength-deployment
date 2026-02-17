"""
Abstract base class for monitoring backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..events import MonitoringEvent

class MonitoringBackend(ABC):
    """
    Interface for monitoring backends (e.g., File, InfluxDB, Prometheus).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the backend with configuration.
        
        Args:
            config: Backend-specific configuration dictionary.
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        
    @abstractmethod
    def record_event(self, event: MonitoringEvent) -> bool:
        """
        Record a monitoring event.
        
        Args:
            event: The fully populated MonitoringEvent.
            
        Returns:
            True if recording was successful, False otherwise.
        """
        pass
        
    @abstractmethod
    def close(self) -> None:
        """
        Close any open connections or file handles.
        """
        pass
