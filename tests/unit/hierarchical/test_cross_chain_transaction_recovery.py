"""Focused regression coverage for durable cross-chain 2PC recovery."""

import threading
from queue import Queue
from types import SimpleNamespace

from hierachain.config.settings import settings
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import OrderingStatus
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.domains.chains.tx_manager import TransactionManager
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.hierarchical.types import TransactionState


class _MemoryJournal:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.fail_before: set[str] = set()
        self.fail_after: set[str] = set()

    def log_event(self, record: dict) -> bool:
        phase = record["phase"]
        if phase in self.fail_before:
            return False
        self.records.append(dict(record))
        return phase not in self.fail_after

    def replay(self):
        yield from self.records

    def close(self) -> None:
        pass


class _Participant:
    def __init__(self, name: str, journal: _MemoryJournal) -> None:
        self.name = name
        self.journal = journal
        self.prepared: set[str] = set()
        self.committed: set[str] = set()
        self.prepare_result = True
        self.commit_results: list[bool] = []
        self.rollback_results: list[bool] = []
        self.commit_calls: list[str] = []
        self.rollback_calls: list[str] = []

    def prepare_transaction(self, tx_id: str, _payload: dict, is_source: bool) -> bool:
        if self.prepare_result:
            self.prepared.add(tx_id)
        return self.prepare_result

    def recover_committed_transaction(
        self, tx_id: str, _payload: dict, is_source: bool
    ) -> bool:
        self.prepared.add(tx_id)
        return True

    def commit_transaction(self, tx_id: str) -> bool:
        assert any(record["phase"] == "commit" for record in self.journal.records)
        self.commit_calls.append(tx_id)
        if self.commit_results and not self.commit_results.pop(0):
            return False
        self.committed.add(tx_id)
        return True

    def rollback_transaction(self, tx_id: str) -> bool:
        self.rollback_calls.append(tx_id)
        result = self.rollback_results.pop(0) if self.rollback_results else True
        if result:
            self.prepared.discard(tx_id)
        return result


class _Hierarchy:
    def __init__(self, source: _Participant, destination: _Participant) -> None:
        self.chains = {source.name: source, destination.name: destination}

    def get_sub_chain(self, name: str):
        return self.chains.get(name)


def _manager(journal: _MemoryJournal, source: _Participant, destination: _Participant):
    return CrossChainTransactionManager(_Hierarchy(source, destination), journal=journal)


def _payload() -> dict:
    return {"entity_id": "asset-1", "operation_type": "transfer", "details": {}}


def test_commit_decision_is_durable_before_any_participant_commit() -> None:
    journal = _MemoryJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert [record["phase"] for record in journal.records] == [
        "begin", "prepared", "commit", "committed"
    ]
    assert source.commit_calls == [tx_id]
    assert destination.commit_calls == [tx_id]
    assert manager.get_transaction(tx_id).state is TransactionState.COMMITTED


def test_retry_pending_skips_transaction_owned_by_initial_prepare() -> None:
    prepare_entered = threading.Event()
    release_prepare = threading.Event()

    class PausingParticipant(_Participant):
        def prepare_transaction(self, tx_id: str, payload: dict, is_source: bool) -> bool:
            prepare_entered.set()
            if not release_prepare.wait(timeout=5):
                raise TimeoutError("prepare barrier was not released")
            return super().prepare_transaction(tx_id, payload, is_source)

    journal = _MemoryJournal()
    source = PausingParticipant("source", journal)
    destination = _Participant("destination", journal)
    manager = _manager(journal, source, destination)
    initiated: list[str] = []
    worker = threading.Thread(
        target=lambda: initiated.append(
            manager.initiate_transaction("source", "destination", _payload())
        )
    )
    worker.start()
    try:
        assert prepare_entered.wait(timeout=5)
        tx_id = next(iter(manager.transactions))

        manager.retry_pending()
        manager.retry_pending()

        assert [record["phase"] for record in journal.records] == ["begin"]
        assert source.rollback_calls == []
        assert destination.rollback_calls == []
    finally:
        release_prepare.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert initiated == [tx_id]
    assert [record["phase"] for record in journal.records] == [
        "begin", "prepared", "commit", "committed"
    ]
    assert source.rollback_calls == []
    assert destination.rollback_calls == []
    assert source.commit_calls == [tx_id]
    assert destination.commit_calls == [tx_id]

    manager.retry_pending()
    assert source.rollback_calls == []
    assert destination.rollback_calls == []
    assert source.commit_calls == [tx_id]
    assert destination.commit_calls == [tx_id]


