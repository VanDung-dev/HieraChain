"""
Two-phase-commit (2PC) transaction manager for HieraChain Ledger.
"""

import time
from typing import Any


class TransactionManager:
    """Manages two-phase-commit (2PC) transaction lifecycle."""

    def __init__(self):
        self._pending: dict[str, dict[str, Any]] = {}

    @property
    def pending_transactions(self) -> dict[str, dict[str, Any]]:
        """Read-only access to pending transactions."""
        return self._pending

    def is_prepared(self, transaction_id: str) -> bool:
        return transaction_id in self._pending

    def store_pending(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool,
    ):
        """Store a prepared transaction."""
        self._pending[transaction_id] = {
            "payload": payload,
            "is_source": is_source,
            "timestamp": time.time(),
        }

    def pop_pending(self, transaction_id: str) -> dict[str, Any] | None:
        """Remove and return the pending transaction data."""
        return self._pending.pop(transaction_id, None)

    def rollback(self, transaction_id: str) -> bool:
        """Rollback (discard) a pending transaction."""
        if transaction_id in self._pending:
            del self._pending[transaction_id]
            return True
        return False
