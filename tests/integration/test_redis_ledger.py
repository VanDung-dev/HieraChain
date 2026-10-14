"""Opt-in signed ledger validation against a disposable Redis Docker instance."""

import os
import subprocess
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import redis

from hierachain.adapters.database.redis_adapter import RedisStorageError
from hierachain.adapters.database.redis_ledger import RedisLedgerAdapter
from hierachain.config.settings import settings
from hierachain.consensus.ordering.storage import (
    OrderingStorageHandler,
    _block_from_dict,
)
from hierachain.core.block import Block
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.identity_loader import (
    load_node_identity,
    load_trusted_block_keys,
)
from hierachain.security.verify.block_verifier import sign_block
from hierachain.serialization import dumps_json

pytestmark = pytest.mark.integration


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[RedisLedgerAdapter, None, None]:
    url = os.getenv("HRC_REDIS_LEDGER_TEST_URL")
    if not url:
        pytest.skip("Set HRC_REDIS_LEDGER_TEST_URL to a disposable Redis instance")
    parsed = urlsplit(url)
    monkeypatch.setattr(settings, "REDIS_HOST", parsed.hostname)
    monkeypatch.setattr(settings, "REDIS_PORT", parsed.port or 6379)
    monkeypatch.setattr(settings, "REDIS_DB", int(parsed.path.lstrip("/") or "0"))
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "redis")
    monkeypatch.chdir(tmp_path)
    client = redis.from_url(url, decode_responses=True)
    before = set(client.scan_iter(match="hierachain:*"))
    adapter = RedisLedgerAdapter()
    try:
        yield adapter
    finally:
        adapter.close()
        added = set(client.scan_iter(match="hierachain:*")) - before
        if added:
            client.delete(*added)
        client.close()


def signed_block(name: str, index: int = 0, previous_hash: str = "0", value: str = "original") -> dict[str, Any]:
    identity = load_node_identity()
    assert identity is not None
    block = Block(index, [{
        "entity_id": "E-1", "event": "received", "timestamp": 1.0,
        "event_id": f"{name}-{index}", "details": {"value": value},
    }], timestamp=1.0, previous_hash=previous_hash)
    sign_block(block, identity.node_id, identity.signing_keypair)
    return {**block.to_dict(), "chain_name": name}


def test_signed_round_trip_and_queries(ledger: RedisLedgerAdapter) -> None:
    name = f"ledger:{uuid.uuid4().hex}"
    data = signed_block(name)
    handler = OrderingStorageHandler({"storage_backend": "redis", "chain_name": name})
    try:
        block = _block_from_dict(data, handler.trusted_public_keys)
        assert handler.save_block(block, name)[0] == 1
        loaded = handler.get_blocks_from_db(0)[0]
        assert loaded.to_dict() == block.to_dict()
        assert loaded.signature == data["signature"]
        assert ledger.get_event_by_id(data["events"][0]["event_id"])["block_hash"] == data["hash"]
        assert ledger.get_entity_events("E-1", name) == data["events"]
        assert ledger.get_events_by_type("received", name) == data["events"]
    finally:
        handler.close()


def test_retries_conflicts_gaps_and_links(ledger: RedisLedgerAdapter) -> None:
    name = f"ledger-{uuid.uuid4().hex}"
    first = signed_block(name)
    assert ledger.save_block(first)
    assert ledger.save_block(first)
    assert not ledger.save_block(signed_block(name, value="conflicting"))
    assert not ledger.save_block(signed_block(name, 2, first["hash"]))
    assert not ledger.save_block(signed_block(name, 1, "wrong-parent"))
    second = signed_block(name, 1, first["hash"])
    assert ledger.save_block(second)
    assert [block["hash"] for block in ledger.get_blocks_from_index(0, name)] == [first["hash"], second["hash"]]
    assert ledger.get_latest_block(name)["index"] == 1


