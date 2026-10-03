"""Real backend and HTTP contracts for shared registry revisions and access state."""

import os
import threading
import uuid
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import orjson
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.adapters.database.redis_adapter import RedisStorageAdapter
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.api.business.router import business_router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.hierarchical import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


@pytest.fixture(params=["sqlite", "postgres", "redis"])
def managers(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[HierarchyManager, HierarchyManager]]:
    monkeypatch.chdir(tmp_path)
    backend = request.param
    if backend == "sqlite":
        def factory() -> Any:
            return SQLiteAdapter(str(tmp_path / "registry.db"))
    elif backend == "postgres":
        url = os.getenv("HRC_TEST_POSTGRES_URL", "")
        if not url:
            pytest.skip("HRC_TEST_POSTGRES_URL is required")
        def factory() -> Any:
            return PostgresAdapter(url)
    else:
        port = os.getenv("HRC_TEST_REDIS_PORT", "")
        if not port:
            pytest.skip("HRC_TEST_REDIS_PORT is required")
        def factory() -> Any:
            return RedisStorageAdapter(port=int(port), db=14)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(factory))
    instances: list[HierarchyManager] = []
    try:
        for _ in range(2):
            instances.append(HierarchyManager("registry-main"))
        yield instances[0], instances[1]
    finally:
        for manager in instances:
            manager.transaction_manager.journal.close()
            manager.storage.close()


def _name() -> str:
    return "registry-" + uuid.uuid4().hex[:12]


def _app(manager: HierarchyManager, verifier: APIKeyVerifier) -> FastAPI:
    app = FastAPI()
    app.state.auth_verifier = verifier
    app.include_router(business_router)
    def current_manager() -> HierarchyManager:
        return manager
    app.dependency_overrides[get_hierarchy_manager] = current_manager
    return app


def test_authenticated_workers_preserve_organizations_and_read_fresh_state(
    managers: tuple[HierarchyManager, HierarchyManager],
) -> None:
    key_manager = KeyManager()
    key = key_manager.create_key("admin", ["chains", "organizations:manage"])
    verifier = APIKeyVerifier({"enabled": True, "key_location": "header", "key_name": "x-api-key",
                               "cache_ttl": 0}, key_manager=key_manager)
    apps = [_app(manager, verifier) for manager in managers]
    first_id, second_id = _name(), _name()
    try:
        with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
            headers = {"x-api-key": key}
            assert first.post("/api/business/organizations", headers=headers,
                              json={"org_id": first_id, "ca_config": {}}).status_code == 200
            assert second.get(f"/api/business/organizations/{first_id}", headers=headers).status_code == 200
            assert second.post("/api/business/organizations", headers=headers,
                               json={"org_id": second_id, "ca_config": {}}).status_code == 200
            assert first.get(f"/api/business/organizations/{second_id}", headers=headers).status_code == 200
        state = managers[0].storage.load_hierarchy_registry()
        assert {first_id, second_id} <= set(state["organizations"])
    finally:
        key_manager.key_cache.clear()
        key_manager.permission_cache.clear()


