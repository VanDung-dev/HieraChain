"""
Zero Knowledge Proof Generator for HieraChain Ledger.

This module implements the ZKProver class that generates ZK proofs for SubChain
block state transitions. These proofs are submitted to MainChain for verification.

Supports two modes:
- Mock: Uses SHA-256 hash for development/testing.
- Production: Integrates with ZoKrates or external proving service.
"""

import hashlib
import json
import time
import os
import asyncio
import random
import logging
from typing import Any
from dataclasses import dataclass

from hierachain.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ZKProofResult:
    """
    Result of ZK proof generation.
    
    Contains the proof bytes and metadata about the generation.
    """
    proof: bytes
    public_inputs: dict[str, Any]
    generation_time_ms: float
    mode: str
    success: bool
    error: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "proof": self.proof.hex() if self.proof else None,
            "public_inputs": self.public_inputs,
            "generation_time_ms": self.generation_time_ms,
            "mode": self.mode,
            "success": self.success,
            "error": self.error
        }


class ZKProvingError(Exception):
    """Exception raised when ZK proof generation fails."""
    pass


def _generate_mock_proof(old_state_root: str, new_state_root: str, block_index: int) -> bytes:
    """
    Generate mock proof simulating Groth16/Plonk ZK-SNARK proofs.

    Creates a 2KB-4KB proof that mimics real ZK-SNARK proof structure:
    - Magic header for identification
    - Deterministic commitment from public inputs
    - Random padding to simulate real proof bytes

    This is used for development, testing, and pressure testing.

    Args:
        old_state_root: Previous state root.
        new_state_root: New state root.
        block_index: Block index.

    Returns:
        Simulated ZK proof bytes (2KB-4KB).
    """

    # 1. Serialize public inputs to JSON
    public_inputs = {
        "old_state_root": old_state_root,
        "new_state_root": new_state_root,
        "block_index": block_index,
        "sub_chain_name": ""  # Default empty as per current schema
    }
    payload_bytes = json.dumps(public_inputs, sort_keys=True).encode('utf-8')

    # 2. Compute deterministic commitment (SHA-256)
    commitment = hashlib.sha256(payload_bytes).digest()

    # 3. Generate realistic proof size (2KB - 4KB, simulating Groth16/Plonk)
    # Groth16: ~192 bytes, but with padding and metadata: ~2KB
    # Plonk: variable, typically 2KB-4KB
    proof_size = random.randint(2048, 4096)

    # 4. Build proof structure
    magic_bytes = b"mock_zkp_v2\x00"  # 12 bytes header
    version_bytes = b"\x01\x00\x00\x00"  # 4 bytes version (little-endian)
    size_bytes = proof_size.to_bytes(4, 'little')  # 4 bytes size

    # 5. Generate random proof body (simulating curve points and field elements)
    # Keep deterministic header but random body for pressure testing
    header = magic_bytes + version_bytes + size_bytes + commitment  # 12+4+4+32 = 52 bytes
    random_body = os.urandom(proof_size - len(header))

    return header + random_body


def _verify_mock_proof(proof: bytes) -> bool:
    """Verify mock proof structure. Returns True if valid."""
    magic = b"mock_zkp_v2\x00"

    # Check for legacy format compatibility
    if proof.startswith(b"mock_proof"):
        return True

    # Verify new format
    if not proof.startswith(magic):
        return False

    # Verify proof size is reasonable (at least header size)
    return len(proof) >= 52


