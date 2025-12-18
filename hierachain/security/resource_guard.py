"""
Guard against resource exhaustion for Hierachain framework.

This middleware is designed to be used in conjunction with the PerformanceMonitor
to provide a basic layer of DoS protection and load shedding. It checks the current
system health (CPU and memory usage) before processing each request. If the system
health is critical, it rejects the request with a 503 Service Unavailable response.
"""

import logging
from typing import Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from hierachain.monitoring.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class ResourceGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that rejects requests when system resources are critically low.

    This middleware is OPTIONAL. Developers can choose to include it in their
    FastAPI/Starlette application to provide a basic layer of DoS protection
    and load shedding.
    """

    def __init__(
        self,
        app: ASGIApp,
        monitor: Optional[PerformanceMonitor] = None,
        memory_threshold_percent: float = 80.0,
        cpu_threshold_percent: float = 80.0,
        exempt_paths: Optional[Set[str]] = None,
    ):
        """
        Initialize the ResourceGuardMiddleware.

        Args:
            app: The ASGI application.
            monitor: Instance of PerformanceMonitor. If None, a new one is created.
            memory_threshold_percent: Reject requests if memory usage exceeds this %.
            cpu_threshold_percent: Reject requests if CPU usage exceeds this %.
            exempt_paths: Set of paths to exclude from checks (e.g., /health).
        """
        super().__init__(app)
        self.monitor = monitor or PerformanceMonitor()
        self.memory_threshold = memory_threshold_percent
        self.cpu_threshold = cpu_threshold_percent
        self.exempt_paths = exempt_paths or {
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

        # Ensure monitor is gathering data if we created it
        if not monitor and not self.monitor.monitoring_active:
            # Note: In a real app, you might want to share the global monitor instance
            # rather than creating a new one here.
            self.monitor.start_monitoring()

    async def dispatch(self, request: Request, call_next):
        """
        Check system health before processing the request.
        """
        # 1. Skip checks for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # 2. Get current metrics
        metrics = self.monitor.get_current_metrics()

        # 3. Check Memory
        mem_metric = metrics.get("memory_usage")
        if mem_metric and mem_metric.get("current_value", 0) > self.memory_threshold:
            logger.warning(
                f"ResourceGuard: Rejecting request due to high memory usage "
                f"({mem_metric['current_value']:.1f}% > {self.memory_threshold}%)"
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": "System overloaded (Memory)",
                    "retry_after": 30,
                },
                headers={"Retry-After": "30"},
            )

        # 4. Check CPU
        cpu_metric = metrics.get("cpu_usage")
        if cpu_metric and cpu_metric.get("current_value", 0) > self.cpu_threshold:
            logger.warning(
                f"ResourceGuard: Rejecting request due to high CPU usage "
                f"({cpu_metric['current_value']:.1f}% > {self.cpu_threshold}%)"
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": "System overloaded (CPU)",
                    "retry_after": 10,
                },
                headers={"Retry-After": "10"},
            )

        # 5. Proceed if safe
        return await call_next(request)
