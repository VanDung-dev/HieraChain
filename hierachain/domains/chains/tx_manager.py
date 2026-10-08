"""
Two-phase-commit (2PC) transaction manager for HieraChain Ledger.
"""

import copy
import time
from typing import Any


class TransactionManager:
    """Manages two-phase-commit (2PC) transaction lifecycle."""

    def __init__(self):
        self._pending: dict[str, dict[str, Any]] = {}
        self._committed: set[str] = set()

    @property
    def pending_transactions(self) -> dict[str, dict[str, Any]]:
        """Return a detached snapshot of pending transactions."""
        return copy.deepcopy(self._pending)

    @property
    def committed_transactions(self) -> set[str]:
        """Transaction IDs committed by this participant in the current process."""
        return self._committed

    def mark_committed(self, transaction_id: str) -> None:
        """Remember a successful commit so repeated acknowledgments are idempotent."""
        self._committed.add(transaction_id)

    def is_prepared(self, transaction_id: str) -> bool:
        return transaction_id in self._pending

    def store_pending(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool,
        recovery_commit: bool = False,
    ) -> bool:
        """Store an isolated snapshot of a prepared transaction."""
        try:
            payload_snapshot = copy.deepcopy(payload)
        except Exception:
            return False
        self._pending[transaction_id] = {
            "payload": payload_snapshot,
            "is_source": is_source,
            "recovery_commit": recovery_commit,
            "timestamp": time.time(),
        }
        return True

    def mark_recovery_commit(self, transaction_id: str) -> bool:
        """Mark a stored prepare for recovery after a durable COMMIT decision."""
        pending = self._pending.get(transaction_id)
        if pending is None:
            return False
        pending["recovery_commit"] = True
        return True

    def pop_pending(self, transaction_id: str) -> dict[str, Any] | None:
        """Remove and return the pending transaction data."""
        return self._pending.pop(transaction_id, None)

    def rollback(self, transaction_id: str) -> bool:
        """Discard prepared state; an absent prepare is an idempotent no-op."""
        if transaction_id in self._committed:
            return False
        self._pending.pop(transaction_id, None)
        return True
