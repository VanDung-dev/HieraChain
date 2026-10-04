"""Regression tests for confirmed findings in issues.md."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("failure", ["consensus", "storage"])
def test_hc001_failed_block_save_does_not_advance_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    from unittest.mock import Mock

    from hierachain.consensus.ordering.types import OrderingStatus
    from hierachain.core.block import Block
    from hierachain.hierarchical.sub_chain import base as sub_chain_base
    from hierachain.hierarchical.sub_chain.base import SubChain

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    chain = SubChain("failed_commit", config={"db_url": f"sqlite:///{tmp_path / 'chain.db'}"})
    service = chain.ordering_service
    try:
        chain.consensus.config["block_interval"] = 0.0
        save = Mock(wraps=service.storage_handler.storage.save_block)
        monkeypatch.setattr(service.storage_handler.storage, "save_block", save)
        if failure == "consensus":
            monkeypatch.setattr(type(chain.consensus), "validate_block", lambda *_args: False)
        else:
            save.return_value = False
        block = Block(
            index=0, events=[{"entity_id": "E1", "event": "updated", "timestamp": time.time()}],
            previous_hash="",
        )
        with pytest.raises((ValueError, RuntimeError), match="Consensus rejected|Storage adapter rejected"):
            service.processor.block_manager.commit_block(block)
        assert save.call_count == (0 if failure == "consensus" else 1)
        assert service.blocks_created == 1
        assert service.commit_queue.empty()
        assert service.storage_handler.last_block.index == 0
        assert service.status is OrderingStatus.MAINTENANCE
        assert len(chain.chain) == 1
        assert not chain.world_state.get_entity_state("E1")
        assert [block.index for block in service.storage_handler.get_blocks_from_db(0)] == [0]
    finally:
        chain.shutdown()


def test_hc002_database_contains_finalized_block_after_ordering_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import Mock

    from hierachain.config.settings import settings
    from hierachain.core.block import Block
    from hierachain.hierarchical.sub_chain import base as sub_chain_base
    from hierachain.hierarchical.sub_chain.base import SubChain

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.02)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    config = {"db_url": f"sqlite:///{tmp_path / 'chain.db'}"}
    chain = SubChain("lagged_consumer", config=config)
    try:
        service = chain.ordering_service
        storage = service.storage_handler
        save = Mock(wraps=storage.save_block)
        monkeypatch.setattr(storage, "save_block", save)
        # Producer advances three blocks while the consumer still has only genesis.
        for index in range(3):
            service.processor.block_manager.commit_block(Block(
                index=0, previous_hash="",
                events=[{"entity_id": f"E{index}", "event": "updated", "timestamp": time.time()}],
            ))
        persisted = storage.get_blocks_from_db(0)
        snapshots = [block.to_dict() for block in persisted]
        assert [block.index for block in persisted] == [0, 1, 2, 3]
        for previous, block in zip(persisted, persisted[1:]):
            assert block.previous_hash == previous.hash
            assert block.timestamp - previous.timestamp >= 0.01
            assert chain.consensus.validate_block(block, previous)
            finalization = block.to_event_list()[-1]
            assert finalization["event"] == "consensus_finalization"
            assert not finalization["details"]["authority_signature"].startswith("valid_")
            assert block.signature
        assert len(chain.chain) == 1
        assert chain.finalize_sub_chain_block()["block_index"] == 3
        assert save.call_count == 3  # Consumer must never re-finalize, re-sign or rewrite.
        assert [block.to_dict() for block in storage.get_blocks_from_db(0)] == snapshots
        assert [block.to_dict() for block in chain.chain] == snapshots
        assert chain.is_chain_valid()
    finally:
        chain.shutdown()
    reopened = SubChain("lagged_consumer", config=config)
    try:
        assert [block.to_dict() for block in reopened.chain] == snapshots
        assert reopened.ordering_service.blocks_created == 4
        assert reopened.ordering_service.commit_queue.empty()
        assert reopened.is_chain_valid()
    finally:
        reopened.shutdown()


def test_hc003_product_compose_requires_node_auth() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker/docker-compose.yml").read_text(encoding="utf-8")
    service_blocks = re.findall(
        r"(?ms)^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", compose
    )

    product_nodes = [
        block for _name, block in service_blocks
        if re.search(r"(?m)^      - HRC_ENV=product$", block)
    ]
    assert len(product_nodes) == 4
    assert all(
        re.search(r"(?m)^      - HRC_AUTH_ENABLED=true$", block)
        and re.search(r"(?m)^      - HRC_API_KEYS_FILE=/run/secrets/hrc_api_keys$", block)
        and re.search(r"(?m)^    secrets:\n      - hrc_api_keys$", block)
        for block in product_nodes
    )


def test_hc004_endpoint_verifier_can_validate_key_from_app_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hierachain.security.verify.api_key_verifier as auth_module
    from hierachain.api import server

    class NoopBruteForceProtector:
        def __init__(self, _config: dict) -> None:
            pass

    settings = server.get_settings()
    settings.AUTH_ENABLED = True
    settings.get_auth_config = lambda: {"enabled": True, "brute_force": {}}
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth_module, "BruteForceProtector", NoopBruteForceProtector
    )

    app = server.create_app()
    app_verifier = app.state.auth_verifier
    endpoint_verifier = auth_module._get_active_verifier(SimpleNamespace(app=app))
    api_key = app_verifier.key_manager.create_key(
        "test-user", ["events"]
    )

    assert endpoint_verifier.key_manager.is_valid(api_key) is True


def test_hc004_created_key_permission_is_visible_to_endpoint_checker() -> None:
    from hierachain.security.verify.api_key_verifier import (
        APIKeyVerifier,
        ResourcePermissionChecker,
    )

    verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "x-api-key",
            "cache_ttl": 0,
            "brute_force": {},
        }
    )
    api_key = verifier.key_manager.create_key("test-user", ["events"])
    context = verifier._build_success_context(api_key, api_key[:8])

    assert ResourcePermissionChecker.has_permission(context, "events") is True


def test_hc005_websocket_with_auth_connects_without_request_typeerror(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    api_key = "hrc_" + "a" * 40
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(
        json.dumps({api_key: {"user_id": "test_user", "permissions": ["chains", "events"]}}),
        encoding="utf-8",
    )
    script = """
