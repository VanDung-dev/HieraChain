"""Tests for certificate-bound MSP handshake authentication."""

import logging
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hierachain.network import (
    SecureConnectionManager,
    sign_handshake_payload,
    verify_handshake_signature,
)
from hierachain.security import HierarchicalMSP, IdentityManager, KeyPair


@pytest.fixture
def identity_mgr() -> IdentityManager:
    manager = IdentityManager()
    manager.register_organization("org-1", "Organization 1")
    return manager


@pytest.fixture
def msp() -> HierarchicalMSP:
    return HierarchicalMSP(
        "org-1", {"root_cert": "test-root", "policy": {}}
    )


@pytest.fixture
def peer_keypair() -> KeyPair:
    return KeyPair.generate()


@pytest.fixture
def node_keypair() -> KeyPair:
    return KeyPair.generate()


def _register_identity(
    msp: HierarchicalMSP,
    identity_mgr: IdentityManager,
    entity_id: str,
    keypair: KeyPair,
    org_id: str = "org-1",
) -> Any:
    if identity_mgr.get_organization_info(org_id) is None:
        identity_mgr.register_organization(org_id, org_id)
    certificate = msp.ca.issue_certificate(
        subject=entity_id,
        public_key=keypair.public_key,
        attributes={"organization_id": org_id},
    )
    identity_mgr.register_user(
        entity_id, org_id, "peer", public_key=keypair.public_key
    )
    return certificate


def _signed_handshake(
    keypair: KeyPair, certificate: Any, **fields: Any
) -> dict[str, Any]:
    handshake_data: dict[str, Any] = {
        "type": "HANDSHAKE_INIT",
        "sender_msp_id": "org-1",
        "certificate_id": certificate.cert_id,
        "sender_public_key": keypair.public_key,
        "timestamp": time.time(),
        "nonce": uuid.uuid4().hex,
        **fields,
    }
    handshake_data["signature"] = sign_handshake_payload(
        handshake_data, keypair
    )
    return handshake_data


def _signed_ack(
    keypair: KeyPair,
    certificate: Any,
    request_nonce: str,
    **fields: Any,
) -> dict[str, Any]:
    ack_data: dict[str, Any] = {
        "type": "HANDSHAKE_ACK",
        "status": "OK",
        "sender_msp_id": "org-1",
        "certificate_id": certificate.cert_id,
        "sender_public_key": keypair.public_key,
        "handshake_nonce": request_nonce,
        "timestamp": time.time(),
        "nonce": uuid.uuid4().hex,
        **fields,
    }
    ack_data["signature"] = sign_handshake_payload(ack_data, keypair)
    return ack_data


def _replay_gate() -> Any:
    """Build a ZMQ replay validator without starting sockets."""
    from hierachain.network.zmq_transport import ZmqNode

    node = object.__new__(ZmqNode)
    node.replay_tolerance = 60
    node.replay_buffer = set()
    return node


@pytest.fixture
def manager_factory(msp, identity_mgr):
    def build(node_id: str, keypair: KeyPair) -> SecureConnectionManager:
        with patch(
            "hierachain.network.secure_connection.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.env = "dev"
            settings.get_p2p_config.return_value = {
                "trust_policy": "open",
                "peer_allowlist": [],
                "require_signatures": True,
            }
            mock_settings.return_value = settings
            with patch(
                "hierachain.network.secure_connection.zmq.curve_keypair",
                return_value=(b"fake_pub_key", b"fake_sec_key"),
            ), patch("hierachain.network.secure_connection.ZmqNode"):
                manager = SecureConnectionManager(
                    node_id=node_id,
                    port=5000,
                    msp=msp,
                    identity_mgr=identity_mgr,
                    signing_keypair=keypair,
                )

        manager.transport = MagicMock()
        manager.transport.address = "tcp://127.0.0.1:5000"
        manager.transport.peers = {}
        manager.transport.send_direct = AsyncMock(return_value=True)
        return manager

    return build


@pytest.fixture
def manager(manager_factory, msp, identity_mgr, node_keypair):
    _register_identity(msp, identity_mgr, "node-local", node_keypair)
    return manager_factory("node-local", node_keypair)


class TestHandshakeSignatureVerification:
    """Test Ed25519 signature verification in handshake."""

    def test_valid_handshake_signature(self, peer_keypair):
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
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(handshake_data, peer_keypair)
        handshake_data["sender_msp_id"] = "org-evil"
        assert verify_handshake_signature(
            handshake_data, signature, peer_keypair.public_key
        ) is False

    def test_wrong_key_signature(self, peer_keypair):
        other_keypair = KeyPair.generate()
        handshake_data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-peer",
            "sender_public_key": peer_keypair.public_key,
        }
        signature = sign_handshake_payload(handshake_data, other_keypair)
        assert verify_handshake_signature(
            handshake_data, signature, peer_keypair.public_key
        ) is False


