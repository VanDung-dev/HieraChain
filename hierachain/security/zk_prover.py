"""
Zero Knowledge Proof Generator for HieraChain Ledger.

Generates ZK proofs for SubChain block state transitions.
Supports mock (SHA-256 hash) and production (ZoKrates) modes.
"""

from __future__ import annotations

import hashlib
import orjson
import time
import os
import asyncio
import secrets
import logging
from typing import Any
from dataclasses import dataclass

from hierachain.config.settings import settings


class ZKProvingError(Exception):
    pass


@dataclass
class ZKProofResult:
    proof: bytes
    public_inputs: dict[str, Any]
    generation_time_ms: float
    mode: str
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof": self.proof.hex() if self.proof else None,
            "public_inputs": self.public_inputs,
            "generation_time_ms": self.generation_time_ms,
            "mode": self.mode,
            "success": self.success,
            "error": self.error,
        }

logger = logging.getLogger(__name__)

__all__ = [
    "ZKProofResult",
    "ZKProvingError",
    "ZKProver",
    "get_zk_prover",
    "reset_zk_prover",
    "generate_zk_proof",
]


def _generate_mock_proof(old_state_root: str, new_state_root: str, block_index: int) -> bytes:
    public_inputs = {"old_state_root": old_state_root, "new_state_root": new_state_root, "block_index": block_index, "sub_chain_name": ""}
    payload_bytes = orjson.dumps(public_inputs, option=orjson.OPT_SORT_KEYS)
    commitment = hashlib.sha256(payload_bytes).digest()
    proof_size = secrets.randbelow(2049) + 2048
    magic_bytes = b"mock_zkp_v2\x00"
    version_bytes = b"\x01\x00\x00\x00"
    size_bytes = proof_size.to_bytes(4, 'little')
    header = magic_bytes + version_bytes + size_bytes + commitment
    random_body = os.urandom(proof_size - len(header))
    return header + random_body



def _verify_mock_proof(proof: bytes) -> bool:
    magic = b"mock_zkp_v2\x00"
    if proof.startswith(b"mock_proof"):
        return True
    if not proof.startswith(magic):
        return False
    return len(proof) >= 52


class ZKProver:
    def __init__(self, mode: str | None = None):
        import warnings
        self.mode = mode or getattr(settings, 'ZK_MODE', 'mock')
        if self.mode == "mock":
            warnings.warn("ZKProver running in MOCK mode - NOT for production!", UserWarning)
        self.proving_key: bytes | None = None
        self.circuit_path: str | None = None
        self.stats = {"total_proofs_generated": 0, "successful_generations": 0, "failed_generations": 0, "total_generation_time_ms": 0.0}
        if self.mode == "production":
            self._load_proving_key()
            self._load_circuit()
        logger.info("ZKProver initialized in '%s' mode", self.mode)

    def generate_proof(self, old_state_root: str, new_state_root: str, block_index: int, events: list[dict[str, Any]] | None = None, sub_chain_name: str = "") -> ZKProofResult:
        self.stats["total_proofs_generated"] += 1
        start_time = time.time()
        public_inputs = {"old_state_root": old_state_root, "new_state_root": new_state_root, "block_index": block_index, "sub_chain_name": sub_chain_name}
        try:
            if self.mode == "mock":
                proof = _generate_mock_proof(old_state_root, new_state_root, block_index)
            elif self.mode == "production":
                proof = self._generate_production_proof(old_state_root, new_state_root, block_index, events or [])
            else:
                raise ZKProvingError(f"Unknown proving mode: {self.mode}")
            generation_time = (time.time() - start_time) * 1000
            self.stats["successful_generations"] += 1
            self.stats["total_generation_time_ms"] += generation_time
            logger.debug("Generated ZK proof for block %d in %.2fms", block_index, generation_time)
            return ZKProofResult(proof=proof, public_inputs=public_inputs, generation_time_ms=generation_time, mode=self.mode, success=True)
        except Exception as e:
            generation_time = (time.time() - start_time) * 1000
            self.stats["failed_generations"] += 1
            logger.error("ZK Proof generation failed: %s", e)
            return ZKProofResult(proof=b"", public_inputs=public_inputs, generation_time_ms=generation_time, mode=self.mode, success=False, error=str(e))

    def generate_proof_bytes(self, old_state_root: str, new_state_root: str, block_index: int, events: list[dict[str, Any]] | None = None) -> bytes:
        result = self.generate_proof(old_state_root, new_state_root, block_index, events)
        if not result.success:
            raise ZKProvingError(f"Proof generation failed: {result.error}")
        return result.proof

    async def generate_proof_async(self, old_state_root: str, new_state_root: str, block_index: int, events: list[dict[str, Any]] | None = None, sub_chain_name: str = "") -> ZKProofResult:
        if self.mode == "mock":
            await asyncio.sleep(secrets.randbelow(400) / 1000 + 0.1)
        return self.generate_proof(old_state_root, new_state_root, block_index, events, sub_chain_name)

    async def verify_proof_async(self, proof: bytes, public_inputs: dict[str, Any]) -> bool:
        _ = public_inputs
        if self.mode == "mock":
            await asyncio.sleep(secrets.randbelow(150) / 1000 + 0.05)
            return _verify_mock_proof(proof)
        raise NotImplementedError("Production verification not yet implemented")

    def _generate_production_proof(self, old_state_root: str, new_state_root: str, block_index: int, events: list[dict[str, Any]]) -> bytes:
        raise NotImplementedError("Production ZK proving not yet implemented. See ZK_PROOF_ARCHITECTURE.md Section 4.3 for implementation details.")

    def _load_proving_key(self) -> None:
        key_path = getattr(settings, 'ZK_PROVING_KEY_PATH', '')
        if not key_path:
            logger.warning("ZK_PROVING_KEY_PATH not configured")
            return
        try:
            with open(key_path, 'rb') as f:
                self.proving_key = f.read()
            logger.info("Loaded proving key from %s", key_path)
        except FileNotFoundError:
            logger.error("Proving key not found at %s", key_path)
        except Exception as e:
            logger.error("Error loading proving key: %s", e)

    def _load_circuit(self) -> None:
        circuit_path = getattr(settings, 'ZK_CIRCUIT_PATH', '')
        if not circuit_path:
            logger.warning("ZK_CIRCUIT_PATH not configured")
            return
        self.circuit_path = circuit_path
        logger.info("Circuit path set to %s", circuit_path)

    def get_stats(self) -> dict[str, Any]:
        stats = self.stats.copy()
        stats["avg_generation_time_ms"] = stats["total_generation_time_ms"] / stats["successful_generations"] if stats["successful_generations"] > 0 else 0.0
        return stats

    def reset_stats(self) -> None:
        self.stats = {"total_proofs_generated": 0, "successful_generations": 0, "failed_generations": 0, "total_generation_time_ms": 0.0}


_default_prover: ZKProver | None = None


def get_zk_prover() -> ZKProver:
    global _default_prover
    if _default_prover is None:
        _default_prover = ZKProver()
    prover = _default_prover
    if prover is None:
        raise RuntimeError("ZKProver initialization failed")
    return prover


def reset_zk_prover() -> None:
    global _default_prover
    if _default_prover is not None:
        _default_prover.reset_stats()
    _default_prover = None


def generate_zk_proof(old_state_root: str, new_state_root: str, block_index: int, events: list[dict[str, Any]] | None = None) -> bytes:
    prover = get_zk_prover()
    return prover.generate_proof_bytes(old_state_root, new_state_root, block_index, events)
