"""
SubChainRebalancer — manages dynamic sub-chain rebalancing through automatic splitting.
"""

import logging
import threading
import time
from typing import Any, Callable

from hierachain.hierarchical.rebalancer.types import (
    RebalanceMetrics,
    RebalanceStatus,
    SplitResult,
    SplitStrategy,
)
from hierachain.hierarchical.rebalancer.metrics import (
    _update_rebalance_metrics_for_subchain,
    _should_split_for_rebalancer,
)
from hierachain.hierarchical.rebalancer.split_ops import (
    _migrate_state_for_rebalancer,
    _select_target_child_for_rebalancer,
    _split_sub_chain_for_rebalancer,
)

logger = logging.getLogger(__name__)


class SubChainRebalancer:
    def __init__(
        self,
        threshold_eps: int = 1000,
        check_interval: float = 60.0,
        min_events_for_split: int = 5000,
        cooldown_seconds: float = 300.0,
        split_strategy: SplitStrategy = SplitStrategy.HASH_BASED,
        k8s_namespace_manager: Any = None,
    ):
        self.threshold_eps = threshold_eps
        self.check_interval = check_interval
        self.min_events_for_split = min_events_for_split
        self.cooldown_seconds = cooldown_seconds
        self.split_strategy = split_strategy
        self._k8s_manager = k8s_namespace_manager
        self._rr_counter = 0

        self._status = RebalanceStatus.IDLE
        self._monitored_chains: dict[str, RebalanceMetrics] = {}
        self._event_counts: dict[str, list[tuple[float, int]]] = {}
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()

        self._subchains: dict[str, Any] = {}
        self._hierarchy_manager: Any = None

        self._on_threshold_exceeded: Callable[
            [str, RebalanceMetrics], bool
        ] | None = None
        self._on_split_complete: Callable[[SplitResult], None] | None = None

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
        self._subchains[sub_chain_id] = subchain
        self._monitored_chains[sub_chain_id] = RebalanceMetrics(
            sub_chain_id=sub_chain_id
        )
        self._event_counts[sub_chain_id] = []
        logger.info(f"Registered sub-chain for monitoring: {sub_chain_id}")

    def unregister_subchain(self, sub_chain_id: str) -> None:
        self._subchains.pop(sub_chain_id, None)
        self._monitored_chains.pop(sub_chain_id, None)
        self._event_counts.pop(sub_chain_id, None)
        logger.info("Unregistered sub-chain: %s", sub_chain_id)

    def set_hierarchy_manager(self, manager: Any) -> None:
        self._hierarchy_manager = manager

    def start_monitoring(self) -> None:
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
        self._stop_monitoring.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        self._status = RebalanceStatus.IDLE
        logger.info("Stopped rebalancer monitoring")

    def _monitoring_loop(self) -> None:
        while not self._stop_monitoring.is_set():
            try:
                self._check_all_thresholds()
            except Exception as e:
                logger.error("Monitoring loop error: %s", e)

            self._stop_monitoring.wait(timeout=self.check_interval)

    def _check_all_thresholds(self) -> None:
        self._stats["checks_total"] += 1

        for sub_chain_id, subchain in list(self._subchains.items()):
            self._process_single_chain_rebalance(sub_chain_id, subchain)

    def _process_single_chain_rebalance(self, sub_chain_id: str, subchain: Any) -> None:
        metrics = self._collect_metrics(sub_chain_id, subchain)
        self._monitored_chains[sub_chain_id] = metrics

        if self._should_split(metrics):
            self._handle_threshold_exceedance(sub_chain_id, subchain, metrics)

    def _handle_threshold_exceedance(
        self, sub_chain_id: str, subchain: Any, metrics: RebalanceMetrics
    ) -> None:
        self._stats["thresholds_exceeded"] += 1
        self._status = RebalanceStatus.THRESHOLD_EXCEEDED

        if self._is_split_authorized(sub_chain_id, metrics):
            self._execute_split_operation(subchain, metrics)

    def _is_split_authorized(
        self, sub_chain_id: str, metrics: RebalanceMetrics
    ) -> bool:
        if self._on_threshold_exceeded:
            return self._on_threshold_exceeded(sub_chain_id, metrics)
        return True

    def _execute_split_operation(
        self, subchain: Any, metrics: RebalanceMetrics
    ) -> None:
        result = self.split_sub_chain(subchain)
        if result.success:
            metrics.last_split_time = time.time()
            metrics.splits_total += 1

    def _collect_metrics(self, sub_chain_id: str, subchain: Any) -> RebalanceMetrics:
        metrics = self._monitored_chains.get(
            sub_chain_id, RebalanceMetrics(sub_chain_id=sub_chain_id)
        )
        return _update_rebalance_metrics_for_subchain(
            metrics, sub_chain_id, subchain, self._event_counts
        )

    def _should_split(self, metrics: RebalanceMetrics) -> bool:
        return _should_split_for_rebalancer(
            metrics, self.threshold_eps,
            self.min_events_for_split, self.cooldown_seconds
        )

    def check_threshold(self, sub_chain_id: str) -> bool:
        if sub_chain_id not in self._subchains:
            return False

        subchain = self._subchains[sub_chain_id]
        metrics = self._collect_metrics(sub_chain_id, subchain)
        return self._should_split(metrics)

    def split_sub_chain(self, sub_chain: Any) -> SplitResult:
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
        children = []
        for child_id in child_ids:
            child = self._initialize_single_child_chain(parent_id, child_id)
            if child:
                children.append(child)
        return children

    def _initialize_single_child_chain(self, parent_id: str, child_id: str) -> Any:
        child = None
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

        k8s_manager = self._k8s_manager
        if k8s_manager is not None:
            from typing import cast
            cast(Any, k8s_manager).create_namespace(child_id)

        return child

    def _migrate_state(self, parent: Any, children: list[Any]) -> tuple[int, int]:
        return _migrate_state_for_rebalancer(self, parent, children)

    def _select_target_child(self, event: Any, num_children: int) -> int:
        if num_children <= 0:
            return 0
        return _select_target_child_for_rebalancer(self, event, num_children)

    def get_metrics(self, sub_chain_id: str) -> RebalanceMetrics | None:
        return self._monitored_chains.get(sub_chain_id)

    def get_all_metrics(self) -> dict[str, RebalanceMetrics]:
        return self._monitored_chains.copy()

    def get_status(self) -> RebalanceStatus:
        return self._status

    def get_stats(self) -> dict[str, Any]:
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
        self._on_threshold_exceeded = on_threshold
        self._on_split_complete = on_split
