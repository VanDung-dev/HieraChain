"""
Shared types for the Proof Aggregation package.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import hashlib
import time


class AggregationStatus(Enum):
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    READY = "ready"
    SUBMITTED = "submitted"
    FAILED = "failed"


@dataclass
class ProofEntry:
    sub_chain_id: str
    proof: bytes
    block_index: int
    state_root: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_chain_id": self.sub_chain_id,
            "proof_hash": hashlib.sha256(self.proof).hexdigest()[:16],
            "block_index": self.block_index,
            "state_root": self.state_root,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedProof:
    aggregation_id: str
    proof_data: bytes
    source_proofs: list[str]
    block_indices: dict[str, int]
    merkle_root: str
    timestamp: float = field(default_factory=time.time)
    compression_ratio: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregation_id": self.aggregation_id,
            "proof_hash": hashlib.sha256(self.proof_data).hexdigest()[:16],
            "source_proofs": self.source_proofs,
            "block_indices": self.block_indices,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "compression_ratio": self.compression_ratio,
            "num_proofs": len(self.source_proofs),
        }
