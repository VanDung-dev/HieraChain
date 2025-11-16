"""
Consensus mechanisms for Hierarchical-Blockchain Framework.

This module provides consensus algorithms suitable for enterprise applications:
- ProofOfAuthority: Authority-based consensus for business use
- BaseConsensus: Base class for consensus mechanisms
"""

from hierarchical_blockchain.core.consensus.base_consensus import BaseConsensus
from hierarchical_blockchain.core.consensus.proof_of_authority import ProofOfAuthority

__all__ = ['BaseConsensus', 'ProofOfAuthority']
