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


def _get_sub_chain_id(subchain: Any) -> str:
    """Get sub-chain ID."""
    if hasattr(subchain, "name"):
        return subchain.name
    if hasattr(subchain, "sub_chain_id"):
        return subchain.sub_chain_id
    return f"subchain-{id(subchain)}"


def _get_event_count(subchain: Any) -> int:
    """Get event count from sub-chain."""
    if hasattr(subchain, "get_event_count"):
        return subchain.get_event_count()
    if hasattr(subchain, "blockchain"):
        blocks = subchain.blockchain.get_chain()
        return sum(len(b.events) for b in blocks if hasattr(b, "events"))
    return 0


def _get_block_count(subchain: Any) -> int:
    """Get block count from sub-chain."""
    if hasattr(subchain, "get_block_count"):
        return subchain.get_block_count()
    if hasattr(subchain, "blockchain"):
        return len(subchain.blockchain.get_chain())
    return 0


def _get_pending_events(subchain: Any) -> list[Any]:
    """Get pending events from sub-chain."""
    if hasattr(subchain, "get_pending_events"):
        return subchain.get_pending_events()
    return []


def _add_event_to_chain(chain: Any, event: Any) -> bool:
    """Add event to a chain."""
    try:
        if hasattr(chain, "add_event"):
            return chain.add_event(event)
        return True
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to add event to chain: %s", e)
        return False


def _get_event_entity_id(event: Any) -> str:
    """Extract entity ID from event."""
    if isinstance(event, dict):
        return event.get("entity_id", str(id(event)))
    if hasattr(event, "entity_id"):
        return event.entity_id
    return str(id(event))


def _get_event_timestamp(event: Any) -> float:
    """Extract timestamp from event."""
    if isinstance(event, dict):
        return event.get("timestamp", time.time())
    if hasattr(event, "timestamp"):
        return event.timestamp
    return time.time()


def _mark_chain_as_split(parent: Any, children: list[Any]) -> None:
    """Mark parent chain as split."""
    if hasattr(parent, "mark_split"):
        child_ids = [_get_sub_chain_id(c) for c in children]
        parent.mark_split(child_ids)


def _update_rebalance_metrics_for_subchain(
    metrics: "RebalanceMetrics",
    sub_chain_id: str,
    subchain: Any,
    event_counts: dict[str, list[tuple[float, int]]],
    window_seconds: float = 60.0,
) -> "RebalanceMetrics":
    """Update rebalance metrics for a sub-chain."""
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
    metrics: "RebalanceMetrics",
    threshold_eps: int,
    min_events_for_split: int,
    cooldown_seconds: float,
) -> bool:
    """Determine if rebalancing should occur based on metrics."""
    if metrics.last_split_time > 0:
        elapsed = time.time() - metrics.last_split_time
        if elapsed < cooldown_seconds:
            return False

    if metrics.event_count < min_events_for_split:
        return False

    if metrics.current_eps >= threshold_eps:
        return True

    return False


def _split_sub_chain_for_rebalancer(
    rebalancer: "SubChainRebalancer", sub_chain: Any
) -> "SplitResult":
    """Split a sub-chain into two child branches."""
    start_time = time.time()
    rebalancer.stats["splits_initiated"] += 1
    rebalancer.status = RebalanceStatus.SPLITTING

    parent_id = _get_sub_chain_id(sub_chain)
    child_ids = [f"{parent_id}-a", f"{parent_id}-b"]

    try:
        children = rebalancer.create_child_chains(parent_id, child_ids)
        if not children:
            raise RuntimeError("Failed to create child chains")

        rebalancer.status = RebalanceStatus.MIGRATING
        events_migrated, blocks_migrated = _migrate_state_for_rebalancer(
            rebalancer, sub_chain, children
        )

        rebalancer.stats["events_migrated"] += events_migrated
        rebalancer.stats["splits_completed"] += 1
        rebalancer.status = RebalanceStatus.COMPLETE

        result = SplitResult(
            success=True,
            parent_chain_id=parent_id,
            child_chain_ids=child_ids,
            events_migrated=events_migrated,
            blocks_migrated=blocks_migrated,
            duration_seconds=time.time() - start_time,
        )

        if rebalancer.on_split_complete:
            rebalancer.on_split_complete(result)

        logger.info(
            "Split complete: %s -> %s, %d events migrated",
            parent_id, child_ids, events_migrated
        )

        rebalancer.status = RebalanceStatus.COOLDOWN

        return result

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Split failed for %s: %s", parent_id, e)
        rebalancer.stats["splits_failed"] += 1
        rebalancer.status = RebalanceStatus.FAILED
        return SplitResult(
            success=False,
            parent_chain_id=parent_id,
            error_message=str(e),
            duration_seconds=time.time() - start_time,
        )


