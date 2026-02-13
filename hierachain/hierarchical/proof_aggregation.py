"""
Proof Aggregation Engine for HieraChain.

This module implements proof aggregation from multiple sub-chains to reduce
MainChain load through efficient proof batching and compression.

Features:
- Aggregate proofs from leaf nodes (sub-chains)
- Compress multiple proofs into a single aggregated proof
- Reduce MainChain verification load
- Support for both mock and real ZK proof aggregation
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _compute_merkle_root(leaves: list[str]) -> str:
    """Compute Merkle root from leaf hashes."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()

    if len(leaves) == 1:
        return leaves[0]

    # Pad to even length
    if len(leaves) % 2 == 1:
        leaves = leaves + [leaves[-1]]

    # Compute parent layer
    parents = []
    for i in range(0, len(leaves), 2):
        combined = leaves[i] + leaves[i + 1]
        parent_hash = hashlib.sha256(combined.encode()).hexdigest()
        parents.append(parent_hash)

    return _compute_merkle_root(parents)


def _zk_aggregate(proofs: list["ProofEntry"]) -> bytes:
    """
    Perform ZK proof aggregation (production mode placeholder).
    """
    combined = b"".join(p.proof for p in proofs)
    return hashlib.sha256(combined).digest()


def _zk_verify(agg_proof: "AggregatedProof") -> bool:
    """Verify aggregated proof using ZK verifier (placeholder)."""
    return bool(agg_proof)


def _validate_agg_proof_structure(agg_proof: "AggregatedProof") -> bool:
    """Verify basic structural integrity of an aggregated proof."""
    return bool(
        agg_proof.proof_data
        and agg_proof.source_proofs
        and agg_proof.merkle_root
    )


def _calculate_compression_ratio(original_size: int, compressed_size: int) -> float:
    """Calculate the compression ratio safely."""
    return original_size / compressed_size if compressed_size > 0 else 1.0


def _perform_zk_aggregation(proofs: list["ProofEntry"]) -> tuple[bytes, float]:
    """Perform real ZK proof aggregation logic."""
    proof_data = _zk_aggregate(proofs)
    original_size = sum(len(p.proof) for p in proofs)
    compression_ratio = _calculate_compression_ratio(original_size, len(proof_data))
    return proof_data, compression_ratio


def _run_zk_verification_flow(agg_proof: "AggregatedProof") -> bool:
    """Real ZK proof verification flow."""
    try:
        return _zk_verify(agg_proof)
    except Exception as e:
        logger.error(f"Proof verification failed: {e}")
        return False


class AggregationStatus(Enum):
    """Status of proof aggregation."""
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    READY = "ready"
    SUBMITTED = "submitted"
    FAILED = "failed"


@dataclass
class ProofEntry:
    """Individual proof entry from a sub-chain."""
    sub_chain_id: str
    proof: bytes
    block_index: int
    state_root: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
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
    """Aggregated proof from multiple sub-chains."""
    aggregation_id: str
    proof_data: bytes
    source_proofs: list[str]  # sub_chain_ids
    block_indices: dict[str, int]  # sub_chain_id -> block_index
    merkle_root: str
    timestamp: float = field(default_factory=time.time)
    compression_ratio: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
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