def test_coordinator_does_not_commit_on_unreadable_journal_ack() -> None:
    class FalseAckJournal(_MemoryJournal):
        def log_event(self, record: dict) -> bool:
            if record["phase"] == "commit":
                return True
            return super().log_event(record)

    journal = FalseAckJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert source.commit_calls == []
    assert destination.commit_calls == []


def test_terminal_state_waits_for_durable_readback() -> None:
    journal = _MemoryJournal()
    journal.fail_before.add("committed")
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())
    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert tx_id in source.committed and tx_id in destination.committed

    journal.fail_before.clear()
    manager.retry_pending()
    assert manager.get_transaction(tx_id).state is TransactionState.COMMITTED


def test_prepare_failure_requires_both_rollback_acknowledgments() -> None:
    journal = _MemoryJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    destination.prepare_result = False
    source.rollback_results = [False, True]
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert source.rollback_calls == [tx_id]
    assert destination.rollback_calls == [tx_id]
    assert not any(record["phase"] == "commit" for record in journal.records)

    manager.retry_pending()

    assert manager.get_transaction(tx_id).state is TransactionState.ROLLED_BACK
    assert source.rollback_calls == [tx_id, tx_id]
    assert destination.rollback_calls == [tx_id, tx_id]


def test_failed_commit_retries_forward_without_rollback() -> None:
    journal = _MemoryJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    destination.commit_results = [False, True]
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert source.rollback_calls == []
    assert destination.rollback_calls == []
    assert manager.requires_2pc_participant("source")
    assert manager.requires_2pc_participant("destination")
    assert not manager.requires_2pc_participant("other")
    transaction = manager.get_transaction(tx_id)
    assert transaction is not None
    assert not manager._abort_before_decision(transaction, source, destination)
    assert source.rollback_calls == []
    assert destination.rollback_calls == []

    manager.retry_pending()

    assert manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    assert len(source.commit_calls) == 2
    assert len(destination.commit_calls) == 2
    assert source.rollback_calls == []
    assert destination.rollback_calls == []
    assert not manager.requires_2pc_participant("source")


def test_restart_replays_durable_commit_forward() -> None:
    journal = _MemoryJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    destination.commit_results = [False]
    first_manager = _manager(journal, source, destination)
    tx_id = first_manager.initiate_transaction("source", "destination", _payload())

    restored_source = _Participant("source", journal)
    restored_destination = _Participant("destination", journal)
    restored_hierarchy = _Hierarchy(restored_source, restored_destination)
    restored_manager = CrossChainTransactionManager(restored_hierarchy, journal=journal)
    assert restored_manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT

    restored_hierarchy.chains.pop("destination")
    restored_manager.retry_pending()
    assert restored_source.commit_calls == []
    assert restored_destination.commit_calls == []

    restored_hierarchy.chains["destination"] = restored_destination
    restored_manager.retry_pending()

    assert restored_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    assert restored_source.commit_calls == [tx_id]
    assert restored_destination.commit_calls == [tx_id]
    assert restored_source.rollback_calls == []
    assert restored_destination.rollback_calls == []


def test_ambiguous_commit_journal_write_is_resolved_before_action() -> None:
    journal = _MemoryJournal()
    source = _Participant("source", journal)
    destination = _Participant("destination", journal)
    journal.fail_after.add("commit")
    manager = _manager(journal, source, destination)

    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert source.commit_calls == []
    assert destination.commit_calls == []
    assert source.rollback_calls == []
    assert destination.rollback_calls == []

    manager.retry_pending()

    assert manager.get_transaction(tx_id).state is TransactionState.COMMITTED


class _EventJournal:
    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = records or []

    def replay(self):
        yield from self.records


