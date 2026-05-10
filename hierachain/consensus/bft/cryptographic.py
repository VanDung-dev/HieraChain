"""
Cryptographic and verification logic for BFT consensus.
"""

import logging
import hashlib
from typing import Any
from hierachain.config.settings import settings
from hierachain.security.security_utils import verify_signature
from hierachain.security.verify.zk_verifier import ZKVerifier
from hierachain.consensus.bft.types import BFTMessage

logger = logging.getLogger(__name__)


def sign_message(key_provider, data: bytes) -> str:
    """Sign message data using Ed25519."""
    if not key_provider:
        return ""
    return key_provider.sign(data)


def verify_message_signature(
    message: BFTMessage, node_public_keys: dict[str, str]
) -> bool:
    """Verify message signature using Ed25519."""
    import time
    if message.sender_id not in node_public_keys:
        logger.warning(f"No public key for node {message.sender_id}")
        return False

    now = time.time()
    if abs(now - message.timestamp) > 30.0:
        logger.warning(f"BFTMessage timestamp drift too large (replay/old message?): {abs(now - message.timestamp)}s")
        return False
        
    public_key = node_public_keys[message.sender_id]
    payload = message.get_signable_payload()
    
    try:
        return verify_signature(public_key, payload, message.signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def hash_request(request: dict[str, Any]) -> str:
    """Create hash of request"""
    # Simple JSON-like stable hash
    req_str = (
        f"{request.get('client_id')}:"
        f"{request.get('timestamp')}:"
        f"{request.get('operation')}"
    )
    return hashlib.sha256(req_str.encode()).hexdigest()


def verify_operation_zk_proof(data: dict[str, Any]) -> bool:
    """
    Verify ZK proof attached to an operation in consensus.
    """
    operation = data.get("operation", {})
    zk_proof_hex = operation.get("zk_proof")

    # If no ZK proof and not required, accept
    if zk_proof_hex is None:
        if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
            return False
        return True

    try:
        verifier = ZKVerifier(mode=settings.ZK_MODE)
        zk_proof = bytes.fromhex(zk_proof_hex)

        # Extract public inputs from operation
        public_inputs = {
            "old_state_root": operation.get("previous_state", ""),
            "new_state_root": operation.get("current_state", ""),
            "block_index": operation.get("sequence", 0)
        }

        return verifier.verify(zk_proof, public_inputs)

    except Exception as e:
        logger.error("ZK verification error in BFT: %s", e)
        return False
