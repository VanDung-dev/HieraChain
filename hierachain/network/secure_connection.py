"""
Secure Channel Management for HieraChain Ledger

This module bridges the gap between the application-level security (MSP/Certificates)
and the network transport (ZeroMQ). It handles:
1. Transport Key Management (Curve25519)
2. Application Logic Handshake (verifying MSP certificates over the channel)
3. Cryptographic message authentication (Ed25519 signatures)
4. Connection Lifecycle Management
"""

import zmq
import zmq.auth
import logging
from typing import Any

from hierachain.config.settings import get_settings
from hierachain.network.zmq_transport import ZmqNode
from hierachain.network.peer_trust_manager import PeerTrustManager
from hierachain.network.message_cryptographic import (
    sign_message,
    verify_message,
    sign_handshake_payload,
    verify_handshake_signature,
)
from hierachain.security.msp import HierarchicalMSP
from hierachain.security.identity import IdentityManager
from hierachain.security.security_utils import KeyPair

logger = logging.getLogger(__name__)


def handle_data_message(
    authenticated_peers: dict[str, bool],
    require_signatures: bool,
    peer_public_keys: dict[str, str],
    message: dict[str, Any],
    sender_id: str,
) -> bool:
    if not authenticated_peers.get(sender_id):
        logger.warning(f"Dropped Unauthenticated Message from {sender_id}")
        return False

    if not require_signatures:
        return True

    peer_key = peer_public_keys.get(sender_id)
    if not peer_key:
        logger.warning(f"No public key for peer {sender_id}, dropping message")
        return False

    if not verify_message(message, peer_key):
        logger.warning(f"Invalid signature on message from {sender_id}, dropping message")
        return False

    return True


def check_trust_policy(trust_manager: PeerTrustManager, sender_id: str) -> bool:
    if trust_manager.is_trusted(sender_id):
        return True

    logger.warning(f"Handshake rejected: Peer {sender_id} is not trusted by policy.")
    return False


def is_certificate_valid_in_ca(msp: HierarchicalMSP, cert_id: str) -> bool:
    if hasattr(msp, "ca") and msp.ca:
        is_valid = msp.ca.verify_certificate(cert_id)
        if not is_valid:
            logger.debug(f"Certificate {cert_id} failed CA verification")
            return False

    return True


def is_certificate_org_match(
    identity_mgr: IdentityManager | None,
    cert_id: str,
    sender_msp_id: str,
) -> bool:
    if not identity_mgr:
        return True

    user_info = identity_mgr.get_user_info(cert_id)
    if not user_info:
        return True

    if user_info.get("org_id") != sender_msp_id:
        logger.debug(
            f"Certificate {cert_id} org mismatch: "
            f"claimed {sender_msp_id}, "
            f"actual {user_info.get('org_id')}"
        )
        return False

    return True


def verify_msp_certificate(
    msp: HierarchicalMSP,
    identity_mgr: IdentityManager | None,
    cert_id: str,
    sender_msp_id: str,
) -> bool:
    if not is_certificate_valid_in_ca(msp, cert_id):
        return False

    if not is_certificate_org_match(identity_mgr, cert_id, sender_msp_id):
        return False

    return True


def validate_msp_from_message(
    msp: HierarchicalMSP,
    identity_mgr: IdentityManager | None,
    message: dict[str, Any],
    sender_id: str,
) -> bool:
    cert_id = message.get("certificate_id")
    sender_msp_id = message.get("sender_msp_id")

    if not cert_id or not sender_msp_id:
        logger.warning(f"Handshake rejected from {sender_id}: Missing certificate_id or sender_msp_id.")
        return False

    if not verify_msp_certificate(msp, identity_mgr, cert_id, sender_msp_id):
        logger.warning(f"Handshake rejected from {sender_id}: Invalid MSP certificate '{cert_id}'.")
        return False

    return True


def validate_handshake_signature_from_message(
    require_signatures: bool,
    peer_public_keys: dict[str, str],
    message: dict[str, Any],
    sender_id: str,
) -> bool:
    sender_public_key = message.get("sender_public_key")
    signature = message.get("signature")

    if sender_public_key and signature:
        handshake_data = {k: v for k, v in message.items() if k != "signature"}
        if not verify_handshake_signature(handshake_data, signature, sender_public_key):
            logger.warning(f"Handshake rejected from {sender_id}: Invalid cryptographic signature.")
            return False

        peer_public_keys[sender_id] = sender_public_key
        return True

    if require_signatures:
        logger.warning(
            f"Handshake rejected from {sender_id}: "
            "Missing public key or signature "
            "(signatures required in this environment)."
        )
        return False

    return True