def test_participant_retry_skips_already_journaled_start_event() -> None:
    tx_id = "tx-1"
    event_journal = _EventJournal([{
        "event_id": "evt-start",
        "channel_id": "test-chain",
        "transaction_id": tx_id,
        "transaction_step": "start",
    }])
    chain = DomainChain.__new__(DomainChain)
    chain.name = "test-chain"
    chain.ordering_service = SimpleNamespace(
        journal=event_journal,
        reconcile_journal_event=lambda event: event["event_id"],
    )
    chain._transaction_event_markers = None
    starts: list[str] = []
    completions: list[str] = []

    def start(_entity_id, _operation_type, _details, transaction_id):
        starts.append(transaction_id)
        event_journal.records.append({
            "event_id": "evt-new-start",
            "channel_id": "test-chain",
            "transaction_id": transaction_id,
            "transaction_step": "start",
        })
        return True

    def complete(_entity_id, _operation_type, _result, transaction_id):
        completions.append(transaction_id)
        event_journal.records.append({
            "event_id": "evt-new-complete",
            "channel_id": "test-chain",
            "transaction_id": transaction_id,
            "transaction_step": "complete",
        })
        return True

    chain.start_domain_operation = start
    chain.complete_domain_operation = complete
    pending = {"payload": _payload()}

    assert chain._execute_commit(tx_id, pending)
    assert starts == []
    assert completions == [tx_id]

    assert chain._execute_commit(tx_id, pending)
    assert starts == []
    assert completions == [tx_id]


def test_durable_commit_recovery_finishes_start_only_marker_without_validation() -> None:
    tx_id = "tx-start-only"
    event_journal = _EventJournal([{
        "event_id": "evt-start-only",
        "channel_id": "test-chain",
        "transaction_id": tx_id,
        "transaction_step": "start",
    }])
    chain = DomainChain.__new__(DomainChain)
    chain.name = "test-chain"
    chain.entity_registry = {}
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain.ordering_service = SimpleNamespace(
        journal=event_journal,
        reconcile_journal_event=lambda event: event["event_id"],
    )
    chain._transaction_event_markers = None

    def reject_validation(*_args, **_kwargs):
        raise AssertionError("durable COMMIT recovery must not rerun business validation")

    chain.start_domain_operation = reject_validation
    chain.complete_domain_operation = reject_validation

    def start(_entity_id, _operation_type, _details, transaction_id):
        event_journal.records.append({
            "event_id": "evt-start-only",
            "channel_id": "test-chain",
            "transaction_id": transaction_id,
            "transaction_step": "start",
        })
        return True

    def complete(_entity_id, _operation_type, _result, transaction_id):
        event_journal.records.append({
            "event_id": "evt-complete-only",
            "channel_id": "test-chain",
            "transaction_id": transaction_id,
            "transaction_step": "complete",
        })
        return True

    chain.start_operation = start
    chain.complete_operation = complete

    assert chain.recover_committed_transaction(tx_id, _payload())
    assert chain.commit_transaction(tx_id)
    assert [
        row["transaction_step"]
        for row in event_journal.records
        if row.get("transaction_id") == tx_id
    ] == ["start", "complete"]