class TestSecureConnectionHandshake:
    """Test signed handshakes against real CA certificates and identities."""

    def test_production_warns_for_insecure_p2p_settings(
        self, msp, identity_mgr, node_keypair, caplog
    ):
        settings = MagicMock()
        settings.env = "production"
        settings.get_p2p_config.return_value = {
            "trust_policy": "open",
            "peer_allowlist": [],
            "require_signatures": False,
        }

        with patch(
            "hierachain.network.secure_connection.get_settings",
            return_value=settings,
        ), patch(
            "hierachain.network.secure_connection.zmq.curve_keypair",
            return_value=(b"fake_pub_key", b"fake_sec_key"),
        ), patch("hierachain.network.secure_connection.ZmqNode"):
            with caplog.at_level(logging.WARNING):
                SecureConnectionManager(
                    node_id="node-local",
                    port=5000,
                    msp=msp,
                    identity_mgr=identity_mgr,
                    signing_keypair=node_keypair,
                )

        assert "P2P trust_policy='open' instead of 'strict'" in caplog.text
        assert "without P2P message signature verification" in caplog.text

    @pytest.mark.asyncio
    async def test_valid_round_trip_uses_transport_replay_envelopes(
        self, manager, manager_factory, msp, identity_mgr, peer_keypair
    ):
        _register_identity(msp, identity_mgr, "node-peer", peer_keypair)
        responder = manager_factory("node-peer", peer_keypair)

        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        init = manager.transport.send_direct.await_args.args[1]
        gate = _replay_gate()
        assert gate._is_valid_replay(init)
        assert verify_handshake_signature(
            {key: value for key, value in init.items() if key != "signature"},
            init["signature"],
            manager.signing_keypair.public_key,
        )

        await responder.handle_handshake_request(init, "node-local")
        ack = responder.transport.send_direct.await_args.args[1]
        assert ack["handshake_nonce"] == init["nonce"]
        assert gate._is_valid_replay(ack)
        assert verify_handshake_signature(
            {key: value for key, value in ack.items() if key != "signature"},
            ack["signature"],
            responder.signing_keypair.public_key,
        )

        await manager.handle_handshake_ack(ack, "node-peer")

        assert responder.authenticated_peers["node-local"] is True
        assert manager.authenticated_peers["node-peer"] is True
        assert manager.pending_handshakes == {}
        assert manager.peer_public_keys["node-peer"] == peer_keypair.public_key

    @pytest.mark.asyncio
    async def test_invalid_signature_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        message = _signed_handshake(peer_keypair, certificate)
        message["signature"] = "invalid_hex_signature"

        await manager.handle_handshake_request(message, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_revoked_certificate_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        msp.ca.revoke_certificate(certificate.cert_id)

        await manager.handle_handshake_request(
            _signed_handshake(peer_keypair, certificate), "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_blocked_peer_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        manager.trust_manager.block_peer("node-peer")

        await manager.handle_handshake_request(
            _signed_handshake(peer_keypair, certificate), "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_missing_certificate_is_rejected(self, manager):
        message = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "sender_public_key": "a" * 64,
            "timestamp": time.time(),
            "nonce": uuid.uuid4().hex,
        }

        await manager.handle_handshake_request(message, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_stale_handshake_envelope_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        message = _signed_handshake(peer_keypair, certificate)
        message["timestamp"] = time.time() - 61
        message["signature"] = sign_handshake_payload(
            {key: value for key, value in message.items() if key != "signature"},
            peer_keypair,
        )

        await manager.handle_handshake_request(message, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_claimed_organization_must_match_registered_identity(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair, "org-real"
        )

        await manager.handle_handshake_request(
            _signed_handshake(
                peer_keypair, certificate, sender_msp_id="org-fake"
            ),
            "node-peer",
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_certificate_subject_must_match_routing_identity(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-real", peer_keypair
        )

        await manager.handle_handshake_request(
            _signed_handshake(peer_keypair, certificate), "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_certificate_key_must_match_handshake_signing_key(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        unbound_keypair = KeyPair.generate()

        await manager.handle_handshake_request(
            _signed_handshake(
                unbound_keypair,
                certificate,
                sender_public_key=unbound_keypair.public_key,
            ),
            "node-peer",
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_identity_registry_entry_is_required(
        self, manager, msp, peer_keypair
    ):
        certificate = msp.ca.issue_certificate(
            subject="node-peer",
            public_key=peer_keypair.public_key,
            attributes={"organization_id": "org-1"},
        )

        await manager.handle_handshake_request(
            _signed_handshake(peer_keypair, certificate), "node-peer"
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_unsolicited_self_signed_ack_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        ack = _signed_ack(peer_keypair, certificate, "unsolicited-challenge")

        await manager.handle_handshake_ack(ack, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None
        assert manager.peer_public_keys.get("node-peer") is None
        assert manager._handle_data_message(
            {"payload": {"event": "forged"}}, "node-peer"
        ) is False

    @pytest.mark.asyncio
    async def test_ack_must_match_pending_handshake_nonce(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        ack = _signed_ack(peer_keypair, certificate, "different-challenge")

        await manager.handle_handshake_ack(ack, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_expired_pending_handshake_ack_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        request = manager.transport.send_direct.await_args.args[1]
        manager.pending_handshakes["node-peer"] = (
            request["nonce"], time.time() - 61
        )

        await manager.handle_handshake_ack(
            _signed_ack(peer_keypair, certificate, request["nonce"]),
            "node-peer",
        )

        assert manager.authenticated_peers.get("node-peer") is None
        assert "node-peer" not in manager.pending_handshakes

    @pytest.mark.asyncio
    async def test_ack_obeys_strict_trust_policy(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        manager.trust_manager.set_policy("strict")
        request = manager.transport.send_direct.await_args.args[1]

        await manager.handle_handshake_ack(
            _signed_ack(peer_keypair, certificate, request["nonce"]),
            "node-peer",
        )

        assert manager.authenticated_peers.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_ack_certificate_key_must_match_signature_key(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        request = manager.transport.send_direct.await_args.args[1]
        unbound_keypair = KeyPair.generate()
        ack = _signed_ack(
            unbound_keypair,
            certificate,
            request["nonce"],
            sender_public_key=unbound_keypair.public_key,
        )

        await manager.handle_handshake_ack(ack, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None
        assert manager.peer_public_keys.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_ack_invalid_signature_is_rejected(
        self, manager, msp, identity_mgr, peer_keypair
    ):
        certificate = _register_identity(
            msp, identity_mgr, "node-peer", peer_keypair
        )
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        request = manager.transport.send_direct.await_args.args[1]
        ack = _signed_ack(peer_keypair, certificate, request["nonce"])
        ack["signature"] = "invalid_signature"

        await manager.handle_handshake_ack(ack, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None
        assert manager.peer_public_keys.get("node-peer") is None

    @pytest.mark.asyncio
    async def test_refused_ack_does_not_authenticate(self, manager):
        await manager.connect_to_peer(
            "node-peer", "tcp://127.0.0.1:5001", "peer-transport-key"
        )
        request = manager.transport.send_direct.await_args.args[1]
        ack = {
            "type": "HANDSHAKE_ACK",
            "status": "REJECTED",
            "handshake_nonce": request["nonce"],
            "timestamp": time.time(),
            "nonce": uuid.uuid4().hex,
        }

        await manager.handle_handshake_ack(ack, "node-peer")

        assert manager.authenticated_peers.get("node-peer") is None


@pytest.mark.asyncio
async def test_invalid_signature_cannot_reserve_transport_replay_state(
    manager, msp, identity_mgr, peer_keypair
) -> None:
    from hierachain.network.zmq_transport import ZmqNode, _process_message_data

    certificate = _register_identity(msp, identity_mgr, "node-peer", peer_keypair)
    message = _signed_handshake(peer_keypair, certificate)
    node = ZmqNode("replay-auth", 0)
    node.set_message_validator(manager._prevalidate_message)
    received = []
    node.set_handler(lambda payload, sender: received.append(sender))
    try:
        invalid = dict(message, nonce="untrusted", signature="00" * 64)
        await _process_message_data(node, invalid, "node-peer")
        assert node.peer_replay_buffers == {}
        await _process_message_data(node, message, "node-peer")
        await _process_message_data(node, message, "node-peer")
        assert received == ["node-peer"]
        assert len(node.peer_replay_buffers["node-peer"]) == 1
    finally:
        await node.stop()
