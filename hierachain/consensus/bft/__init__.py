"""
BFT Consensus Package
"""

from typing import Any

from hierachain.consensus.bft.types import (
    ConsensusState,
    MessageType,
    BFTMessage,
    ConsensusError
)
from hierachain.consensus.bft.helpers import (
    sign_message,
    verify_message_signature,
    hash_request,
    verify_operation_zk_proof,
    send_via_zmq,
    broadcast,
    forward_to_primary,
    validate_view_change_proof,
    start_view_change_timer,
    validate_consensus_message,
)
from hierachain.consensus.bft.consensus import BFTConsensus


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
    'ConsensusState',
    'MessageType',
    'BFTMessage',
    'ConsensusError',
    'sign_message',
    'verify_message_signature',
    'hash_request',
    'verify_operation_zk_proof',
    'send_via_zmq',
    'broadcast',
    'forward_to_primary',
    'validate_view_change_proof',
    'start_view_change_timer',
    'validate_consensus_message',
    'create_bft_network',
]