def test_ambiguous_event_append_is_reconciled_once_without_duplicate_journal_row() -> None:
    class _AmbiguousJournal(_EventJournal):
        def __init__(self) -> None:
            super().__init__()
            self.fail_after_first_append = True

        def log_event(self, event: dict) -> bool:
            self.records.append(dict(event))
            if self.fail_after_first_append:
                self.fail_after_first_append = False
                raise OSError("write raised after the event was persisted")
            return True

    journal = _AmbiguousJournal()
    service = OrderingService.__new__(OrderingService)
    service._commit_lock = threading.RLock()
    service.enqueue_timeout = 1.0
    service.should_stop = threading.Event()
    service.status = OrderingStatus.ACTIVE
    service.config = {"chain_name": "test-chain"}
    service.metrics = SimpleNamespace(record_received=lambda: None)
    service.pending_events = {}
    service.event_pool = Queue()
    service.journal = journal
    service.storage_handler = SimpleNamespace(
        storage=SimpleNamespace(get_event_by_id=lambda _event_id: None),
        processed_events={},
    )
    service.block_builder = SimpleNamespace(current_batch_ids=set())

    tx_id = "tx-ambiguous-event"
    chain = DomainChain.__new__(DomainChain)
    chain.name = "test-chain"
    chain.domain_type = "finance"
    chain.lock = threading.RLock()
    chain.pending_events = []
    chain.completed_operations = 0
    chain.entity_registry = {"asset-1": {"status": "registered"}}
    chain.event_handlers = {}
    chain._domain_projection_healthy = True
    chain._domain_projection_errors = []
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain._transaction_event_markers = None
    chain.ordering_service = service
    chain._tx_manager.store_pending(tx_id, _payload(), is_source=True)
    chain.start_domain_operation = lambda entity_id, operation_type, details, transaction_id: (
        chain.start_operation(
            entity_id, operation_type, details, transaction_id=transaction_id
        )
    )
    chain.complete_domain_operation = lambda entity_id, operation_type, result, transaction_id: (
        chain.complete_operation(
            entity_id, operation_type, result, transaction_id=transaction_id
        )
    )

    assert chain.commit_transaction(tx_id) is False
    assert len(journal.records) == 1
    assert service.pending_events == {}
    assert service.event_pool.empty()
    assert chain._transaction_event_markers is None

    assert chain.commit_transaction(tx_id) is True
    start_record = next(
        record
        for record in journal.records
        if record.get("transaction_step") == "start"
    )
    assert sum(
        record.get("transaction_step") == "start" for record in journal.records
    ) == 1
    assert service.event_pool.qsize() == 2

    queued = list(service.event_pool.queue)
    queued_start, queued_complete = queued
    assert queued_start.event_id == start_record["event_id"]
    assert queued_start.channel_id == start_record["channel_id"]
    assert queued_start.event_data == {
        key: value for key, value in start_record.items() if key != "channel_id"
    }
    assert queued_complete.event_data["transaction_step"] == "complete"

    assert service.reconcile_journal_event(start_record) == start_record["event_id"]
    assert chain.commit_transaction(tx_id) is True
    assert service.event_pool.qsize() == 2
    assert sum(
        record.get("transaction_step") == "start" for record in journal.records
    ) == 1

    stored_record = {
        **start_record,
        "event_id": "evt-already-stored",
        "transaction_id": "tx-already-stored",
    }
    journal.records.append(stored_record)
    service.storage_handler.storage.get_event_by_id = (
        lambda event_id: {
            "event_id": event_id,
            "chain_name": "test-chain",
            "data": stored_record,
        }
        if event_id == "evt-already-stored"
        else None
    )
    assert service.reconcile_journal_event(stored_record) == "evt-already-stored"
    assert service.event_pool.qsize() == 2


def test_transaction_event_markers_round_trip_as_top_level_journal_fields(
    tmp_path, monkeypatch
) -> None:
    from hierachain.error_mitigation.journal import TransactionJournal

    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="ordering", active_log_name="events.arrow")
    assert journal.log_event({
        "entity_id": "asset-1",
        "event": "operation_start",
        "timestamp": 1.0,
        "transaction_id": "tx-roundtrip",
        "transaction_step": "start",
    })

    replayed = list(journal.replay())
    journal.close()

    assert replayed[0]["transaction_id"] == "tx-roundtrip"
    assert replayed[0]["transaction_step"] == "start"


def test_participant_keeps_prepared_payload_until_event_acceptance() -> None:
    tx_id = "tx-2"
    chain = DomainChain.__new__(DomainChain)
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain._transaction_event_markers = {}
    chain.name = "source"
    event_journal = _EventJournal()
    chain.ordering_service = SimpleNamespace(
        journal=event_journal,
        reconcile_journal_event=lambda event: event["event_id"],
    )
    chain._tx_manager.store_pending(tx_id, _payload(), is_source=True)
    results = iter((False, True))

    def execute(_tx_id: str, _pending: dict) -> bool:
        success = next(results)
        if success:
            event_journal.records.extend({
                "event_id": f"evt-{step}",
                "channel_id": chain.name,
                "transaction_id": tx_id,
                "transaction_step": step,
            } for step in ("start", "complete"))
        return success

    chain._execute_commit = execute

    assert chain.commit_transaction(tx_id) is False
    assert tx_id in chain.pending_transactions
    assert chain.commit_transaction(tx_id) is True
    assert tx_id not in chain.pending_transactions
    assert chain.commit_transaction(tx_id) is True