class ZKProver:
    """
    Zero Knowledge Proof Generator for SubChain.
    
    Responsibilities:
    - Generate ZK proofs for block state transitions.
    - Interface with ZoKrates or external proving service.
    - Ensure proofs are verifiable by MainChain's ZKVerifier.
    
    Usage:
        prover = ZKProver(mode="mock")
        result = prover.generate_proof(
            old_state_root="abc123...",
            new_state_root="def456...",
            block_index=42,
            events=[...]
        )
        proof_bytes = result.proof
    """
    
    def __init__(self, mode: str | None = None):
        """
        Initialize ZK Prover.
        
        Args:
            mode: Proving mode ("mock" or "production").
                  Defaults to settings.ZK_MODE if not specified.
                  
        Note:
            ⚠️ Running in MOCK mode is insecure and NOT for production use!
        """
        import warnings
        
        self.mode = mode or getattr(settings, 'ZK_MODE', 'mock')
        
        if self.mode == "mock":
            warnings.warn(
                "ZKProver running in MOCK mode - NOT for production!",
                UserWarning
            )
        
        self.proving_key: bytes | None = None
        self.circuit_path: str | None = None
        self.stats = {
            "total_proofs_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "total_generation_time_ms": 0.0
        }
        
        # Load proving key for production mode
        if self.mode == "production":
            self._load_proving_key()
            self._load_circuit()
        
        logger.info(f"ZKProver initialized in '{self.mode}' mode")
    
    def generate_proof(
        self,
        old_state_root: str,
        new_state_root: str,
        block_index: int,
        events: list[dict[str, Any]] | None = None,
        sub_chain_name: str = ""
    ) -> ZKProofResult:
        """
        Generate ZK proof for a state transition.
        
        Args:
            old_state_root: Merkle root of previous state (from previous block).
            new_state_root: Merkle root of new state (current block).
            block_index: Block index (prevents replay attacks).
            events: List of events in the block (used as witness in production mode).
            sub_chain_name: Name of the SubChain generating the proof.
        
        Returns:
            ZKProofResult containing the proof and metadata.
        
        Raises:
            ZKProvingError: If proof generation fails.
        """
        self.stats["total_proofs_generated"] += 1
        start_time = time.time()
        
        public_inputs = {
            "old_state_root": old_state_root,
            "new_state_root": new_state_root,
            "block_index": block_index,
            "sub_chain_name": sub_chain_name
        }
        
        try:
            if self.mode == "mock":
                proof = _generate_mock_proof(old_state_root, new_state_root, block_index)
            elif self.mode == "production":
                proof = self._generate_production_proof(
                    old_state_root, new_state_root, block_index, events or []
                )
            else:
                raise ZKProvingError(f"Unknown proving mode: {self.mode}")
            
            generation_time = (time.time() - start_time) * 1000  # Convert to ms
            self.stats["successful_generations"] += 1
            self.stats["total_generation_time_ms"] += generation_time
            
            logger.debug(
                f"Generated ZK proof for block {block_index} in {generation_time:.2f}ms"
            )
            
            return ZKProofResult(
                proof=proof,
                public_inputs=public_inputs,
                generation_time_ms=generation_time,
                mode=self.mode,
                success=True
            )
            
        except Exception as e:
            generation_time = (time.time() - start_time) * 1000
            self.stats["failed_generations"] += 1
            
            logger.error(f"ZK Proof generation failed: {e}")
            
            return ZKProofResult(
                proof=b"",
                public_inputs=public_inputs,
                generation_time_ms=generation_time,
                mode=self.mode,
                success=False,
                error=str(e)
            )
    
    def generate_proof_bytes(
        self,
        old_state_root: str,
        new_state_root: str,
        block_index: int,
        events: list[dict[str, Any]] | None = None
    ) -> bytes:
        """
        Convenience method to generate proof and return just the bytes.
        
        Args:
            old_state_root: Merkle root of previous state.
            new_state_root: Merkle root of new state.
            block_index: Block index.
            events: List of events in the block.
        
        Returns:
            Proof bytes.
        
        Raises:
            ZKProvingError: If proof generation fails.
        """
        result = self.generate_proof(old_state_root, new_state_root, block_index, events)

        if not result.success:
            raise ZKProvingError(f"Proof generation failed: {result.error}")

        return result.proof

    async def generate_proof_async(
        self,
        old_state_root: str,
        new_state_root: str,
        block_index: int,
        events: list[dict[str, Any]] | None = None,
        sub_chain_name: str = ""
    ) -> ZKProofResult:
        """
        Async version of generate_proof with realistic latency simulation.

        In mock mode, adds 100-500ms delay to simulate real ZK-SNARK proving time.
        This is essential for pressure testing and realistic performance evaluation.

        Args:
            old_state_root: Merkle root of previous state.
            new_state_root: Merkle root of new state.
            block_index: Block index.
            events: List of events in the block.
            sub_chain_name: Name of the SubChain.

        Returns:
            ZKProofResult containing the proof and metadata.
        """

        # Simulate ZK-SNARK proving latency (100-500ms)
        if self.mode == "mock":
            await asyncio.sleep(random.uniform(0.1, 0.5))

        return self.generate_proof(
            old_state_root, new_state_root, block_index, events, sub_chain_name
        )

    async def verify_proof_async(self, proof: bytes, _public_inputs: dict[str, Any]) -> bool:
        """
        Async proof verification with realistic latency simulation.

        In mock mode, adds 50-200ms delay to simulate real verification time.
        Verification is typically faster than proving.

        Args:
            proof: The proof bytes to verify.
            _public_inputs: Dictionary containing old_state_root, new_state_root,
                            block_index, and sub_chain_name.

        Returns:
            True if proof is valid, False otherwise.
        """
        # Simulate ZK-SNARK verification latency (50-200ms)
        if self.mode == "mock":
            await asyncio.sleep(random.uniform(0.05, 0.2))
            return _verify_mock_proof(proof)

        # Production verification (not implemented)
        raise NotImplementedError("Production verification not yet implemented")

    def _generate_production_proof(
        self,
        old_state_root: str,
        new_state_root: str,
        block_index: int,
        events: list[dict[str, Any]]
    ) -> bytes:
        """
        Generate production ZK-SNARK proof using ZoKrates.
        
        Args:
            old_state_root: Previous state root.
            new_state_root: New state root.
            block_index: Block index.
            events: List of events (witness data).
        
        Returns:
            Serialized ZK-SNARK proof.
        
        Raises:
            NotImplementedError: Production mode not yet implemented.
        """
        raise NotImplementedError(
            "Production ZK proving not yet implemented. "
            "See ZK_PROOF_ARCHITECTURE.md Section 4.3 for implementation details."
        )
    
    def _load_proving_key(self) -> None:
        """Load proving key from configured path."""
        key_path = getattr(settings, 'ZK_PROVING_KEY_PATH', '')
        
        if not key_path:
            logger.warning("ZK_PROVING_KEY_PATH not configured")
            return
        
        try:
            with open(key_path, 'rb') as f:
                self.proving_key = f.read()
            logger.info(f"Loaded proving key from {key_path}")
        except FileNotFoundError:
            logger.error(f"Proving key not found at {key_path}")
        except Exception as e:
            logger.error(f"Error loading proving key: {e}")
    
    def _load_circuit(self) -> None:
        """Load compiled circuit from configured path."""
        circuit_path = getattr(settings, 'ZK_CIRCUIT_PATH', '')
        
        if not circuit_path:
            logger.warning("ZK_CIRCUIT_PATH not configured")
            return
        
        self.circuit_path = circuit_path
        logger.info(f"Circuit path set to {circuit_path}")
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get proof generation statistics.
        
        Returns:
            Dictionary containing generation counts and timing.
        """
        stats = self.stats.copy()
        
        # Calculate average generation time
        if stats["successful_generations"] > 0:
            stats["avg_generation_time_ms"] = (
                stats["total_generation_time_ms"] / stats["successful_generations"]
            )
        else:
            stats["avg_generation_time_ms"] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset proof generation statistics."""
        self.stats = {
            "total_proofs_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "total_generation_time_ms": 0.0
        }


# Singleton instance for global access
_default_prover: ZKProver | None = None


def get_zk_prover() -> ZKProver:
    """
    Get the default ZKProver instance.
    
    Creates a new instance if one doesn't exist.
    
    Returns:
        ZKProver instance.
    """
    global _default_prover
    if _default_prover is None:
        _default_prover = ZKProver()
    return _default_prover


def reset_zk_prover() -> None:
    """
    Reset the singleton ZKProver instance.
    
    This is primarily for testing purposes to ensure a clean state
    between test runs.
    """
    global _default_prover
    if _default_prover is not None:
        _default_prover.reset_stats()
    _default_prover = None


def generate_zk_proof(
    old_state_root: str,
    new_state_root: str,
    block_index: int,
    events: list[dict[str, Any]] | None = None
) -> bytes:
    """
    Convenience function to generate a ZK proof.
    
    Args:
        old_state_root: Merkle root of previous state.
        new_state_root: Merkle root of new state.
        block_index: Block index.
        events: List of events in the block.
    
    Returns:
        Proof bytes.
    
    Raises:
        ZKProvingError: If proof generation fails.
    """
    prover = get_zk_prover()
    return prover.generate_proof_bytes(old_state_root, new_state_root, block_index, events)
