from collections.abc import Iterator
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.hierarchical.hierarchy_manager import HierarchyManager


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> Iterator[HierarchyManager]:
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    instance = HierarchyManager()
    instance.create_organization("org-a", "A", ["alice"])
    instance.create_organization("org-b", "B", ["bob"])
    instance.sub_chains["orders"] = SimpleNamespace(shutdown=Mock())
    instance.sub_chains["public"] = SimpleNamespace(shutdown=Mock())
    yield instance
    instance.close()


def test_assignment_grants_only_registered_members_and_selected_permissions(manager: HierarchyManager) -> None:
    assert manager.assign_organization_to_chain("org-a", "orders", permissions=["read"])
    assert manager.can_access_chain("orders", "alice", "read")
    assert not manager.can_access_chain("orders", "alice", "write")
    assert not manager.can_access_chain("orders", "bob", "read")
    assert not manager.can_access_chain("orders", None, "read")
    assert manager.can_access_chain("public", None, "read")
    assert manager.assign_organization_to_chain("org-b", "orders", permissions=["write", "proofs"])
    assert manager.can_access_chain("orders", "bob", "write")
    assert manager.can_access_chain("orders", "bob", "proofs")
    assert not manager.can_access_chain("orders", "bob", "read")


def test_revoke_last_assignment_keeps_chain_protected(manager: HierarchyManager) -> None:
    assert manager.assign_organization_to_chain("org-a", "orders")
    assert manager.revoke_organization_from_chain("org-a", "orders")
    assert manager.get_chain_access("orders") == {}
    assert not manager.can_access_chain("orders", "alice", "read")


def test_membership_is_resolved_from_live_registry(manager: HierarchyManager) -> None:
    assert manager.assign_organization_to_chain("org-a", "orders")
    manager.organizations["org-a"].members["alice"]["identity"]["org_id"] = "org-b"
    assert not manager.can_access_chain("orders", "alice", "read")


def test_failed_persistence_rolls_back_assignment(manager: HierarchyManager, monkeypatch: pytest.MonkeyPatch) -> None:
    before = deepcopy(manager._hierarchy_registry_snapshot())
    monkeypatch.setattr(manager, "_persist_hierarchy_registry", lambda: False)
    with pytest.raises(RuntimeError):
        manager.assign_organization_to_chain("org-a", "orders")
    assert manager._hierarchy_registry_snapshot() == before


@pytest.mark.parametrize("permissions", [[], ["admin"], ["read", 1], "read"])
def test_invalid_grants_are_rejected(manager: HierarchyManager, permissions: object) -> None:
    with pytest.raises(ValueError):
        manager.assign_organization_to_chain("org-a", "orders", permissions=permissions)
    assert manager.get_chain_access("orders") is None


def test_registry_round_trip_and_legacy_snapshot(manager: HierarchyManager) -> None:
    legacy = deepcopy(manager._hierarchy_registry_snapshot())
    legacy.pop("chain_access", None)
    assert manager.assign_organization_to_chain("org-a", "orders", permissions=["proofs"])
    snapshot = deepcopy(manager._hierarchy_registry_snapshot())
    manager._apply_hierarchy_registry(snapshot)
    assert manager.can_access_chain("orders", "alice", "proofs")
    assert not manager.can_access_chain("orders", "alice", "read")
    snapshot["chain_access"]["orders"]["unknown"] = ["read"]
    with pytest.raises(RuntimeError):
        manager._apply_hierarchy_registry(snapshot)
    assert manager.can_access_chain("orders", "alice", "proofs")
    manager._apply_hierarchy_registry(legacy)
    assert manager.get_chain_access("orders") is None
