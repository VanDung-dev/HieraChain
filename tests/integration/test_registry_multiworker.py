"""Real backend and HTTP contracts for shared registry revisions and access state."""

import os
import threading
import uuid
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.adapters.database import redis_adapter
from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.adapters.database.redis_adapter import RedisStorageAdapter
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.api.business.router import business_router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.core.block import Block
from hierachain.hierarchical import HierarchyManager
from hierachain.hierarchical.channel import Channel
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier
from hierachain.serialization import dumps_json


@pytest.fixture(params=["sqlite", "postgres", "redis"])
def managers(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[HierarchyManager, HierarchyManager]]:
    monkeypatch.chdir(tmp_path)
    backend = request.param
    if backend == "sqlite":
        def cleanup() -> None:
            pass
        def factory() -> Any:
            return SQLiteAdapter(str(tmp_path / "registry.db"))
    elif backend == "postgres":
        url = os.getenv("HRC_TEST_POSTGRES_URL", "")
        if not url:
            pytest.skip("HRC_TEST_POSTGRES_URL is required")
        import psycopg
        from psycopg.conninfo import make_conninfo
        schema = "hrc_registry_" + uuid.uuid4().hex
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{schema}"')
        isolated_url = make_conninfo(url, options=f"-csearch_path={schema}")
        def cleanup() -> None:
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        def factory() -> Any:
            return PostgresAdapter(isolated_url)
    else:
        port = os.getenv("HRC_TEST_REDIS_PORT", "")
        if not port:
            pytest.skip("HRC_TEST_REDIS_PORT is required")
        prefix = "hrc_registry_" + uuid.uuid4().hex
        monkeypatch.setattr(redis_adapter, "_KEY_PREFIX", prefix)
        def factory() -> Any:
            return RedisStorageAdapter(port=int(port), db=14)
        def cleanup() -> None:
            store = factory()
            try:
                keys = list(store.client.scan_iter(match=prefix + ":*"))
                if keys:
                    store.client.delete(*keys)
            finally:
                store.close()
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(factory))
    instances: list[HierarchyManager] = []
    try:
        for _ in range(2):
            instances.append(HierarchyManager("registry-main"))
        yield instances[0], instances[1]
    finally:
        for manager in instances:
            manager.close()
        cleanup()


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
    store.update_state("hierarchy_registry", dumps_json(legacy), "")
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


