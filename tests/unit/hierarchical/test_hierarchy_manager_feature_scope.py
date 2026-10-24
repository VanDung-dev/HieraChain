"""Organization assignments acknowledge only applied access changes."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.hierarchical.hierarchy_manager import HierarchyManager


@pytest.mark.parametrize(
    ("org_id", "chain_name", "assigned"),
    [("org-a", "orders", True), ("missing", "orders", False), ("org-a", "missing", False)],
)
def test_chain_assignment_applies_only_existing_resources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    org_id: str,
    chain_name: str,
    assigned: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    try:
        organization = manager.create_organization("org-a", "Org A", ["alice"])
        chain = SimpleNamespace(name="orders", shutdown=Mock())
        manager.sub_chains["orders"] = chain
        before = manager._hierarchy_registry_snapshot()

        assert manager.assign_organization_to_chain(org_id, chain_name) is assigned
        assert (manager._hierarchy_registry_snapshot() != before) is assigned
        assert manager.can_access_chain("orders", "alice", "read")
        assert manager.get_organization("org-a") is organization
        assert manager.get_sub_chain("orders") is chain
        assert not (tmp_path / "data" / "transactions").exists()
    finally:
        manager.close()
