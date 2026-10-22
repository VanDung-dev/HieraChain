import asyncio
from typing import Any

import pytest
import zmq

from hierachain.network.network_client import NetworkClient, NetworkClientConfig
from hierachain.network.zmq_transport import NetworkError, ZmqNode


@pytest.mark.asyncio
async def test_bind_failure_closes_transport_resources() -> None:
    blocker = ZmqNode("blocker", 0)
    await blocker.start()
    assert blocker.router is not None
    port = int(blocker.router.getsockopt(zmq.LAST_ENDPOINT).decode().rsplit(":", 1)[1])
    node = ZmqNode("blocked", port)
    try:
        with pytest.raises(NetworkError, match="Address already in use"):
            await node.start()
        assert node.ctx.closed
        assert node.router is not None
        assert node.router.closed
        await node.stop()
    finally:
        await node.stop()
        await blocker.stop()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_client_can_retry_after_bind_failure() -> None:
    blocker = ZmqNode("blocker", 0)
    await blocker.start()
    assert blocker.router is not None
    port = int(blocker.router.getsockopt(zmq.LAST_ENDPOINT).decode().rsplit(":", 1)[1])
    client = NetworkClient(NetworkClientConfig(enabled=True, node_id="retry", port=port))
    try:
        assert await client.start() is False
        assert not client.is_running
        assert client._zmq_node is None
        await client.stop()
        await blocker.stop()
        await asyncio.sleep(0)

        assert await client.start() is True
        assert client.is_running
        transport = client._zmq_node
        assert await client.start() is True
        assert client._zmq_node is transport
        await client.stop()
        await client.stop()
        assert transport.ctx.closed
        assert client._zmq_node is None
        assert not client.is_running
    finally:
        if client._zmq_node is not None:
            await client._zmq_node.stop()
        await client.stop()
        await blocker.stop()
        await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("setup_method", ["set_handler", "register_peer"])
async def test_client_cleans_up_when_setup_fails(
    monkeypatch: pytest.MonkeyPatch, setup_method: str,
) -> None:
    nodes: list[ZmqNode] = []

    def fail_setup(node: ZmqNode, *args: Any, **kwargs: Any) -> None:
        nodes.append(node)
        raise RuntimeError("setup failed")

    monkeypatch.setattr(ZmqNode, setup_method, fail_setup)
    client = NetworkClient(NetworkClientConfig(
        enabled=True, node_id="setup-failure", seed_nodes=["peer@127.0.0.1:1"],
    ))
    try:
        assert await client.start() is False
        assert nodes[0].ctx.closed
        assert client._zmq_node is None
        assert not client.is_running
        await client.stop()
    finally:
        for node in nodes:
            await node.stop()


@pytest.mark.asyncio
async def test_stop_cleans_transport_that_never_started() -> None:
    node = ZmqNode("unstarted", 0)
    client = NetworkClient(NetworkClientConfig(enabled=True))
    client._zmq_node = node
    try:
        await client.stop()
        await client.stop()
        assert node.ctx.closed
        assert client._zmq_node is None
        assert not client.is_running
    finally:
        await node.stop()