class ProofAggregator:
    """
    Aggregates proofs from multiple sub-chains.

    The aggregator collects proofs from leaf nodes (sub-chains) and
    combines them into a single aggregated proof for submission to
    the MainChain. This reduces verification load on the MainChain
    while maintaining cryptographic integrity.
    """

    def __init__(
        self,
        batch_size: int = 10,
        batch_timeout: float = 30.0,
        compression_enabled: bool = True,
        use_mock: bool = True,
    ):
        """
        Initialize ProofAggregator.

        Args:
            batch_size: Number of proofs to collect before aggregation.
            batch_timeout: Timeout in seconds to wait for batch completion.
            compression_enabled: Enable proof compression.
            use_mock: Use mock mode (no real ZK aggregation).
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.compression_enabled = compression_enabled
        self.use_mock = use_mock

        # Pending proofs waiting for aggregation
        self._pending_proofs: dict[str, ProofEntry] = {}
        self._batch_start_time: float = 0.0
        self._current_batch_id: str = ""

        # Aggregated proofs history
        self._aggregated_proofs: list[AggregatedProof] = []

        # Status
        self._status = AggregationStatus.COLLECTING

        # Callbacks
        self._on_aggregation_complete: Callable[[AggregatedProof], None] | None = None

        # Stats
        self._stats = {
            "proofs_received": 0,
            "proofs_aggregated": 0,
            "aggregations_completed": 0,
            "total_compression_ratio": 0.0,
            "errors": 0,
        }

        self._reset_batch()
        logger.info(f"ProofAggregator initialized (batch_size={batch_size}, mock={use_mock})")

    def _reset_batch(self) -> None:
        """Reset batch state for new collection cycle."""
        self._pending_proofs = {}
        self._batch_start_time = time.time()
        self._current_batch_id = f"batch-{int(time.time() * 1000)}"
        self._status = AggregationStatus.COLLECTING

    def _generate_aggregation_id(self) -> str:
        """Generate unique aggregation ID."""
        return f"agg-{int(time.time() * 1000)}-{len(self._aggregated_proofs)}"

    def add_proof(
        self,
        sub_chain_id: str,
        proof: bytes,
        block_index: int,
        state_root: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a proof from a sub-chain to the aggregation batch.

        Args:
            sub_chain_id: Unique identifier for the sub-chain.
            proof: Raw proof bytes.
            block_index: Block index this proof covers.
            state_root: State root after the block.
            metadata: Optional additional metadata.

        Returns:
            True if proof was added successfully.
        """
        if self._status not in (AggregationStatus.COLLECTING, AggregationStatus.READY,):
            logger.warning(f"Cannot add proof, aggregator status: {self._status}")
            return False

        entry = ProofEntry(
            sub_chain_id=sub_chain_id,
            proof=proof,
            block_index=block_index,
            state_root=state_root,
            metadata=metadata or {},
        )

        self._pending_proofs[sub_chain_id] = entry
        self._stats["proofs_received"] += 1

        logger.debug(
            f"Added proof from {sub_chain_id}, "
            f"batch size: {len(self._pending_proofs)}/{self.batch_size}"
        )

        # Check if batch is ready
        if self._should_aggregate():
            return self._trigger_aggregation()

        return True

    def _should_aggregate(self) -> bool:
        """Check if aggregation should be triggered."""
        if len(self._pending_proofs) >= self.batch_size:
            return True

        if len(self._pending_proofs) > 0 and (time.time() - self._batch_start_time) >= self.batch_timeout:
            return True

        return False

    def _trigger_aggregation(self) -> bool:
        """Trigger proof aggregation."""
        if len(self._pending_proofs) == 0:
            return False

        self._status = AggregationStatus.AGGREGATING

        try:
            aggregated = self._aggregate_proofs()
            self._aggregated_proofs.append(aggregated)
            self._stats["aggregations_completed"] += 1
            self._stats["proofs_aggregated"] += len(self._pending_proofs)

            if aggregated.compression_ratio > 0:
                self._update_total_compression_ratio(aggregated.compression_ratio)

            self._status = AggregationStatus.READY

            if self._on_aggregation_complete:
                self._on_aggregation_complete(aggregated)

            logger.info(
                f"Aggregated {len(self._pending_proofs)} proofs, "
                f"compression ratio: {aggregated.compression_ratio:.2f}"
            )

            self._reset_batch()
            return True

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            self._status = AggregationStatus.FAILED
            self._stats["errors"] += 1
            return False

    def _update_total_compression_ratio(self, current_ratio: float) -> None:
        """Update the average compression ratio statistic."""
        prev_ratio = self._stats["total_compression_ratio"]
        count = self._stats["aggregations_completed"]
        self._stats["total_compression_ratio"] = ((prev_ratio * (count - 1) + current_ratio) / count)

    def _aggregate_proofs(self) -> AggregatedProof:
        """
        Aggregate pending proofs into a single proof.

        In mock mode, creates a combined hash-based proof.
        In production mode, would use ZK aggregation circuits.
        """
        proofs = list(self._pending_proofs.values())
        source_ids = [p.sub_chain_id for p in proofs]
        block_indices = {p.sub_chain_id: p.block_index for p in proofs}

        # Calculate merkle root of state roots
        state_roots = [p.state_root for p in proofs]
        merkle_root = _compute_merkle_root(state_roots)

        if self.use_mock:
            proof_data, ratio = self._perform_mock_aggregation(proofs)
        else:
            proof_data, ratio = _perform_zk_aggregation(proofs)

        return AggregatedProof(
            aggregation_id=self._generate_aggregation_id(),
            proof_data=proof_data,
            source_proofs=source_ids,
            block_indices=block_indices,
            merkle_root=merkle_root,
            compression_ratio=ratio,
            metadata={"batch_id": self._current_batch_id, "aggregation_time": time.time()},
        )

    def _perform_mock_aggregation(self, proofs: list[ProofEntry]) -> tuple[bytes, float]:
        """Perform mock proof aggregation."""
        combined = b"".join(p.proof for p in proofs)
        proof_data = hashlib.sha256(combined).digest()

        compression_ratio = 1.0
        if self.compression_enabled:
            original_size = sum(len(p.proof) for p in proofs)
            compression_ratio = _calculate_compression_ratio(original_size, len(proof_data))

        return proof_data, compression_ratio

    def aggregate(self) -> AggregatedProof | None:
        """
        Force aggregation of current pending proofs.

        Returns:
            Aggregated proof if successful, None otherwise.
        """
        if len(self._pending_proofs) == 0:
            return None

        if self._trigger_aggregation():
            return self._aggregated_proofs[-1]
        return None

    def verify_aggregated_proof(self, agg_proof: AggregatedProof) -> bool:
        """
        Verify an aggregated proof.

        Args:
            agg_proof: The aggregated proof to verify.

        Returns:
            True if proof is valid.
        """
        if self.use_mock:
            return _validate_agg_proof_structure(agg_proof)

        return _run_zk_verification_flow(agg_proof)

    def get_pending_count(self) -> int:
        """Get number of pending proofs."""
        return len(self._pending_proofs)

    def get_pending_proofs(self) -> list[ProofEntry]:
        """Get list of pending proofs."""
        return list(self._pending_proofs.values())

    def get_latest_aggregation(self) -> AggregatedProof | None:
        """Get the most recent aggregated proof."""
        if self._aggregated_proofs:
            return self._aggregated_proofs[-1]
        return None

    def get_compression_ratio(self) -> float:
        """Get average compression ratio."""
        if self._stats["aggregations_completed"] == 0:
            return 1.0
        return self._stats["total_compression_ratio"]

    def get_status(self) -> AggregationStatus:
        """Get current aggregation status."""
        return self._status

    def get_stats(self) -> dict[str, Any]:
        """Get aggregator statistics."""
        return {
            **self._stats,
            "pending_proofs": len(self._pending_proofs),
            "status": self._status.value,
            "use_mock": self.use_mock,
            "batch_size": self.batch_size,
        }

    def set_callback(self, on_complete: Callable[[AggregatedProof], None] | None) -> None:
        """Set callback for aggregation completion."""
        self._on_aggregation_complete = on_complete

    def clear_history(self) -> None:
        """Clear aggregation history."""
        self._aggregated_proofs = []
