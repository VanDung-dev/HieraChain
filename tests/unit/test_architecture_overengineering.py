"""Executable evidence for duplicated runtime paths and state ownership."""

from queue import Queue
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.hierarchical.sub_chain.block import (
    _process_and_finalize_single_block,
)
from hierachain.security.key_manager import KeyManager


class _OrderingStub:
    authoritative_id = "ordering-event-id"

    def __init__(self) -> None:
        self.pending_events: dict[str, dict] = {}
        self.event_pool: Queue[dict] = Queue()

    def receive_event(
        self, event_data: dict, channel_id: str, submitter_org: str
    ) -> str:
        self.pending_events[self.authoritative_id] = event_data.copy()
        self.event_pool.put(event_data.copy())
        return self.authoritative_id


def _bare_sub_chain(ordering_service: _OrderingStub) -> SubChain:
    sub_chain = object.__new__(SubChain)
    sub_chain.name = "orders"
    sub_chain.ordering_service = ordering_service
    sub_chain.lock = Lock()
    sub_chain.pending_events = []
    return sub_chain


def test_sub_chain_returns_ordering_service_event_id() -> None:
    ordering = _OrderingStub()
    sub_chain = _bare_sub_chain(ordering)

    returned_id = SubChain.add_event(
        sub_chain,
        {"entity_id": "E-1", "event": "created", "details": {}},
    )

    assert returned_id == ordering.authoritative_id
    assert len(sub_chain.pending_events) == 1
    assert len(ordering.pending_events) == 1
    assert ordering.event_pool.qsize() == 1


def test_proof_submission_runs_subchain_and_cross_level_paths() -> None:
    manager = object.__new__(HierarchyManager)
    chain = Mock()
    chain.submit_proof_to_main.return_value = True
    sync = Mock()
    sync.sync_to_mainchain.return_value = SimpleNamespace(
        success=True, error_message=None
    )
    manager.main_chain = object()
    manager.cross_level_sync = sync
    manager.get_sub_chain = Mock(return_value=chain)

    assert HierarchyManager.submit_proof_to_main_chain(manager, "orders")
    chain.submit_proof_to_main.assert_called_once_with(manager.main_chain)
    sync.sync_to_mainchain.assert_called_once_with("orders")


def test_auto_proof_uses_new_block_when_certification_removed_pending_event() -> None:
    sub_chain = object.__new__(SubChain)
    sub_chain.last_proof_submission = 0.0
    sub_chain.proof_submission_interval = 60.0
    sub_chain.last_proof_block_index = 0
    sub_chain.lock = Lock()
    sub_chain.chain = [SimpleNamespace(index=1)]
    sub_chain.ordering_service = SimpleNamespace(pending_events={})

    assert SubChain.should_submit_proof(sub_chain)


def test_storage_failure_does_not_append_block_in_memory() -> None:
    block = SimpleNamespace(
        index=-1,
        previous_hash=None,
        hash=None,
        calculate_hash=Mock(return_value="a" * 64),
    )
    sub_chain = SimpleNamespace(
        name="orders",
        block_processing_lock=Lock(),
        get_latest_block=Mock(return_value=SimpleNamespace(index=0, hash="b" * 64)),
        consensus=SimpleNamespace(finalize_block=Mock(return_value=block)),
        ordering_service=SimpleNamespace(
            storage_handler=SimpleNamespace(
                save_block=Mock(side_effect=OSError("storage unavailable"))
            )
        ),
        add_block=Mock(return_value=True),
        world_state=SimpleNamespace(apply_block=Mock()),
        auto_submit_proof_if_needed=Mock(),
    )

    assert not _process_and_finalize_single_block(sub_chain, block)
    sub_chain.ordering_service.storage_handler.save_block.assert_called_once()
    sub_chain.add_block.assert_not_called()


def test_key_manager_starts_one_cache_cleanup_worker_per_cache(monkeypatch) -> None:
    started: list[object] = []

    class _Thread:
        def __init__(self, *args, **kwargs) -> None:
            self.target = kwargs.get("target") or (args[0] if args else None)

        def start(self) -> None:
            started.append(self.target)

    monkeypatch.setattr("hierachain.core.cache.threading.Thread", _Thread)

    KeyManager(storage_backend={}, config={"verify_signatures": True})

    assert len(started) == 2
