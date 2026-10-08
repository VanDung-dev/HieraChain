"""
Network Client for HieraChain P2P Network.

This module provides a Python interface to interact with
the network layer, including peer management and status inspection.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
PEER_TIMEOUT = 60.0


@dataclass
class PeerInfo:
    """Information about a network peer."""
    peer_id: str
    address: str
    last_seen: float = 0.0
    is_healthy: bool = True
    public_key: bytes | None = None
    _last_activity: float = field(default_factory=time.monotonic, repr=False, compare=False)


@dataclass
class NetworkStatus:
    """Current status of the network."""
    node_id: str
    address: str
    is_running: bool
    peer_count: int
    healthy_peers: int
    p2p_enabled: bool


@dataclass
class NetworkClientConfig:
    """Configuration for the network client."""
    enabled: bool = False
    node_id: str = ""
    host: str = "127.0.0.1"
    port: int = 5555
    seed_nodes: list[str] = field(default_factory=list)
    transport_secret_key: bytes | None = None
    transport_public_key: bytes | None = None


class NetworkClient:
    """
    Client to interact with the P2P network layer.

    This client provides methods to:
    - Start/stop the P2P network
    - Query network status
    - Get peer information
    - Register/unregister peers
    """

    def __init__(self, config: NetworkClientConfig | None = None) -> None:
        """
        Initialize the network client.

        Args:
            config: Network configuration. If None, uses defaults.
        """
        self.config = config or NetworkClientConfig()
        self._zmq_node: Any = None
        self._is_running: bool = False
        self._peers: dict[str, PeerInfo] = {}

    @staticmethod
    def _parse_seed_node(seed: str) -> tuple[str | None, str | None, bytes | None]:
        """Analyze the structure of the seed node configuration chain."""
        if "@" in seed:
            # Format: peer_id@ip:port[:public_key]
            peer_id, rest = seed.split("@", 1)
            parts = rest.split(":")
            if len(parts) >= 2:
                address = f"tcp://{parts[0]}:{parts[1]}"
                pub_key = ":".join(parts[2:]).replace("$$", "$").encode('utf-8') if len(parts) >= 3 else None
                return peer_id, address, pub_key
            return None, f"tcp://{rest}", None

        if ":" in seed:
            # Format: ip:port[:public_key]
            parts = seed.split(":")
            if len(parts) >= 2:
                peer_id = parts[0]
                address = f"tcp://{parts[0]}:{parts[1]}"
                pub_key = ":".join(parts[2:]).replace("$$", "$").encode('utf-8') if len(parts) >= 3 else None
                return peer_id, address, pub_key
            return parts[0], f"tcp://{seed}", None

        return None, None, None

    async def start(self) -> bool:
        """
        Start the P2P network if enabled.

        Returns:
            True if started successfully or already running,
            False if disabled.
        """
        if not self.config.enabled:
            logger.debug("P2P network is disabled")
            return False

        if self._is_running:
            return True

        try:
            # Import here to avoid circular imports
            from hierachain.network.zmq_transport import ZmqNode

            self._zmq_node = ZmqNode(
                node_id=self.config.node_id or "default-node",
                port=self.config.port,
                host=self.config.host,
                server_secret_key=self.config.transport_secret_key,
                server_public_key=self.config.transport_public_key,
            )
            self._zmq_node.set_handler(self._on_message_received)

            for peer in self._peers.values():
                peer.last_seen = time.time()
                peer._last_activity = time.monotonic()
                peer.is_healthy = True
                self._zmq_node.register_peer(peer.peer_id, peer.address, public_key=peer.public_key)

            # Register seed nodes
            for seed in self.config.seed_nodes:
                if not seed.strip():
                    continue

                peer_id, address, pub_key = self._parse_seed_node(seed)

                if peer_id and address:
                    self.register_peer(peer_id, address, public_key=pub_key)
                    key_info = " (with public key)" if pub_key else ""
                    logger.info("Registered seed peer: %s at %s%s", peer_id, address, key_info)

            await self._zmq_node.start()
            
            self._is_running = True
            logger.info(
                "NetworkClient started: %s at %s:%s",
                self.config.node_id, self.config.host, self.config.port
            )
            return True

        except Exception as e:
            logger.error("Failed to start NetworkClient: %s", e)
            self._is_running = False
            return False

    async def stop(self) -> None:
        """Stop the P2P network."""
        if not self._is_running:
            return

        try:
            if self._zmq_node:
                await self._zmq_node.stop()
                self._zmq_node = None

            self._is_running = False
            logger.info("NetworkClient stopped")

        except Exception as e:
            logger.error("Error stopping NetworkClient: %s", e)

    def get_network_status(self) -> NetworkStatus:
        """
        Get the current network status.

        Returns:
            NetworkStatus object with current state information.
        """
        self._refresh_peer_health()
        return NetworkStatus(
            node_id=self.config.node_id,
            address=f"tcp://{self.config.host}:{self.config.port}",
            is_running=self._is_running,
            peer_count=len(self._peers),
            healthy_peers=sum(1 for p in self._peers.values() if p.is_healthy),
            p2p_enabled=self.config.enabled,
        )

    def get_peers(self) -> list[PeerInfo]:
        """
        Get list of known peers.

        Returns:
            List of PeerInfo objects.
        """
        self._refresh_peer_health()
        return list(self._peers.values())

    def get_healthy_peers(self) -> list[PeerInfo]:
        """
        Get list of healthy (active) peers.

        Returns:
            List of healthy PeerInfo objects.
        """
        self._refresh_peer_health()
        return [p for p in self._peers.values() if p.is_healthy]

    def _refresh_peer_health(self) -> None:
        """Expire peers without recent inbound activity."""
        now = time.monotonic()
        for peer in self._peers.values():
            peer.is_healthy = now - peer._last_activity < PEER_TIMEOUT

    def register_peer(
        self,
        peer_id: str,
        address: str,
        public_key: bytes | None = None,
    ) -> None:
        """
        Register a new peer.

        Args:
            peer_id: Unique identifier for the peer.
            address: Network address (e.g., "tcp://127.0.0.1:5556").
            public_key: Optional CurveZMQ public key.
        """
        if public_key is None and peer_id in self._peers:
            public_key = self._peers[peer_id].public_key
        self._peers[peer_id] = PeerInfo(
            peer_id=peer_id,
            address=address,
            last_seen=time.time(),
            is_healthy=True,
            public_key=public_key,
        )

        if self._zmq_node:
            self._zmq_node.register_peer(peer_id, address, public_key=public_key)

        logger.debug("Registered peer: %s at %s", peer_id, address)

    def unregister_peer(self, peer_id: str) -> None:
        """
        Unregister a peer.

        Args:
            peer_id: ID of the peer to remove.
        """
        if self._zmq_node:
            self._zmq_node.unregister_peer(peer_id)
        if self._peers.pop(peer_id, None) is not None:
            logger.debug("Unregistered peer: %s", peer_id)

    async def send_direct(self, target_peer_id: str, message: dict[str, Any]) -> bool:
        """Send a message directly to a peer."""
        if not self._zmq_node or not self._is_running:
            return False
        return await self._zmq_node.send_direct(target_peer_id, message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all known peers."""
        if not self._zmq_node or not self._is_running:
            return
        await self._zmq_node.broadcast(message)

    async def _on_message_received(self, message: dict[str, Any], sender_id: str) -> None:
        """Handle incoming messages."""
        logger.debug("Received message from %s: %s", sender_id, message.get("type"))
        peer = self._peers.get(sender_id)
        if peer is not None:
            peer.last_seen = time.time()
            peer._last_activity = time.monotonic()
            peer.is_healthy = True
        
        # Internal ping-pong for testing
        if message.get("type") == "ping":
            pong_msg = {
                "type": "pong",
                "timestamp": time.time(),
                "nonce": uuid.uuid4().hex,
                "node_id": self.config.node_id
            }
            asyncio.create_task(self.send_direct(sender_id, pong_msg))

    @property
    def is_running(self) -> bool:
        """Check if the network client is running."""
        return self._is_running

    @property
    def peer_count(self) -> int:
        """Get the number of known peers."""
        return len(self._peers)