def test_concurrent_member_registration_retries_with_latest_snapshot(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id = _name()
    first.create_organization(org_id, org_id, ["admin"])
    barrier = threading.Barrier(2)
    errors: list[Exception] = []
    for manager in managers:
        original = manager.storage.save_hierarchy_registry
        def synchronize(save: Any) -> Any:
            initial = True
            def wrapped(state: dict[str, Any], **kwargs: Any) -> bool:
                nonlocal initial
                if initial:
                    initial = False
                    barrier.wait(timeout=5)
                return save(state, **kwargs)
            return wrapped
        monkeypatch.setattr(manager.storage, "save_hierarchy_registry", synchronize(original))
    def register(manager: HierarchyManager, member_id: str) -> None:
        try:
            manager.register_organization_member(
                org_id, member_id, {"user_id": member_id, "org_id": org_id, "role": "member"}, "member",
            )
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=register, args=(manager, member_id))
               for manager, member_id in zip(managers, ("alice", "bob"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert not errors
    assert {"admin", "alice", "bob"} <= set(second.get_organization(org_id).members)


def test_held_channel_refreshes_policy_and_fails_closed_on_read_error(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    first.register_organization_member(
        org_id, "member", {"user_id": "member", "org_id": org_id, "role": "member"}, "member",
    )
    writer = first.create_channel(channel_id, [org_id], {"write": "MEMBER"})
    held = second.get_channel(channel_id)
    assert held is not None
    event = {"entity_id": "item", "event": "created"}
    assert held.submit_event(event, org_id, submitter_user_id="member")
    assert writer.update_channel_policy({"write": "ADMIN"}, [org_id])
    assert not held.submit_event(event, org_id, submitter_user_id="member")
    assert held.event_statistics["total_events"] == 1
    assert second.get_channel(channel_id) is held
    def fail_read() -> None:
        raise RuntimeError("backend unavailable")
    monkeypatch.setattr(second.storage, "load_hierarchy_registry", fail_read)
    with pytest.raises(RuntimeError, match="backend unavailable"):
        held.submit_event(event, org_id, submitter_user_id="admin")
    monkeypatch.setattr(second.storage, "load_hierarchy_registry", lambda: None)
    with pytest.raises(RuntimeError, match="registry is missing"):
        held.submit_event(event, org_id, submitter_user_id="admin")
    assert held.event_statistics["total_events"] == 1


def test_channel_policy_conflict_rolls_back_without_overwriting_remote_policy(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    writer = first.create_channel(channel_id, [org_id], {"write": "MEMBER"})
    held = second.get_channel(channel_id)
    assert held is not None
    save = second.storage.save_hierarchy_registry
    def race(state: dict[str, Any], **kwargs: Any) -> bool:
        assert writer.update_channel_policy({"write": "OPERATOR"}, [org_id])
        return save(state, **kwargs)
    monkeypatch.setattr(second.storage, "save_hierarchy_registry", race)
    assert not held.update_channel_policy({"write": "ADMIN"}, [org_id])
    assert not held.ledger.current_block_events
    assert second.get_channel(channel_id) is held
    assert held.policy.write_policy == "OPERATOR"


def test_legacy_sqlite_registry_is_upgraded_without_losing_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    def factory() -> SQLiteAdapter:
        return SQLiteAdapter(str(tmp_path / "legacy.db"))
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(factory))
    seed = HierarchyManager("legacy-main")
    try:
        seed.create_organization("existing-org", "existing-org", ["admin"])
        legacy = seed.storage.load_hierarchy_registry()
        legacy.pop("_revision")
    finally:
        seed.transaction_manager.journal.close()
        seed.storage.close()
    store = factory()
    store.update_state("hierarchy_registry", orjson.dumps(legacy).decode(), "")
    store.close()
    manager = HierarchyManager("legacy-main")
    try:
        manager.create_organization("legacy-org", "legacy-org")
        state = manager.storage.load_hierarchy_registry()
        assert state["_revision"]
        assert set(state["organizations"]) == {"existing-org", "legacy-org"}
        assert state["organizations"]["existing-org"]["members"]["admin"]["role"] == "admin"
    finally:
        manager.transaction_manager.journal.close()
        manager.storage.close()


def test_backend_rejects_stale_and_missing_registry_revision(
    managers: tuple[HierarchyManager, HierarchyManager],
) -> None:
    first, second = managers
    org_id = _name()
    first.create_organization(org_id, org_id)
    original = first.storage.load_hierarchy_registry()
    revision = original["_revision"]
    state = deepcopy(original)
    state["_revision"] = uuid.uuid4().hex
    assert first.storage.save_hierarchy_registry(state, expected_revision=revision)
    stale = deepcopy(original)
    stale["_revision"] = uuid.uuid4().hex
    assert not second.storage.save_hierarchy_registry(stale, expected_revision=revision)
    assert not second.storage.save_hierarchy_registry(stale)
    assert second.storage.load_hierarchy_registry() == state


def test_http_member_retry_rechecks_admin_after_permission_withdrawal(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id = _name()
    first.create_organization(org_id, org_id, ["admin"])
    key_manager = KeyManager()
    key = key_manager.create_key("admin", ["chains"])
    verifier = APIKeyVerifier({"enabled": True, "key_location": "header", "key_name": "x-api-key",
                               "cache_ttl": 0}, key_manager=key_manager)
    original_save = second.storage.save_hierarchy_registry
    def withdraw_before_save(state: dict[str, Any], **kwargs: Any) -> bool:
        org = first.get_organization(org_id)
        org.members["admin"]["role"] = "member"
        org.members["admin"]["identity"]["role"] = "member"
        assert first._persist_hierarchy_registry()
        return original_save(state, **kwargs)
    monkeypatch.setattr(second.storage, "save_hierarchy_registry", withdraw_before_save)
    try:
        with TestClient(_app(second, verifier)) as client:
            response = client.post(f"/api/business/organizations/{org_id}/members",
                                   headers={"x-api-key": key},
                                   json={"member_id": "unauthorized-member", "role": "member"})
            assert response.status_code == 403, response.text
        assert "unauthorized-member" not in second.get_organization(org_id).members
        assert "unauthorized-member" not in first.storage.load_hierarchy_registry()["organizations"][org_id]["members"]
    finally:
        key_manager.key_cache.clear()
        key_manager.permission_cache.clear()
