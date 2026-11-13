"""Two-phase-commit participant behavior for :class:`DomainChain`.

Kept as a mixin so the public ``DomainChain`` API is unchanged while the
transaction lifecycle code lives in its own module.
"""

import copy
import logging
import threading
from typing import Any

from hierachain.domains.chains.base_chain import BaseChain
from hierachain.domains.chains.tx_manager import TransactionManager

logger = logging.getLogger(__name__)


class TransactionOperationsMixin(BaseChain):
    """Prepare/commit/rollback handling for cross-chain 2PC participants."""

    _tx_manager: TransactionManager
    _tx_commit_lock: threading.RLock

    def prepare_transaction(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool = True
    ) -> bool:
        """Prepare once under the participant commit lock."""
        with self._tx_commit_lock:
            return self._prepare_transaction_locked(
                transaction_id, payload, is_source
            )

    def _prepare_transaction_locked(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool,
    ) -> bool:
        """
        Phase 1: Prepare for a cross-chain transaction.

        Args:
            transaction_id: Unique transaction identifier.
            payload: Transaction details.
            is_source: True if this is the source chain.

        Returns:
            True if prepared successfully.
        """
        if transaction_id in self._tx_manager.committed_transactions:
            return True

        try:
            payload_snapshot = copy.deepcopy(payload)
        except (copy.Error, RecursionError, TypeError):
            return False
        if not isinstance(payload_snapshot, dict):
            return False

        if self._tx_manager.is_prepared(transaction_id):
            pending = self._tx_manager.pending_transactions.get(transaction_id)
            return (
                pending is not None
                and pending.get("payload") == payload_snapshot
                and pending.get("is_source") is is_source
            )

        entity_id = payload_snapshot.get("entity_id")
        if not isinstance(entity_id, str):
            return False

        operation_type = payload_snapshot.get("operation_type")
        if not isinstance(operation_type, str):
            return False

        details = payload_snapshot.get("details", {})

        if not self._validate_transaction_payload(entity_id, operation_type, details):
            return False

        return self._tx_manager.store_pending(
            transaction_id, payload_snapshot, is_source
        )

    def recover_committed_transaction(
        self,
        transaction_id: str,
        payload: dict[str, Any],
        is_source: bool = True,
    ) -> bool:
        """Restore participant input after the coordinator's durable COMMIT decision."""
        with self._tx_commit_lock:
            if transaction_id in self._tx_manager.committed_transactions:
                return True

            try:
                payload_snapshot = copy.deepcopy(payload)
            except (copy.Error, RecursionError, TypeError):
                return False
            if not isinstance(payload_snapshot, dict):
                return False

            pending = self._tx_manager.pending_transactions.get(transaction_id)
            if pending is not None:
                if (
                    pending.get("payload") != payload_snapshot
                    or pending.get("is_source") is not is_source
                ):
                    return False
                return self._tx_manager.mark_recovery_commit(transaction_id)

            if not self._load_transaction_event_markers():
                return False

            entity_id = payload_snapshot.get("entity_id")
            operation_type = payload_snapshot.get("operation_type")
            details = payload_snapshot.get("details", {})
            if (
                not isinstance(entity_id, str)
                or not isinstance(operation_type, str)
                or not isinstance(details, dict)
            ):
                return False

            markers = self._transaction_event_markers
            if markers is None:
                return False
            if all(
                (transaction_id, step) in markers
                for step in ("start", "complete")
            ):
                if not self._reconcile_transaction_events(transaction_id):
                    self._transaction_event_markers = None
                    return False
                self._tx_manager.mark_committed(transaction_id)
                return True

            self._tx_manager.store_pending(
                transaction_id,
                payload_snapshot,
                is_source,
                recovery_commit=True,
            )
            return True

    def _validate_transaction_payload(
        self,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any],
    ) -> bool:
        """Validate domain rules and operation data for a 2PC prepare."""
        validation_op = f"prepare_{operation_type}"
        if not self.validate_domain_rules(entity_id, validation_op):
            return False
        return self.validate_domain_operation(entity_id, operation_type, details)

    def commit_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2: Commit the transaction.

        Args:
            transaction_id: Transaction ID to commit.

        Returns:
            True if committed successfully.
        """
        with self._tx_commit_lock:
            if transaction_id in self._tx_manager.committed_transactions:
                return True

            pending_data = self._tx_manager.pending_transactions.get(transaction_id)
            if pending_data is None:
                if not self._load_transaction_event_markers():
                    return False
                markers = self._transaction_event_markers
                if markers is None:
                    return False
                if all(
                    (transaction_id, step) in markers
                    for step in ("start", "complete")
                ):
                    if not self._reconcile_transaction_events(transaction_id):
                        self._transaction_event_markers = None
                        return False
                    self._tx_manager.mark_committed(transaction_id)
                    return True
                return False

            if not self._execute_commit(transaction_id, pending_data):
                return False

            # An ordering ACK is only a commit ACK once both events can be
            # read back from the durable journal after the write.
            if not callable(getattr(self.ordering_service.journal, "read_since", None)):
                self._transaction_event_markers = None
            if not self._load_transaction_event_markers():
                return False
            markers = self._transaction_event_markers
            if markers is None or not all(
                isinstance(markers.get((transaction_id, step)), dict)
                for step in ("start", "complete")
            ):
                self._transaction_event_markers = None
                return False
            if not self._reconcile_transaction_events(transaction_id):
                self._transaction_event_markers = None
                return False

            self._tx_manager.pop_pending(transaction_id)
            self._tx_manager.mark_committed(transaction_id)
            return True

    def _load_transaction_event_markers(self) -> bool:
        """Load durable 2PC event markers once so participant retries are idempotent."""
        journal = getattr(getattr(self, "ordering_service", None), "journal", None)
        replay = getattr(journal, "replay", None)
        if not callable(replay):
            return False

        read_since = getattr(journal, "read_since", None)
        if self._transaction_event_markers is not None and not callable(read_since):
            return True
        markers: dict[tuple[str, str], dict[str, Any] | None] = self._transaction_event_markers or {}
        try:
            if callable(read_since):
                cursor = (
                    getattr(self, "_transaction_journal_cursor", None)
                    if self._transaction_event_markers is not None else None
                )
                events, cursor = read_since(cursor)
            else:
                events, cursor = replay(), None
            for event in events:
                if not isinstance(event, dict):
                    continue
                tx_id = event.get("transaction_id")
                step = event.get("transaction_step")
                if isinstance(tx_id, str) and step in {"start", "complete"}:
                    markers[(tx_id, step)] = event
        except (OSError, RuntimeError, TypeError, ValueError):
            logger.exception("Could not read transaction markers from %s journal", self.name)
            return False

        self._transaction_event_markers = markers
        self._transaction_journal_cursor = cursor
        return True

    def _reconcile_transaction_events(self, transaction_id: str) -> bool:
        """Ensure durable transaction events are represented in live ordering state."""
        markers = self._transaction_event_markers
        if markers is None:
            return False

        for step in ("start", "complete"):
            event = markers.get((transaction_id, step))
            if event is not None and not self._reconcile_journal_event(event):
                return False
        return True

    def _reconcile_journal_event(self, event: dict[str, Any]) -> bool:
        reconcile = getattr(
            getattr(self, "ordering_service", None),
            "reconcile_journal_event",
            None,
        )
        if not callable(reconcile):
            return False
        try:
            return reconcile(event) == event.get("event_id")
        except Exception:
            logger.exception(
                "Could not reconcile transaction event on %s", self.name
            )
            return False

    def _execute_commit(
        self, transaction_id: str, pending_data: dict[str, Any]
    ) -> bool:
        """Execute the on-chain operations for a 2PC commit."""
        if not self._load_transaction_event_markers():
            return False

        payload = pending_data["payload"]
        entity_id = payload.get("entity_id")
        operation_type = payload.get("operation_type")
        details = payload.get("details", {})

        try:
            markers = self._transaction_event_markers
            assert markers is not None
            recovery_commit = pending_data.get("recovery_commit", False)

            start_key = (transaction_id, "start")
            if start_key in markers:
                start_event = markers[start_key]
                if start_event is not None and not self._reconcile_journal_event(start_event):
                    self._transaction_event_markers = None
                    return False
            else:
                if recovery_commit:
                    success = self.start_operation(
                        entity_id,
                        operation_type,
                        details,
                        transaction_id=transaction_id,
                    )
                else:
                    success = self.start_domain_operation(
                        entity_id,
                        operation_type,
                        details,
                        transaction_id=transaction_id,
                    )
                if not success:
                    self._transaction_event_markers = None
                    return False
                markers[start_key] = None

            complete_key = (transaction_id, "complete")
            if complete_key in markers:
                event = markers[complete_key]
                if event is not None and not self._reconcile_journal_event(event):
                    self._transaction_event_markers = None
                    return False
            else:
                if recovery_commit:
                    success = self.complete_operation(
                        entity_id,
                        operation_type,
                        {"status": "committed", "tx_id": transaction_id},
                        transaction_id=transaction_id,
                    )
                else:
                    success = self.complete_domain_operation(
                        entity_id,
                        operation_type,
                        {"status": "committed", "tx_id": transaction_id},
                        transaction_id=transaction_id,
                    )
                if not success:
                    self._transaction_event_markers = None
                    return False
                markers[complete_key] = None
            return True
        except Exception:
            self._transaction_event_markers = None
            logger.exception(
                "Could not submit transaction %s events to %s",
                transaction_id,
                self.name,
            )
            return False

    def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Phase 2 (Alternative): Rollback the transaction.

        Args:
            transaction_id: Transaction ID to rollback.

        Returns:
            True if rolled back successfully.
        """
        with self._tx_commit_lock:
            if transaction_id in self._tx_manager.committed_transactions:
                return False
            return self._tx_manager.rollback(transaction_id)
