"""
ProofAggregator — aggregates proofs from multiple sub-chains.
"""

import hashlib
import logging
import time
from typing import Any, Callable

from hierachain.hierarchical.proof_aggregation.types import (
    AggregatedProof,
    AggregationStatus,
    ProofEntry,
)
from hierachain.hierarchical.proof_aggregation.crypto_utils import (
    _calculate_compression_ratio,
    _compute_merkle_root,
    _perform_zk_aggregation,
    _run_zk_verification_flow,
    _validate_agg_proof_structure,
)

logger = logging.getLogger(__name__)


class ProofAggregator:
    def __init__(
        self,
        batch_size: int = 10,
        batch_timeout: float = 30.0,
        compression_enabled: bool = True,
        use_mock: bool = True,
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.compression_enabled = compression_enabled
        self.use_mock = use_mock

        self._pending_proofs: dict[str, ProofEntry] = {}
        self._batch_start_time: float = 0.0
        self._current_batch_id: str = ""

        self._aggregated_proofs: list[AggregatedProof] = []

        self._status = AggregationStatus.COLLECTING

        self._on_aggregation_complete: Callable[[AggregatedProof], None] | None = None

        self._stats = {
            "proofs_received": 0,
            "proofs_aggregated": 0,
            "aggregations_completed": 0,
            "total_compression_ratio": 0.0,
            "errors": 0,
        }

        self._reset_batch()
        logger.info(
            "ProofAggregator initialized (batch_size=%d, mock=%s)",
            batch_size, use_mock,
        )

    def _reset_batch(self) -> None:
        self._pending_proofs = {}
        self._batch_start_time = time.time()
        self._current_batch_id = f"batch-{int(time.time() * 1000)}"
        self._status = AggregationStatus.COLLECTING

    def _generate_aggregation_id(self) -> str:
        return f"agg-{int(time.time() * 1000)}-{len(self._aggregated_proofs)}"

    def add_proof(
        self,
        sub_chain_id: str,
        proof: bytes,
        block_index: int,
        state_root: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if self._status not in (AggregationStatus.COLLECTING, AggregationStatus.READY,):
            logger.warning(
                "Cannot add proof, aggregator status: %s", self._status
            )
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
            "Added proof from %s, batch size: %d/%d",
            sub_chain_id, len(self._pending_proofs), self.batch_size,
        )

        if self._should_aggregate():
            return self._trigger_aggregation()

        return True

    def _should_aggregate(self) -> bool:
        if len(self._pending_proofs) >= self.batch_size:
            return True

        if (
            len(self._pending_proofs) > 0 and
            (time.time() - self._batch_start_time) >= self.batch_timeout
        ):
            return True

        return False

    def _trigger_aggregation(self) -> bool:
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
                "Aggregated %d proofs, compression ratio: %.2f",
                len(self._pending_proofs), aggregated.compression_ratio,
            )

            self._reset_batch()
            return True

        except Exception as e:
            logger.error("Aggregation failed: %s", e)
            self._status = AggregationStatus.FAILED
            self._stats["errors"] += 1
            return False

    def _update_total_compression_ratio(self, current_ratio: float) -> None:
        prev_ratio = self._stats["total_compression_ratio"]
        count = self._stats["aggregations_completed"]
        self._stats["total_compression_ratio"] = (
            (prev_ratio * (count - 1) + current_ratio) / count
        )

    def _aggregate_proofs(self) -> AggregatedProof:
        proofs = list(self._pending_proofs.values())
        source_ids = [p.sub_chain_id for p in proofs]
        block_indices = {p.sub_chain_id: p.block_index for p in proofs}

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
            metadata={
                "batch_id": self._current_batch_id, "aggregation_time": time.time()
            },
        )

    def _perform_mock_aggregation(
        self, proofs: list[ProofEntry]
    ) -> tuple[bytes, float]:
        combined = b"".join(p.proof for p in proofs)
        proof_data = hashlib.sha256(combined).digest()

        compression_ratio = 1.0
        if self.compression_enabled:
            original_size = sum(len(p.proof) for p in proofs)
            compression_ratio = _calculate_compression_ratio(
                original_size, len(proof_data)
            )

        return proof_data, compression_ratio

    def aggregate(self) -> AggregatedProof | None:
        if len(self._pending_proofs) == 0:
            return None

        if self._trigger_aggregation():
            return self._aggregated_proofs[-1]
        return None

    def verify_aggregated_proof(self, agg_proof: AggregatedProof) -> bool:
        if self.use_mock:
            return _validate_agg_proof_structure(agg_proof)

        return _run_zk_verification_flow(agg_proof)

    def get_pending_count(self) -> int:
        return len(self._pending_proofs)

    def get_pending_proofs(self) -> list[ProofEntry]:
        return list(self._pending_proofs.values())

    def get_latest_aggregation(self) -> AggregatedProof | None:
        if self._aggregated_proofs:
            return self._aggregated_proofs[-1]
        return None

    def get_compression_ratio(self) -> float:
        if self._stats["aggregations_completed"] == 0:
            return 1.0
        return self._stats["total_compression_ratio"]

    def get_status(self) -> AggregationStatus:
        return self._status

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "pending_proofs": len(self._pending_proofs),
            "status": self._status.value,
            "use_mock": self.use_mock,
            "batch_size": self.batch_size,
        }

    def set_callback(
        self, on_complete: Callable[[AggregatedProof], None] | None
    ) -> None:
        self._on_aggregation_complete = on_complete

    def clear_history(self) -> None:
        self._aggregated_proofs = []
