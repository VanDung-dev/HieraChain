"""
Crypto Operations at Scale Stress Test.

Tests run in the stress-tester's local process — no network required.

Measures:
  - Batch signature verification throughput
  - ZK proof generation time
  - Block chain verification time

These tests run independently, no REAL_REQUESTS needed.
"""

import hashlib
import logging
import os
import random
import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

logger = logging.getLogger(__name__)

BENCHMARK_SMALL = int(os.getenv("CRYPTO_BENCHMARK_SMALL", "500"))
BENCHMARK_MEDIUM = int(os.getenv("CRYPTO_BENCHMARK_MEDIUM", "5000"))


def _make_event_dict(entity_id: str, payload: str) -> dict:
    return {
        "entity_id": entity_id,
        "event_type": "benchmark",
        "details": {"data": payload},
    }


class TestSignatureVerificationScale:
    """Measure signature verification throughput."""

    @pytest.fixture
    def crypto_utils(self) -> dict[str, Any]:
        try:
            from hierachain.security.security_utils import KeyPair
            from hierachain.security.verify.signature_verifier import SignatureVerifier
            sv = SignatureVerifier()
            return {"keypair_cls": KeyPair, "verifier": sv}
        except ImportError as e:
            pytest.skip(f"Crypto modules not available: {e}")

    def test_single_signature_verify_throughput(self, crypto_utils: dict[str, Any]) -> None:
        """Measure time to verify 1 signature via verify_event_signature."""
        KeyPair = crypto_utils["keypair_cls"]
        sv = crypto_utils["verifier"]

        kp = KeyPair.generate()
        event = _make_event_dict("bench", os.urandom(32).hex())
        event["sender"] = kp.public_key
        canonical = sv.get_canonical_bytes(event)
        sig = kp.sign(canonical)
        event["signature"] = sig

        iterations = BENCHMARK_MEDIUM
        start = time.time()
        for _ in range(iterations):
            assert sv.verify_event_signature(event, kp.public_key)
        elapsed = time.time() - start

        ops_per_sec = iterations / elapsed if elapsed else 0
        logger.info("verify_event_signature: %d iterations in %.2fs (%.0f ops/sec)",
                     iterations, elapsed, ops_per_sec)
        assert elapsed > 0

    def test_batch_verify_speedup(self, crypto_utils: dict[str, Any]) -> None:
        """Compare batch verify vs sequential verify."""
        KeyPair = crypto_utils["keypair_cls"]
        sv = crypto_utils["verifier"]

        batch_size = BENCHMARK_SMALL
        items = []
        for _ in range(batch_size):
            kp = KeyPair.generate()
            event = _make_event_dict(f"e_{_}", os.urandom(16).hex())
            event["sender"] = kp.public_key
            canonical = sv.get_canonical_bytes(event)
            sig = kp.sign(canonical)
            event["signature"] = sig
            items.append(event)

        # Sequential
        start = time.time()
        for ev in items:
            assert sv.verify_event_signature(ev, ev["sender"])
        seq_time = time.time() - start

        start = time.time()
        results = sv.batch_verify([{"item": ev, "public_key": ev["sender"]} for ev in items])
        batch_time = time.time() - start
        assert len(results) == len(items) and all(results)
        speedup = seq_time / batch_time if batch_time else 0
        logger.info("Sequential: %.4fs, Batch: %.4fs, Speedup: %.1fx", seq_time, batch_time, speedup)

    def test_many_keys_no_degradation(self, crypto_utils: dict[str, Any]) -> None:
        """Verify with many public keys — no degradation."""
        KeyPair = crypto_utils["keypair_cls"]
        sv = crypto_utils["verifier"]

        keys = [KeyPair.generate() for _ in range(min(BENCHMARK_MEDIUM, 500))]
        events = []
        for kp in keys:
            ev = _make_event_dict("bench", os.urandom(16).hex())
            ev["sender"] = kp.public_key
            canonical = sv.get_canonical_bytes(ev)
            sig = kp.sign(canonical)
            ev["signature"] = sig
            events.append((ev, kp.public_key))

        start = time.time()
        for ev, pk in events:
            assert sv.verify_event_signature(ev, pk)
        elapsed = time.time() - start

        logger.info("Verified %d unique keys in %.2fs", len(keys), elapsed)


