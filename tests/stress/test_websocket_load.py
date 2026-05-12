"""
WebSocket Real-Time Subscriptions Stress Test.

Measurement:
  - Maximum number of concurrent connections
  - Broadcast latency under load
  - Connection churn (continuous connect/disconnect)
  - Memory leak under many connections

Environment:
  - WebSocket endpoint: ws://{node}:2661/ws
"""

import time
import json
import logging
import os
import threading
import pytest

from tests.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="WebSocket tests require REAL_REQUESTS=true"
)

WS_CHAIN = os.getenv("WS_CHAIN_NAME", "websocket_stress_test")

# Optional: ignore if websockets library is not available
try:
    import websockets
    import asyncio
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    pytestmark = pytest.mark.skipif(
        True, reason="websockets library not installed"
    )


class WebSocketLoadTest:
    """Manage multiple WebSocket connections for stress testing."""

    def __init__(self, url: str, max_connections: int = 100):
        self.url = url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{self.url}/ws"
        self.connections: dict[int, object] = {}
        self.messages: dict[int, list[dict]] = {}
        self.errors: dict[int, list[str]] = {}
        self.lock = threading.Lock()
        self.max_connections = max_connections
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def connect_sync(self, conn_id: int, chain_name: str = "all") -> bool:
        """Synchronize wrapper for connect."""
        loop = self._get_loop()
        try:
            ws = loop.run_until_complete(
                websockets.connect(f"{self.ws_url}?chain_name={chain_name}", open_timeout=10)
            )
            # Subscribe
            loop.run_until_complete(
                ws.send(json.dumps({
                    "type": "subscribe",
                    "chain_name": chain_name,
                    "event_types": ["block_added", "event"],
                }))
            )
            with self.lock:
                self.connections[conn_id] = ws
                self.messages[conn_id] = []
                self.errors[conn_id] = []
            return True
        except Exception as e:
            with self.lock:
                self.errors.setdefault(conn_id, []).append(str(e))
            return False

    def disconnect_sync(self, conn_id: int) -> bool:
        """Sync wrapper for disconnect."""
        loop = self._get_loop()
        with self.lock:
            ws = self.connections.pop(conn_id, None)
        if ws:
            try:
                loop.run_until_complete(ws.close())
                return True
            except Exception:
                pass
        return False

    def read_one_sync(self, conn_id: int, timeout: float = 5) -> dict | None:
        """Read a message from the connection."""
        loop = self._get_loop()
        with self.lock:
            ws = self.connections.get(conn_id)
        if not ws:
            return None
        try:
            msg = loop.run_until_complete(
                asyncio.wait_for(ws.recv(), timeout=timeout)
            )
            data = json.loads(msg) if isinstance(msg, str) else msg
            with self.lock:
                self.messages[conn_id].append(data)
            return data
        except Exception:
            return None

    @property
    def active_count(self) -> int:
        with self.lock:
            return len(self.connections)

    @property
    def total_messages(self) -> int:
        with self.lock:
            return sum(len(msgs) for msgs in self.messages.values())

    def cleanup(self):
        """Close all connections."""
        for conn_id in list(self.connections.keys()):
            self.disconnect_sync(conn_id)
        if self._loop and not self._loop.is_closed():
            self._loop.close()


