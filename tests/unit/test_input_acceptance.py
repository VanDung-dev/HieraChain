"""Regression checks for the implemented P2 input paths."""

import asyncio
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hierachain.adapters.database.redis_rate_limiter import RedisRateLimiter
from hierachain.api.graphql.schema import schema
from hierachain.api.middleware import add_rate_limit
from hierachain.core.blockchain import Blockchain
from hierachain.core.utils import sanitize_metadata_for_main_chain
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.network.network_client import (
    PEER_TIMEOUT,
    NetworkClient,
    NetworkClientConfig,
)
from hierachain.network.zmq_transport import MAX_REPLAY_ENTRIES, ZmqNode
from hierachain.sdk.async_client import HieraChainAsyncClient
from hierachain.sdk.client import HieraChainClient
from hierachain.sdk.exceptions import HieraChainAPIError
from hierachain.sdk.types import CircuitBreaker, CircuitState, HieraChainClientConfig


def test_database_adapter_package_exports_remain_available() -> None:
    from hierachain.adapters.database import PostgresAdapter, SQLBase, SQLiteAdapter

    assert issubclass(PostgresAdapter, SQLBase)
    assert issubclass(SQLiteAdapter, SQLBase)


def test_sdk_sync_exposes_400_without_retry() -> None:
    client = HieraChainClient(HieraChainClientConfig(max_retries=3))
    response = requests.Response()
    response.status_code = 400
    response._content = b'{"detail":"invalid"}'
    client._session = Mock()
    client._session.request.return_value = response

    with pytest.raises(HieraChainAPIError) as exc:
        client.submit_event("chain", {"entity_id": "e"})

    assert exc.value.status_code == 400
    client._session.request.assert_called_once()


def test_sdk_sync_does_not_retry_ambiguous_post_failure() -> None:
    client = HieraChainClient(HieraChainClientConfig(max_retries=3))
    client._session = Mock()
    client._session.request.side_effect = requests.ConnectionError("response lost")

    with pytest.raises(HieraChainAPIError):
        client.submit_event("chain", {"entity_id": "e"})

    client._session.request.assert_called_once()


@pytest.mark.asyncio
async def test_sdk_async_exposes_400_and_does_not_retry_post() -> None:
    client = HieraChainAsyncClient(HieraChainClientConfig(max_retries=3))
    response = Mock(status=400, headers={})
    with pytest.raises(HieraChainAPIError) as exc:
        await client._handle_response(response)
    assert exc.value.status_code == 400

    client._execute_request = AsyncMock(side_effect=asyncio.TimeoutError("response lost"))
    with pytest.raises(HieraChainAPIError):
        await client.submit_event("chain", {"entity_id": "e"})
    client._execute_request.assert_awaited_once()


def test_sdk_half_open_admits_one_concurrent_probe() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
    breaker.record_failure()
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: breaker.acquire_request(), range(32)))
    assert results.count(CircuitState.HALF_OPEN) == 1
    assert results.count(None) == 31


def test_invalid_event_never_enters_pending_queue() -> None:
    chain = Blockchain("p2-validation")
    with pytest.raises(ValueError, match="Invalid event structure"):
        chain.add_event({"entity_id": "e", "event": "created", "timestamp": "wrong"})
    assert chain.pending_events == []


def test_main_chain_metadata_sanitizes_nested_lists() -> None:
    metadata = {"summary": [{"safe": 1, "raw_data": "secret"}, [{"internal_data": "secret", "ok": 2}]]}
    assert sanitize_metadata_for_main_chain(metadata) == {"summary": [{"safe": 1}, [{"ok": 2}]]}


def test_main_chain_registration_never_exposes_raw_metadata() -> None:
    chain = MainChain("p2-main")
    metadata = {"summary": [{"safe": 1, "raw_data": "secret"}]}
    assert chain.register_sub_chain("p2-sub", metadata)
    assert chain.get_sub_chain_summary("p2-sub")["metadata"] == {"summary": [{"safe": 1}]}
    assert chain.pending_events[-1]["details"]["metadata"] == {"summary": [{"safe": 1}]}


