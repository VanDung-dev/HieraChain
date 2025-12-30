"""
Network Client for HieraChain P2P Network.

This module provides a Python interface to interact with
the network layer, including peer management and status inspection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PeerInfo:
    """Information about a network peer."""
    peer_id: str
    address: str
    last_seen: float = 0.0
    is_healthy: bool = True


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
            )
            await self._zmq_node.start()

            # Register seed nodes
            for seed in self.config.seed_nodes:
                if ":" in seed:
                    peer_id = seed.split(":")[0]
                    self._zmq_node.register_peer(peer_id, seed)

            self._is_running = True
            logger.info(
                f"NetworkClient started: {self.config.node_id} "
                f"at {self.config.host}:{self.config.port}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start NetworkClient: {e}")
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
            logger.error(f"Error stopping NetworkClient: {e}")

    def get_network_status(self) -> NetworkStatus:
        """
        Get the current network status.

        Returns:
            NetworkStatus object with current state information.
        """
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
        return list(self._peers.values())

    def get_healthy_peers(self) -> list[PeerInfo]:
        """
        Get list of healthy (active) peers.

        Returns:
            List of healthy PeerInfo objects.
        """
        return [p for p in self._peers.values() if p.is_healthy]

    def register_peer(
        self,
        peer_id: str,
        address: str,
    ) -> None:
        """
        Register a new peer.

        Args:
            peer_id: Unique identifier for the peer.
            address: Network address (e.g., "tcp://127.0.0.1:5556").
        """
        self._peers[peer_id] = PeerInfo(
            peer_id=peer_id,
            address=address,
            is_healthy=True,
        )

        if self._zmq_node and self._is_running:
            self._zmq_node.register_peer(peer_id, address)

        logger.debug(f"Registered peer: {peer_id} at {address}")

    def unregister_peer(self, peer_id: str) -> None:
        """
        Unregister a peer.

        Args:
            peer_id: ID of the peer to remove.
        """
        if peer_id in self._peers:
            del self._peers[peer_id]
            logger.debug(f"Unregistered peer: {peer_id}")

    @property
    def is_running(self) -> bool:
        """Check if the network client is running."""
        return self._is_running

    @property
    def peer_count(self) -> int:
        """Get the number of known peers."""
        return len(self._peers)


class NetworkClientSync:
    """
    Synchronous wrapper for NetworkClient.

    Example:
        with NetworkClientSync(config) as client:
            status = client.get_network_status()
            print(status)
    """

    def __init__(self, config: NetworkClientConfig | None = None) -> None:
        """Initialize sync network client wrapper."""
        self._async_client = NetworkClient(config)
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self) -> NetworkClientSync:
        """Context manager entry."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._async_client.start())
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit."""
        if self._loop:
            self._loop.run_until_complete(self._async_client.stop())
            self._loop.close()
            self._loop = None

    def get_network_status(self) -> NetworkStatus:
        """Get current network status."""
        return self._async_client.get_network_status()

    def get_peers(self) -> list[PeerInfo]:
        """Get list of known peers."""
        return self._async_client.get_peers()

    def get_healthy_peers(self) -> list[PeerInfo]:
        """Get list of healthy peers."""
        return self._async_client.get_healthy_peers()

    def register_peer(self, peer_id: str, address: str) -> None:
        """Register a new peer."""
        self._async_client.register_peer(peer_id, address)

    def unregister_peer(self, peer_id: str) -> None:
        """Unregister a peer."""
        self._async_client.unregister_peer(peer_id)
