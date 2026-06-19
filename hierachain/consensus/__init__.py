"""
Consensus module for the HieraChain Ledger.
"""

# Ordering Service
from hierachain.consensus.ordering import (
    OrderingService,
    OrderingNode,
    OrderingStatus,
    EventStatus,
    PendingEvent,
    EventCertifier,
    BlockBuilder
)

# BFT Consensus
from hierachain.consensus.bft import (
    BFTConsensus,
    create_bft_network,
    ConsensusError,
    BFTMessage,
    MessageType,
    sign_message,
    verify_message_signature,
    validate_consensus_message,
)

# Base Consensus
from hierachain.consensus.base_consensus import BaseConsensus
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.consensus.proof_of_federation import ProofOfFederation

__all__ = [
    # Ordering Service
    "OrderingService",
    "OrderingNode", 
    "OrderingStatus",
    "EventStatus",
    "PendingEvent",
    "EventCertifier",
    "BlockBuilder",

    # BFT Consensus
    "BFTConsensus",
    "create_bft_network",
    "ConsensusError",
    "BFTMessage",
    "MessageType",
    "sign_message",
    "verify_message_signature",
    "validate_consensus_message",

    # Base Consensus
    "BaseConsensus",
    "ProofOfAuthority",
    "ProofOfFederation"
]
