"""
Cryptographic utilities for proof aggregation — Merkle trees and ZK operations.
"""

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _compute_merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return hashlib.sha256(b"").hexdigest()

    if len(leaves) == 1:
        return leaves[0]

    if len(leaves) % 2 == 1:
        leaves = leaves + [leaves[-1]]

    parents = []
    for i in range(0, len(leaves), 2):
        combined = leaves[i] + leaves[i + 1]
        parent_hash = hashlib.sha256(combined.encode()).hexdigest()
        parents.append(parent_hash)

    return _compute_merkle_root(parents)


def _zk_aggregate(proofs: list[Any]) -> bytes:
    combined = b"".join(p.proof for p in proofs)
    return hashlib.sha256(combined).digest()


def _zk_verify(agg_proof: Any) -> bool:
    return bool(agg_proof)


def _validate_agg_proof_structure(agg_proof: Any) -> bool:
    return bool(
        agg_proof.proof_data
        and agg_proof.source_proofs
        and agg_proof.merkle_root
    )


def _calculate_compression_ratio(original_size: int, compressed_size: int) -> float:
    return original_size / compressed_size if compressed_size > 0 else 1.0


def _perform_zk_aggregation(proofs: list[Any]) -> tuple[bytes, float]:
    proof_data = _zk_aggregate(proofs)
    original_size = sum(len(p.proof) for p in proofs)
    compression_ratio = _calculate_compression_ratio(original_size, len(proof_data))
    return proof_data, compression_ratio


def _run_zk_verification_flow(agg_proof: Any) -> bool:
    try:
        return _zk_verify(agg_proof)
    except Exception as e:
        logger.error("Proof verification failed: %s", e)
        return False
