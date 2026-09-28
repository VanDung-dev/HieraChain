"""
Cross-chain transaction coordinator with a durable 2PC decision journal.

The coordinator's journal is separate from each OrderingService event journal:
its records must never be replayed as ledger events.
"""

import logging
import threading
import time
import uuid
from typing import Any

from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.hierarchical.types import CrossChainTransaction, TransactionState

# Backward-compat re-exports
CrossChainTransaction = CrossChainTransaction
TransactionState = TransactionState

logger = logging.getLogger(__name__)
_JOURNAL_EVENT = "cross_chain_2pc"
_UNRESOLVED_PHASES = {"begin", "prepared", "abort_pending", "commit", "commit_unknown"}
_COMMIT_PHASES = {"commit", "commit_unknown"}


def _supports_2pc(chain: Any) -> bool:
    """Return whether a chain can participate in the transaction protocol."""
    return all(
        callable(getattr(chain, method, None))
        for method in ("prepare_transaction", "commit_transaction", "rollback_transaction")
    )


class CrossChainTransactionManager:
    """Coordinates cross-chain transactions using durable forward recovery."""

    def __init__(self, hierarchy_manager: Any, journal: Any | None = None) -> None:
        self.hierarchy_manager = hierarchy_manager
        self.transactions: dict[str, CrossChainTransaction] = {}
        self._phases: dict[str, str] = {}
        self._journal_lock = threading.RLock()
        self.journal = journal or TransactionJournal(
            storage_dir="transactions",
            active_log_name="cross_chain_2pc.arrow",
        )
        self._load_journal()

    def _journal_record(self, transaction: CrossChainTransaction, phase: str) -> bool:
        record = {
            "entity_id": transaction.transaction_id,
            "event": _JOURNAL_EVENT,
            "timestamp": time.time(),
            "tx_id": transaction.transaction_id,
            "phase": phase,
            "source_chain": transaction.source_chain,
            "destination_chain": transaction.destination_chain,
            "payload": transaction.payload,
            "created_at": transaction.created_at,
            "updated_at": time.time(),
            "error_message": transaction.error_message,
        }
        with self._journal_lock:
            try:
                persisted = self.journal.log_event(record)
            except Exception:
                logger.exception("Could not persist 2PC phase %s for %s", phase, transaction.transaction_id)
                return False
            if persisted is not True:
                return False
            try:
                # ponytail: Full replay proves the ACK; use an indexed tail only if journal size warrants it.
                durable = self._read_latest_records().get(transaction.transaction_id)
            except Exception:
                logger.exception("Could not read back 2PC phase %s for %s", phase, transaction.transaction_id)
                return False
        if durable is None or any(
            durable.get(key) != record[key]
            for key in ("phase", "source_chain", "destination_chain", "payload")
        ):
            return False
        self._phases[transaction.transaction_id] = phase
        return True

    def _read_latest_records(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        with self._journal_lock:
            for record in self.journal.replay():
                if not isinstance(record, dict) or record.get("event") != _JOURNAL_EVENT:
                    continue
                tx_id = record.get("tx_id")
                phase = record.get("phase")
                if isinstance(tx_id, str) and isinstance(phase, str):
                    latest[tx_id] = record
        return latest

    def _load_journal(self) -> None:
        try:
            records = self._read_latest_records()
        except Exception as exc:
            raise RuntimeError("Could not recover the cross-chain transaction journal") from exc

        for tx_id, record in records.items():
            source = record.get("source_chain")
            destination = record.get("destination_chain")
            payload = record.get("payload")
            if not isinstance(source, str) or not isinstance(destination, str) or not isinstance(payload, dict):
                raise RuntimeError(f"Invalid durable 2PC record for transaction {tx_id}")

            phase = record["phase"]
            if phase == "committed":
                state = TransactionState.COMMITTED
            elif phase == "rolled_back":
                state = TransactionState.ROLLED_BACK
            elif phase == "failed":
                state = TransactionState.FAILED
            else:
                state = TransactionState.IN_DOUBT

            transaction = CrossChainTransaction(
                transaction_id=tx_id,
                source_chain=source,
                destination_chain=destination,
                payload=payload,
                state=state,
                created_at=record.get("created_at", record.get("timestamp", time.time())),
                updated_at=record.get("updated_at", record.get("timestamp", time.time())),
                error_message=record.get("error_message"),
            )
            self.transactions[tx_id] = transaction
            self._phases[tx_id] = phase

    def _get_participants(self, transaction: CrossChainTransaction) -> tuple[Any, Any] | None:
        source = self.hierarchy_manager.get_sub_chain(transaction.source_chain)
        destination = self.hierarchy_manager.get_sub_chain(transaction.destination_chain)
        if not _supports_2pc(source) or not _supports_2pc(destination):
            return None
        return source, destination

    def _set_state(self, transaction: CrossChainTransaction, state: TransactionState) -> None:
        transaction.state = state
        transaction.updated_at = time.time()

    def _abort_before_decision(
        self,
        transaction: CrossChainTransaction,
        source_chain: Any,
        dest_chain: Any,
    ) -> bool:
        tx_id = transaction.transaction_id
        self._set_state(transaction, TransactionState.IN_DOUBT)
        # This record is advisory; the durable absence of a COMMIT decision is
        # what makes abort the safe recovery action.
        self._journal_record(transaction, "abort_pending")

        failures: list[str] = []
        for chain_name, chain in (
            (transaction.source_chain, source_chain),
            (transaction.destination_chain, dest_chain),
        ):
            try:
                if chain.rollback_transaction(tx_id) is not True:
                    failures.append(f"{chain_name} did not acknowledge rollback")
            except Exception as exc:
                failures.append(f"{chain_name} rollback failed: {exc}")

        if failures:
            transaction.error_message = "; ".join(
                part for part in (transaction.error_message, *failures) if part
            )
            self._set_state(transaction, TransactionState.IN_DOUBT)
            self._journal_record(transaction, "abort_pending")
            return False

        self._set_state(transaction, TransactionState.ROLLED_BACK)
        if not self._journal_record(transaction, "rolled_back"):
            self._set_state(transaction, TransactionState.IN_DOUBT)
            return False
        return True

    def _prepare_participants(
        self,
        transaction: CrossChainTransaction,
        source_chain: Any,
        dest_chain: Any,
    ) -> bool:
        tx_id = transaction.transaction_id
        try:
            if source_chain.prepare_transaction(tx_id, transaction.payload, is_source=True) is not True:
                raise RuntimeError(f"Source chain {transaction.source_chain} failed to prepare")
            if dest_chain.prepare_transaction(tx_id, transaction.payload, is_source=False) is not True:
                raise RuntimeError(f"Destination chain {transaction.destination_chain} failed to prepare")
        except Exception as exc:
            logger.warning("2PC prepare failed for %s: %s", tx_id, exc)
            transaction.error_message = str(exc)
            self._abort_before_decision(transaction, source_chain, dest_chain)
            return False

        self._set_state(transaction, TransactionState.PREPARED)
        if not self._journal_record(transaction, "prepared"):
            transaction.error_message = "Could not persist prepared phase"
            self._abort_before_decision(transaction, source_chain, dest_chain)
            return False
        return True

    def _commit_forward(
        self,
        transaction: CrossChainTransaction,
        source_chain: Any,
        dest_chain: Any,
        *,
        restore_committed_state: bool = False,
    ) -> bool:
        tx_id = transaction.transaction_id
        if restore_committed_state:
            try:
                for chain_name, chain, is_source in (
                    (transaction.source_chain, source_chain, True),
                    (transaction.destination_chain, dest_chain, False),
                ):
                    recover = getattr(chain, "recover_committed_transaction", None)
                    if not callable(recover):
                        raise RuntimeError(
                            f"{chain_name} does not support committed-transaction recovery"
                        )
                    if recover(tx_id, transaction.payload, is_source=is_source) is not True:
                        raise RuntimeError(
                            f"{chain_name} could not restore committed transaction state"
                        )
            except Exception as exc:
                transaction.error_message = f"Forward recovery is waiting for prepared participants: {exc}"
                self._set_state(transaction, TransactionState.IN_DOUBT)
                logger.warning("2PC forward recovery is waiting for %s: %s", tx_id, exc)
                return False

        failures: list[str] = []
        for chain_name, chain in (
            (transaction.source_chain, source_chain),
            (transaction.destination_chain, dest_chain),
        ):
            try:
                if chain.commit_transaction(tx_id) is not True:
                    failures.append(f"{chain_name} did not acknowledge commit")
            except Exception as exc:
                failures.append(f"{chain_name} commit failed: {exc}")

        if failures:
            transaction.error_message = "; ".join(failures)
            self._set_state(transaction, TransactionState.IN_DOUBT)
            logger.error("2PC commit decision %s remains in doubt: %s", tx_id, transaction.error_message)
            return False

        self._set_state(transaction, TransactionState.COMMITTED)
        if not self._journal_record(transaction, "committed"):
            transaction.error_message = "Both participants committed, but the terminal acknowledgment was not persisted"
            self._set_state(transaction, TransactionState.IN_DOUBT)
            return False
        return True

    def _execute_2pc(self, transaction: CrossChainTransaction) -> bool:
        source_chain = self.hierarchy_manager.get_sub_chain(transaction.source_chain)
        dest_chain = self.hierarchy_manager.get_sub_chain(transaction.destination_chain)
        if not _supports_2pc(source_chain) or not _supports_2pc(dest_chain):
            transaction.error_message = "Source or destination is not a registered 2PC participant"
            self._set_state(transaction, TransactionState.FAILED)
            return False

        if not self._journal_record(transaction, "begin"):
            transaction.error_message = "Could not persist transaction before prepare"
            self._set_state(transaction, TransactionState.FAILED)
            return False

        if not self._prepare_participants(transaction, source_chain, dest_chain):
            return False

        # The fsynced decision is the point after which rollback is forbidden.
        if not self._journal_record(transaction, "commit"):
            transaction.error_message = "Could not confirm durable COMMIT decision"
            self._phases[transaction.transaction_id] = "commit_unknown"
            self._set_state(transaction, TransactionState.IN_DOUBT)
            return False

        self._set_state(transaction, TransactionState.IN_DOUBT)
        return self._commit_forward(transaction, source_chain, dest_chain)

    def _refresh_unknown_decisions(self) -> None:
        try:
            records = self._read_latest_records()
        except Exception:
            logger.exception("Could not resolve ambiguous 2PC journal writes")
            return
        for tx_id, phase in list(self._phases.items()):
            if phase != "commit_unknown":
                continue
            record = records.get(tx_id)
            if record is None:
                continue
            durable_phase = record.get("phase")
            if isinstance(durable_phase, str):
                self._phases[tx_id] = durable_phase

    def retry_pending(self) -> None:
        """Retry unresolved aborts or durable COMMIT decisions when chains are live."""
        self._refresh_unknown_decisions()
        for tx_id, transaction in list(self.transactions.items()):
            phase = self._phases.get(tx_id)
            if phase not in _UNRESOLVED_PHASES:
                continue
            participants = self._get_participants(transaction)
            if participants is None:
                continue
            source_chain, dest_chain = participants
            if phase in _COMMIT_PHASES:
                if phase == "commit_unknown":
                    continue
                self._commit_forward(
                    transaction,
                    source_chain,
                    dest_chain,
                    restore_committed_state=True,
                )
            else:
                self._abort_before_decision(transaction, source_chain, dest_chain)

    def initiate_transaction(
        self,
        source_chain_name: str,
        dest_chain_name: str,
        payload: dict[str, Any],
    ) -> str:
        """Start a transaction and return its identifier."""
        tx_id = uuid.uuid4().hex
        transaction = CrossChainTransaction(
            transaction_id=tx_id,
            source_chain=source_chain_name,
            destination_chain=dest_chain_name,
            payload=payload,
        )
        self.transactions[tx_id] = transaction
        self._execute_2pc(transaction)
        return tx_id

    def get_transaction(self, tx_id: str) -> CrossChainTransaction | None:
        """Return the in-memory or recovered transaction state."""
        return self.transactions.get(tx_id)

    def requires_2pc_participant(self, chain_name: str) -> bool:
        """Whether an unresolved durable decision needs this chain rebound as DomainChain."""
        return any(
            self._phases.get(tx_id) in _UNRESOLVED_PHASES
            and chain_name in {transaction.source_chain, transaction.destination_chain}
            for tx_id, transaction in self.transactions.items()
        )
