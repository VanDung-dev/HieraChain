"""
ZK proof types for HieraChain Ledger.
"""

from typing import Any
from dataclasses import dataclass


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
