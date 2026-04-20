"""
Prometheus Metrics for HieraChain.

Defines core metrics for API observability and blockchain health monitoring.
Activated via the ``HRC_METRICS_ENABLED=true`` environment variable.

Metrics exposed at ``GET /metrics`` (Prometheus text format):

- ``hrc_api_requests_total``        — Counter: total HTTP requests by method, path, status.
- ``hrc_api_latency_seconds``       — Histogram: request latency distribution.
- ``hrc_events_submitted_total``    — Counter: business events submitted to sub-chains.
- ``hrc_blocks_created_total``      — Counter: blocks created across all chains.

Usage (in request processing code)::

    from hierachain.monitoring.metrics import metrics
    metrics.record_request("GET", "/api/v1/chains", 200, 0.042)
    metrics.inc_events_submitted(chain_id="supply_chain")
"""

import logging
from typing import Any, cast

logger = logging.getLogger(__name__)


def _import_prometheus() -> Any:
    """Return prometheus_client module or None if not installed."""
    try:
        import prometheus_client  # type: ignore[import]
        return prometheus_client
    except ImportError:
        logger.warning(
            "prometheus-client is not installed. Metrics collection disabled. "
            "Install with: pip install prometheus-client==0.21.1"
        )
        return None


_prom = _import_prometheus()


_REQUEST_COUNTER: Any | None = None
_LATENCY_HISTOGRAM: Any | None = None
_EVENTS_COUNTER: Any | None = None
_BLOCKS_COUNTER: Any | None = None

if _prom is not None:
    _REQUEST_COUNTER = _prom.Counter(
        "hrc_api_requests_total",
        "Total HTTP requests processed by the HieraChain API",
        ["method", "path", "status"],
    )
    _LATENCY_HISTOGRAM = _prom.Histogram(
        "hrc_api_latency_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    _EVENTS_COUNTER = _prom.Counter(
        "hrc_events_submitted_total",
        "Total business events submitted to sub-chains",
        ["chain_id"],
    )
    _BLOCKS_COUNTER = _prom.Counter(
        "hrc_blocks_created_total",
        "Total blocks created across all chains",
        ["chain_id"],
    )


class PrometheusMetrics:
    """
    Thin facade around prometheus_client metric objects.

    Safe to call even when ``prometheus-client`` is not installed — all
    methods are no-ops in that case.
    """

    @staticmethod
    def record_request(method: str, path: str, status: int, latency: float) -> None:
        """
        Record a completed HTTP request.

        Args:
            method:  HTTP method (GET, POST, …).
            path:    URL path (normalised, no query string).
            status:  HTTP status code.
            latency: Request duration in seconds.
        """
        counter = _REQUEST_COUNTER
        if counter is not None:
            cast(Any, counter).labels(
                method=method, path=path, status=str(status)
            ).inc()
        histogram = _LATENCY_HISTOGRAM
        if histogram is not None:
            cast(Any, histogram).labels(method=method, path=path).observe(latency)

    @staticmethod
    def inc_events_submitted(chain_id: str = "unknown") -> None:
        """Increment the events-submitted counter for a chain."""
        counter = _EVENTS_COUNTER
        if counter is not None:
            cast(Any, counter).labels(chain_id=chain_id).inc()

    @staticmethod
    def inc_blocks_created(chain_id: str = "unknown") -> None:
        """Increment the blocks-created counter for a chain."""
        counter = _BLOCKS_COUNTER
        if counter is not None:
            cast(Any, counter).labels(chain_id=chain_id).inc()

    @property
    def available(self) -> bool:
        """Return True if prometheus_client is installed."""
        return _prom is not None


# Singleton — import and use directly:
#   from hierachain.monitoring.metrics import metrics
metrics = PrometheusMetrics()
