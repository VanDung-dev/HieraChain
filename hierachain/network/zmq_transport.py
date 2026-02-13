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
import json
import asyncio
import time
import logging
from typing import Any, Callable

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
        peers (Dict[str, str]): Mapping of peer_id -> address (e.g., "tcp://127.0.0.1:5001").
    """

    def __init__(
        self,
        node_id: str,
        port: int,
        host: str = "127.0.0.1",
        server_secret_key: bytes = None,
        server_public_key: bytes = None
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.peers: dict[str, dict[str, Any]] = {}  # peer_id -> {address, public_key}
        
        # CurveZMQ keys (Curve25519)
        self.server_secret = server_secret_key
        self.server_public = server_public_key
        
        self.ctx = zmq.asyncio.Context()
        self._stop_event = asyncio.Event()
        self._message_handler: Callable[[dict[str, Any], str], Any] | None = None

        # Replay Protection
        self.replay_buffer: set[tuple[float, str]] = set() # (timestamp, nonce)
        self.replay_tolerance = 60 # seconds
        
        # Sockets
        self.router = None  # For receiving (bind)
        self.dealer_pool: dict[str, zmq.asyncio.Socket] = {} # For sending (connect)

    async def start(self):
        """Start the node: bind listener and start receiver loop."""
        try:
            self.router = self.ctx.socket(zmq.ROUTER)
            self.router.setsockopt(zmq.IDENTITY, self.node_id.encode('utf-8'))
            
            # Enable CurveZMQ for Server (ROUTER)
            if self.server_secret:
                self.router.setsockopt(zmq.CURVE_SERVER, 1)
                self.router.setsockopt(zmq.CURVE_SECRETKEY, self.server_secret)
                logger.info(f"Node {self.node_id}: Security Enabled (CurveZMQ Server)")
            
            self.router.bind(self.address)
            logger.info(f"Node {self.node_id} listening on {self.address}")
            
            # Start receiver loop in background
            asyncio.create_task(self._receiver_loop())
        except Exception as e:
            raise NetworkError(f"Failed to start node {self.node_id}: {e}")

    async def stop(self):
        """Stop the node and close sockets."""
        self._stop_event.set()
        
        if self.router:
            self.router.close()
        
        for peer_id, socket in self.dealer_pool.items():
            socket.close()
            
        self.ctx.term()
        logger.info(f"Node {self.node_id} stopped")

    def register_peer(self, peer_id: str, address: str, public_key: bytes = None):
        """Register a known peer with optional public key."""
        self.peers[peer_id] = {
            "address": address,
            "public_key": public_key
        }

    def set_handler(self, handler: Callable[[dict[str, Any], str], Any]):
        """Set the callback function for processing received messages."""
        self._message_handler = handler

    def _is_valid_replay(self, message_data: dict[str, Any]) -> bool:
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
        
        # 1. Check timestamp freshness
        if abs(now - timestamp) > self.replay_tolerance:
            logger.warning(f"Message timestamp out of tolerance: {timestamp} (now={now})")
            return False
            
        # 2. Check nonce uniqueness
        entry = (timestamp, nonce)
        if entry in self.replay_buffer:
            logger.warning(f"Replay detected: {nonce}")
            return False
            
        # 3. Add to buffer and cleanup
        self.replay_buffer.add(entry)
        
        # Cleanup old entries
        cutoff = now - self.replay_tolerance
        self.replay_buffer = {e for e in self.replay_buffer if e[0] > cutoff}
        
        return True

    async def send_direct(self, target_peer_id: str, message: dict[str, Any]) -> bool:
        """
        Send a message directly to a peer.
        
        Args:
            target_peer_id: Destination node ID.
            message: Dictionary message content.
        """
        if target_peer_id not in self.peers:
            logger.error(f"Unknown peer: {target_peer_id}")
            return False

        try:
            socket = await self._get_or_create_dealer(target_peer_id)
            encoded_msg = json.dumps(message).encode('utf-8')
            await socket.send(encoded_msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {target_peer_id}: {e}")
            return False

    async def broadcast(self, message: dict[str, Any], exclude: list[str] = None):
        """Broadcast message to all registered peers."""
        exclude = exclude or []
        for peer_id in self.peers:
            if peer_id not in exclude:
                await self.send_direct(peer_id, message)

    async def _get_or_create_dealer(self, peer_id: str) -> zmq.asyncio.Socket:
        """Get existing DEALER socket or create a new one."""
        if peer_id in self.dealer_pool:
            return self.dealer_pool[peer_id]
            
        peer_info = self.peers[peer_id]
        address = peer_info["address"]
        peer_public_key = peer_info.get("public_key")
        
        socket = self.ctx.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY, self.node_id.encode('utf-8'))
        
        # Enable CurveZMQ for Client (DEALER)
        if self.server_secret and peer_public_key:
            socket.setsockopt(zmq.CURVE_SERVERKEY, peer_public_key)
            socket.setsockopt(zmq.CURVE_PUBLICKEY, self.server_public)
            socket.setsockopt(zmq.CURVE_SECRETKEY, self.server_secret)
            # logger.debug(f"Connecting to {peer_id} with CurveZMQ")
        
        socket.connect(address)
        
        self.dealer_pool[peer_id] = socket
        return socket

    async def _receiver_loop(self):
        """Loop to receive messages from ROUTER socket."""
        while not self._stop_event.is_set():
            try:
                await self._receive_once()
            except Exception as e:
                if not await self._handle_receiver_error(e):
                    break

    async def _receive_once(self):
        """Receive and handle a single multipart message."""
        msg_parts = await self.router.recv_multipart()
        await self._handle_received_message(msg_parts)

    async def _handle_receiver_error(self, e: Exception) -> bool:
        """
        Handle errors in the receiver loop.
        Returns True if the loop should continue, False if it should stop.
        """
        if isinstance(e, zmq.ZMQError):
            if not self._stop_event.is_set():
                logger.error(f"ZMQ Receive error: {e}")
            return False  # Stop the loop for ZMQ errors
            
        logger.error(f"Unexpected error in receiver loop: {e}")
        await asyncio.sleep(1)
        return True  # Continue for other exceptions

    async def _handle_received_message(self, msg_parts: list[bytes]):
        """Process raw message parts from the socket."""
        if len(msg_parts) < 2:
            return

        try:
            sender_id = msg_parts[0].decode('utf-8')
            message_str = msg_parts[-1].decode('utf-8')
            message_data = json.loads(message_str)
            
            await self._process_message_data(message_data, sender_id)
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Received invalid message format or encoding")
        except Exception as e:
            logger.error(f"Error processing message parts: {e}")

    async def _process_message_data(self, message_data: dict[str, Any], sender_id: str):
        """Perform validation and invoke the message handler."""
        # Replay Check
        if not self._is_valid_replay(message_data):
            return

        if not self._message_handler:
            return

        try:
            # Process message (could be async or sync)
            if asyncio.iscoroutinefunction(self._message_handler):
                await self._message_handler(message_data, sender_id)
            else:
                self._message_handler(message_data, sender_id)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
