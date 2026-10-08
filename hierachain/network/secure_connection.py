"""
Secure Channel Management for HieraChain Ledger

This module bridges the gap between the application-level security (MSP/Certificates)
and the network transport (ZeroMQ). It handles:
1. Transport Key Management (Curve25519)
2. Application Logic Handshake (verifying MSP certificates over the channel)
3. Cryptographic message authentication (Ed25519 signatures)
4. Connection Lifecycle Management
"""

import logging
import math
import time
import uuid
from typing import Any, cast

import zmq
import zmq.auth

from hierachain.config.settings import get_settings
from hierachain.network.message_cryptographic import (
    sign_handshake_payload,
    sign_message,
    verify_handshake_signature,
    verify_message,
)
from hierachain.network.peer_trust_manager import PeerTrustManager
from hierachain.network.zmq_transport import ZmqNode
from hierachain.security.identity import IdentityManager
from hierachain.security.msp import HierarchicalMSP
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
        logger.warning("Dropped Unauthenticated Message from %s", sender_id)
        return False

    if not require_signatures:
        return True

    peer_key = peer_public_keys.get(sender_id)
    if not peer_key:
        logger.warning("No public key for peer %s, dropping message", sender_id)
        return False

    if not verify_message(message, peer_key):
        logger.warning(
            "Invalid signature on message from %s, dropping message",
            sender_id,
        )
        return False

    return True


def check_trust_policy(trust_manager: PeerTrustManager, sender_id: str) -> bool:
    if trust_manager.is_trusted(sender_id):
        return True

    logger.warning(
        "Handshake rejected: Peer %s is not trusted by policy.",
        sender_id,
    )
    return False


def is_certificate_valid_in_ca(msp: HierarchicalMSP, cert_id: str) -> bool:
    ca = getattr(msp, "ca", None)
    certificates = getattr(ca, "issued_certificates", None)
    verify_certificate = getattr(ca, "verify_certificate", None)
    if (
        not isinstance(cert_id, str)
        or not isinstance(certificates, dict)
        or cert_id not in certificates
        or not callable(verify_certificate)
    ):
        return False

    try:
        return bool(verify_certificate(cert_id))
    except Exception:
        logger.exception("Certificate %s failed CA verification", cert_id)
        return False


def is_certificate_org_match(
    identity_mgr: IdentityManager | None,
    entity_id: str,
    sender_msp_id: str,
    sender_public_key: str,
) -> bool:
    if identity_mgr is None:
        return False

    try:
        user_info = identity_mgr.get_user_info(entity_id)
    except Exception:
        logger.exception("Failed to resolve registered identity %s", entity_id)
        return False
    if not user_info:
        return False

    if (
        user_info.get("org_id") != sender_msp_id
        or user_info.get("public_key") != sender_public_key
    ):
        logger.debug(
            "Identity %s does not match claimed organization or certificate key",
            entity_id,
        )
        return False

    return True


def verify_msp_certificate(
    msp: HierarchicalMSP,
    identity_mgr: IdentityManager | None,
    cert_id: str,
    sender_msp_id: str,
    sender_id: str,
    sender_public_key: str,
) -> bool:
    if not is_certificate_valid_in_ca(msp, cert_id):
        return False

    try:
        certificate = msp.ca.issued_certificates[cert_id]
    except Exception:
        logger.exception("Failed to resolve CA certificate %s", cert_id)
        return False
    if (
        getattr(certificate, "subject", None) != sender_id
        or getattr(certificate, "public_key", None) != sender_public_key
    ):
        logger.warning(
            "Certificate %s does not bind routing identity %s and signing key",
            cert_id,
            sender_id,
        )
        return False

    if not is_certificate_org_match(
        identity_mgr, sender_id, sender_msp_id, sender_public_key
    ):
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
    sender_public_key = message.get("sender_public_key")

    if not all(
        isinstance(value, str) and value
        for value in (cert_id, sender_msp_id, sender_public_key, sender_id)
    ):
        logger.warning(
            "Handshake rejected from %s: "
            "Missing certificate, routing identity, organization, or public key.",
            sender_id,
        )
        return False

    if not verify_msp_certificate(
        msp,
        identity_mgr,
        cert_id,
        sender_msp_id,
        sender_id,
        sender_public_key,
    ):
        logger.warning(
            "Handshake rejected from %s: "
            "Invalid MSP certificate '%s'.",
            sender_id,
            cert_id,
        )
        return False

    return True


