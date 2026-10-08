"""Recovery and bootstrap contract for persisted sub-chain metadata."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.hierarchical.sub_chain import base as sub_chain_base
from hierachain.security.identity_loader import load_node_identity


@pytest.fixture(autouse=True)
def isolated_manager_journals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> Generator[None, None, None]:
    monkeypatch.chdir(tmp_path)
    created: list[HierarchyManager] = []
    original_init = HierarchyManager.__init__

    def tracked_init(manager: HierarchyManager, *args: Any, **kwargs: Any) -> None:
        original_init(manager, *args, **kwargs)
        created.append(manager)

    monkeypatch.setattr(HierarchyManager, "__init__", tracked_init)
    yield
    for manager in reversed(created):
        manager.close()


class _MetadataStorage:
    def __init__(self, chains: list[dict[str, str]]) -> None:
        self.chains = chains
        self.stored: list[object] = []

    def store_chain(self, chain: object) -> bool:
        self.stored.append(chain)
        return True

    def list_chains(self) -> list[dict[str, str]]:
        return self.chains

    def load_chain(self, name: str) -> dict[str, object]:
        return {"name": name, "chain": []}

    def close(self) -> None:
        pass


def test_registry_workers_acquire_coordinator_only_when_needed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    first = HierarchyManager()
    second = HierarchyManager()
    assert not (tmp_path / "data" / "transactions").exists()
    first.create_organization("first", "First")
    second.create_organization("second", "Second")
    assert not (tmp_path / "data" / "transactions").exists()
    coordinator = first.transaction_manager
    with pytest.raises(RuntimeError, match="owning writer"):
        _ = second.transaction_manager
    with pytest.raises(RuntimeError, match="owning writer"):
        HierarchyManager()
    assert coordinator.journal.log_event({"entity_id": "probe", "event": "probe"})
    first.close()
    assert second.transaction_manager.journal.log_event({"entity_id": "after-close", "event": "probe"})
    second.close()
    with pytest.raises(RuntimeError, match="closed"):
        _ = second.transaction_manager


def test_close_idle_manager_does_not_create_coordinator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    manager.close()
    manager.close()
    assert not (tmp_path / "data" / "transactions").exists()


class _CreatedSubChain:
    def __init__(self, name: str, domain_type: str, calls: list[str]) -> None:
        self.name = name
        self.domain_type = domain_type
        self.calls = calls

    def connect_to_main_chain(self, _main_chain: object) -> bool:
        self.calls.append("connect")
        return True

    def shutdown(self) -> None:
        self.calls.append("shutdown")


@pytest.mark.parametrize("stage", ["_restore_main_chain", "_restore_sub_chains", "_restore_hierarchy_registry"])
def test_failed_bootstrap_closes_storage_journal_and_started_chains(
    monkeypatch: pytest.MonkeyPatch, stage: str, tmp_path: Path,
) -> None:
    # Existing coordinator history must recover eagerly and release on failure.
    (tmp_path / "data" / "transactions").mkdir(parents=True)
    storage = Mock()
    coordinator = Mock()
    chain = Mock()
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    monkeypatch.setattr(
        "hierachain.hierarchical.hierarchy_manager.base.CrossChainTransactionManager",
        lambda _manager: coordinator,
    )
    monkeypatch.setattr(HierarchyManager, "_restore_main_chain", lambda _self: None)
    monkeypatch.setattr(
        HierarchyManager, "_restore_sub_chains", lambda manager: manager.sub_chains.update({"restored": chain}),
    )

    def fail(_self: HierarchyManager) -> None:
        raise RuntimeError("broken persisted chain")

    monkeypatch.setattr(HierarchyManager, stage, fail)
    with pytest.raises(RuntimeError, match="broken persisted chain"):
        HierarchyManager()
    storage.close.assert_called_once()
    coordinator.journal.close.assert_called_once()
    assert chain.shutdown.call_count == (1 if stage == "_restore_hierarchy_registry" else 0)


@pytest.mark.parametrize("injected", [False, True])
def test_transaction_recovery_failure_closes_only_owned_journal(
    monkeypatch: pytest.MonkeyPatch, injected: bool,
) -> None:
    from hierachain.hierarchical import transaction_manager as transactions

    journal = Mock()
    monkeypatch.setattr(transactions, "TransactionJournal", lambda **_kwargs: journal)
    monkeypatch.setattr(
        transactions.CrossChainTransactionManager, "_load_journal",
        Mock(side_effect=RuntimeError("broken journal")),
    )
    with pytest.raises(RuntimeError, match="broken journal"):
        transactions.CrossChainTransactionManager(Mock(), journal=journal if injected else None)
    assert journal.close.call_count == (0 if injected else 1)


def test_manager_restores_persisted_subchains(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _MetadataStorage([
        {"name": "payments", "chain_type": "sub", "domain_type": "finance"}
    ])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))

    class RestoredSubChain:
        def __init__(self, name: str, domain_type: str, node_identity: object) -> None:
            self.name = name
            self.domain_type = domain_type
            self.node_identity = node_identity

        def connect_to_main_chain(self, _main_chain: object) -> bool:
            return True

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(
        "hierachain.hierarchical.sub_chain.SubChain", RestoredSubChain
    )
    identity = load_node_identity()
    assert identity is not None

    manager = HierarchyManager(node_identity=identity)

    restored = manager.get_sub_chain("payments")
    assert isinstance(restored, RestoredSubChain)
    assert restored.domain_type == "finance"
    assert restored.node_identity is identity
    assert manager.get_all_sub_chains() == {"payments": restored}


def test_restored_signed_registration_rebuilds_mainchain_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hierachain.consensus.ordering import storage as ordering_storage

    registration = {
        "entity_id": "payments",
        "event": "sub_chain_registration",
        "timestamp": 12.0,
        "details": {
            "sub_chain_name": "payments",
            "metadata": {
                "sub_chain_name": "payments",
                "domain_type": "finance",
                "connected_at": 11.0,
            },
        },
    }
    legacy_registration = {
        "entity_id": "legacy",
        "event": "sub_chain_registration",
        "timestamp": 13.0,
        "details": {"sub_chain_name": "legacy", "metadata": {}},
    }
    event_block = SimpleNamespace(
        index=0, to_event_list=lambda: [registration, legacy_registration]
    )
    authority_metadata: dict[str, dict[str, object]] = {}
    consensus = SimpleNamespace(
        authorities={"main_chain"},
        authority_metadata=authority_metadata,
        add_authority=lambda name, metadata: authority_metadata.setdefault(name, metadata) is not None,
    )
    main = SimpleNamespace(
        name="main",
        trusted_public_keys={},
        chain=[],
        consensus=consensus,
        registered_sub_chains=set(),
        sub_chain_metadata={},
        _rebuild_event_indexes=lambda: None,
        proof_count=0,
    )
    manager = HierarchyManager.__new__(HierarchyManager)
    manager.main_chain = main
    manager.storage = SimpleNamespace(load_chain=lambda _name: {"chain": [event_block]})

    monkeypatch.setattr(ordering_storage, "_block_from_dict", lambda row, _keys: row)
    monkeypatch.setattr(ordering_storage, "_verify_chain_links", lambda _blocks: None)
    monkeypatch.setattr(
        "hierachain.hierarchical.main_chain.proofs._refresh_durable_proofs",
        lambda chain: setattr(chain, "latest_proofs", {}),
    )

    manager._restore_main_chain()

    assert main.registered_sub_chains == {"payments", "legacy"}
    assert main.sub_chain_metadata["payments"]["domain_type"] == "finance"
    assert authority_metadata["payments"]["role"] == "sub_chain"
    assert authority_metadata["payments"]["registered_at"] == 12.0
    assert main.sub_chain_metadata["legacy"] == {}
    assert authority_metadata["legacy"]["metadata"] == {}


def test_subchain_reconnect_preserves_registration_and_connection_event() -> None:
    from hierachain.hierarchical.sub_chain.proof import _connect_sub_chain_to_main

    main = SimpleNamespace(
        name="main",
        registered_sub_chains={"payments"},
        sub_chain_metadata={
            "payments": {
                "sub_chain_name": "payments",
                "domain_type": "finance",
                "connected_at": 7.0,
            }
        },
        latest_proofs={"payments": {"timestamp": 6.0, "latest_block_index": 3}},
        register_sub_chain=Mock(side_effect=AssertionError("duplicate registration")),
    )
    pending: list[dict[str, object]] = []
    child = SimpleNamespace(
        name="payments",
        domain_type="finance",
        main_chain_connection=None,
        chain=[],
        pending_events=pending,
        ordering_service=SimpleNamespace(pending_events={}, journal=None),
        add_event=lambda event: pending.append(dict(event)),
        get_latest_block=lambda: SimpleNamespace(index=3),
    )

    assert _connect_sub_chain_to_main(child, main)
    assert _connect_sub_chain_to_main(child, main)

    assert child.main_chain_connection is main
    assert len(pending) == 1
    assert pending[0]["event_id"] == "main-connection:payments:main"
    assert child.last_proof_submission == 6.0
    assert child.last_proof_block_index == 3
    main.register_sub_chain.assert_not_called()

    main.registered_sub_chains.add("legacy")
    main.sub_chain_metadata["legacy"] = {}
    legacy_events: list[dict[str, object]] = []
    legacy = SimpleNamespace(
        name="legacy",
        domain_type="legacy-domain",
        main_chain_connection=None,
        chain=[],
        pending_events=legacy_events,
        ordering_service=SimpleNamespace(pending_events={}, journal=None),
        add_event=lambda event: legacy_events.append(dict(event)),
    )
    assert _connect_sub_chain_to_main(legacy, main)


def test_subchain_reconnect_rejects_registered_domain_mismatch() -> None:
    from hierachain.hierarchical.sub_chain.proof import _connect_sub_chain_to_main

    main = SimpleNamespace(
        name="main",
        registered_sub_chains={"payments"},
        sub_chain_metadata={"payments": {"sub_chain_name": "payments", "domain_type": "legal"}},
        latest_proofs={},
    )
    child = SimpleNamespace(
        name="payments", domain_type="finance", main_chain_connection=None
    )

    assert not _connect_sub_chain_to_main(child, main)
    assert child.main_chain_connection is None


def test_manager_accepts_empty_inventory_for_new_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))

    manager = HierarchyManager()

    assert manager.get_all_sub_chains() == {}


def test_organization_channel_registry_survives_manager_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter

    database_path = str(tmp_path / "hierarchy.db")
    monkeypatch.setattr(
        HierarchyManager,
        "_create_storage",
        staticmethod(lambda: SQLiteAdapter(database_path=database_path)),
    )

    first = HierarchyManager()
    first.create_organization("org-a", "org-a", admin_users=["alice"])
    first.register_organization_member(
        "org-a",
        "bob",
        {"user_id": "bob", "org_id": "org-a", "role": "member"},
        "member",
    )
    first.create_channel("shared", ["org-a"], {"write": "ADMIN"})

    first.transaction_manager.journal.close()
    first.storage.close()

    restored = HierarchyManager()
    assert restored.get_organization("org-a").members["bob"]["role"] == "member"
    channel = restored.get_channel("shared")
    assert channel is not None
    assert channel.submit_event(
        {"entity_id": "item-1", "event": "created"},
        "org-a",
        submitter_user_id="bob",
    ) is False
    assert channel.submit_event(
        {"entity_id": "item-1", "event": "created"},
        "org-a",
        submitter_user_id="alice",
    ) is True

    assert channel.update_channel_policy({"write": "MEMBER"}, ["org-a"])
    restored.transaction_manager.journal.close()
    restored.storage.close()
    restored_again = HierarchyManager()
    updated_channel = restored_again.get_channel("shared")
    assert updated_channel is not None
    assert updated_channel.submit_event(
        {"entity_id": "item-2", "event": "created"},
        "org-a",
        submitter_user_id="bob",
    ) is True


def test_organization_is_not_registered_when_registry_save_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingStorage(_MetadataStorage):
        def save_hierarchy_registry(self, _state: dict[str, object]) -> bool:
            return False

    storage = FailingStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()

    with pytest.raises(RuntimeError, match="Failed to persist organization registry"):
        manager.create_organization("org-a", "org-a", admin_users=["alice"])

    assert manager.get_organization("org-a") is None


def test_create_subchain_connects_before_persisting_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)

    def store_chain(chain: object) -> bool:
        if getattr(chain, "name", None) == "payments":
            assert manager.get_sub_chain("payments") is None
            calls.append("persist")
        return True

    monkeypatch.setattr(storage, "store_chain", store_chain)
    monkeypatch.setattr(
        "hierachain.domains.chains.domain_chain.DomainChain",
        lambda _name, _domain_type, metadata=None: sub_chain,
    )

    assert manager.create_sub_chain("payments", "finance")

    assert calls == ["connect", "persist"]
    assert manager.get_sub_chain("payments") is sub_chain


def test_create_subchain_stops_when_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)

    def connect_and_register(main_chain: Any) -> bool:
        calls.append("connect")
        return main_chain.register_sub_chain(
            "payments",
            {
                "sub_chain_name": "payments",
                "domain_type": "finance",
                "connected_at": 1.0,
            },
        )

    sub_chain.connect_to_main_chain = connect_and_register

    def store_chain(chain: object) -> bool:
        calls.append("persist")
        return getattr(chain, "name", None) != "payments"

    monkeypatch.setattr(storage, "store_chain", store_chain)
    monkeypatch.setattr(
        "hierachain.domains.chains.domain_chain.DomainChain",
        lambda _name, _domain_type, metadata=None: sub_chain,
    )

    with pytest.raises(RuntimeError, match="Failed to persist sub-chain metadata: payments"):
        manager.create_sub_chain("payments", "finance")

    assert calls == ["connect", "persist", "shutdown"]
    assert manager.get_sub_chain("payments") is None
    assert "payments" not in manager.main_chain.registered_sub_chains
    assert "payments" not in manager.main_chain.sub_chain_metadata
    assert not any(
        event.get("event") == "sub_chain_registration"
        and event.get("entity_id") == "payments"
        for event in manager.main_chain.pending_events
    )


@pytest.mark.parametrize("raises", [False, True])
def test_failed_connection_does_not_persist_or_publish_subchain(
    monkeypatch: pytest.MonkeyPatch, raises: bool,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)

    def fail_connection(main_chain: Any) -> bool:
        calls.append("connect")
        if raises:
            assert main_chain.register_sub_chain("payments", {"domain_type": "finance"})
            raise RuntimeError("Failed to connect sub-chain to main chain after registration")
        return False

    sub_chain.connect_to_main_chain = fail_connection
    monkeypatch.setattr(storage, "store_chain", lambda _chain: calls.append("persist") or True)

    with pytest.raises(RuntimeError, match="Failed to connect sub-chain to main chain"):
        manager.add_sub_chain("payments", sub_chain)

    assert calls == ["connect"]
    assert manager.get_sub_chain("payments") is None
    assert "payments" not in manager.main_chain.registered_sub_chains
    assert "payments" not in manager.main_chain.sub_chain_metadata
    assert not any(
        event.get("event") == "sub_chain_registration" and event.get("entity_id") == "payments"
        for event in manager.main_chain.pending_events
    )


def test_cross_level_failure_rolls_back_new_mainchain_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)

    def connect_and_register(main_chain: Any) -> bool:
        calls.append("connect")
        return main_chain.register_sub_chain(
            "payments",
            {"sub_chain_name": "payments", "domain_type": "finance"},
        )

    sub_chain.connect_to_main_chain = connect_and_register
    manager.cross_level_sync = SimpleNamespace(
        connect_subchain=lambda _name, _chain: (_ for _ in ()).throw(
            RuntimeError("sync registration failed")
        ),
        disconnect_subchain=lambda name: calls.append(f"disconnect:{name}"),
    )

    with pytest.raises(RuntimeError, match="sync registration failed"):
        manager.add_sub_chain("payments", sub_chain)

    assert manager.get_sub_chain("payments") is None
    assert "payments" not in manager.main_chain.registered_sub_chains
    assert calls == ["connect", "disconnect:payments"]


def test_late_registration_failure_cleans_manager_and_sync_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)
    sync_calls: list[str] = []
    manager.cross_level_sync = SimpleNamespace(
        connect_subchain=lambda name, _chain: sync_calls.append(f"connect:{name}"),
        disconnect_subchain=lambda name: sync_calls.append(f"disconnect:{name}"),
    )
    monkeypatch.setattr(storage, "store_chain", lambda _chain: True)
    monkeypatch.setattr(
        manager.transaction_manager,
        "retry_pending",
        lambda: (_ for _ in ()).throw(RuntimeError("retry failed")),
    )

    manager.add_sub_chain("payments", sub_chain)

    assert manager.get_sub_chain("payments") is sub_chain
    assert sync_calls == ["connect:payments"]


def test_configured_postgres_failure_does_not_fall_back_to_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hierachain.adapters.database.postgres_adapter as postgres_module

    postgres = SimpleNamespace(
        _get_connection=lambda: _failing_connection(), close=lambda: None
    )
    monkeypatch.setattr(postgres_module, "PostgresAdapter", lambda **_kwargs: postgres)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")

    with pytest.raises(RuntimeError, match="Configured PostgreSQL storage is unavailable"):
        HierarchyManager._create_storage()


def test_postgres_adapter_lists_subchain_inventory_with_dict_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hierachain.adapters.database.postgres_adapter import PostgresAdapter

    class CursorStub:
        def execute(self, query: str) -> None:
            assert "WHERE chain_type = 'sub' ORDER BY name" in query

        def fetchall(self) -> list[dict[str, str]]:
            return [
                {"name": "payments", "chain_type": "sub", "domain_type": "finance"}
            ]

    adapter = object.__new__(PostgresAdapter)
    connection = SimpleNamespace(cursor=lambda: CursorStub())

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(adapter, "_get_connection", get_connection)

    assert adapter.list_chains() == [
        {"name": "payments", "chain_type": "sub", "domain_type": "finance"}
    ]


class _OrderingServiceStub:
    def __init__(self, *, active: bool, fail_read: bool = False) -> None:
        self.storage_handler = SimpleNamespace(save_block=lambda *_args: True)
        self.active = active
        self.fail_read = fail_read
        self.stopped = False

    def take_bootstrap_blocks(self) -> None:
        if self.fail_read:
            raise OSError("ordering storage unavailable")
        return None

    def wait_for_active(self, timeout: float | None) -> bool:
        assert timeout is None
        return self.active

    def shutdown(self) -> None:
        self.stopped = True


def _failing_connection():
    raise OSError("postgres unavailable")


@pytest.mark.parametrize(
    ("active", "fail_read", "message"),
    [
        (False, False, "did not become active"),
        (True, True, "ordering storage unavailable"),
    ],
)
def test_subchain_recovery_failure_is_propagated_and_stops_ordering(
    monkeypatch: pytest.MonkeyPatch,
    active: bool,
    fail_read: bool,
    message: str,
) -> None:
    service = _OrderingServiceStub(active=active, fail_read=fail_read)
    monkeypatch.setattr(
        sub_chain_base.SubChain,
        "_init_ordering_service",
        lambda self: setattr(self, "ordering_service", service),
    )

    with pytest.raises((RuntimeError, OSError), match=message):
        sub_chain_base.SubChain("payments", domain_type="finance")

    assert service.stopped
