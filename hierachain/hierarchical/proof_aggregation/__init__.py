"""
Proof Aggregation package — batch aggregation of sub-chain proofs.
"""

from hierachain.hierarchical.proof_aggregation.aggregator import ProofAggregator
from hierachain.hierarchical.proof_aggregation.types import (
    AggregatedProof,
    AggregationStatus,
    ProofEntry,
)

__all__ = [
    "ProofAggregator",
    "AggregatedProof",
    "ProofEntry",
    "AggregationStatus",
]
