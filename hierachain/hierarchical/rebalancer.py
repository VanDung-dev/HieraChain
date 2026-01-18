"""
Dynamic Sub-chain Rebalancer for HieraChain.

This module implements automatic sub-chain splitting when load exceeds
the optimal Python throughput threshold. It enables dynamic scaling
of the hierarchical blockchain system.

Features:
- Detect event count threshold exceedance
- Automatically split sub-chain into child branches
- State migration during split operation
- Monitoring and metrics for rebalancing decisions
"""

import hashlib
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RebalanceStatus(Enum):
    """Status of rebalancing operation."""
    IDLE = "idle"
    MONITORING = "monitoring"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    SPLITTING = "splitting"
    MIGRATING = "migrating"
    COMPLETE = "complete"
    COOLDOWN = "cooldown"
    FAILED = "failed"


class SplitStrategy(Enum):
    """Strategy for splitting sub-chain."""
    HASH_BASED = "hash_based"  # Split by entity ID hash
    TIME_BASED = "time_based"  # Split by event timestamp
    ROUND_ROBIN = "round_robin"  # Distribute evenly
    LOAD_BASED = "load_based"  # Split by computational load


@dataclass
class RebalanceMetrics:
    """Metrics for rebalancing decisions."""
    sub_chain_id: str
    current_eps: float = 0.0  # Events per second
    avg_eps: float = 0.0
    peak_eps: float = 0.0
    event_count: int = 0
    block_count: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    last_split_time: float = 0.0
    splits_total: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sub_chain_id": self.sub_chain_id,
            "current_eps": self.current_eps,
            "avg_eps": self.avg_eps,
            "peak_eps": self.peak_eps,
            "event_count": self.event_count,
            "block_count": self.block_count,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "last_split_time": self.last_split_time,
            "splits_total": self.splits_total,
            "timestamp": self.timestamp,
        }


@dataclass
class SplitResult:
    """Result of a split operation."""
    success: bool
    parent_chain_id: str
    child_chain_ids: list[str] = field(default_factory=list)
    events_migrated: int = 0
    blocks_migrated: int = 0
    duration_seconds: float = 0.0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "parent_chain_id": self.parent_chain_id,
            "child_chain_ids": self.child_chain_ids,
            "events_migrated": self.events_migrated,
            "blocks_migrated": self.blocks_migrated,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