def register_dynamic_peer(
    transport: ZmqNode,
    message: dict[str, Any],
    sender_id: str,
) -> None:
    if sender_id in transport.peers:
        return

    return_addr = message.get("return_address")
    transport_key = message.get("transport_public_key")

    if not return_addr or not transport_key:
        return

    logger.info(f"Dynamically registering peer {sender_id} from Handshake")
    transport.register_peer(
        sender_id,
        return_addr,
        public_key=transport_key.encode("utf-8"),
    )


class SecureConnectionManager:
    """
    Manages secure connections between nodes using:
    - Transport Encryption: CurveZMQ (Curve25519)
    - Authentication: MSP Certificates (Ed25519 signatures validation)
    - Message Integrity: Ed25519 signed P2P messages
    """

    def __init__(
        self,
        node_id: str,
        port: int,
        msp: HierarchicalMSP,
        identity_mgr: IdentityManager,
        signing_keypair: KeyPair | None = None,
    ):
        self.node_id = node_id
        self.msp = msp
        self.identity_mgr = identity_mgr

        # Ed25519 signing keypair for this node
        self.signing_keypair = signing_keypair or KeyPair.generate()

        # Load P2P configuration from settings
        settings = get_settings()
        p2p_config = settings.get_p2p_config()

        # Trust Manager with environment-aware policy
        trust_policy = p2p_config["trust_policy"]
        initial_allowlist = set(
            pid.strip()
            for pid in p2p_config["peer_allowlist"]
            if pid.strip()
        )
        self.require_signatures = p2p_config["require_signatures"]

        self.trust_manager = PeerTrustManager(
            identity_manager=identity_mgr,
            trust_policy=trust_policy,
            initial_allowlist=initial_allowlist or None,
        )

        # Warn on insecure production configuration
        if settings.ENV == "product" and trust_policy != "strict":
            logger.warning(
                "SECURITY WARNING: Production environment running with "
                f"P2P trust_policy='{trust_policy}' instead of 'strict'. "
                "This allows any peer to connect without allowlist. "
                "Set HRC_P2P_TRUST_POLICY=strict for production."
            )

        if settings.ENV == "product" and not self.require_signatures:
            logger.warning(
                "SECURITY WARNING: Production environment running without "
                "P2P message signature verification. "
                "Set HRC_P2P_REQUIRE_SIGNATURES=true for production."
            )

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
        # Store verified peer public keys for message verification
        self.peer_public_keys: dict[str, str] = {}

    async def start(self):
        """Start the secure transport."""
        # Set handler to intercept messages for handshake
        self.transport.set_handler(self._handle_message)
        await self.transport.start()
        logger.info(
            f"Secure Node {self.node_id} started. "
            f"Transport Key: {self.transport_public.decode('utf-8')[:8]}..."
        )

    async def connect_to_peer(
        self,
        peer_id: str,
        address: str,
        peer_transport_key: str,
    ):
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
            public_key=(
                peer_transport_key.encode("utf-8")
                if peer_transport_key
                else None
            ),
        )

        # Trigger Application-Level Handshake (to verify Identity)
        await self._initiate_handshake(peer_id)

    async def send_secure(self, peer_id: str, payload: dict[str, Any]) -> bool:
        """
        Send a cryptographically signed message to a peer.

        Args:
            peer_id: Target peer ID.
            payload: Message payload to send.

        Returns:
            True if message was sent successfully.
        """
        if not self.authenticated_peers.get(peer_id):
            logger.warning(f"Cannot send to unauthenticated peer {peer_id}")
            return False

        if self.require_signatures:
            message = sign_message(payload, self.signing_keypair, self.node_id)
        else:
            message = payload

        return await self.transport.send_direct(peer_id, message)

    async def _initiate_handshake(self, peer_id: str):
        """Send a handshake request to prove Identity (MSP)."""
        logger.info(f"Initiating Handshake with {peer_id}...")

        # Create handshake payload (without signature)
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": self.msp.organization_id,
            "certificate_id": self.node_id,
            "sender_public_key": self.signing_keypair.public_key,
            "return_address": self.transport.address,
            "transport_public_key": self.transport_public.decode("utf-8"),
        }

        # Sign the handshake payload
        signature = sign_handshake_payload(handshake_data, self.signing_keypair)
        handshake_data["signature"] = signature

        success = await self.transport.send_direct(peer_id, handshake_data)
        if not success:
            logger.error(f"Failed to send handshake to {peer_id}")

    async def _handle_message(self, message: dict[str, Any],sender_id: str):
        """Intercept messages to handle Handshake vs Data."""
        msg_type = message.get("type")

        if msg_type == "HANDSHAKE_INIT":
            await self._handle_handshake_request(message, sender_id)
            return

        if msg_type == "HANDSHAKE_ACK":
            await self._handle_handshake_ack(message, sender_id)
            return

        if self._handle_data_message(message, sender_id):
            logger.info(f"Received Authenticated Message from {sender_id}")

    def _handle_data_message(self, message: dict[str, Any], sender_id: str) -> bool:
        return handle_data_message(
            self.authenticated_peers,
            self.require_signatures,
            self.peer_public_keys,
            message,
            sender_id,
        )

    async def handle_handshake_request(self, message: dict[str, Any], sender_id: str):
        await self._handle_handshake_request(message, sender_id)

    async def handle_handshake_ack(self, message: dict[str, Any], sender_id: str):
        await self._handle_handshake_ack(message, sender_id)

    async def _handle_handshake_request(self, message: dict[str, Any], sender_id: str):
        """
        Process incoming handshake with full identity verification.

        Steps:
        1. Trust policy check (allowlist/blocklist)
        2. MSP certificate verification
        3. Handshake signature cryptographic verification
        4. Only then mark peer as authenticated
        """
        if not self._check_trust_policy(sender_id):
            return

        if not self._validate_msp_from_message(message, sender_id):
            return

        if not self._validate_handshake_signature_from_message(message, sender_id):
            return

        self._register_dynamic_peer(message, sender_id)

        logger.info(f"Handshake Validated for {sender_id}. Trust + MSP + Signature verified. Sending ACK.")
        self.authenticated_peers[sender_id] = True

        # Create signed ACK
        ack_data = {
            "type": "HANDSHAKE_ACK",
            "status": "OK",
            "sender_public_key": self.signing_keypair.public_key,
        }
        ack_signature = sign_handshake_payload(ack_data, self.signing_keypair)
        ack_data["signature"] = ack_signature

        await self.transport.send_direct(sender_id, ack_data)

    async def _handle_handshake_ack(self, message: dict[str, Any], sender_id: str):
        """Handle Handshake Acknowledgement with signature verification."""
        if message.get("status") != "OK":
            logger.error(f"Handshake Refused by {sender_id} ❌")
            return

        # Verify ACK signature if present
        sender_public_key = message.get("sender_public_key")
        signature = message.get("signature")

        if sender_public_key and signature:
            ack_data = {k: v for k, v in message.items() if k != "signature"}
            if not verify_handshake_signature(ack_data, signature, sender_public_key):
                logger.warning(f"Handshake ACK from {sender_id} has invalid signature, rejecting.")
                return

            # Store verified public key
            self.peer_public_keys[sender_id] = sender_public_key
        elif self.require_signatures:
            logger.warning(
                f"Handshake ACK from {sender_id} missing "
                "public key or signature "
                "(signatures required in this environment)."
            )
            return

        logger.info(f"Secure Connection Established with {sender_id} ✅")
        self.authenticated_peers[sender_id] = True

    def _check_trust_policy(self, sender_id: str) -> bool:
        return check_trust_policy(self.trust_manager, sender_id)

    def _validate_msp_from_message(self, message: dict[str, Any], sender_id: str) -> bool:
        return validate_msp_from_message(
            self.msp,
            self.identity_mgr,
            message,
            sender_id,
        )

    def _validate_handshake_signature_from_message(self, message: dict[str, Any], sender_id: str) -> bool:
        return validate_handshake_signature_from_message(
            self.require_signatures,
            self.peer_public_keys,
            message,
            sender_id,
        )

    def _register_dynamic_peer(self, message: dict[str, Any], sender_id: str) -> None:
        register_dynamic_peer(self.transport, message, sender_id)

    def _verify_msp_certificate(self, cert_id: str, sender_msp_id: str) -> bool:
        """
        Verify a peer's MSP certificate.
        
        Checks:
        1. Certificate exists in the MSP's CA
        2. Certificate is valid (not expired, not revoked)
        3. Certificate belongs to the claimed MSP organization
        
        Args:
            cert_id: Certificate ID to verify.
            sender_msp_id: Claimed MSP organization ID.
        
        Returns:
            True if the certificate is valid, False otherwise.
        """
        try:
            return verify_msp_certificate(
                self.msp,
                self.identity_mgr,
                cert_id,
                sender_msp_id,
            )
        except Exception as e:
            logger.error(f"MSP certificate verification error: {e}")
            return False

    def _is_certificate_valid_in_ca(self, cert_id: str) -> bool:
        return is_certificate_valid_in_ca(self.msp, cert_id)

    def _is_certificate_org_match(self, cert_id: str, sender_msp_id: str) -> bool:
        return is_certificate_org_match(self.identity_mgr, cert_id, sender_msp_id)
