"""System-wide reporting and maintenance behavior for :class:`HierarchyManager`."""

import logging
import os
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any

from hierachain.hierarchical.hierarchy_manager.contracts import HierarchyHost
from hierachain.hierarchical.hierarchy_manager.organization import _trace_entity_history
from hierachain.hierarchical.hierarchy_manager.validation import (
    _compute_proof_consistency,
    _compute_system_integrity_report,
    _validate_cross_chain_consistency,
)

logger = logging.getLogger(__name__)

_SHARED_POOL = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


@contextmanager
def _shared_pool(max_workers: int | None = None) -> Iterator[ThreadPoolExecutor]:
    if max_workers and max_workers != getattr(_SHARED_POOL, "_max_workers", None):
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            yield pool
    else:
        yield _SHARED_POOL


class SystemOperationsMixin(HierarchyHost):
    """Aggregation, proof batching and maintenance operations."""

    def get_system_overview(self) -> dict[str, Any]:
        total_tx = 0
        total_blocks = len(self.main_chain.chain)
        domain_distribution: dict[str, int] = {}

        for chain in self.sub_chains.values():
            stats = chain.get_domain_statistics()
            total_tx += stats.get("total_operations", 0) + stats.get("total_events", 0)
            total_blocks += stats.get("total_blocks", 0)
            d_type = chain.domain_type
            domain_distribution[d_type] = domain_distribution.get(d_type, 0) + 1

        return {
            "uptime_seconds": time.time() - self.system_started_at,
            "total_chains": len(self.sub_chains),
            "main_chain_blocks": len(self.main_chain.chain),
            "total_system_blocks": total_blocks,
            "total_system_transactions": total_tx,
            "domain_distribution": domain_distribution,
        }

    def trace_entity_across_chains(
        self, entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        return _trace_entity_history(self.sub_chains, entity_id)

    def get_system_integrity_report(self) -> dict[str, Any]:
        return _compute_system_integrity_report(self)

    def submit_all_proofs(self) -> dict[str, bool]:
        names = list(self.sub_chains.keys())
        results: dict[str, bool] = {}

        with _shared_pool(max_workers=min(len(names), 8)) as pool:
            futures = {
                pool.submit(self.submit_proof_to_main_chain, name): name
                for name in names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error("Proof submission failed for %s: %s", name, e)
                    results[name] = False

        return results

    def sync_all_subchains_from_mainchain(self) -> dict[str, dict[str, Any]]:
        names = list(self.sub_chains.keys())
        results: dict[str, dict[str, Any]] = {}

        with _shared_pool(max_workers=min(len(names), 8)) as pool:
            futures = {
                pool.submit(self.cross_level_sync_subchain, name): name
                for name in names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error("Sync failed for %s: %s", name, e)
                    results[name] = {"success": False, "error_message": str(e)}

        return results

    def cross_level_sync_subchain(
        self, sub_chain_name: str, from_block: int = 0, to_block: int = -1
    ) -> dict[str, Any]:
        if not self.cross_level_sync:
            return {"success": False, "error_message": "Cross-level sync not enabled"}

        result = self.cross_level_sync.sync_from_mainchain(
            sub_chain_name, from_block, to_block
        )
        return result.to_dict()

    def finalize_main_chain_block(self) -> Any | None:
        if hasattr(self.main_chain, "finalize_block"):
            return self.main_chain.finalize_block()
        return None

    def get_cross_chain_statistics(self) -> dict[str, Any]:
        total_entities = 0
        domain_dist = {}
        for chain in self.sub_chains.values():
            if hasattr(chain, "entity_registry"):
                total_entities += len(chain.entity_registry)
                domain_dist[chain.domain_type] = len(chain.entity_registry)

        return {
            "total_unique_entities": total_entities,
            "cross_chain_operations": 0,
            "total_proofs_submitted": self.main_chain.proof_count,
            "domain_distribution": domain_dist,
        }

    def configure_auto_proof_submission(
        self, enabled: bool, interval: float = 60.0
    ) -> None:
        self.auto_proof_submission = enabled
        self.proof_submission_interval = int(interval)

        for sub_chain in self.sub_chains.values():
            sub_chain.auto_proof_submission = enabled
            sub_chain.proof_submission_interval = interval

    def execute_system_maintenance(self) -> dict[str, Any]:
        maintenance_results: dict[str, Any] = {
            "timestamp": time.time(), "operations": []
        }
        operations: list[dict[str, Any]] = maintenance_results["operations"]

        proof_results = self.submit_all_proofs()
        operations.append({"operation": "proof_submission", "results": proof_results})

        main_chain_result = self.finalize_main_chain_block()
        if main_chain_result:
            operations.append(
                {"operation": "main_chain_finalization", "result": main_chain_result}
            )

        self.system_stats["system_uptime"] = time.time() - self.system_started_at

        return maintenance_results

    def validate_cross_chain_consistency(self) -> dict[str, Any]:
        return _validate_cross_chain_consistency(self)

    def _check_proof_consistency(self) -> dict[str, Any]:
        return _compute_proof_consistency(self.main_chain, self.sub_chains)
