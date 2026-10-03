"""Authenticated HTTP regressions for P2 API behavior."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.business import contracts, state
from hierachain.api.ledger import blocks, chains, depds
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    monkeypatch.setattr(depds, "_hierarchy_manager", manager)
    keys = KeyManager()
    key = keys.create_key("p2-reader", ["chains"])
    app = FastAPI()
    app.state.auth_verifier = APIKeyVerifier(
        {"enabled": True, "key_location": "header", "key_name": "X-API-Key", "cache_ttl": 0},
        key_manager=keys,
    )
    app.include_router(chains.router)
    app.include_router(blocks.router)
    app.include_router(contracts.router)
    try:
        with TestClient(app, headers={"X-API-Key": key}) as http:
            yield http, manager
    finally:
        manager.transaction_manager.journal.close()


def test_subchain_registration_conflict_is_not_reported_as_created(client, monkeypatch) -> None:
    http, manager = client

    def race(*args, **kwargs) -> None:
        raise ValueError("concurrent registration")

    monkeypatch.setattr(manager, "add_sub_chain", race)
    response = http.post("/chains/conflicting/create")
    assert response.status_code == 409
    assert response.json()["success"] is False
    assert manager.get_sub_chain("conflicting") is None


def test_failed_subchain_registration_stops_started_worker(client, monkeypatch) -> None:
    http, manager = client
    attempted = []

    def fail(_name, chain) -> None:
        attempted.append(chain)
        raise RuntimeError("metadata unavailable")

    stopped = []
    original_shutdown = chains.SubChain.shutdown

    def shutdown(chain) -> None:
        stopped.append(chain)
        original_shutdown(chain)

    monkeypatch.setattr(manager, "add_sub_chain", fail)
    monkeypatch.setattr(chains.SubChain, "shutdown", shutdown)
    assert http.post("/chains/failed/create").status_code == 500
    assert stopped == attempted
    assert len(stopped) == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "limit=101", "offset=-1"])
def test_block_listing_rejects_invalid_pagination(client, query: str) -> None:
    http, _ = client
    assert http.get(f"/chains/main_chain/blocks?{query}").status_code == 422


def test_block_listing_accepts_boundaries_and_returns_real_rows(client) -> None:
    http, _ = client
    response = http.get("/chains/main_chain/blocks?limit=100&offset=0")
    assert response.status_code == 200
    assert response.json()["blocks"][0]["events"][0]["entity_id"] == "SYSTEM"


def test_contract_execution_reports_unsupported_engine(client, monkeypatch) -> None:
    http, _ = client
    monkeypatch.setitem(state._contracts, "registered", {"version": "1", "implementation": "unused"})
    payload = {"contract_id": "registered", "event": {"entity_id": "E", "event": "run"}, "context": {}}
    response = http.post("/contracts/execute", json=payload)
    assert response.status_code == 501
    assert response.json()["detail"] == "Contract execution engine is not implemented."
    payload["contract_id"] = "missing"
    assert http.post("/contracts/execute", json=payload).status_code == 404