def test_channel_append_and_finalize_do_not_rewrite_registry_or_old_blocks(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    channel = first.create_channel(channel_id, [org_id])
    other = first.create_channel(_name(), [org_id])
    assert channel.submit_event({"entity_id": "old", "event": "created"}, org_id, submitter_user_id="admin")
    old_block = channel.finalize_block()
    metadata = first.storage.load_hierarchy_registry()
    assert all("ledger" not in saved for saved in metadata["channels"].values())

    def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("A channel append must not serialize history or save registry metadata")

    monkeypatch.setattr(channel.ledger, "snapshot", unexpected)
    monkeypatch.setattr(other.ledger, "snapshot", unexpected)
    serialize = Block.to_dict
    def serialize_new(block: Block) -> dict[str, Any]:
        assert block is not old_block, "Must not reserialize committed history"
        return serialize(block)
    monkeypatch.setattr(Block, "to_dict", serialize_new)
    monkeypatch.setattr(first.storage, "save_hierarchy_registry", unexpected)
    assert channel.submit_event({"entity_id": "new", "event": "created"}, org_id, submitter_user_id="admin")
    assert channel.finalize_block() is not None
    assert first.storage.load_hierarchy_registry() == metadata
    remote = second.get_channel(channel_id)
    assert remote.ledger.height == 2
    assert remote.event_statistics["total_events"] == 2

    calls = []
    load = second.storage.load_channel_records
    def suffix(channel_id: str, *, after_sequence: int = 0) -> dict[str, Any]:
        result = load(channel_id, after_sequence=after_sequence)
        calls.append((after_sequence, len(result["records"])))
        return result
    monkeypatch.setattr(second.storage, "load_channel_records", suffix)
    assert channel.submit_event({"entity_id": "suffix", "event": "created"}, org_id, submitter_user_id="admin")
    second.get_channel(channel_id)
    second.get_channel(channel_id)
    assert calls == [(5, 1), (6, 0)]
    assert remote.event_statistics["total_events"] == 3


def test_appends_to_different_channels_do_not_conflict_on_registry_revision(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id = _name()
    first.create_organization(org_id, org_id, ["admin"])
    channels = [first.create_channel(_name(), [org_id]) for _ in range(2)]
    remote = second.get_channel(channels[1].channel_id)
    barrier = threading.Barrier(2)
    errors = []
    for manager in managers:
        append = manager.storage.append_channel_record
        def synchronized(write: Any) -> Any:
            def wrapped(*args: Any, **kwargs: Any) -> bool:
                barrier.wait(timeout=5)
                return write(*args, **kwargs)
            return wrapped
        monkeypatch.setattr(manager.storage, "append_channel_record", synchronized(append))
    def submit(channel: Channel) -> None:
        try:
            assert channel.submit_event({"entity_id": "item", "event": "created"}, org_id,
                                        submitter_user_id="admin")
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=submit, args=(channel,)) for channel in (channels[0], remote)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert not errors


def test_channel_append_rejects_access_revision_revoked_after_authorization(
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
    append = second.storage.append_channel_record
    def revoke(*args: Any, **kwargs: Any) -> bool:
        assert writer.update_channel_policy({"write": "ADMIN"}, [org_id])
        return append(*args, **kwargs)
    monkeypatch.setattr(second.storage, "append_channel_record", revoke)
    with pytest.raises(RuntimeError, match="persist channel ledger"):
        held.submit_event({"entity_id": "denied", "event": "created"}, org_id, submitter_user_id="member")
    assert held.event_statistics["total_events"] == 0
    assert not held.ledger.current_block_events
    assert not held.submit_event({"entity_id": "denied", "event": "created"}, org_id, submitter_user_id="member")
    assert all(event["entity_id"] != "denied" for event in writer.ledger.current_block_events)


def test_legacy_embedded_channel_ledger_migrates_with_signed_blocks_and_pending_events(
    managers: tuple[HierarchyManager, HierarchyManager],
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    storage = first.storage
    # Construct the old embedded format without initializing a durable channel stream.
    first.storage = None
    try:
        channel = first.create_channel(channel_id, [org_id])
        assert channel.submit_event({"entity_id": "committed", "event": "created"}, org_id,
                                    submitter_user_id="admin")
        block = channel.finalize_block()
        assert channel.submit_event({"entity_id": "pending", "event": "created"}, org_id,
                                    submitter_user_id="admin")
        legacy = first._hierarchy_registry_snapshot()
        legacy.pop("_channel_ledger_version")
        legacy["channels"][channel_id]["ledger"] = channel.ledger.snapshot()
        legacy["channels"] = {channel_id: legacy["channels"][channel_id]}
        legacy["_revision"] = uuid.uuid4().hex
    finally:
        first.storage = storage
    revision = storage.load_hierarchy_registry()["_revision"]
    assert storage.save_hierarchy_registry(legacy, expected_revision=revision)
    restored = second.get_channel(channel_id)
    assert restored.ledger.last_block_hash == block.hash
    assert restored.ledger.current_block_events[0]["entity_id"] == "pending"
    assert restored.event_statistics["total_events"] == 2
    metadata = storage.load_hierarchy_registry()
    assert metadata["_channel_ledger_version"] == 1
    assert "ledger" not in metadata["channels"][channel_id]
    assert restored.submit_event({"entity_id": "after-migration", "event": "created"}, org_id,
                                 submitter_user_id="admin")
    assert restored.finalize_block() is not None
    restarted = HierarchyManager("registry-main")
    try:
        channel = restarted.get_channel(channel_id)
        assert channel.ledger.height == 2
        assert not channel.ledger.current_block_events
        assert channel.event_statistics["total_events"] == 3
    finally:
        restarted.close()


def test_channel_refresh_fails_closed_on_missing_durable_suffix(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    writer = first.create_channel(channel_id, [org_id])
    held = second.get_channel(channel_id)
    assert writer.submit_event({"entity_id": "durable", "event": "created"}, org_id, submitter_user_id="admin")
    def missing(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"revision": 2, "records": []}
    monkeypatch.setattr(second.storage, "load_channel_records", missing)
    with pytest.raises(RuntimeError, match="ledger suffix"):
        held.submit_event({"entity_id": "not-accepted", "event": "created"}, org_id, submitter_user_id="admin")
    assert held.event_statistics["total_events"] == 0
    assert not held.ledger.current_block_events


def test_invalid_signed_suffix_leaves_ledger_and_counters_unchanged(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    writer = first.create_channel(channel_id, [org_id])
    held = second.get_channel(channel_id)
    assert writer.submit_event({"entity_id": "durable", "event": "created"}, org_id, submitter_user_id="admin")
    assert writer.finalize_block() is not None
    load = second.storage.load_channel_records
    def tamper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = load(*args, **kwargs)
        result["records"][-1]["data"]["previous_hash"] = "altered"
        return result
    with monkeypatch.context() as patch:
        patch.setattr(second.storage, "load_channel_records", tamper)
        with pytest.raises(RuntimeError, match="signed channel block history"):
            held.get_channel_info()
        assert held.ledger.height == 0
        assert not held.ledger.current_block_events
        assert held.event_statistics["total_events"] == 0
    held.get_channel_info()
    assert held.ledger.height == 1
    assert held.event_statistics["total_events"] == 1


@pytest.mark.parametrize("finalize", [False, True])
def test_same_channel_concurrent_writers_ack_only_one_durable_change(
    managers: tuple[HierarchyManager, HierarchyManager], monkeypatch: pytest.MonkeyPatch, finalize: bool,
) -> None:
    first, second = managers
    org_id, channel_id = _name(), _name()
    first.create_organization(org_id, org_id, ["admin"])
    channel = first.create_channel(channel_id, [org_id])
    if finalize:
        assert channel.submit_event({"entity_id": "pending", "event": "created"}, org_id,
                                    submitter_user_id="admin")
    channels = [channel, second.get_channel(channel_id)]
    barrier = threading.Barrier(2)
    accepted = []
    originals = []
    for manager in managers:
        append = manager.storage.append_channel_record
        originals.append(append)
        def synchronized(write: Any) -> Any:
            def wrapped(*args: Any, **kwargs: Any) -> bool:
                barrier.wait(timeout=5)
                return write(*args, **kwargs)
            return wrapped
        monkeypatch.setattr(manager.storage, "append_channel_record", synchronized(append))
    def change(channel: Channel, entity_id: str) -> None:
        try:
            if finalize:
                accepted.append(channel.finalize_block() is not None)
            else:
                accepted.append(channel.submit_event({"entity_id": entity_id, "event": "created"}, org_id,
                                                      submitter_user_id="admin"))
        except RuntimeError:
            accepted.append(False)
    threads = [threading.Thread(target=change, args=(channel, str(index)))
               for index, channel in enumerate(channels)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(accepted) == [False, True]
    for manager, append in zip(managers, originals):
        monkeypatch.setattr(manager.storage, "append_channel_record", append)
        recovered = manager.get_channel(channel_id)
        assert recovered.event_statistics["total_events"] == 1
        assert recovered.ledger.height == int(finalize)
        assert len(recovered.ledger.current_block_events) == int(not finalize)
