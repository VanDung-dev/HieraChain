"""
Tests for handshake authentication with MSP/Identity verification.

Covers:
- Handshake with valid signed payload
- Rejection of handshake with invalid signature
- Rejection of handshake with invalid/revoked MSP certificate
- Authenticated_peers flag only set when all checks pass
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hierachain.network import SecureConnectionManager
from hierachain.network import (
    sign_handshake_payload,
    verify_handshake_signature,
)
from hierachain.security import HierarchicalMSP, IdentityManager, KeyPair


@pytest.fixture
def identity_mgr():
    mgr = MagicMock(spec=IdentityManager)
    mgr.get_user_info.return_value = {
        "org_id": "org-1",
        "role": "peer",
        "public_key": None,
    }
    return mgr


@pytest.fixture
def msp():
    m = MagicMock(spec=HierarchicalMSP)
    m.organization_id = "org-1"
    m.ca = MagicMock()
    m.ca.verify_certificate.return_value = True
    return m


@pytest.fixture
def peer_keypair():
    return KeyPair.generate()


@pytest.fixture
def node_keypair():
    return KeyPair.generate()


class TestHandshakeSignatureVerification:
    """Test Ed25519 signature verification in handshake."""

    def test_valid_handshake_signature(self, peer_keypair):
        """Valid signature should verify correctly."""
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(handshake_data, peer_keypair)
        assert verify_handshake_signature(
            handshake_data, signature, peer_keypair.public_key
        ) is True

    def test_invalid_handshake_signature(self, peer_keypair):
        """Tampered payload should fail verification."""
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(handshake_data, peer_keypair)

        # Tamper with the data
        handshake_data["sender_msp_id"] = "org-evil"
        assert verify_handshake_signature(
            handshake_data, signature, peer_keypair.public_key
        ) is False

    def test_wrong_key_signature(self, peer_keypair):
        """Signature by a different key should fail verification."""
        other_keypair = KeyPair.generate()
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        # Sign with other key but verify with peer_keypair
        signature = sign_handshake_payload(handshake_data, other_keypair)
        assert verify_handshake_signature(
            handshake_data, signature, peer_keypair.public_key
        ) is False


async def _run_signed_handshake(manager, peer_keypair):
    handshake_data = {
        "type": "HANDSHAKE_INIT",
        "sender_msp_id": "org-1",
        "certificate_id": "node-peer",
        "sender_public_key": peer_keypair.public_key,
    }
    signature = sign_handshake_payload(handshake_data, peer_keypair)
    handshake_data["signature"] = signature

    await manager.handle_handshake_request(
        handshake_data, "node-peer"
    )

    return manager.authenticated_peers.get("node-peer")


class TestSecureConnectionHandshake:
    """Test SecureConnectionManager handshake flow."""

    @pytest.fixture
    def manager(self, msp, identity_mgr, node_keypair):
        """Create SecureConnectionManager with mocked settings."""
        with patch(
            "hierachain.network.secure_connection.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.ENV = "dev"
            settings.get_p2p_config.return_value = {
                "trust_policy": "open",
                "peer_allowlist": [],
                "require_signatures": True,
            }
            mock_settings.return_value = settings

            with patch(
                "hierachain.network.secure_connection.zmq.curve_keypair"
            ) as mock_curve:
                mock_curve.return_value = (b"fake_pub_key", b"fake_sec_key")
                with patch(
                    "hierachain.network.secure_connection.ZmqNode"
                ):
                    mgr = SecureConnectionManager(
                        node_id="node-local",
                        port=5000,
                        msp=msp,
                        identity_mgr=identity_mgr,
                        signing_keypair=node_keypair,
                    )
                    mgr.transport = MagicMock()
                    mgr.transport.peers = {}
                    mgr.transport.send_direct = AsyncMock(
                        return_value=True
                    )
                    return mgr

    @pytest.mark.asyncio
    async def test_handshake_valid_full_auth(
        self, manager, peer_keypair, msp
    ):
        """Full valid handshake should authenticate peer."""
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
            "return_address": "tcp://127.0.0.1:5001",
            "transport_public_key": "fake_transport_key",
        }
        signature = sign_handshake_payload(
            handshake_data, peer_keypair
        )
        handshake_data["signature"] = signature

        await manager.handle_handshake_request(
            handshake_data, "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is True
        assert manager.peer_public_keys.get("node-peer") == (
            peer_keypair.public_key
        )

    @pytest.mark.asyncio
    async def test_handshake_invalid_signature_rejected(
        self, manager, peer_keypair
    ):
        """Handshake with invalid signature should be rejected."""
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
            "signature": "invalid_hex_signature",
        }

        await manager.handle_handshake_request(
            handshake_data, "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_handshake_revoked_cert_rejected(
        self, manager, peer_keypair, msp
    ):
        """Handshake with revoked MSP certificate should be rejected."""
        msp.ca.verify_certificate.return_value = False

        result = await _run_signed_handshake(
            manager, peer_keypair
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_handshake_untrusted_peer_rejected(
        self, manager, peer_keypair
    ):
        """Untrusted peer (blocked) should have handshake rejected."""
        manager.trust_manager.block_peer("node-peer")

        result = await _run_signed_handshake(
            manager, peer_keypair
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_handshake_missing_cert_rejected(self, manager):
        """Handshake without certificate_id should be rejected."""
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
        }

        await manager.handle_handshake_request(
            handshake_data, "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_handshake_org_mismatch_rejected(
        self, manager, peer_keypair, identity_mgr
    ):
        """Handshake claiming wrong org should be rejected."""
        identity_mgr.get_user_info.return_value = {
            "org_id": "org-real",
            "role": "peer",
        }

        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-fake",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(
            handshake_data, peer_keypair
        )
        handshake_data["signature"] = signature

        await manager.handle_handshake_request(
            handshake_data, "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_handshake_ack_valid(
        self, manager, peer_keypair
    ):
        """Valid handshake ACK should authenticate peer."""
        ack_data = {
            "type": "HANDSHAKE_ACK",
            "status": "OK",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(ack_data, peer_keypair)
        ack_data["signature"] = signature

        await manager.handle_handshake_ack(ack_data, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is True

    @pytest.mark.asyncio
    async def test_handshake_ack_invalid_signature(
        self, manager, peer_keypair
    ):
        """ACK with invalid signature should not authenticate."""
        ack_data = {
            "type": "HANDSHAKE_ACK",
            "status": "OK",
            "sender_public_key": peer_keypair.public_key,
            "signature": "invalid_signature",
        }

        await manager.handle_handshake_ack(ack_data, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_handshake_ack_refused(self, manager):
        """Refused ACK should not authenticate."""
        ack_data = {
            "type": "HANDSHAKE_ACK",
            "status": "REJECTED",
        }

        await manager.handle_handshake_ack(ack_data, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None