class SubChainRebalancer:
    """
    Manages dynamic sub-chain rebalancing through automatic splitting.

    When a sub-chain's load exceeds the configured threshold, the rebalancer
    automatically splits it into two child branches, migrating state
    to ensure continued operation without overload.
    """

    def __init__(
        self,
        threshold_eps: int = 1000,
        check_interval: float = 60.0,
        min_events_for_split: int = 5000,
        cooldown_seconds: float = 300.0,
        split_strategy: SplitStrategy = SplitStrategy.HASH_BASED,
        k8s_namespace_manager: Any = None,
    ):
        """
        Initialize SubChainRebalancer.

        Args:
            threshold_eps: Events per second threshold for splitting.
            check_interval: Interval between threshold checks.
            min_events_for_split: Minimum events before split allowed.
            cooldown_seconds: Cooldown after split before next check.
            split_strategy: Strategy for distributing events.
            k8s_namespace_manager: K8sNamespaceManager for K8s integration.
        """
        self.threshold_eps = threshold_eps
        self.check_interval = check_interval
        self.min_events_for_split = min_events_for_split
        self.cooldown_seconds = cooldown_seconds
        self.split_strategy = split_strategy
        self._k8s_manager = k8s_namespace_manager

        # Monitoring state
        self._status = RebalanceStatus.IDLE
        self._monitored_chains: dict[str, RebalanceMetrics] = {}
        self._event_counts: dict[str, list[tuple[float, int]]] = {}
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()

        # Sub-chain references
        self._subchains: dict[str, Any] = {}
        self._hierarchy_manager: Any = None

        # Callbacks
        self._on_threshold_exceeded: Callable[
            [str, RebalanceMetrics], bool
        ] | None = None
        self._on_split_complete: Callable[
            [SplitResult], None
        ] | None = None

        # Stats
        self._stats = {
            "checks_total": 0,
            "thresholds_exceeded": 0,
            "splits_initiated": 0,
            "splits_completed": 0,
            "splits_failed": 0,
            "events_migrated": 0,
        }

        logger.info(
            f"SubChainRebalancer initialized "
            f"(threshold={threshold_eps} eps, interval={check_interval}s)"
        )

    def register_subchain(
        self, sub_chain_id: str, subchain: Any
    ) -> None:
        """
        Register a sub-chain for monitoring.

        Args:
            sub_chain_id: Unique sub-chain identifier.
            subchain: Sub-chain instance reference.
        """
        self._subchains[sub_chain_id] = subchain
        self._monitored_chains[sub_chain_id] = RebalanceMetrics(
            sub_chain_id=sub_chain_id
        )
        self._event_counts[sub_chain_id] = []
        logger.info(f"Registered sub-chain for monitoring: {sub_chain_id}")

    def unregister_subchain(self, sub_chain_id: str) -> None:
        """Unregister a sub-chain from monitoring."""
        self._subchains.pop(sub_chain_id, None)
        self._monitored_chains.pop(sub_chain_id, None)
        self._event_counts.pop(sub_chain_id, None)
        logger.info(f"Unregistered sub-chain: {sub_chain_id}")

    def set_hierarchy_manager(self, manager: Any) -> None:
        """Set reference to HierarchyManager for creating new sub-chains."""
        self._hierarchy_manager = manager

    def start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self._status = RebalanceStatus.MONITORING
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitor_thread.start()
        logger.info("Started rebalancer monitoring")

    def stop_monitoring(self) -> None:
        """Stop background monitoring thread."""
        self._stop_monitoring.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        self._status = RebalanceStatus.IDLE
        logger.info("Stopped rebalancer monitoring")

    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                self._check_all_thresholds()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

            self._stop_monitoring.wait(timeout=self.check_interval)

    def _check_all_thresholds(self) -> None:
        """Check thresholds for all monitored sub-chains."""
        self._stats["checks_total"] += 1

        for sub_chain_id, subchain in list(self._subchains.items()):
            metrics = self._collect_metrics(sub_chain_id, subchain)
            self._monitored_chains[sub_chain_id] = metrics

            if self._should_split(metrics):
                self._stats["thresholds_exceeded"] += 1
                self._status = RebalanceStatus.THRESHOLD_EXCEEDED

                # Check callback
                should_proceed = True
                if self._on_threshold_exceeded:
                    should_proceed = self._on_threshold_exceeded(
                        sub_chain_id, metrics
                    )

                if should_proceed:
                    result = self.split_sub_chain(subchain)
                    if result.success:
                        metrics.last_split_time = time.time()
                        metrics.splits_total += 1

    def _collect_metrics(
        self, sub_chain_id: str, subchain: Any
    ) -> RebalanceMetrics:
        """Collect current metrics for a sub-chain."""
        now = time.time()
        metrics = self._monitored_chains.get(
            sub_chain_id, RebalanceMetrics(sub_chain_id=sub_chain_id)
        )

        # Get event count
        event_count = self._get_event_count(subchain)
        block_count = self._get_block_count(subchain)

        # Calculate EPS
        history = self._event_counts.get(sub_chain_id, [])
        history.append((now, event_count))

        # Keep last 60 seconds of history
        cutoff = now - 60
        history = [(t, c) for t, c in history if t > cutoff]
        self._event_counts[sub_chain_id] = history

        if len(history) >= 2:
            time_span = history[-1][0] - history[0][0]
            count_diff = history[-1][1] - history[0][1]
            current_eps = count_diff / time_span if time_span > 0 else 0
        else:
            current_eps = 0

        # Update metrics
        metrics.current_eps = current_eps
        metrics.avg_eps = (metrics.avg_eps + current_eps) / 2
        metrics.peak_eps = max(metrics.peak_eps, current_eps)
        metrics.event_count = event_count
        metrics.block_count = block_count
        metrics.timestamp = now

        return metrics

    def _should_split(self, metrics: RebalanceMetrics) -> bool:
        """Determine if a sub-chain should be split."""
        # Check cooldown
        if metrics.last_split_time > 0:
            elapsed = time.time() - metrics.last_split_time
            if elapsed < self.cooldown_seconds:
                return False

        # Check minimum events
        if metrics.event_count < self.min_events_for_split:
            return False

        # Check EPS threshold
        if metrics.current_eps >= self.threshold_eps:
            return True

        return False

    def check_threshold(self, sub_chain_id: str) -> bool:
        """
        Check if a specific sub-chain exceeds threshold.

        Args:
            sub_chain_id: Sub-chain to check.

        Returns:
            True if threshold is exceeded.
        """
        if sub_chain_id not in self._subchains:
            return False

        subchain = self._subchains[sub_chain_id]
        metrics = self._collect_metrics(sub_chain_id, subchain)
        return self._should_split(metrics)

    def split_sub_chain(self, sub_chain: Any) -> SplitResult:
        """
        Split a sub-chain into two child branches.

        Args:
            sub_chain: The sub-chain to split.

        Returns:
            SplitResult with operation outcome.
        """
        start_time = time.time()
        self._stats["splits_initiated"] += 1
        self._status = RebalanceStatus.SPLITTING

        parent_id = self._get_sub_chain_id(sub_chain)
        child_ids = [f"{parent_id}-a", f"{parent_id}-b"]

        try:
            # Create child sub-chains
            children = self._create_child_chains(parent_id, child_ids)
            if not children:
                raise RuntimeError("Failed to create child chains")

            # Migrate state
            self._status = RebalanceStatus.MIGRATING
            events_migrated, blocks_migrated = self._migrate_state(
                sub_chain, children
            )

            self._stats["events_migrated"] += events_migrated
            self._stats["splits_completed"] += 1
            self._status = RebalanceStatus.COMPLETE

            result = SplitResult(
                success=True,
                parent_chain_id=parent_id,
                child_chain_ids=child_ids,
                events_migrated=events_migrated,
                blocks_migrated=blocks_migrated,
                duration_seconds=time.time() - start_time,
            )

            if self._on_split_complete:
                self._on_split_complete(result)

            logger.info(
                f"Split complete: {parent_id} -> "
                f"{child_ids}, {events_migrated} events migrated"
            )

            # Enter cooldown
            self._status = RebalanceStatus.COOLDOWN

            return result

        except Exception as e:
            logger.error(f"Split failed for {parent_id}: {e}")
            self._stats["splits_failed"] += 1
            self._status = RebalanceStatus.FAILED
            return SplitResult(
                success=False,
                parent_chain_id=parent_id,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _create_child_chains(
        self, parent_id: str, child_ids: list[str]
    ) -> list[Any]:
        """Create child sub-chains."""
        children = []

        for child_id in child_ids:
            # Use HierarchyManager if available
            if self._hierarchy_manager:
                success = self._hierarchy_manager.create_sub_chain(
                    name=child_id,
                    domain_type="split_child",
                    metadata={"parent": parent_id},
                )
                if success:
                    child = self._hierarchy_manager.get_sub_chain(child_id)
                    if child:
                        children.append(child)
                        self.register_subchain(child_id, child)

            # Create K8s namespace if manager available
            if self._k8s_manager:
                self._k8s_manager.create_namespace(child_id)

        return children

    def _migrate_state(
        self, parent: Any, children: list[Any]
    ) -> tuple[int, int]:
        """
        Migrate state from parent to child chains.

        Args:
            parent: Parent sub-chain.
            children: List of child sub-chains.

        Returns:
            Tuple of (events_migrated, blocks_migrated).
        """
        events_migrated = 0
        blocks_migrated = 0

        if len(children) < 2:
            return 0, 0

        # Get events from parent
        events = self._get_pending_events(parent)

        # Distribute events based on strategy
        for i, event in enumerate(events):
            target_idx = self._select_target_child(event, len(children))
            target = children[target_idx]

            if self._add_event_to_chain(target, event):
                events_migrated += 1

        # Mark parent as split (optional: keep for routing)
        self._mark_chain_as_split(parent, [c for c in children])

        logger.info(
            f"Migrated {events_migrated} events from parent to "
            f"{len(children)} children"
        )

        return events_migrated, blocks_migrated

    def _select_target_child(self, event: Any, num_children: int) -> int:
        """Select target child for event based on strategy."""
        if self.split_strategy == SplitStrategy.HASH_BASED:
            # Hash the entity_id to select child
            entity_id = self._get_event_entity_id(event)
            hash_val = int(hashlib.md5(
                entity_id.encode()
            ).hexdigest()[:8], 16)
            return hash_val % num_children

        elif self.split_strategy == SplitStrategy.TIME_BASED:
            # Older events to first child, newer to second
            timestamp = self._get_event_timestamp(event)
            median_time = time.time() - 30  # Simple median
            return 0 if timestamp < median_time else 1

        elif self.split_strategy == SplitStrategy.ROUND_ROBIN:
            # Simple round robin
            if not hasattr(self, "_rr_counter"):
                self._rr_counter = 0
            self._rr_counter += 1
            return self._rr_counter % num_children

        # Default: hash-based
        return 0

    def get_metrics(self, sub_chain_id: str) -> RebalanceMetrics | None:
        """Get metrics for a specific sub-chain."""
        return self._monitored_chains.get(sub_chain_id)

    def get_all_metrics(self) -> dict[str, RebalanceMetrics]:
        """Get metrics for all monitored sub-chains."""
        return self._monitored_chains.copy()

    def get_status(self) -> RebalanceStatus:
        """Get current rebalancer status."""
        return self._status

    def get_stats(self) -> dict[str, Any]:
        """Get rebalancer statistics."""
        return {
            **self._stats,
            "status": self._status.value,
            "monitored_chains": len(self._subchains),
            "threshold_eps": self.threshold_eps,
            "cooldown_seconds": self.cooldown_seconds,
        }

    def set_callbacks(
        self,
        on_threshold: Callable[
            [str, RebalanceMetrics], bool
        ] | None = None,
        on_split: Callable[[SplitResult], None] | None = None,
    ) -> None:
        """Set callback functions."""
        self._on_threshold_exceeded = on_threshold
        self._on_split_complete = on_split

    # Helper methods

    def _get_sub_chain_id(self, subchain: Any) -> str:
        """Get sub-chain ID."""
        if hasattr(subchain, "name"):
            return subchain.name
        if hasattr(subchain, "sub_chain_id"):
            return subchain.sub_chain_id
        return f"subchain-{id(subchain)}"

    def _get_event_count(self, subchain: Any) -> int:
        """Get event count from sub-chain."""
        if hasattr(subchain, "get_event_count"):
            return subchain.get_event_count()
        if hasattr(subchain, "blockchain"):
            blocks = subchain.blockchain.get_chain()
            return sum(len(b.events) for b in blocks if hasattr(b, "events"))
        return 0

    def _get_block_count(self, subchain: Any) -> int:
        """Get block count from sub-chain."""
        if hasattr(subchain, "get_block_count"):
            return subchain.get_block_count()
        if hasattr(subchain, "blockchain"):
            return len(subchain.blockchain.get_chain())
        return 0

    def _get_pending_events(self, subchain: Any) -> list[Any]:
        """Get pending events from sub-chain."""
        if hasattr(subchain, "get_pending_events"):
            return subchain.get_pending_events()
        return []

    def _add_event_to_chain(self, chain: Any, event: Any) -> bool:
        """Add event to a chain."""
        try:
            if hasattr(chain, "add_event"):
                return chain.add_event(event)
            return True
        except Exception:
            return False

    def _get_event_entity_id(self, event: Any) -> str:
        """Extract entity ID from event."""
        if isinstance(event, dict):
            return event.get("entity_id", str(id(event)))
        if hasattr(event, "entity_id"):
            return event.entity_id
        return str(id(event))

    def _get_event_timestamp(self, event: Any) -> float:
        """Extract timestamp from event."""
        if isinstance(event, dict):
            return event.get("timestamp", time.time())
        if hasattr(event, "timestamp"):
            return event.timestamp
        return time.time()

    def _mark_chain_as_split(
        self, parent: Any, children: list[Any]
    ) -> None:
        """Mark parent chain as split."""
        if hasattr(parent, "mark_split"):
            child_ids = [self._get_sub_chain_id(c) for c in children]
            parent.mark_split(child_ids)