def test_concurrent_competing_appends_have_one_winner(ledger: RedisLedgerAdapter) -> None:
    name = f"ledger-{uuid.uuid4().hex}"
    candidates = [signed_block(name, value=str(i)) for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as workers:
        accepted = list(workers.map(ledger.save_block, candidates))
    assert accepted.count(True) == 1
    assert len(ledger.get_blocks_from_index(0, name)) == 1


@pytest.mark.parametrize("damage", ["payload", "signature", "json", "index"])
def test_persisted_corruption_is_rejected(ledger: RedisLedgerAdapter, damage: str) -> None:
    name = f"ledger-{uuid.uuid4().hex}"
    data = signed_block(name)
    assert ledger.save_block(data)
    bad = deepcopy(data)
    if damage == "payload":
        bad["events"][0]["details"]["value"] = "tampered"
    elif damage == "signature":
        bad["signature"] = "00" * 64
    elif damage == "index":
        bad["index"] = 99
    ledger.client.lset(ledger._blocks_key(name), 0, "{invalid" if damage == "json" else dumps_json(bad))
    with pytest.raises((RedisStorageError, ValueError)):
        rows = ledger.get_blocks_from_index(0, name)
        _block_from_dict(rows[0], load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE))


def test_runtime_policy_change_and_expiring_history_are_rejected(ledger: RedisLedgerAdapter) -> None:
    name = f"ledger-{uuid.uuid4().hex}"
    data = signed_block(name)
    ledger.client.config_set("appendfsync", "everysec")
    try:
        with pytest.raises(RedisStorageError, match="requires AOF"):
            ledger.save_block(data)
    finally:
        ledger.client.config_set("appendfsync", "always")
    assert ledger.get_block_by_index(0, name) is None
    assert ledger.save_block(data)
    ledger.client.expire(ledger._blocks_key(name), 60)
    with pytest.raises(RedisStorageError, match="must not expire"):
        ledger.save_block(signed_block(name, 1, data["hash"]))


def test_hierarchy_subchain_and_mainchain_proof_recover(ledger: RedisLedgerAdapter) -> None:
    manager = HierarchyManager()
    try:
        assert manager.create_sub_chain("redis-orders", "generic")
        sub = manager.sub_chains["redis-orders"]
        assert isinstance(sub.ordering_service.storage_handler.storage, RedisLedgerAdapter)
        sub.start_operation("E-1", "received", {"value": "durable"})
        sub.complete_operation("E-1", "received", {"value": "durable"})
        sub.flush_pending_and_finalize()
        assert sub.submit_proof_to_main(manager.main_chain)
        sub.flush_pending_and_finalize()
        original_sub = [block.to_dict() for block in sub.chain]
        original_main = [block.to_dict() for block in manager.main_chain.chain]
    finally:
        manager.close()
    restored = HierarchyManager()
    try:
        assert [block.to_dict() for block in restored.sub_chains["redis-orders"].chain] == original_sub
        assert [block.to_dict() for block in restored.main_chain.chain] == original_main
        assert restored.main_chain.proof_count >= 1
        assert restored.storage.get_chain_statistics("redis-orders")["total_events"] >= 2
    finally:
        restored.close()


def test_acknowledged_blocks_survive_redis_sigkill(ledger: RedisLedgerAdapter) -> None:
    container = os.getenv("HRC_REDIS_LEDGER_TEST_CONTAINER", "")
    if not container.startswith("hrc-ledger-test-"):
        pytest.skip("Set HRC_REDIS_LEDGER_TEST_CONTAINER to the disposable hrc-ledger-test-* container")
    name = f"ledger-{uuid.uuid4().hex}"
    first = signed_block(name)
    second = signed_block(name, 1, first["hash"])
    assert ledger.save_block(first) and ledger.save_block(second)
    before = ledger.get_blocks_from_index(0, name)
    assert ledger.save_hierarchy_registry({"_revision": "crash-revision", "channels": {}, "_channel_ledger_version": 1})
    ledger.close()
    subprocess.run(["rtk", "proxy", "docker", "kill", "--signal=KILL", container], check=True, timeout=30)
    subprocess.run(["rtk", "proxy", "docker", "start", container], check=True, timeout=30)
    subprocess.run(["rtk", "proxy", "docker", "exec", container, "redis-cli", "PING"], check=True, timeout=30)
    restored = RedisLedgerAdapter()
    try:
        assert restored.get_blocks_from_index(0, name) == before
        assert restored.load_hierarchy_registry()["_revision"] == "crash-revision"
        for row in restored.get_blocks_from_index(0, name):
            assert _block_from_dict(row, load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)).signature
    finally:
        restored.close()
