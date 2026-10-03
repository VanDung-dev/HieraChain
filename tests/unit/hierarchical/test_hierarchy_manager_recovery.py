"""Recovery and bootstrap contract for persisted sub-chain metadata."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.hierarchical.sub_chain import base as sub_chain_base
from hierachain.security.identity_loader import load_node_identity


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
    monkeypatch: pytest.MonkeyPatch, stage: str,
) -> None:
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


def test_create_subchain_persists_before_registration(
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

    assert calls == ["persist", "connect"]
    assert manager.get_sub_chain("payments") is sub_chain


def test_create_subchain_stops_when_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _MetadataStorage([])
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: storage))
    manager = HierarchyManager()
    calls: list[str] = []
    sub_chain = _CreatedSubChain("payments", "finance", calls)

    def store_chain(chain: object) -> bool:
        return getattr(chain, "name", None) != "payments"

    monkeypatch.setattr(storage, "store_chain", store_chain)
    monkeypatch.setattr(
        "hierachain.domains.chains.domain_chain.DomainChain",
        lambda _name, _domain_type, metadata=None: sub_chain,
    )

    with pytest.raises(RuntimeError, match="Failed to persist sub-chain metadata: payments"):
        manager.create_sub_chain("payments", "finance")

    assert calls == ["shutdown"]
    assert manager.get_sub_chain("payments") is None


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
