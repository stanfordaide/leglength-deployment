"""
Lightweight Graphite client for emitting metrics.

Uses the same approach as Mercure - simple, async, fire-and-forget.
"""

import os
import logging
from typing import Optional

try:
    import graphyte
except ImportError:
    graphyte = None

logger = logging.getLogger(__name__)


class GraphiteClient:
    """
    Simple Graphite client for emitting operational metrics.
    
    Usage:
        client = GraphiteClient()
        client.send("inference.started", 1)
        client.send("inference.duration_ms", 1234.5)
    """
    
    def __init__(self, prefix: str = "leglength", enabled: bool = True):
        """
        Initialize Graphite client.
        
        Args:
            prefix: Metric prefix (default: "leglength")
            enabled: If False, all sends are no-ops (for testing/development)
        """
        self.prefix = prefix
        self.enabled = enabled and graphyte is not None
        
        if not self.enabled:
            if not graphyte:
                logger.debug("graphyte not available - Graphite metrics disabled")
            else:
                logger.debug("Graphite client disabled")
            return
        
        # Get Graphite connection details from environment
        host = os.getenv("GRAPHITE_HOST", "172.17.0.1")
        port = int(os.getenv("GRAPHITE_PORT", "9038"))
        
        try:
            graphyte.init(host, port=port, prefix=prefix)
            logger.info(f"Graphite client initialized: {host}:{port} (prefix: {prefix})")
        except Exception as e:
            logger.warning(f"Failed to initialize Graphite client: {e}")
            self.enabled = False
    
    def send(self, metric: str, value: float, timestamp: Optional[float] = None) -> None:
        """
        Send a metric to Graphite.
        
        Args:
            metric: Metric name (will be prefixed with self.prefix)
            value: Metric value (int or float)
            timestamp: Optional Unix timestamp (default: now)
        
        Examples:
            client.send("inference.started", 1)
            client.send("inference.duration_ms", 1234.5)
            client.send("measurements.femur_cm", 45.2)
        """
        if not self.enabled:
            return
        
        try:
            graphyte.send(metric, value, timestamp=timestamp)
            logger.debug(f"Sent metric: {self.prefix}.{metric} = {value}")
        except Exception as e:
            # Don't crash on metric send failures - metrics are best-effort
            logger.debug(f"Failed to send metric {metric}: {e}")
    
    def increment(self, metric: str, value: int = 1) -> None:
        """
        Increment a counter metric.
        
        Args:
            metric: Metric name
            value: Amount to increment (default: 1)
        
        Example:
            client.increment("inference.started")
        """
        self.send(metric, value)
    
    def gauge(self, metric: str, value: float) -> None:
        """
        Set a gauge metric (current value).
        
        Args:
            metric: Metric name
            value: Current value
        
        Example:
            client.gauge("measurements.femur_cm", 45.2)
        """
        self.send(metric, value)
    
    def timer(self, metric: str, duration_ms: float) -> None:
        """
        Record a timing metric in milliseconds.
        
        Args:
            metric: Metric name
            duration_ms: Duration in milliseconds
        
        Example:
            client.timer("inference.duration_ms", 1234.5)
        """
        self.send(metric, duration_ms)