@pytest.mark.parametrize("query,variables", [
    ('{ blocks(chainName: "test", limit: 10000) { index } events(chainName: "test", limit: 10000) { entityId } }', None),
    ('query($n: Int!) { blocks(chainName: "test", limit: $n) { index } events(chainName: "test", limit: $n) { entityId } }', {"n": 10000}),
])
def test_graphql_bounds_literal_and_variable_limits(query: str, variables: dict | None) -> None:
    from hierachain.api.ledger import depds

    blocks = [SimpleNamespace(index=i, hash=str(i), previous_hash="", timestamp=1.0,
                              nonce="", metadata=None,
                              events=[SimpleNamespace(entity_id=str(i), event_type="created", timestamp=1.0)])
              for i in range(150)]
    manager = Mock()
    manager.get_all_sub_chains.return_value = {"test": SimpleNamespace(chain=blocks)}
    with patch.object(depds, "_hierarchy_manager", manager):
        result = schema.execute(query, variable_values=variables)
    assert result.errors is None
    assert len(result.data["blocks"]) == 100
    assert len(result.data["events"]) == 100


@pytest.mark.asyncio
async def test_redis_rate_check_does_not_block_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow_check(_self: RedisRateLimiter, _ip: str) -> tuple[bool, int]:
        entered.set()
        release.wait(timeout=1)
        return True, 1

    monkeypatch.setattr(RedisRateLimiter, "check", slow_check)
    settings = SimpleNamespace(RATE_LIMIT_ENABLED=True, RATE_LIMIT_BACKEND="redis",
                               RATE_LIMIT_REQUESTS_PER_MINUTE=2, REDIS_HOST="127.0.0.1",
                               REDIS_PORT=1, REDIS_DB=0, TRUSTED_PROXIES="")
    app = FastAPI()
    add_rate_limit(app, settings, set())

    @app.get("/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        request = asyncio.create_task(client.get("/probe"))
        try:
            assert await asyncio.to_thread(entered.wait, 0.5)
            assert not request.done()
        finally:
            release.set()
        assert (await asyncio.wait_for(request, timeout=1)).status_code == 200


def test_replay_buffer_has_hard_cap() -> None:
    node = ZmqNode("p2-replay", 0)
    now = time.time()
    try:
        for i in range(MAX_REPLAY_ENTRIES):
            assert node._is_valid_replay({"timestamp": now, "nonce": str(i)})
        assert not node._is_valid_replay({"timestamp": now, "nonce": "overflow"})
        assert len(node.replay_buffer) == MAX_REPLAY_ENTRIES
    finally:
        node.ctx.term()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.asyncio
async def test_live_zmq_unregister_and_peer_liveness() -> None:
    a = NetworkClient(NetworkClientConfig(enabled=True, node_id="p2-a", port=_free_port()))
    b = NetworkClient(NetworkClientConfig(enabled=True, node_id="p2-b", port=_free_port()))
    received = asyncio.Event()
    try:
        assert await a.start()
        assert await b.start()
        a.register_peer("p2-b", b._zmq_node.address)
        b.register_peer("p2-a", a._zmq_node.address)
        b._peers["p2-a"]._last_activity -= PEER_TIMEOUT + 1
        assert b.get_network_status().healthy_peers == 0

        async def on_message(message: dict, sender_id: str) -> None:
            await b._on_message_received(message, sender_id)
            received.set()

        b._zmq_node.set_handler(on_message)
        assert await a.send_direct("p2-b", {"type": "data", "timestamp": time.time(), "nonce": "p2-live"})
        await asyncio.wait_for(received.wait(), timeout=3)
        assert b.get_network_status().healthy_peers == 1
        assert "p2-b" in a._zmq_node.dealer_pool
        a.unregister_peer("p2-b")
        assert "p2-b" not in a._zmq_node.dealer_pool
        assert not await a.send_direct("p2-b", {"type": "data", "timestamp": time.time(), "nonce": "after"})
    finally:
        await a.stop()
        await b.stop()