def validate_handshake_signature_from_message(
    peer_public_keys: dict[str, str],
    message: dict[str, Any],
    sender_id: str,
) -> bool:
    sender_public_key = message.get("sender_public_key")
    signature = message.get("signature")

    if isinstance(sender_public_key, str) and isinstance(signature, str):
        handshake_data = {k: v for k, v in message.items() if k != "signature"}
        if not verify_handshake_signature(
            handshake_data, cast(str, signature), cast(str, sender_public_key)
        ):
            logger.warning(
                "Handshake rejected from %s: Invalid cryptographic signature.",
                sender_id,
            )
            return False

        peer_public_keys[sender_id] = cast(str, sender_public_key)
        return True

    logger.warning(
        "Handshake rejected from %s: a certificate-bound public key and "
        "signature are required.",
        sender_id,
    )
    return False


def create_replay_fields() -> dict[str, float | str]:
    """Create freshness fields that the ZMQ replay gate requires."""
    return {"timestamp": time.time(), "nonce": uuid.uuid4().hex}


def has_fresh_handshake_envelope(message: dict[str, Any]) -> bool:
    """Check freshness fields for direct handler calls outside ZMQ dispatch."""
    timestamp = message.get("timestamp")
    nonce = message.get("nonce")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return False
    try:
        timestamp_value = float(timestamp)
    except (TypeError, ValueError, OverflowError):
        return False
    if (
        not math.isfinite(timestamp_value)
        or abs(time.time() - timestamp_value) > 60
        or not isinstance(nonce, str)
        or not 0 < len(nonce) <= 128
    ):
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

    logger.info(
        "Dynamically registering peer %s from Handshake",
        sender_id,
    )
    transport.register_peer(
        sender_id,
        cast(str, return_addr),
        public_key=cast(str, transport_key).encode("utf-8"),
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
    ) -> None:
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
        if settings.env == "production" and trust_policy != "strict":
            logger.warning(
                "SECURITY WARNING: Production environment running with "
                "P2P trust_policy='%s' instead of 'strict'. "
                "This allows any peer to connect without allowlist. "
                "Set HRC_P2P_TRUST_POLICY=strict for production.",
                trust_policy,
            )

        if settings.env == "production" and not self.require_signatures:
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
        # Bind each ACK to the nonce of the current outbound handshake.
        self.pending_handshakes: dict[str, tuple[str, float]] = {}

    async def start(self) -> None:
        """Start the secure transport."""
        # Set handler to intercept messages for handshake
        self.transport.set_message_validator(self._prevalidate_message)
        self.transport.set_handler(self._handle_message)
        await self.transport.start()
        logger.info(
            "Secure Node %s started. "
            "Transport Key: %s...",
            self.node_id,
            self.transport_public.decode("utf-8")[:8],
        )

    async def connect_to_peer(
        self, peer_id: str, address: str, peer_transport_key: str,
    ) -> None:
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
                if peer_transport_key else None
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
            logger.warning(
                "Cannot send to unauthenticated peer %s", peer_id,
            )
            return False

        if self.require_signatures:
            message = sign_message(payload, self.signing_keypair, self.node_id)
        else:
            message = payload

        return await self.transport.send_direct(peer_id, message)

    async def _initiate_handshake(self, peer_id: str) -> None:
        """Send a handshake request to prove Identity (MSP)."""
        certificate_id = self._get_local_certificate_id()
        if certificate_id is None:
            logger.warning(
                "Cannot initiate handshake: no active certificate binds node %s "
                "to its signing key",
                self.node_id,
            )
            return

        logger.info(
            "Initiating Handshake with %s...",
            peer_id,
        )

        # Create handshake payload (without signature)
        replay_fields = create_replay_fields()
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": self.msp.organization_id,
            "certificate_id": certificate_id,
            "sender_public_key": self.signing_keypair.public_key,
            "return_address": self.transport.address,
            "transport_public_key": self.transport_public.decode("utf-8"),
            **replay_fields,
        }
        nonce = cast(str, replay_fields["nonce"])
        timestamp = cast(float, replay_fields["timestamp"])

        # Sign the handshake payload
        signature = sign_handshake_payload(handshake_data, self.signing_keypair)
        handshake_data["signature"] = signature

        self.pending_handshakes[peer_id] = (nonce, timestamp)
        success = await self.transport.send_direct(peer_id, handshake_data)
        if not success:
            if self.pending_handshakes.get(peer_id) == (nonce, timestamp):
                self.pending_handshakes.pop(peer_id, None)
            logger.error(
                "Failed to send handshake to %s",
                peer_id,
            )

    def _prevalidate_message(self, message: dict[str, Any], sender_id: str) -> bool:
        """Verify identity/signature before transport stores a replay entry."""
        kind = message.get("type")
        if kind not in ("HANDSHAKE_INIT", "HANDSHAKE_ACK"):
            return self._handle_data_message(message, sender_id)
        if not has_fresh_handshake_envelope(message) or not self._check_trust_policy(sender_id):
            return False
        if kind == "HANDSHAKE_ACK":
            pending = self.pending_handshakes.get(sender_id)
            if (pending is None or time.time() - pending[1] > 60
                    or message.get("handshake_nonce") != pending[0] or message.get("status") != "OK"):
                return False
        return (
            self._validate_msp_from_message(message, sender_id)
            and self._validate_handshake_signature_from_message(message, sender_id)
        )

    async def _handle_message(
        self, message: dict[str, Any], sender_id: str
    ) -> None:
        """Intercept messages to handle Handshake vs Data."""
        msg_type = message.get("type")

        if msg_type == "HANDSHAKE_INIT":
            await self._handle_handshake_request(message, sender_id)
            return

        if msg_type == "HANDSHAKE_ACK":
            await self._handle_handshake_ack(message, sender_id)
            return

        if self._handle_data_message(message, sender_id):
            logger.info(
                "Received Authenticated Message from %s",
                sender_id,
            )

    def _handle_data_message(self, message: dict[str, Any], sender_id: str) -> bool:
        return handle_data_message(
            self.authenticated_peers,
            self.require_signatures,
            self.peer_public_keys,
            message,
            sender_id,
        )

    async def handle_handshake_request(
        self, message: dict[str, Any], sender_id: str
    ) -> None:
        await self._handle_handshake_request(message, sender_id)

    async def handle_handshake_ack(
        self, message: dict[str, Any], sender_id: str
    ) -> None:
        await self._handle_handshake_ack(message, sender_id)

    async def _handle_handshake_request(
        self, message: dict[str, Any], sender_id: str
    ) -> None:
        """
        Process incoming handshake with full identity verification.

        Steps:
        1. Trust policy check (allowlist/blocklist)
        2. MSP certificate verification
        3. Handshake signature cryptographic verification
        4. Only then mark peer as authenticated
        """
        if not has_fresh_handshake_envelope(message):
            logger.warning(
                "Handshake rejected from %s: missing or stale replay fields.",
                sender_id,
            )
            return

        if not self._check_trust_policy(sender_id):
            return

        if not self._validate_msp_from_message(message, sender_id):
            return

        if not self._validate_handshake_signature_from_message(message, sender_id):
            return

        certificate_id = self._get_local_certificate_id()
        if certificate_id is None:
            logger.warning(
                "Handshake rejected from %s: local node %s has no active "
                "certificate bound to its signing key",
                sender_id,
                self.node_id,
            )
            return

        self._register_dynamic_peer(message, sender_id)

        logger.info(
            "Handshake Validated for %s. "
            "Trust + MSP + Signature verified. Sending ACK.",
            sender_id,
        )
        self.authenticated_peers[sender_id] = True

        # Create signed ACK
        ack_data = {
            "type": "HANDSHAKE_ACK",
            "status": "OK",
            "sender_msp_id": self.msp.organization_id,
            "certificate_id": certificate_id,
            "sender_public_key": self.signing_keypair.public_key,
            "handshake_nonce": message["nonce"],
            **create_replay_fields(),
        }
        ack_signature = sign_handshake_payload(ack_data, self.signing_keypair)
        ack_data["signature"] = ack_signature

        await self.transport.send_direct(sender_id, ack_data)

    async def _handle_handshake_ack(
        self, message: dict[str, Any], sender_id: str
    ) -> None:
        """Accept an ACK only for a fresh, trusted, certificate-bound request."""
        pending = self.pending_handshakes.get(sender_id)
        if pending is None:
            logger.warning(
                "Handshake ACK from %s has no pending handshake, rejecting.",
                sender_id,
            )
            return

        request_nonce, request_timestamp = pending
        if (
            time.time() - request_timestamp > 60
            or message.get("handshake_nonce") != request_nonce
            or not has_fresh_handshake_envelope(message)
        ):
            logger.warning(
                "Handshake ACK from %s is stale or does not match the pending "
                "handshake, rejecting.",
                sender_id,
            )
            if time.time() - request_timestamp > 60:
                self.pending_handshakes.pop(sender_id, None)
            return

        if not self._check_trust_policy(sender_id):
            return

        if message.get("status") != "OK":
            logger.error(
                "Handshake Refused by %s ❌", sender_id,
            )
            return

        if not self._validate_msp_from_message(message, sender_id):
            return

        # Verify the ACK with the public key bound to its active MSP certificate.
        if not self._validate_handshake_signature_from_message(message, sender_id):
            return

        self.pending_handshakes.pop(sender_id, None)

        logger.info(
            "Secure Connection Established with %s ✅", sender_id,
        )
        self.authenticated_peers[sender_id] = True

    def _check_trust_policy(self, sender_id: str) -> bool:
        return check_trust_policy(self.trust_manager, sender_id)

    def _validate_msp_from_message(
        self, message: dict[str, Any], sender_id: str
    ) -> bool:
        return validate_msp_from_message(
            self.msp,
            self.identity_mgr,
            message,
            sender_id,
        )

    def _validate_handshake_signature_from_message(
        self, message: dict[str, Any], sender_id: str
    ) -> bool:
        return validate_handshake_signature_from_message(
            self.peer_public_keys,
            message,
            sender_id,
        )

    def _register_dynamic_peer(self, message: dict[str, Any], sender_id: str) -> None:
        register_dynamic_peer(self.transport, message, sender_id)

    def _get_local_certificate_id(self) -> str | None:
        """Resolve this node's active certificate bound to its registered key."""
        try:
            user_info = self.identity_mgr.get_user_info(self.node_id)
            if (
                not user_info
                or user_info.get("org_id") != self.msp.organization_id
                or user_info.get("public_key") != self.signing_keypair.public_key
            ):
                return None

            certificates = getattr(self.msp.ca, "issued_certificates", None)
            if not isinstance(certificates, dict):
                return None

            for cert_id, certificate in certificates.items():
                if (
                    getattr(certificate, "subject", None) == self.node_id
                    and getattr(certificate, "public_key", None)
                    == self.signing_keypair.public_key
                    and is_certificate_valid_in_ca(self.msp, cert_id)
                ):
                    return cert_id
        except Exception:
            logger.exception(
                "Failed to resolve active certificate for node %s", self.node_id
            )
        return None

    def _verify_msp_certificate(
        self,
        cert_id: str,
        sender_msp_id: str,
        sender_id: str,
        sender_public_key: str,
    ) -> bool:
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
                sender_id,
                sender_public_key,
            )
        except Exception as e:
            logger.error("MSP certificate verification error: %s", e,)
            return False

    def _is_certificate_valid_in_ca(self, cert_id: str) -> bool:
        return is_certificate_valid_in_ca(self.msp, cert_id)

    def _is_certificate_org_match(
        self, entity_id: str, sender_msp_id: str, sender_public_key: str
    ) -> bool:
        return is_certificate_org_match(
            self.identity_mgr, entity_id, sender_msp_id, sender_public_key
        )
