"""
Monitoring module for pediatric leg length analysis.

Provides optional InfluxDB and Prometheus integration with graceful fallback
when monitoring services are not available.
Also provides PostgreSQL storage for AI inference results.
"""

from .monitor_manager import MonitorManager

try:
    from .results_db_client import ResultsDBClient
    __all__ = ["MonitorManager", "ResultsDBClient"]
except ImportError:
    # results_db_client may not be available if psycopg2 is not installed
    __all__ = ["MonitorManager"]

__version__ = "0.1.0"
