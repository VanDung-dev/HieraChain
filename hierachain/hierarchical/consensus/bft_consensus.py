"""
Byzantine Fault Tolerance Consensus for HieraChain Ledger (Legacy Entry Point)

This module provides the BFT consensus mechanism, now refactored into the
hierachain.hierarchical.consensus.bft package.
"""

import logging
from typing import Any

from hierachain.hierarchical.consensus.bft import (
    BFTConsensus,
    ConsensusError,
    BFTMessage,
    MessageType,
    ConsensusState,
    sign_message,
    verify_message_signature,
    _validate_consensus_message
)


logger = logging.getLogger(__name__)

def create_bft_network(node_configs: list[dict[str, Any]], fault_tolerance: int = 1) -> dict[str, BFTConsensus]:
    """
    Create a BFT consensus network (Factory function)
    
    Args:
        node_configs: List of node configurations
        fault_tolerance: Number of Byzantine faults to tolerate
    
    Returns:
        Dict mapping node IDs to BFTConsensus instances
    """
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
    'ConsensusError',
    'BFTMessage',
    'MessageType',
    'ConsensusState',
    'sign_message',
    'verify_message_signature',
    '_validate_consensus_message',
    'create_bft_network'
]
