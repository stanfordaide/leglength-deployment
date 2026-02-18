"""
Monitoring - Lightweight Graphite-based metrics

Simple, lightweight monitoring using Graphite (same approach as Mercure).
No complex state management, just emit operational metrics.
"""

from .graphite_client import GraphiteClient

__all__ = ['GraphiteClient']
