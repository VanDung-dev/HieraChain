"""Recovery and bootstrap contract for persisted sub-chain metadata."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.hierarchical.sub_chain import base as sub_chain_base


class _MetadataStorage:
    def __init__(self, chains: list[dict[str, str]]) -> None:
        self.chains = chains
        self.stored: list[object] = []

    def store_chain(self, chain: object) -> bool:
        self.stored.append(chain)
        return True

    def list_chains(self) -> list[dict[str, str]]:
        return self.chains


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

    monkeypatch.setattr(
        "hierachain.hierarchical.sub_chain.SubChain", RestoredSubChain
    )
    identity = object()

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

    def get_latest_block(self) -> None:
        if self.fail_read:
            raise OSError("ordering storage unavailable")
        return None

    def wait_for_active(self, timeout: float) -> bool:
        assert timeout == 10.0
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
