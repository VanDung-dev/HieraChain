"""
BFT Consensus Package
"""

from typing import Any

from hierachain.consensus.bft.consensus import BFTConsensus
from hierachain.consensus.bft.helpers import (
    broadcast,
    forward_to_primary,
    hash_request,
    send_via_zmq,
    sign_message,
    start_view_change_timer,
    validate_consensus_message,
    validate_view_change_proof,
    verify_message_signature,
    verify_operation_zk_proof,
)
from hierachain.consensus.bft.types import (
    BFTMessage,
    ConsensusError,
    ConsensusState,
    MessageType,
)


def create_bft_network(
    node_configs: list[dict[str, Any]], fault_tolerance: int = 1
) -> dict[str, BFTConsensus]:
    from hierachain.security.security_utils import KeyPair

    node_ids = [node["node_id"] for node in node_configs]
    keypairs = {nid: KeyPair() for nid in node_ids}
    public_keys = {nid: kp.public_key for nid, kp in keypairs.items()}

    network = {}
    for node_id in node_ids:
        network[node_id] = BFTConsensus(
            node_id=node_id,
            all_nodes=node_ids,
            f=fault_tolerance,
            keypair=keypairs[node_id],
            node_public_keys=public_keys
        )

    return network


__all__ = [
    'BFTConsensus',
    'BFTMessage',
    'ConsensusError',
    'ConsensusState',
    'MessageType',
    'broadcast',
    'create_bft_network',
    'forward_to_primary',
    'hash_request',
    'send_via_zmq',
    'sign_message',
    'start_view_change_timer',
    'validate_consensus_message',
    'validate_view_change_proof',
    'verify_message_signature',
    'verify_operation_zk_proof',
]
