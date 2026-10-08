"""
Module for loading and managing node identity and peer public keys.
"""

import logging
import os
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from hierachain.config.settings import settings
from hierachain.security.security_utils import KeyPair
from hierachain.serialization import loads_json

logger = logging.getLogger(__name__)

class NodeIdentity:
    """Loaded identity of a node."""
    def __init__(self, data: dict[str, Any]):
        self.node_id = data["node_id"]
        self.msp_id = data["msp_id"]
        self.signing_keypair = KeyPair.from_private_key(data["signing_key"])
        self.signing_public_key = data["signing_public_key"]
        if self.signing_keypair.public_key != self.signing_public_key:
            raise ValueError("Node signing public key does not match its private key")
        self.transport_secret_key = data["transport_secret_key"].encode('utf-8')
        self.transport_public_key = data["transport_public_key"].encode('utf-8')

def load_node_identity() -> NodeIdentity | None:
    """Load node identity from the configured path."""
    path = settings.VALIDATOR_IDENTITY_PATH
    if not os.path.exists(path):
        logger.warning("Identity file not found at %s. Node will run without fixed identity.", path)
        return None
    
    try:
        with open(path, "rb") as f:
            data = loads_json(f.read())
        return NodeIdentity(data)
    except Exception as e:
        logger.error("Failed to load node identity from %s: %s", path, e)
        return None

def load_all_peer_public_keys(peers_file: str) -> dict[str, str]:
    """Load public keys for all peers from a central file (for strict trust policy)."""
    if not os.path.exists(peers_file):
        return {}
    try:
        with open(peers_file, "rb") as f:
            data = loads_json(f.read())
        return {node_id: identity["signing_public_key"] for node_id, identity in data.items()}
    except Exception as e:
        logger.error("Failed to load peer public keys from %s: %s", peers_file, e)
        return {}


def load_trusted_block_keys(path: str) -> dict[str, bytes]:
    """Load the operator-approved node ID to Ed25519 public key map."""
    if not path:
        raise RuntimeError("HRC_BLOCK_TRUSTED_KEYS_FILE is required")
    try:
        with open(path, "rb") as trusted_file:
            raw_keys = loads_json(trusted_file.read())
        if not isinstance(raw_keys, dict) or not raw_keys:
            raise ValueError("Trusted block key map must be a non-empty object")
        result = {}
        for creator_id, public_hex in raw_keys.items():
            if not isinstance(creator_id, str) or not creator_id:
                raise ValueError("Trusted block creator ID must be non-empty")
            if not isinstance(public_hex, str):
                raise ValueError(f"Trusted block key for {creator_id} must be hex")
            public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
            result[creator_id] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        return result
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"Cannot load trusted block keys from {path}: {exc}") from exc


def require_block_identity(
    node_identity: NodeIdentity | None = None,
    trusted_public_keys: dict[str, bytes] | None = None,
) -> tuple[NodeIdentity, dict[str, bytes]]:
    """Resolve a signer and require its public key in the trusted map."""
    identity = node_identity or load_node_identity()
    if identity is None:
        raise RuntimeError("A fixed node identity is required to sign blocks")
    keys = (
        trusted_public_keys if trusted_public_keys is not None
        else load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)
    )
    expected = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(identity.signing_public_key)
    ).public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if keys.get(identity.node_id) != expected:
        raise RuntimeError(f"Node {identity.node_id} has no matching trusted block key")
    return identity, keys
