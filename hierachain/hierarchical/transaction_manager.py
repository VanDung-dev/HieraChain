"""
Cross-Chain Transaction Manager (2PC) for HieraChain.

This module implements the Two-Phase Commit (2PC) protocol to ensure atomic
transactions across multiple chains in the HieraChain system.
"""

import uuid
import time
import logging
from typing import Any

from hierachain.hierarchical.types import CrossChainTransaction, TransactionState

# Backward-compat re-exports
CrossChainTransaction = CrossChainTransaction
TransactionState = TransactionState

logger = logging.getLogger(__name__)


def _rollback(
    transaction: CrossChainTransaction, source_chain: Any, dest_chain: Any
) -> None:
    """Rollback the transaction on both chains."""
    transaction.state = TransactionState.ROLLED_BACK
    transaction.updated_at = time.time()

    if source_chain:
        source_chain.rollback_transaction(transaction.transaction_id)

    if dest_chain:
        dest_chain.rollback_transaction(transaction.transaction_id)


def _run_prepare_phase(
    transaction: CrossChainTransaction, source_chain: Any, dest_chain: Any
) -> bool:
    """Execute Phase 1: Prepare."""
    tx_id = transaction.transaction_id
    try:
        # Ask Source to prepare (lock resources)
        if not source_chain.prepare_transaction(
            tx_id, transaction.payload, is_source=True
        ):
            raise Exception(
                "Source chain %s failed to prepare" % transaction.source_chain
            )

        # Ask Destination to prepare (verify it can accept)
        if not dest_chain.prepare_transaction(
            tx_id, transaction.payload, is_source=False
        ):
            raise Exception(
                "Destination chain %s failed to prepare"
                % transaction.destination_chain
            )

        transaction.state = TransactionState.PREPARED
        transaction.updated_at = time.time()
        return True

    except Exception as e:
        logger.error("2PC Prepare Phase Failed: %s", e)
        transaction.error_message = str(e)
        _rollback(transaction, source_chain, dest_chain)
        return False


def _run_commit_phase(
    transaction: CrossChainTransaction, source_chain: Any, dest_chain: Any
) -> bool:
    """Execute Phase 2: Commit."""
    tx_id = transaction.transaction_id
    try:
        # Commit Source
        if not source_chain.commit_transaction(tx_id):
            raise Exception(
                "Source chain %s failed to commit" % transaction.source_chain
            )

        # Commit Destination
        if not dest_chain.commit_transaction(tx_id):
            raise Exception(
                "Destination chain %s failed to commit after source committed"
                % transaction.destination_chain
            )

        transaction.state = TransactionState.COMMITTED
        transaction.updated_at = time.time()
        return True

    except Exception as e:
        logger.error("2PC Commit Phase Failed: %s", e)
        transaction.error_message = str(e)
        transaction.state = TransactionState.FAILED
        transaction.updated_at = time.time()
        # Rollback source chain since destination commit failed after source was committed
        if source_chain and hasattr(source_chain, 'rollback_transaction'):
            try:
                source_chain.rollback_transaction(tx_id)
                logger.warning(
                    "Rolled back source %s after destination %s commit failure",
                    transaction.source_chain, transaction.destination_chain
                )
            except Exception as rb_e:
                logger.error(
                    "Failed to rollback source %s after commit failure: %s",
                    transaction.source_chain, rb_e
                )
        return False


class CrossChainTransactionManager:
    """
    Manages the lifecycle of cross-chain transactions using 2PC.
    """

    def __init__(self, hierarchy_manager: Any) -> None:
        """
        Initialize the Transaction Manager.

        Args:
            hierarchy_manager: Reference to the HierarchyManager to access chains.
        """
        self.hierarchy_manager = hierarchy_manager
        self.transactions: dict[str, CrossChainTransaction] = {}

    def initiate_transaction(
        self, source_chain_name: str, dest_chain_name: str, payload: dict[str, Any]
    ) -> str:
        """
        Start a new cross-chain transaction.

        Args:
            source_chain_name: Name of the source chain.
            dest_chain_name: Name of the destination chain.
            payload: Data describing the transaction (e.g., asset transfer details).

        Returns:
            Transaction ID.
        """
        tx_id = uuid.uuid4().hex
        transaction = CrossChainTransaction(
            transaction_id=tx_id,
            source_chain=source_chain_name,
            destination_chain=dest_chain_name,
            payload=payload
        )
        self.transactions[tx_id] = transaction

        # Start the 2PC process
        self._execute_2pc(transaction)

        return tx_id

    def get_transaction(self, tx_id: str) -> CrossChainTransaction | None:
        """Get transaction details."""
        return self.transactions.get(tx_id)

    def _execute_2pc(self, transaction: CrossChainTransaction) -> bool:
        """
        Execute the Two-Phase Commit protocol.
        """
        source_chain = self.hierarchy_manager.get_sub_chain(transaction.source_chain)
        dest_chain = self.hierarchy_manager.get_sub_chain(transaction.destination_chain)

        if not source_chain or not dest_chain:
            transaction.state = TransactionState.FAILED
            transaction.error_message = "Source or Destination chain not found"
            transaction.updated_at = time.time()
            return False

        # Phase 1: Prepare
        if not _run_prepare_phase(transaction, source_chain, dest_chain):
            return False

        # Phase 2: Commit
        return _run_commit_phase(transaction, source_chain, dest_chain)