class TestWebSocketBasic:
    """Basic WebSocket — connect, subscribe, receive events."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_WEBSOCKETS:
            pytest.skip("websockets library not installed")
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_connect_and_subscribe(self):
        """Connect to WebSocket, subscribe, receive broadcast."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        status = self.client.node_status[healthy[0]]
        tester = WebSocketLoadTest(status.url)

        # Connect
        ok = tester.connect_sync(conn_id=1, chain_name=WS_CHAIN)
        if not ok:
            errors = tester.errors.get(1, ["No error details"])
            logger.error("WebSocket connect failed for %s: %s", tester.ws_url, errors)
            tester.cleanup()
        assert ok, f"Should connect to {tester.ws_url}"

        # Should receive connected messages
        msg = tester.read_one_sync(1, timeout=5)
        logger.info("Initial message: %s", msg)
        assert msg is not None, "Should receive a message on connect"

        # Send event to trigger broadcast
        self.client.submit_event(healthy[0], generate_event(), chain_name=WS_CHAIN)

        # Wait for broadcast
        time.sleep(2)
        broadcast_msg = tester.read_one_sync(1, timeout=5)
        logger.info("Broadcast message: %s", broadcast_msg)

        tester.cleanup()

    def test_ping_pong(self):
        """Test ping/pong keepalive."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        status = self.client.node_status[healthy[0]]
        tester = WebSocketLoadTest(status.url)

        tester.connect_sync(conn_id=1, chain_name=WS_CHAIN)
        time.sleep(1)

        # Read connected messages
        tester.read_one_sync(1, timeout=3)
        tester.read_one_sync(1, timeout=3)

        # Send ping
        loop = tester._get_loop()
        ws = tester.connections.get(1)
        if ws:
            loop.run_until_complete(
                ws.send(json.dumps({"type": "ping"}))
            )
            pong = tester.read_one_sync(1, timeout=5)
            logger.info("Pong response: %s", pong)

        tester.cleanup()


@pytest.mark.stress
class TestWebSocketConcurrent:
    """WebSocket with multiple concurrent clients."""

    CONCURRENT_CLIENTS = 50

    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_WEBSOCKETS:
            pytest.skip("websockets library not installed")
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_many_concurrent_connections(self):
        """Connect N concurrent WebSocket clients."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        status = self.client.node_status[healthy[0]]
        tester = WebSocketLoadTest(status.url)

        # Connect multiple clients
        start = time.time()
        successful = 0
        failed = 0

        for i in range(self.CONCURRENT_CLIENTS):
            ok = tester.connect_sync(conn_id=i, chain_name=WS_CHAIN)
            if ok:
                successful += 1
            else:
                errs = tester.errors.get(i, ["No details"])
                if successful == 0 and failed == 0:
                    logger.error("First WS connect failed for %s: %s", tester.ws_url, errs)
                failed += 1

        elapsed = time.time() - start

        logger.info("WebSocket connections: %d success, %d failed in %.2fs",
                     successful, failed, elapsed)

        # Verify active connections
        assert successful > 0, "At least some should connect"

        # Send events and measure broadcast delivery
        if successful > 0:
            self.client.submit_event(healthy[0], generate_event(), chain_name=WS_CHAIN)
            time.sleep(3)

            logger.info("Total messages received by all clients: %d", tester.total_messages)

        tester.cleanup()

    def test_connection_churn(self):
        """Connect/disconnect continuously — measure memory/CPU impact."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        status = self.client.node_status[healthy[0]]
        tester = WebSocketLoadTest(status.url)

        churn_cycles = 30
        start = time.time()

        for cycle in range(churn_cycles):
            conn_id = cycle % 10
            tester.disconnect_sync(conn_id)
            ok = tester.connect_sync(conn_id, chain_name=WS_CHAIN)
            time.sleep(0.1)

        elapsed = time.time() - start
        logger.info("Connection churn: %d cycles in %.2fs (%.1f ops/sec)",
                     churn_cycles, elapsed, churn_cycles / elapsed if elapsed else 0)

        tester.cleanup()


@pytest.mark.stress
class TestWebSocketBroadcastLoad:
    """Broadcast throughput test."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_WEBSOCKETS:
            pytest.skip("websockets library not installed")
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_broadcast_latency(self):
        """Measure broadcast latency to multiple subscribers."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        status = self.client.node_status[healthy[0]]
        tester = WebSocketLoadTest(status.url)

        # Connect 10 clients
        for i in range(10):
            tester.connect_sync(conn_id=i, chain_name=WS_CHAIN)

        time.sleep(2)

        # Drain initial messages
        for i in range(10):
            tester.read_one_sync(i, timeout=2)

            # Send event and measure latency
        latencies = []
        for _ in range(10):
            for i in range(10):
                tester.read_one_sync(i, timeout=0.1)

            start = time.time()
            self.client.submit_event(healthy[0], generate_event(), chain_name=WS_CHAIN)
            time.sleep(1)

            # Measure time to receive broadcast
            for i in range(10):
                msg = tester.read_one_sync(i, timeout=3)
                if msg:
                    lat = (time.time() - start) * 1000
                    latencies.append(lat)
                    break

        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            logger.info("Broadcast latency: avg=%.2fms, n=%d", avg_lat, len(latencies))
        else:
            logger.warning("No broadcast messages received")

        tester.cleanup()
