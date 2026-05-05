"""
Module for loading and managing node identity and peer public keys.
"""

import os
import json
import logging
from typing import Any
from hierachain.security.security_utils import KeyPair
from hierachain.config.settings import settings

logger = logging.getLogger(__name__)

class NodeIdentity:
    """Loaded identity of a node."""
    def __init__(self, data: dict[str, Any]):
        self.node_id = data["node_id"]
        self.msp_id = data["msp_id"]
        self.signing_keypair = KeyPair.from_private_key(data["signing_key"])
        self.signing_public_key = data["signing_public_key"]
        self.transport_secret_key = data["transport_secret_key"].encode('utf-8')
        self.transport_public_key = data["transport_public_key"].encode('utf-8')

def load_node_identity() -> NodeIdentity | None:
    """Load node identity from the configured path."""
    path = settings.VALIDATOR_IDENTITY_PATH
    if not os.path.exists(path):
        logger.warning("Identity file not found at %s. Node will run without fixed identity.", path)
        return None
    
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return NodeIdentity(data)
    except Exception as e:
        logger.error("Failed to load node identity from %s: %s", path, e)
        return None

def load_all_peer_public_keys(peers_file: str) -> dict[str, str]:
    """Load public keys for all peers from a central file (for strict trust policy)."""
    if not os.path.exists(peers_file):
        return {}
    
    try:
        with open(peers_file, "r") as f:
            data = json.load(f)
        
        return {node_id: identity["signing_public_key"] for node_id, identity in data.items()}
    except Exception as e:
        logger.error("Failed to load peer public keys from %s: %s", peers_file, e)
        return {}
