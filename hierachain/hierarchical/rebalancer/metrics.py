"""
Rebalancer metrics — EPS tracking, threshold detection, and monitoring helpers.
"""

import logging
import time
from typing import Any

from hierachain.hierarchical.rebalancer.types import RebalanceMetrics
from hierachain.hierarchical.rebalancer.utils import (
    _get_event_count,
    _get_block_count,
)

logger = logging.getLogger(__name__)


def _update_rebalance_metrics_for_subchain(
    metrics: RebalanceMetrics,
    sub_chain_id: str,
    subchain: Any,
    event_counts: dict[str, list[tuple[float, int]]],
    window_seconds: float = 60.0,
) -> RebalanceMetrics:
    now = time.time()
    event_count = _get_event_count(subchain)
    block_count = _get_block_count(subchain)

    history = event_counts.get(sub_chain_id, [])
    history.append((now, event_count))

    cutoff = now - window_seconds
    history = [(t, c) for t, c in history if t > cutoff]
    event_counts[sub_chain_id] = history

    if len(history) >= 2:
        time_span = history[-1][0] - history[0][0]
        count_diff = history[-1][1] - history[0][1]
        current_eps = count_diff / time_span if time_span > 0 else 0
    else:
        current_eps = 0

    metrics.current_eps = current_eps
    metrics.avg_eps = (metrics.avg_eps + current_eps) / 2
    metrics.peak_eps = max(metrics.peak_eps, current_eps)
    metrics.event_count = event_count
    metrics.block_count = block_count
    metrics.timestamp = now

    return metrics


def _should_split_for_rebalancer(
    metrics: RebalanceMetrics,
    threshold_eps: int,
    min_events_for_split: int,
    cooldown_seconds: float,
) -> bool:
    if metrics.last_split_time > 0:
        elapsed = time.time() - metrics.last_split_time
        if elapsed < cooldown_seconds:
            return False

    if metrics.event_count < min_events_for_split:
        return False

    if metrics.current_eps >= threshold_eps:
        return True

    return False