import os
from fastapi.testclient import TestClient
from hierachain.api.server import create_app

client = TestClient(create_app())
try:
    with client.websocket_connect('/ws', headers={'X-API-Key': os.environ['HRC_API_KEY']}) as websocket:
        assert isinstance(websocket.receive_json(), dict)
finally:
    client.close()
"""
    env = os.environ.copy()
    env.update(
        HRC_ENV="product",
        HRC_AUTH_ENABLED="true",
        HRC_API_KEYS_FILE=str(key_file),
        HRC_API_KEY=api_key,
        HRC_P2P_ENABLED="false",
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_hc006_journal_rejection_does_not_accept_or_queue_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hierachain.consensus.ordering.service as service_module
    from hierachain.consensus.ordering.service import OrderingService
    from hierachain.consensus.ordering.types import OrderingStatus

    service = object.__new__(OrderingService)
    service._commit_lock = threading.RLock()
    service.enqueue_timeout = 1.0
    service.should_stop = threading.Event()
    service.status = OrderingStatus.ACTIVE
    service.metrics = SimpleNamespace(record_received=lambda: None)
    service.pending_events = {}
    service.storage_handler = SimpleNamespace(processed_events={})
    service.event_pool = Queue()
    service.journal = SimpleNamespace(log_event=lambda _event: False)
    monkeypatch.setattr(service_module, "generate_event_id", lambda *_args: "event-1")

    with pytest.raises(RuntimeError, match="journal"):
        service.receive_event(
            {"entity_id": "entity-1", "event": "created"},
            "test-channel",
            "test-org",
        )

    assert service.pending_events == {}
    assert service.event_pool.empty()
