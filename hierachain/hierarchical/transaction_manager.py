"""
Cross-Chain Transaction Manager (2PC) for HieraChain.

This module implements the Two-Phase Commit (2PC) protocol to ensure atomic
transactions across multiple chains in the HieraChain system.
"""

import uuid
import time
import logging
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TransactionState(str, Enum):
    """States for a cross-chain transaction."""

    PENDING = "pending"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class CrossChainTransaction:
    """Represents a cross-chain transaction."""

    transaction_id: str
    source_chain: str
    destination_chain: str
    payload: dict[str, Any]
    state: TransactionState = TransactionState.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None


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

    def initiate_transaction(self, source_chain_name: str, dest_chain_name: str, payload: dict[str, Any]) -> str:
        """
        Start a new cross-chain transaction.

        Args:
            source_chain_name: Name of the source chain.
            dest_chain_name: Name of the destination chain.
            payload: Data describing the transaction (e.g., asset transfer details).

        Returns:
            Transaction ID.
        """
        tx_id = str(uuid.uuid4())
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

    def get_transaction(self, tx_id: str) -> Optional[CrossChainTransaction]:
        """Get transaction details."""
        return self.transactions.get(tx_id)

    def _execute_2pc(self, transaction: CrossChainTransaction) -> bool:
        """
        Execute the Two-Phase Commit protocol.

        Phase 1: Prepare
        Phase 2: Commit or Rollback
        """
        tx_id = transaction.transaction_id
        source_chain = self.hierarchy_manager.get_sub_chain(transaction.source_chain)
        dest_chain = self.hierarchy_manager.get_sub_chain(transaction.destination_chain)

        if not source_chain or not dest_chain:
            transaction.state = TransactionState.FAILED
            transaction.error_message = "Source or Destination chain not found"
            transaction.updated_at = time.time()
            return False

        # --- PHASE 1: PREPARE ---
        try:
            # Ask Source to prepare (lock resources)
            source_prepared = source_chain.prepare_transaction(tx_id, transaction.payload, is_source=True)
            if not source_prepared:
                raise Exception(f"Source chain {transaction.source_chain} failed to prepare")

            # Ask Destination to prepare (verify it can accept)
            dest_prepared = dest_chain.prepare_transaction(tx_id, transaction.payload, is_source=False)
            if not dest_prepared:
                # If dest fails, we must rollback source
                raise Exception(f"Destination chain {transaction.destination_chain} failed to prepare")

            transaction.state = TransactionState.PREPARED
            transaction.updated_at = time.time()

        except Exception as e:
            # If Phase 1 fails, we rollback
            logger.error(f"2PC Prepare Phase Failed: {e}")
            transaction.error_message = str(e)
            self._rollback(transaction, source_chain, dest_chain)
            return False

        # --- PHASE 2: COMMIT ---
        try:
            # Commit Source
            source_committed = source_chain.commit_transaction(tx_id)
            if not source_committed:
                raise Exception(f"Source chain {transaction.source_chain} failed to commit")

            # Commit Destination
            dest_committed = dest_chain.commit_transaction(tx_id)
            if not dest_committed:
                raise Exception(f"Destination chain {transaction.destination_chain} failed to commit after source committed")

            transaction.state = TransactionState.COMMITTED
            transaction.updated_at = time.time()
            return True

        except Exception as e:
            logger.error(f"2PC Commit Phase Failed: {e}")
            transaction.error_message = str(e)
            transaction.state = TransactionState.FAILED
            transaction.updated_at = time.time()
            return False

    def _rollback(self, transaction: CrossChainTransaction, source_chain: Any, dest_chain: Any) -> None:
        """Rollback the transaction on both chains."""
        transaction.state = TransactionState.ROLLED_BACK
        transaction.updated_at = time.time()

        if source_chain:
            source_chain.rollback_transaction(transaction.transaction_id)

        if dest_chain:
            dest_chain.rollback_transaction(transaction.transaction_id)