def test_participant_keeps_pending_when_ordering_ack_has_no_durable_events() -> None:
    tx_id = "tx-false-ack"
    chain = DomainChain.__new__(DomainChain)
    chain.name = "source"
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain._transaction_event_markers = None
    chain.ordering_service = SimpleNamespace(journal=_EventJournal())
    chain._tx_manager.store_pending(tx_id, _payload(), is_source=True)
    chain._execute_commit = lambda _tx_id, _pending: True

    assert chain.commit_transaction(tx_id) is False
    assert tx_id in chain.pending_transactions
    assert tx_id not in chain._tx_manager.committed_transactions


def test_restart_finishes_prepared_decision_without_duplicate_events() -> None:
    coordinator_journal = _MemoryJournal()
    source_events = _EventJournal()
    destination_events = _EventJournal()

    def participant(name: str, event_journal: _EventJournal, fail_complete: bool = False):
        chain = DomainChain.__new__(DomainChain)
        chain.name = name
        chain._tx_manager = TransactionManager()
        chain._tx_commit_lock = threading.RLock()
        chain._transaction_event_markers = None
        chain.ordering_service = SimpleNamespace(
            journal=event_journal,
            reconcile_journal_event=lambda event: event["event_id"],
        )
        fail_next_complete = [fail_complete]

        def start(_entity_id, _operation_type, _details, transaction_id):
            event_journal.records.append({
                "event_id": f"evt-{transaction_id}-start",
                "channel_id": name,
                "transaction_id": transaction_id,
                "transaction_step": "start",
            })
            return True

        def complete(_entity_id, _operation_type, _result, transaction_id):
            if fail_next_complete[0]:
                fail_next_complete[0] = False
                return False
            event_journal.records.append({
                "event_id": f"evt-{transaction_id}-complete",
                "channel_id": name,
                "transaction_id": transaction_id,
                "transaction_step": "complete",
            })
            return True

        chain.start_domain_operation = start
        chain.complete_domain_operation = complete
        chain.start_operation = start
        chain.complete_operation = complete

        class _Adapter:
            def __init__(self) -> None:
                self.name = name

            def prepare_transaction(self, tx_id, payload, is_source):
                if tx_id not in chain._tx_manager.pending_transactions:
                    chain._tx_manager.store_pending(tx_id, payload, is_source)
                return True

            def recover_committed_transaction(self, tx_id, payload, is_source):
                return chain.recover_committed_transaction(
                    tx_id, payload, is_source=is_source
                )

            def commit_transaction(self, tx_id):
                return chain.commit_transaction(tx_id)

            def rollback_transaction(self, tx_id):
                return chain.rollback_transaction(tx_id)

        return _Adapter()

    source = participant("source", source_events)
    destination = participant("destination", destination_events, fail_complete=True)
    manager = _manager(coordinator_journal, source, destination)
    tx_id = manager.initiate_transaction("source", "destination", _payload())

    assert manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
    assert [row["transaction_step"] for row in source_events.records] == ["start", "complete"]
    assert [row["transaction_step"] for row in destination_events.records] == ["start"]

    restored_source = participant("source", source_events)
    restored_destination = participant("destination", destination_events)
    restored_manager = _manager(coordinator_journal, restored_source, restored_destination)
    restored_manager.retry_pending()

    assert restored_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    assert [row["transaction_step"] for row in source_events.records] == ["start", "complete"]
    assert [row["transaction_step"] for row in destination_events.records] == ["start", "complete"]


