"""Regression tests for confirmed findings in issues.md."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import deque
from contextlib import nullcontext
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import pytest


def test_hc001_failed_block_save_does_not_advance_state() -> None:
    from collections import deque

    from hierachain.consensus.ordering.storage import OrderingStorageHandler
    from hierachain.hierarchical.sub_chain.block import (
        _process_and_finalize_single_block,
    )

    storage = object.__new__(OrderingStorageHandler)
    storage.storage = SimpleNamespace(save_block=lambda _block_data: False)
    storage.block_history = deque(maxlen=4)
    storage.last_block = None
    storage.processed_events = {}

    actions: list[str] = []
    block = SimpleNamespace(
        index=0,
        previous_hash="",
        hash="",
        calculate_hash=lambda: "block-hash",
    )
    sub_chain = SimpleNamespace(
        name="test-chain",
        block_processing_lock=nullcontext(),
        get_latest_block=lambda: SimpleNamespace(index=2, hash="previous-hash"),
        consensus=SimpleNamespace(finalize_block=lambda current, _name: current),
        ordering_service=SimpleNamespace(storage_handler=storage),
        add_block=lambda _block: actions.append("add") or True,
        world_state=SimpleNamespace(
            apply_block=lambda _block: actions.append("apply")
        ),
        auto_submit_proof_if_needed=lambda: actions.append("proof"),
    )

    result = _process_and_finalize_single_block(sub_chain, block)

    assert result is False
    assert actions == []


def test_hc002_database_contains_finalized_block_after_ordering_commit() -> None:
    from hierachain.consensus.ordering.block_manager import OrderingBlockManager
    from hierachain.consensus.ordering.types import OrderingStatus
    from hierachain.consensus.proof_of_authority import ProofOfAuthority
    from hierachain.core.block import Block
    from hierachain.hierarchical.sub_chain.block import (
        _process_and_finalize_single_block,
    )

    class UniqueIndexStorage:
        def __init__(self) -> None:
            self.rows: dict[tuple[str, int], dict[str, object]] = {}
            self.attempts: list[dict[str, object]] = []

        def save_block(self, block_data: dict[str, object]) -> bool:
            self.attempts.append(block_data.copy())
            key = (str(block_data["chain_name"]), int(block_data["index"]))
            self.rows[key] = block_data.copy()
            return True

    from hierachain.consensus.ordering.storage import OrderingStorageHandler

    genesis = Block(index=0, events=[], previous_hash="0")
    adapter = UniqueIndexStorage()
    storage = object.__new__(OrderingStorageHandler)
    storage.storage = adapter
    storage.block_history = deque(maxlen=16)
    storage.last_block = genesis
    storage.processed_events = {}
    storage.chain_name = "test-chain"

    service = SimpleNamespace(
        blocks_created=1,
        storage_handler=storage,
        block_builder=SimpleNamespace(),
        metrics=SimpleNamespace(record_block_created=lambda *_args: None),
        status=OrderingStatus.ACTIVE,
        config={"chain_name": "test-chain"},
        journal=SimpleNamespace(log_event=lambda _event: True),
        commit_queue=Queue(),
    )
    raw_block = Block(
        index=0,
        events=[{"entity_id": "entity-1", "event": "created", "timestamp": 1.0}],
        previous_hash="",
    )
    OrderingBlockManager(service).commit_block(raw_block)

    consensus = ProofOfAuthority("test-poa")
    consensus.add_authority("test-chain", {"role": "sub_chain_authority"})
    finalized: list[Block] = []
    sub_chain = SimpleNamespace(
        name="test-chain",
        block_processing_lock=nullcontext(),
        get_latest_block=lambda: genesis,
        consensus=consensus,
        ordering_service=SimpleNamespace(storage_handler=storage),
        add_block=lambda block: finalized.append(block) or True,
        world_state=SimpleNamespace(apply_block=lambda _block: None),
        auto_submit_proof_if_needed=lambda: None,
    )

    assert _process_and_finalize_single_block(sub_chain, raw_block) is True
    assert len(adapter.attempts) == 2
    assert adapter.attempts[0]["hash"] != adapter.attempts[1]["hash"]
    assert adapter.rows[("test-chain", 1)]["hash"] == adapter.attempts[1]["hash"]
    assert finalized[0].hash == adapter.rows[("test-chain", 1)]["hash"]
    assert list(storage.block_history) == finalized


def test_hc003_unauthenticated_product_compose_is_loopback_only() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker/docker-compose.yml").read_text(encoding="utf-8")
    service_blocks = re.findall(
        r"(?ms)^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", compose
    )

    unauthenticated_product_node = any(
        re.search(r"(?m)^      - HRC_ENV=product$", block)
        and re.search(r"(?m)^      - HRC_AUTH_ENABLED=false$", block)
        for _name, block in service_blocks
    )
    gateway = re.search(r"(?ms)^  gateway:\n(.*?)(?=^  [\w-]+:|\Z)", compose)
    assert gateway is not None
    if unauthenticated_product_node:
        assert '"127.0.0.1:2660:80"' in gateway.group(1)


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


def test_hc005_websocket_with_auth_connects_without_request_typeerror() -> None:
    root = Path(__file__).resolve().parents[2]
    script = """
from fastapi.testclient import TestClient
from hierachain.api.server import create_app

client = TestClient(create_app())
try:
    with client.websocket_connect('/ws') as websocket:
        assert isinstance(websocket.receive_json(), dict)
finally:
    client.close()
"""
    env = os.environ.copy()
    env.update(
        HRC_ENV="product",
        HRC_AUTH_ENABLED="true",
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
    service.status = OrderingStatus.ACTIVE
    service.metrics = SimpleNamespace(record_received=lambda: None)
    service.pending_events = {}
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
