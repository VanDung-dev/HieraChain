"""
ZeroMQ Transport Layer for HieraChain.

This module implements a high-performance network transport using ZeroMQ (pyzmq).
It provides a `ZmqNode` class that handles:
- Asynchronous message sending (DEALER sockets).
- Message receiving (ROUTER sockets) with identity management.
- Serialization of messages (JSON by default, extensible).
"""

import zmq
import zmq.asyncio
import orjson
import asyncio
import inspect
import time
import logging
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


class NetworkError(Exception):
    """Base exception for network errors."""
    pass


class ZmqNode:
    """
    A ZeroMQ-based network node.
    
    Attributes:
        node_id (str): Unique identifier for this node.
        port (int): The port to bind for listening (ROUTER).
        peers (Dict[str, str]): Mapping of peer_id -> address
                                (e.g., "tcp://127.0.0.1:5001").
    """

    def __init__(
        self,
        node_id: str,
        port: int,
        host: str = "127.0.0.1",
        server_secret_key: bytes | None = None,
        server_public_key: bytes | None = None,
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.peers: dict[str, dict[str, Any]] = {}  # peer_id -> {address, public_key}
        
        # CurveZMQ keys (Curve25519)
        self.server_secret: bytes | None = server_secret_key
        self.server_public: bytes | None = server_public_key
        
        self.ctx = zmq.asyncio.Context()
        self._stop_event = asyncio.Event()
        self._message_handler: Callable[[dict[str, Any], str], Any] | None = None

        # Replay Protection
        self.replay_buffer: set[tuple[float, str]] = set()  # (timestamp, nonce)
        self.replay_tolerance = 60  # seconds
        
        # Sockets
        self.router: zmq.asyncio.Socket | None = None  # For receiving (bind)
        self.dealer_pool: dict[str, zmq.asyncio.Socket] = {}  # For sending (connect)

    @property
    def stop_event(self) -> asyncio.Event:
        """Get the stop event."""
        return self._stop_event

    @property
    def message_handler(self) -> Callable[[dict[str, Any], str], Any] | None:
        """Get the message handler."""
        return self._message_handler

    def _is_valid_replay(self, message_data: dict[str, Any]) -> bool:
        """Validate message replay protection."""
        return _is_valid_replay(self, message_data)

    async def start(self) -> None:
        """Start the node: bind listener and start receiver loop."""
        try:
            router = self.ctx.socket(zmq.ROUTER)
            self.router = router
            router.setsockopt(zmq.IDENTITY, self.node_id.encode('utf-8'))

            # Enable CurveZMQ for Server (ROUTER)
            if self.server_secret:
                router.setsockopt(zmq.CURVE_SERVER, 1)
                router.setsockopt(zmq.CURVE_SECRETKEY, self.server_secret)
                logger.info("Node %s: Security Enabled (CurveZMQ Server)", self.node_id)

            router.bind(self.address)
            logger.info("Node %s listening on %s", self.node_id, self.address)
            
            # Start receiver loop in background
            asyncio.create_task(_receiver_loop(self))
        except Exception as e:
            raise NetworkError(f"Failed to start node {self.node_id}: {e}")

    async def stop(self) -> None:
        """Stop the node and close sockets."""
        self._stop_event.set()
        
        if self.router:
            self.router.close()
        
        for peer_id, socket in self.dealer_pool.items():
            socket.close()
            
        self.ctx.term()
        logger.info("Node %s stopped", self.node_id)

    def register_peer(
        self, peer_id: str, address: str, public_key: bytes | None = None
    ) -> None:
        """Register a known peer with optional public key."""
        self.peers[peer_id] = {
            "address": address,
            "public_key": public_key
        }

    def set_handler(self, handler: Callable[[dict[str, Any], str], Any]) -> None:
        """Set the callback function for processing received messages."""
        self._message_handler = handler

    async def send_direct(self, target_peer_id: str, message: dict[str, Any]) -> bool:
        """
        Send a message directly to a peer.
        
        Args:
            target_peer_id: Destination node ID.
            message: Dictionary message content.
        """
        if target_peer_id not in self.peers:
            logger.error("Unknown peer: %s", target_peer_id)
            return False

        try:
            socket = await _get_or_create_dealer(self, target_peer_id)
            encoded_msg = orjson.dumps(message)
            await socket.send(encoded_msg)
            return True
        except Exception as e:
            logger.error("Failed to send to %s: %s", target_peer_id, e)
            return False

    async def broadcast(
        self, message: dict[str, Any], exclude: list[str] | None = None
    ) -> None:
        """Broadcast message to all registered peers."""
        exclude = exclude or []
        for peer_id in self.peers:
            if peer_id not in exclude:
                await self.send_direct(peer_id, message)

        # networking helpers are defined as module-level functions below


def _is_valid_replay(node: ZmqNode, message_data: dict[str, Any]) -> bool:
    """
    Check if message is a replay.
    Returns True if valid (not a replay), False otherwise.
    """
    timestamp = message_data.get("timestamp")
    nonce = message_data.get("nonce")

    if timestamp is None:
        logger.warning("Message missing timestamp")
        return False

    if nonce is None:
        logger.warning("Message missing nonce")
        return False

    now = time.time()
    ts_val = float(cast(Any, timestamp))

    if abs(now - ts_val) > node.replay_tolerance:
        logger.warning(
            "Message timestamp out of tolerance: %s (now=%s)", ts_val, now
        )
        return False

    entry = (ts_val, str(nonce))
    if entry in node.replay_buffer:
        logger.warning("Replay detected: %s", nonce)
        return False

    node.replay_buffer.add(entry)

    cutoff = now - node.replay_tolerance
    if len(node.replay_buffer) > 1000:
        node.replay_buffer = {e for e in node.replay_buffer if e[0] > cutoff}

    return True


async def _get_or_create_dealer(node: ZmqNode, peer_id: str) -> zmq.asyncio.Socket:
    """Get or create a DEALER socket for a peer."""
    if peer_id in node.dealer_pool:
        return node.dealer_pool[peer_id]

    peer_info = node.peers[peer_id]
    address = peer_info["address"]
    peer_public_key: bytes | None = peer_info.get("public_key")

    socket = node.ctx.socket(zmq.DEALER)
    socket.setsockopt(zmq.IDENTITY, node.node_id.encode('utf-8'))

    if node.server_secret and node.server_public and peer_public_key:
        key_len = len(peer_public_key)
        try:
            logger.debug("Setting CURVE keys for peer %s", peer_id)
            socket.setsockopt(zmq.CURVE_SERVERKEY, peer_public_key)
            socket.setsockopt(zmq.CURVE_PUBLICKEY, node.server_public)
            socket.setsockopt(zmq.CURVE_SECRETKEY, node.server_secret)
        except Exception as e:
            logger.error(
                "Failed to set CURVE keys for %s: %s (key length: %d)",
                peer_id, e, key_len
            )
            raise

    logger.info("Connecting to peer %s at %s", peer_id, address)
    socket.connect(address)

    node.dealer_pool[peer_id] = socket
    return socket


async def _receiver_loop(node: ZmqNode) -> None:
    """
    Main receiver loop for handling incoming messages.
    Continues until the stop event is set.
    """
    while not node.stop_event.is_set():
        try:
            await _receive_once(node)
        except Exception as e:
            should_continue = await _handle_receiver_error(node, e)
            if not should_continue:
                break


async def _receive_once(node: ZmqNode) -> None:
    """Receive a single message and process it."""
    router = node.router
    if router is None:
        raise NetworkError("Router socket is not initialized")
    msg_parts = await router.recv_multipart()
    await _handle_received_message(node, msg_parts)


async def _handle_receiver_error(node: ZmqNode, e: Exception) -> bool:
    """Handle errors in the receiver loop."""
    if isinstance(e, zmq.ZMQError):
        if not node.stop_event.is_set():
            logger.error("ZMQ Receive error: %s", e)
        return False

    logger.error("Unexpected error in receiver loop: %s", e)
    await asyncio.sleep(1)
    return True


async def _handle_received_message(node: ZmqNode, msg_parts: list[bytes]) -> None:
    """Handle a received message."""
    if len(msg_parts) < 2:
        return

    try:
        sender_id = msg_parts[0].decode('utf-8')
        message_str = msg_parts[-1].decode('utf-8')
        message_data = orjson.loads(message_str)

        await _process_message_data(node, message_data, sender_id)
    except (UnicodeDecodeError, orjson.JSONDecodeError):
        logger.warning("Received invalid message format or encoding")
    except Exception as e:
        logger.error("Error processing message parts: %s", e)


async def _process_message_data(
    node: ZmqNode, message_data: dict[str, Any], sender_id: str,
) -> None:
    """Process received message data."""
    if not _is_valid_replay(node, message_data):
        return

    handler = node.message_handler
    if handler is None:
        return

    try:
        if inspect.iscoroutinefunction(handler):
            await handler(message_data, sender_id)
        else:
            handler(message_data, sender_id)
    except Exception as e:
        logger.error("Error in message handler: %s", e)
