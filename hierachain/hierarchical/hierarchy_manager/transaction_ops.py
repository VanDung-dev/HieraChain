"""Transaction coordination behavior for :class:`HierarchyManager`."""

import logging
from typing import Any

from hierachain.hierarchical.hierarchy_manager.contracts import HierarchyHost

logger = logging.getLogger(__name__)


class TransactionCoordinationMixin(HierarchyHost):
    """Lifecycle plumbing for the single cross-chain coordinator writer."""

    def initiate_cross_chain_transaction(
        self, source_chain_name: str, dest_chain_name: str, payload: dict[str, Any],
    ) -> str | None:
        return self.transaction_manager.initiate_transaction(
            source_chain_name, dest_chain_name, payload
        )

    def start_operation(
        self,
        sub_chain_name: str,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any] | None = None
    ) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False
        return chain.start_domain_operation(entity_id, operation_type, details)

    def complete_operation(
        self,
        sub_chain_name: str,
        entity_id: str,
        operation_type: str,
        result: dict[str, Any] | None = None
    ) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False
        return chain.complete_operation(entity_id, operation_type, result)

    def submit_proof_to_main_chain(self, sub_chain_name: str) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False

        if self.cross_level_sync:
            sync_result = self.cross_level_sync.sync_to_mainchain(
                sub_chain_name
            )
            if not sync_result.success:
                logger.warning(
                    "Cross-level sync to MainChain failed: %s",
                    sync_result.error_message,
                )
                return False
            return True

        return chain.submit_proof_to_main(self.main_chain) is True