def test_real_hierarchy_restart_recovers_entity_state_and_committed_transaction(
    tmp_path, monkeypatch
) -> None:
    from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
    from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "sqlite")
    monkeypatch.setattr(
        settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'metadata.db'}"
    )
    monkeypatch.setattr(settings, "CROSS_LEVEL_SYNC_ENABLED", False)

    def close_manager(manager: HierarchyManager) -> None:
        for chain in manager.get_all_sub_chains().values():
            chain.shutdown()
        manager.transaction_manager.journal.close()
        manager.storage.close()

    manager = HierarchyManager()
    try:
        assert isinstance(manager.storage, SQLiteAdapter)
        assert manager.create_sub_chain("source", "finance")
        assert manager.create_sub_chain("destination", "finance")
        source = manager.get_sub_chain("source")
        destination = manager.get_sub_chain("destination")
        initial_data = {"asset_type": "equipment"}
        assert source.register_entity("asset-1", initial_data)
        assert destination.register_entity("asset-1", initial_data)

        destination.commit_transaction = lambda _tx_id: False
        tx_id = manager.initiate_cross_chain_transaction(
            "source", "destination", _payload()
        )
        assert tx_id is not None
        assert (
            manager.transaction_manager.get_transaction(tx_id).state
            is TransactionState.IN_DOUBT
        )

        source_events = list(source.ordering_service.journal.replay())
        destination_events = list(destination.ordering_service.journal.replay())
        assert [
            event["transaction_step"]
            for event in source_events
            if event.get("transaction_id") == tx_id
        ] == ["start", "complete"]
        assert [
            event["transaction_step"]
            for event in destination_events
            if event.get("transaction_id") == tx_id
        ] == []
    finally:
        close_manager(manager)

    recovered = HierarchyManager()
    try:
        source = recovered.get_sub_chain("source")
        destination = recovered.get_sub_chain("destination")
        assert source.get_entity_info("asset-1")["asset_type"] == "equipment"
        assert destination.get_entity_info("asset-1")["asset_type"] == "equipment"
        assert source.get_entity_info("asset-1").get("current_operation") is None
        assert source.start_domain_operation("asset-1", "inspection")
        assert source.get_entity_info("asset-1")["current_operation"] == "inspection"
        assert not source.start_domain_operation("asset-1", "approval")
        assert source.complete_domain_operation("asset-1", "inspection")
        assert (
            recovered.transaction_manager.get_transaction(tx_id).state
            is TransactionState.COMMITTED
        )

        source_events = list(source.ordering_service.journal.replay())
        destination_events = list(destination.ordering_service.journal.replay())
        assert [
            event["transaction_step"]
            for event in source_events
            if event.get("transaction_id") == tx_id
        ] == ["start", "complete"]
        assert [
            event["transaction_step"]
            for event in destination_events
            if event.get("transaction_id") == tx_id
        ] == ["start", "complete"]
    finally:
        close_manager(recovered)


def test_domain_chain_can_replace_generic_restored_placeholder(
    monkeypatch,
) -> None:
    from hierachain.hierarchical.hierarchy_manager import base as hierarchy_module

    calls: list[str] = []

    class _Storage:
        def __init__(self) -> None:
            self.stored_names: list[str] = []

        def store_chain(self, _chain) -> bool:
            self.stored_names.append(_chain.name)
            return True

        def list_chains(self) -> list[dict[str, str]]:
            return [{"name": "payments", "domain_type": "finance"}]

        def load_chain(self, name: str) -> dict:
            return {"name": name, "chain": []}

        def close(self) -> None:
            pass

    class _TransactionManager:
        def __init__(self, manager) -> None:
            self.manager = manager
            self.journal = _MemoryJournal()

        def retry_pending(self) -> None:
            calls.append(f"retry:{','.join(self.manager.sub_chains)}")

        def get_transaction(self, _tx_id: str):
            return None

        def requires_2pc_participant(self, _chain_name: str) -> bool:
            return False

    class _MainChain:
        def __init__(self, name: str, node_identity=None) -> None:
            self.name = name
            self.node_identity = node_identity
            self.registered_sub_chains = set()
            self.pending_events = []

    class _Placeholder:
        def __init__(self, name: str, domain_type: str, node_identity=None) -> None:
            self.name = name
            self.domain_type = domain_type

        def connect_to_main_chain(self, _main_chain) -> bool:
            calls.append("placeholder-connect")
            return True

        def shutdown(self) -> None:
            calls.append("placeholder-shutdown")

    class _DomainParticipant(_Placeholder):
        def __init__(self, name: str, domain_type: str, metadata=None) -> None:
            super().__init__(name, domain_type)

        def prepare_transaction(self, *_args, **_kwargs) -> bool:
            return True

        def commit_transaction(self, *_args, **_kwargs) -> bool:
            return True

        def rollback_transaction(self, *_args, **_kwargs) -> bool:
            return True

        def connect_to_main_chain(self, _main_chain) -> bool:
            calls.append("domain-connect")
            return True

        def shutdown(self) -> None:
            calls.append("domain-shutdown")

    monkeypatch.setattr(hierarchy_module, "MainChain", _MainChain)
    monkeypatch.setattr(
        hierarchy_module,
        "CrossChainTransactionManager",
        lambda manager: _TransactionManager(manager),
    )
    monkeypatch.setattr(hierarchy_module.HierarchyManager, "_create_storage", staticmethod(lambda: _Storage()))
    monkeypatch.setattr("hierachain.hierarchical.sub_chain.SubChain", _Placeholder)
    monkeypatch.setattr("hierachain.domains.chains.domain_chain.DomainChain", _DomainParticipant)

    manager = hierarchy_module.HierarchyManager()
    placeholder = manager.get_sub_chain("payments")
    storage = manager.storage
    calls.clear()

    assert manager.create_sub_chain("payments", "finance") is True
    assert manager.get_sub_chain("payments") is not placeholder
    assert calls == ["domain-connect", "placeholder-shutdown", "retry:payments"]
    assert "payments" not in storage.stored_names

    coordinator_journal = _MemoryJournal()
    manager.transaction_manager = CrossChainTransactionManager(
        manager, journal=coordinator_journal
    )
    assert manager.create_sub_chain("logistics", "finance") is True
    tx_id = manager.initiate_cross_chain_transaction(
        "payments", "logistics", _payload()
    )
    assert manager.transaction_manager.get_transaction(tx_id).state is TransactionState.COMMITTED


