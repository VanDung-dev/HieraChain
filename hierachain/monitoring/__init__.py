"""
Monitoring module for HieraChain Ledger.
"""

from hierachain.monitoring.alert_system import AlertManager
from hierachain.monitoring.performance_monitor import PerformanceMonitor

__all__ = [
    "AlertManager",
    "PerformanceMonitor",
    "alert_manager",
]

# Global singleton instance
alert_manager = AlertManager()
