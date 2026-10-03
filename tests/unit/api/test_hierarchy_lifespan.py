"""API hierarchy resources must not retain writer leases across lifespans."""

from contextlib import nullcontext
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.api import server
from hierachain.api.ledger import depds
from hierachain.hierarchical import HierarchyManager


@pytest.mark.parametrize("startup_failure", [False, True])
def test_api_shutdown_releases_coordinator_and_resets_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, startup_failure: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage",
                        staticmethod(lambda: SQLiteAdapter(str(tmp_path / "main.db"))))
    monkeypatch.setattr(depds, "_hierarchy_manager", None)
    monkeypatch.setattr(depds, "_entity_tracer", None)

    async def no_network(_settings: object) -> None:
        if startup_failure:
            raise RuntimeError("P2P startup failed")

    monkeypatch.setattr(server, "_start_p2p_network_layer", no_network)
    manager = depds.get_hierarchy_manager()
    coordinator = manager.transaction_manager
    assert coordinator.journal.log_event({"entity_id": "probe", "event": "probe"})
    depds.get_entity_tracer(manager)
    expected = pytest.raises(RuntimeError, match="P2P startup failed") if startup_failure else nullcontext()
    with expected, TestClient(server.create_app()):
        pass
    assert depds._hierarchy_manager is None
    assert depds._entity_tracer is None
    reopened = HierarchyManager()
    try:
        assert reopened.transaction_manager.journal.log_event({"entity_id": "next", "event": "probe"})
    finally:
        reopened.close()