def test_restore_uses_domain_chains_only_for_unresolved_participants(monkeypatch) -> None:
    from hierachain.hierarchical.hierarchy_manager import base as hierarchy_module

    class _Storage:
        def store_chain(self, _chain) -> bool:
            return True

        def list_chains(self) -> list[dict[str, str]]:
            return [
                {"name": "source", "domain_type": "generic"},
                {"name": "unrelated", "domain_type": "generic"},
            ]

        def load_chain(self, name: str) -> dict:
            return {"name": name, "chain": []}

        def close(self) -> None:
            pass

    class _TransactionManager:
        def __init__(self, manager) -> None:
            self.manager = manager
            self.journal = _MemoryJournal()

        def requires_2pc_participant(self, chain_name: str) -> bool:
            return chain_name == "source"

        def retry_pending(self) -> None:
            return None

        def get_transaction(self, _tx_id: str):
            return None

    class _MainChain:
        def __init__(self, name: str, node_identity=None) -> None:
            self.name = name
            self.node_identity = node_identity
            self.registered_sub_chains = set()
            self.pending_events = []

    class _Chain:
        def __init__(self, name: str, domain_type: str, **_kwargs) -> None:
            self.name = name
            self.domain_type = domain_type

        def connect_to_main_chain(self, _main_chain) -> bool:
            return True

        def shutdown(self) -> None:
            return None

    class _DomainParticipant(_Chain):
        def prepare_transaction(self, *_args, **_kwargs) -> bool:
            return True

        def commit_transaction(self, *_args, **_kwargs) -> bool:
            return True

        def rollback_transaction(self, *_args, **_kwargs) -> bool:
            return True

    monkeypatch.setattr(hierarchy_module, "MainChain", _MainChain)
    monkeypatch.setattr(
        hierarchy_module,
        "CrossChainTransactionManager",
        lambda manager: _TransactionManager(manager),
    )
    monkeypatch.setattr(
        hierarchy_module.HierarchyManager,
        "_create_storage",
        staticmethod(lambda: _Storage()),
    )
    monkeypatch.setattr("hierachain.hierarchical.sub_chain.SubChain", _Chain)
    monkeypatch.setattr("hierachain.domains.chains.domain_chain.DomainChain", _DomainParticipant)

    manager = hierarchy_module.HierarchyManager()

    assert isinstance(manager.get_sub_chain("source"), _DomainParticipant)
    assert type(manager.get_sub_chain("unrelated")) is _Chain