class TestZKProofScale:
    """Measure ZK proof generation and verification throughput."""

    @pytest.fixture
    def zk_modules(self) -> dict[str, Any]:
        try:
            from hierachain.security.verify.zk_verifier import ZKVerifier
            from hierachain.security.zk_prover import ZKProver
            return {"prover": ZKProver, "verifier": ZKVerifier}
        except ImportError as e:
            pytest.skip(f"ZK modules not available: {e}")

    def test_mock_proof_generation_throughput(self, zk_modules: dict[str, Any]) -> None:
        """Measure ZK proof generation throughput (mock mode)."""
        ZKProver = zk_modules["prover"]
        prover = ZKProver()

        num_proofs = BENCHMARK_SMALL
        start = time.time()

        proofs = []
        for i in range(num_proofs):
            proof = prover.generate_proof(
                old_state_root=hashlib.sha256(f"old_{i}".encode()).hexdigest(),
                new_state_root=hashlib.sha256(f"new_{i}".encode()).hexdigest(),
                block_index=i,
                sub_chain_name=f"chain_{i % 10}",
            )
            proofs.append(proof)

        elapsed = time.time() - start

        logger.info("Generated %d mock proofs in %.2fs (%.1f proofs/sec)",
                     num_proofs, elapsed, num_proofs / elapsed if elapsed else 0)
        assert len(proofs) == num_proofs
        assert elapsed < 30, "Generation too slow"

    def test_mock_proof_verify_throughput(self, zk_modules: dict[str, Any]) -> None:
        """Measure ZK proof verification throughput (mock mode)."""
        ZKProver = zk_modules["prover"]
        ZKVerifier = zk_modules["verifier"]
        prover = ZKProver()
        verifier = ZKVerifier()

        num_proofs = BENCHMARK_SMALL
        proofs = []
        for i in range(num_proofs):
            proof_result = prover.generate_proof(
                old_state_root=hashlib.sha256(f"old_{i}".encode()).hexdigest(),
                new_state_root=hashlib.sha256(f"new_{i}".encode()).hexdigest(),
                block_index=i,
                sub_chain_name=f"chain_{i % 10}",
            )
            proofs.append(proof_result)

        start = time.time()
        for pr in proofs:
            assert verifier.verify(pr.proof, pr.public_inputs)
        elapsed = time.time() - start

        logger.info("Verified %d mock proofs in %.2fs (%.0f proofs/sec)",
                     num_proofs, elapsed, num_proofs / elapsed if elapsed else 0)


class TestBlockVerificationScale:
    """Measure block chain verification throughput — using real Block objects."""

    @pytest.fixture
    def block_module(self) -> dict[str, Any]:
        try:
            from hierachain.core.block import Block
            from hierachain.security.verify.block_verifier import BlockVerifier
            private_key = Ed25519PrivateKey.generate()
            return {
                "block_cls": Block, "verifier": BlockVerifier(), "private_key": private_key,
                "public_key": private_key.public_key().public_bytes(
                    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
                ),
            }
        except ImportError as e:
            pytest.skip(f"Block modules not available: {e}")

    def _generate_chain(self, length: int, block_cls: type, private_key: Ed25519PrivateKey) -> list:
        """Create chain with real Block objects."""
        from hierachain.security.verify.block_verifier import BlockVerifier

        chain = []
        prev_hash = ""
        for i in range(length):
            events = [
                {
                    "entity_id": f"entity_{random.randint(1, 100)}",
                    "event_type": random.choice(["create", "update", "delete"]),
                    "timestamp": time.time(),
                    "details": {"data": "x" * random.randint(10, 100)},
                }
                for _ in range(random.randint(1, 10))
            ]
            block = block_cls(
                index=i,
                events=events,
                timestamp=time.time() + i,
                previous_hash=prev_hash,
                creator_id="benchmark_node",
            )
            block.signature = private_key.sign(BlockVerifier._get_signable_content(block)).hex()
            block_hash = block.calculate_hash()
            chain.append((block, block_hash))
            prev_hash = block_hash
        return chain

    def test_chain_verify_throughput(self, block_module: dict[str, Any]) -> None:
        """Measure time to verify chain with different lengths."""
        Block = block_module["block_cls"]
        bv = block_module["verifier"]

        for length in [100, 500]:
            chain_data = self._generate_chain(length, Block, block_module["private_key"])
            chain = [b for b, _ in chain_data]

            start = time.time()
            for i, block in enumerate(chain):
                prev = chain[i - 1] if i > 0 else None
                result = bv.verify_block(block, prev, public_key=block_module["public_key"])
                assert result.is_valid, result.details
            elapsed = time.time() - start

            logger.info("Verified chain of %d blocks in %.2fs (%.0f blocks/sec)",
                         length, elapsed, length / elapsed if elapsed else 0)

    def test_merkle_root_integrity(self, block_module: dict[str, Any]) -> None:
        """Generate chain and verify Merkle root + chain link consistency."""
        Block = block_module["block_cls"]
        bv = block_module["verifier"]

        chain_data = self._generate_chain(50, Block, block_module["private_key"])
        chain = [b for b, _ in chain_data]

        verified = 0
        for i, block in enumerate(chain):
            prev = chain[i - 1] if i > 0 else None
            try:
                result = bv.verify_block(block, prev, public_key=block_module["public_key"])
                if result.is_valid:
                    verified += 1
            except Exception as e:
                logger.warning("Block %d verify failed: %s", i, e)

        logger.info("Verified %d/%d blocks", verified, len(chain))
        assert verified == len(chain), "All blocks should verify"
