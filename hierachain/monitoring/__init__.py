"""
Monitoring module for HieraChain Ledger.
"""

from importlib import import_module

__all__ = [
    "AlertManager",
    "PerformanceMonitor",
]

_MODULES = {
    "AlertManager": "alert_system",
    "PerformanceMonitor": "performance_monitor",
}


def __getattr__(name: str) -> type:
    """Load metric collection and alert delivery independently when requested."""
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