def _migrate_state_for_rebalancer(
    rebalancer: "SubChainRebalancer",
    parent: Any,
    children: list[Any]
) -> tuple[int, int]:
    """Migrate state from parent to child chains."""
    events_migrated = 0
    blocks_migrated = 0

    if len(children) < 2:
        return 0, 0

    events = _get_pending_events(parent)

    for event in events:
        target_idx = _select_target_child_for_rebalancer(
            rebalancer,
            event,
            len(children),
        )
        target = children[target_idx]

        if _add_event_to_chain(target, event):
            events_migrated += 1

    _mark_chain_as_split(parent, [c for c in children])

    logger.info(
        "Migrated %d events from parent %s to %d children",
        events_migrated, parent, len(children)
    )

    return events_migrated, blocks_migrated


def _select_target_child_for_rebalancer(
    rebalancer: "SubChainRebalancer",
    event: Any,
    num_children: int,
) -> int:
    """Select target child for event based on strategy."""
    if rebalancer.split_strategy == SplitStrategy.HASH_BASED:
        entity_id = _get_event_entity_id(event)
        hash_val = int(hashlib.sha256(entity_id.encode()).hexdigest()[:8], 16)
        return hash_val % num_children

    if rebalancer.split_strategy == SplitStrategy.TIME_BASED:
        timestamp = _get_event_timestamp(event)
        median_time = time.time() - 30
        return 0 if timestamp < median_time else 1

    if rebalancer.split_strategy == SplitStrategy.ROUND_ROBIN:
        rebalancer.rr_counter = rebalancer.rr_counter + 1
        return rebalancer.rr_counter % num_children

    return 0


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
        self._rr_counter = 0

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
        self._on_split_complete: Callable[[SplitResult], None] | None = None

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
            "SubChainRebalancer initialized (threshold=%d eps, interval=%.2fs)",
            threshold_eps, check_interval
        )

    def register_subchain(self, sub_chain_id: str, subchain: Any) -> None:
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
        logger.info("Unregistered sub-chain: %s", sub_chain_id)

    def set_hierarchy_manager(self, manager: Any) -> None:
        """Set reference to HierarchyManager for creating new sub-chains."""
        self._hierarchy_manager = manager

    def start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self._status = RebalanceStatus.MONITORING
        monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitor_thread = monitor_thread
        monitor_thread.start()
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
                logger.error("Monitoring loop error: %s", e)

            self._stop_monitoring.wait(timeout=self.check_interval)

    def _check_all_thresholds(self) -> None:
        """Check thresholds for all monitored sub-chains."""
        self._stats["checks_total"] += 1

        for sub_chain_id, subchain in list(self._subchains.items()):
            self._process_single_chain_rebalance(sub_chain_id, subchain)

    def _process_single_chain_rebalance(self, sub_chain_id: str, subchain: Any) -> None:
        """Process rebalancing check and action for a single sub-chain."""
        metrics = self._collect_metrics(sub_chain_id, subchain)
        self._monitored_chains[sub_chain_id] = metrics

        if self._should_split(metrics):
            self._handle_threshold_exceedance(sub_chain_id, subchain, metrics)

    def _handle_threshold_exceedance(
        self, sub_chain_id: str, subchain: Any, metrics: "RebalanceMetrics"
    ) -> None:
        """Handle the situation where a threshold is exceeded."""
        self._stats["thresholds_exceeded"] += 1
        self._status = RebalanceStatus.THRESHOLD_EXCEEDED

        if self._is_split_authorized(sub_chain_id, metrics):
            self._execute_split_operation(subchain, metrics)

    def _is_split_authorized(
        self, sub_chain_id: str, metrics: "RebalanceMetrics"
    ) -> bool:
        """Check with optional callback if split is authorized to proceed."""
        if self._on_threshold_exceeded:
            return self._on_threshold_exceeded(sub_chain_id, metrics)
        return True

    def _execute_split_operation(
        self, subchain: Any, metrics: "RebalanceMetrics"
    ) -> None:
        """Execute the sub-chain split and update statistics on success."""
        result = self.split_sub_chain(subchain)
        if result.success:
            metrics.last_split_time = time.time()
            metrics.splits_total += 1

    def _collect_metrics(self, sub_chain_id: str, subchain: Any) -> RebalanceMetrics:
        """Collect current metrics for a sub-chain."""
        metrics = self._monitored_chains.get(
            sub_chain_id, RebalanceMetrics(sub_chain_id=sub_chain_id)
        )
        return _update_rebalance_metrics_for_subchain(
            metrics, sub_chain_id, subchain, self._event_counts
        )

    def _should_split(self, metrics: RebalanceMetrics) -> bool:
        """Determine if a sub-chain should be split."""
        return _should_split_for_rebalancer(
            metrics, self.threshold_eps,
            self.min_events_for_split, self.cooldown_seconds
        )

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
        return _split_sub_chain_for_rebalancer(self, sub_chain)

    @property
    def stats(self) -> dict[str, Any]:
        return self._stats

    @property
    def status(self) -> RebalanceStatus:
        return self._status

    @status.setter
    def status(self, value: RebalanceStatus) -> None:
        self._status = value

    @property
    def on_split_complete(self) -> Callable[[SplitResult], None] | None:
        return self._on_split_complete

    @on_split_complete.setter
    def on_split_complete(self, callback: Callable[[SplitResult], None] | None) -> None:
        self._on_split_complete = callback

    @property
    def rr_counter(self) -> int:
        return self._rr_counter

    @rr_counter.setter
    def rr_counter(self, value: int) -> None:
        self._rr_counter = value

    def create_child_chains(self, parent_id: str, child_ids: list[str]) -> list[Any]:
        return self._create_child_chains(parent_id, child_ids)

    def _create_child_chains(self, parent_id: str, child_ids: list[str]) -> list[Any]:
        """Create child sub-chains."""
        children = []
        for child_id in child_ids:
            child = self._initialize_single_child_chain(parent_id, child_id)
            if child:
                children.append(child)
        return children

    def _initialize_single_child_chain(self, parent_id: str, child_id: str) -> Any:
        """Initialize a single child chain with hierarchy and K8s."""
        child = None
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
                    self.register_subchain(child_id, child)

        # Create K8s namespace if manager available
        k8s_manager = self._k8s_manager
        if k8s_manager is not None:
            from typing import cast
            cast(Any, k8s_manager).create_namespace(child_id)

        return child

    def _migrate_state(self, parent: Any, children: list[Any]) -> tuple[int, int]:
        """
        Migrate state from parent to child chains.

        Args:
            parent: Parent sub-chain.
            children: List of child sub-chains.

        Returns:
            Tuple of (events_migrated, blocks_migrated).
        """
        return _migrate_state_for_rebalancer(self, parent, children)

    def _select_target_child(self, event: Any, num_children: int) -> int:
        """Select target child for event based on strategy."""
        return _select_target_child_for_rebalancer(self, event, num_children)

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
        on_threshold: Callable[[str, RebalanceMetrics], bool] | None = None,
        on_split: Callable[[SplitResult], None] | None = None,
    ) -> None:
        """Set callback functions."""
        self._on_threshold_exceeded = on_threshold
        self._on_split_complete = on_split
