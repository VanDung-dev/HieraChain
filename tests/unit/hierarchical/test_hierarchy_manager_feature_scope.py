"""Unsupported facade branches must not acknowledge unapplied access changes."""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.hierarchical.hierarchy_manager import HierarchyManager


@pytest.mark.parametrize(
    ("org_id", "chain_name", "warns"),
    [("org-a", "orders", True), ("missing", "orders", False), ("org-a", "missing", False)],
)
def test_chain_assignment_never_acknowledges_unapplied_permissions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    org_id: str,
    chain_name: str,
    warns: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    try:
        organization = manager.create_organization("org-a", "Org A", ["alice"])
        chain = SimpleNamespace(name="orders", shutdown=Mock())
        manager.sub_chains["orders"] = chain
        before = manager._hierarchy_registry_snapshot()

        with caplog.at_level(logging.WARNING):
            assert manager.assign_organization_to_chain(org_id, chain_name) is False

        assert ("Organization-to-chain assignment is not implemented" in caplog.text) is warns
        assert manager._hierarchy_registry_snapshot() == before
        assert manager.get_organization("org-a") is organization
        assert manager.get_sub_chain("orders") is chain
        assert not (tmp_path / "data" / "transactions").exists()
    finally:
        manager.close()
