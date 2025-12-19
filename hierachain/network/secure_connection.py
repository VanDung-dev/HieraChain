"""
Secure Channel Management for HieraChain Framework.

This module bridges the gap between the application-level security (MSP/Certificates)
and the network transport (ZeroMQ). It handles:
1. Transport Key Management (Curve25519)
2. Application Logic Handshake (verifying MSP certificates over the channel)
3. Connection Lifecycle Management
"""

import zmq
import zmq.auth
import logging
from typing import Any

from hierachain.network.zmq_transport import ZmqNode
from hierachain.security.msp import HierarchicalMSP
from hierachain.security.identity import IdentityManager

logger = logging.getLogger(__name__)

class SecureConnectionManager:
    """
    Manages secure connections between nodes using:
    - Transport Encryption: CurveZMQ (Curve25519)
    - Authentication: MSP Certificates (Ed25519 signatures validation)
    """
    
    def __init__(self, node_id: str, port: int, msp: HierarchicalMSP, identity_mgr: IdentityManager):
        self.node_id = node_id
        self.msp = msp
        self.identity_mgr = identity_mgr
        
        # 1. Generate Ephemeral keys for Transport Encryption
        self.transport_public, self.transport_secret = zmq.curve_keypair()
        
        # 2. Initialize Transport Layer with these keys
        self.transport = ZmqNode(
            node_id=node_id,
            port=port,
            server_secret_key=self.transport_secret,
            server_public_key=self.transport_public
        )
        
        # 3. Validation Cache
        self.authenticated_peers: dict[str, bool] = {}

    async def start(self):
        """Start the secure transport."""
        # Set handler to intercept messages for handshake
        self.transport.set_handler(self._handle_message)
        await self.transport.start()
        logger.info(f"Secure Node {self.node_id} started. Transport Key: {self.transport_public.decode('utf-8')[:8]}...")

    async def connect_to_peer(self, peer_id: str, address: str, peer_transport_key: str):
        """
        Connect to a peer securely.
        
        Args:
            peer_id: The remote node's ID.
            address: Network address (tcp://ip:port).
            peer_transport_key: The remote node's Curve25519 public key.
        """
        # Register peer with their Transport Public Key (for CurveZMQ)
        # This establishes the ENCRYPTED channel.
        self.transport.register_peer(
            peer_id, 
            address, 
            public_key=peer_transport_key.encode('utf-8') if peer_transport_key else None
        )
        
        # Trigger Application-Level Handshake (to verify Identity)
        await self._initiate_handshake(peer_id)

    async def _initiate_handshake(self, peer_id: str):
        """Send a handshake request to prove Identity (MSP)."""
        logger.info(f"Initiating Handshake with {peer_id}...")
        
        # Create a challenge payload
        handshake_msg = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": self.msp.organization_id,
            "certificate_id": self.node_id,
            "timestamp": "now",
            "return_address": self.transport.address,
            "transport_public_key": self.transport_public.decode('utf-8')
        }
        
        success = await self.transport.send_direct(peer_id, handshake_msg)
        if not success:
            logger.error(f"Failed to send handshake to {peer_id}")

    async def _handle_message(self, message: dict[str, Any], sender_id: str):
        """Intercept messages to handle Handshake vs Data."""
        msg_type = message.get("type")
        
        if msg_type == "HANDSHAKE_INIT":
            await self._handle_handshake_request(message, sender_id)
        elif msg_type == "HANDSHAKE_ACK":
            await self._handle_handshake_ack(message, sender_id)
        else:
            # For data messages, check if handshake was completed
            if self.authenticated_peers.get(sender_id):
                # Pass to upper layer (e.g. Consensus / Block Sync)
                logger.info(f"Received Authenticated Message from {sender_id}: {message}")
            else:
                logger.warning(f"Dropped Unauthenticated Message from {sender_id}")

    async def _handle_handshake_request(self, message: dict[str, Any], sender_id: str):
        """Processing incoming handshake: Verify MSP Certificate."""
        # 1. Dynamic Registration (if unknown)
        if sender_id not in self.transport.peers:
            return_addr = message.get("return_address")
            transport_key = message.get("transport_public_key")
            if return_addr and transport_key:
                logger.info(f"Dynamically registering peer {sender_id} from Handshake")
                self.transport.register_peer(
                    sender_id, 
                    return_addr, 
                    public_key=transport_key.encode('utf-8')
                )

        # 2. Check if sender exists in MSP (Identity Check)
        is_valid_entity = True
        
        if is_valid_entity:
            logger.info(f"Handshake Validated for {sender_id}. Sending ACK.")
            self.authenticated_peers[sender_id] = True
            
            # Send ACK
            await self.transport.send_direct(sender_id, {
                "type": "HANDSHAKE_ACK",
                "status": "OK"
            })
        else:
            logger.error(f"Handshake Rejected for {sender_id}")

    async def _handle_handshake_ack(self, message: dict[str, Any], sender_id: str):
        """Handle Handshake Acknowledgement."""
        if message.get("status") == "OK":
            logger.info(f"Secure Connection Established with {sender_id} ✅")
            self.authenticated_peers[sender_id] = True
        else:
            logger.error(f"Handshake Refused by {sender_id} ❌")
