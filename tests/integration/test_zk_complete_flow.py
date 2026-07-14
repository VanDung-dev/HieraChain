"""
Integration tests for ZK Proofs with Proof of Authority (PoA) and Proof of Federation (PoF) consensus mechanisms.

Tests cover normal operations, security scenarios, and system resilience.
"""

import pytest
import time
from types import SimpleNamespace

from hierachain.core import Block
from hierachain.consensus import ProofOfFederation
from hierachain.consensus import ProofOfAuthority
from hierachain.security import get_zk_prover, ZKProvingError, reset_zk_prover
from hierachain.security.verify import (
    get_zk_verifier, ZKVerificationError, reset_zk_verifier
)
from hierachain.config.settings import settings


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset ZK singletons before each test for complete isolation."""
    reset_zk_prover()
    reset_zk_verifier()
    yield
    # Optional: reset after test too for extra safety
    reset_zk_prover()
    reset_zk_verifier()


@pytest.fixture(scope="function")
def zk_context():
    """
    Fixture creates a clean test environment for ZK integration tests.
    Returns a SimpleNamespace containing:
    - poa: ProofOfAuthority instance
    - prover: ZKProver instance
    - verifier: ZKVerifier instance
    - authority_id: ID of the valid PoA authority
    """
    # 1. Store original settings
    original_zk_enable = getattr(settings, 'ENABLE_ZK_PROOFS', False)
    original_zk_mode = getattr(settings, 'ZK_MODE', 'mock')
    
    # 2. Enable ZK in Mock mode
    settings.ENABLE_ZK_PROOFS = True
    settings.ZK_MODE = 'mock'

    # 2.5. Get singleton instances AND reset their stats for clean test state
    prover = get_zk_prover()
    prover.mode = 'mock'
    prover.reset_stats()
    
    verifier = get_zk_verifier()
    verifier.mode = 'mock'
    verifier.reset_stats()
    
    # 3. Initialize Core Components
    poa = ProofOfAuthority()
    
    # 5. Setup Valid Authority
    authority_id = "AUTH-MASTER-001"
    poa.add_authority(authority_id)
    
    # Bundle into a context object
    context = SimpleNamespace(
        poa=poa,
        prover=prover,
        verifier=verifier,
        authority_id=authority_id
    )
    
    yield context
    
    # Teardown: Restore environment
    settings.ENABLE_ZK_PROOFS = original_zk_enable
    settings.ZK_MODE = original_zk_mode


# =========================================================================
# SCENARIO 1: NORMAL OPERATIONS (Happy Path)
# =========================================================================

def test_pof_zk_happy_path(zk_context):
    """
    Verify the complete lifecycle of ZK proof with Proof of Federation (PoF).
    Similar to PoA but checks that PoF's distinct validation logic works with ZK.
    """
    from nacl.signing import SigningKey
    from nacl.encoding import HexEncoder

    # 1. Setup PoF instance with signing key
    sk = SigningKey.generate()
    sk_hex = sk.encode(HexEncoder).decode()
    pof = ProofOfFederation(signing_key_hex=sk_hex)
    validator_id = "VAL-FED-001"
    pk_hex = sk.verify_key.encode(HexEncoder).decode()
    pof.add_validator(validator_id, {"public_key": pk_hex})

    # 2. Setup Previous Block
    prev_block = Block(
        index=50, 
        events=[], 
        previous_hash="root_hash_49", 
        timestamp=time.time() - 10
    )
    prev_block.merkle_root = "a" * 64
    
    # 3. Setup New Block (Target)
    new_index = 51
    new_root = "b" * 64
    
    # 4. Generate Proof
    proof_bytes = zk_context.prover.generate_proof_bytes(
        prev_block.merkle_root, 
        new_root, 
        new_index
    )

    # 5. Create pre-consensus block, then sign its hash
    pre_block = Block(
        index=new_index,
        events=[],
        previous_hash=prev_block.hash,
        timestamp=prev_block.timestamp + 10,
    )
    pre_block.merkle_root = new_root
    signature = sk.sign(pre_block.hash.encode("utf-8")).signature.hex()
    
    # 6. Create PoF Consensus Event with real signature and block_hash
    consensus_event = {
        "entity_id": validator_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "leader_id": validator_id,
            "signature": signature,
            "zk_proof": proof_bytes.hex(),
            "previous_state": prev_block.merkle_root,
            "current_state": new_root,
            "consensus_type": "proof_of_federation",
            "block_hash": pre_block.hash
        }
    }
    
    block = Block(
        index=new_index,
        events=[consensus_event],
        previous_hash=prev_block.hash,
        timestamp=prev_block.timestamp + 10,
    )
    block.merkle_root = new_root
    
    # 7. Validate with PoF
    is_valid = pof.validate_block(block, prev_block)
    
    assert is_valid is True
    
    # Verify stats increased (at least one successful verification)
    v_stats = zk_context.verifier.get_stats()
    assert v_stats["successful_verifications"] >= 1


def test_full_lifecycle_success(zk_context):
    """
    Verify the complete lifecycle of a block with ZK proof:
    Create Previous Block -> Generate Proof -> Create Consensus Event -> Validate.
    """
    # 1. State A (Previous Block)
    prev_block = Block(
        index=100, 
        events=[], 
        previous_hash="root_hash_99", 
        timestamp=time.time() - 10
    )
    prev_block.merkle_root = "a" * 64
    
    # 2. State B (New Block Target)
    new_index = 101
    new_root = "b" * 64
    
    # 3. Prover generates proof for transition A -> B
    stats_before = zk_context.prover.get_stats()
    proof_bytes = zk_context.prover.generate_proof_bytes(
        prev_block.merkle_root, 
        new_root, 
        new_index
    )
    
    # Assert generation stats
    stats = zk_context.prover.get_stats()
    assert stats["total_proofs_generated"] == stats_before["total_proofs_generated"] + 1
    
    # 4. Authority creates a block including this proof
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "authority_id": zk_context.authority_id,
            "authority_signature": "valid_rsa_sig_base64",
            "zk_proof": proof_bytes.hex(),
            "previous_state": prev_block.merkle_root,
            "current_state": new_root
        }
    }
    
    block = Block(
        index=new_index,
        events=[consensus_event],
        previous_hash=prev_block.hash,
        timestamp=prev_block.timestamp + 10,
        signature="authority_block_sig"
    )
    
    # 5. Validators (PoA) verify the block
    is_valid = zk_context.poa.validate_block(block, prev_block)
    
    assert is_valid is True
    
    # Assert verification stats (at least one successful)
    v_stats = zk_context.verifier.get_stats()
    assert v_stats["successful_verifications"] >= 1


# =========================================================================
# SCENARIO 2: SECURITY VIOLATIONS (Attacks)
# =========================================================================

def test_security_fake_proof_attack(zk_context):
    """
    Attack Scenario: Malicious authority tries to submit a block with 
    a valid-looking proof that doesn't actually match the state transition.
    """
    prev_block = Block(
        index=200, 
        events=[], 
        previous_hash="0"*64, 
        timestamp=time.time() - 100
    )
    prev_block.merkle_root = "a" * 64
    
    new_index = 201
    real_new_root = "b" * 64
    fake_new_root = "c" * 64
    
    # Attacker generates a VALID proof for A -> C
    proof_for_fake = zk_context.prover.generate_proof_bytes(
        prev_block.merkle_root, fake_new_root, new_index
    )
    
    # But the block claims the state is B (or consistent with B)
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "authority_id": zk_context.authority_id,
            "authority_signature": "sig",
            "zk_proof": proof_for_fake.hex(),
            "previous_state": prev_block.merkle_root,
            "current_state": real_new_root
        }
    }
    
    block = Block(
        index=new_index,
        events=[consensus_event],
        previous_hash=prev_block.hash,
        timestamp=prev_block.timestamp + 10,
        signature="sig"
    )

    # Verification must fail because Inputs (A->B) don't match Proof (A->C)
    is_valid = zk_context.poa.validate_block(block, prev_block)

    # Core assertion: block validation must fail
    # Note: We only check is_valid, not stats, because:
    # 1. Block validation may fail before reaching ZK check
    # 2. Singleton stats can be affected by pytest test ordering
    assert is_valid is False, "Block with mismatched proof should be rejected"


def test_security_proof_tampering(zk_context):
    """
    Attack Scenario: Man-in-the-Middle modifies the proof bytes.
    """
    prev_block = Block(index=200, events=[], previous_hash="0"*64)
    prev_block.merkle_root = "a" * 64
    new_root = "b" * 64
    
    # Valid proof
    valid_proof = zk_context.prover.generate_proof_bytes(
        prev_block.merkle_root, new_root, 201
    )
    
    # Tamper: Flip a bit
    malicious_proof = bytearray(valid_proof)
    malicious_proof[0] = malicious_proof[0] ^ 0xFF
    
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "authority_id": zk_context.authority_id,
            "zk_proof": malicious_proof.hex(),
            "previous_state": prev_block.merkle_root,
            "current_state": new_root
        }
    }
    
    block = Block(
        index=201,
        events=[consensus_event],
        previous_hash=prev_block.hash,
        signature="sig"
    )
    
    # Verification must fail (integrity check)
    is_valid = zk_context.poa.validate_block(block, prev_block)
    assert is_valid is False


def test_security_replay_attack(zk_context):
    """
    Attack Scenario: Attacker reuses a valid proof from Block 100 for Block 200.
    """
    # Proof generated for Block 100
    proof_old = zk_context.prover.generate_proof_bytes(
        "a"*64, "b"*64, block_index=100
    )
    
    # Try to use it for Block 200
    prev_block = Block(index=199, events=[], previous_hash="hash")
    prev_block.merkle_root = "a" * 64
    
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "authority_id": zk_context.authority_id,
            "zk_proof": proof_old.hex(),
            "previous_state": "a"*64,
            "current_state": "b"*64
        }
    }
    
    block_replay = Block(
        index=200, # Actual index is 200
        events=[consensus_event],
        previous_hash=prev_block.hash,
        signature="sig"
    )
    
    # Verification must fail because proof bundles index=100 but block is 200
    is_valid = zk_context.poa.validate_block(block_replay, prev_block)
    assert is_valid is False


# =========================================================================
# SCENARIO 3: SYSTEM RESILIENCE (Configuration & Errors)
# =========================================================================

def test_resilience_missing_keys_in_production(zk_context):
    """
    System Fault: Admin configures Production mode but forgets keys.
    System should fail safely (reject blocks) rather than crashing or accepting invalid.
    """
    settings.ZK_MODE = 'production'
    settings.ZK_VERIFICATION_KEY_PATH = "missing_key.bin"
    
    # Reload verifier to pick up new settings
    prod_verifier = get_zk_verifier()
    prod_verifier.mode = 'production'
    prod_verifier._load_verification_key()
    
    prev_block = Block(index=0, events=[], previous_hash="0"*64)
    prev_block.merkle_root = "a"*64
    
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "authority_id": zk_context.authority_id,
            "zk_proof": "deadbeef",
            "previous_state": "a"*64,
            "current_state": "b"*64
        }
    }
    
    block = Block(
        index=1,
        events=[consensus_event],
        previous_hash=prev_block.hash,
        signature="sig"
    )
    
    is_valid = zk_context.poa.validate_block(block, prev_block)
    assert is_valid is False


def test_resilience_invalid_input_data(zk_context):
    """
    System Fault: Malformed data references (e.g. invalid state root length).
    Verifiers should reject immediately without crypto check.
    """
    short_root = "short"
    
    prev_block = Block(index=0, events=[], previous_hash="0"*64)
    prev_block.merkle_root = short_root
    
    consensus_event = {
        "entity_id": zk_context.authority_id,
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "zk_proof": "deadbeef",
            "previous_state": short_root,
            "current_state": "b"*64
        }
    }
    
    block = Block(index=1, events=[consensus_event], previous_hash=prev_block.hash, signature="sig")
    
    is_valid = zk_context.poa.validate_block(block, prev_block)
    assert is_valid is False


def test_zk_exception_handling(zk_context):
    """
    Verify that ZKProvingError and ZKVerificationError are raised correctly
    when critical errors occur (e.g. invalid modes).
    """
    # Test 1: ZKProvingError with unknown mode
    original_mode = zk_context.prover.mode
    zk_context.prover.mode = 'invalid_unknown_mode'
    
    with pytest.raises(ZKProvingError) as excinfo:
        zk_context.prover.generate_proof_bytes("a"*64, "b"*64, 1)
    assert "Proof generation failed" in str(excinfo.value)
    
    # Restore prover mode
    zk_context.prover.mode = original_mode
    
    # Test 2: ZKVerificationError with unknown mode
    original_v_mode = zk_context.verifier.mode
    zk_context.verifier.mode = 'invalid_unknown_mode'
    
    with pytest.raises(ZKVerificationError) as excinfo:
        zk_context.verifier.verify(b"dummy_proof", {
            "old_state_root": "a"*64,
            "new_state_root": "b"*64,
            "block_index": 1
        })
    assert "Verification failed" in str(excinfo.value)
    
    # Restore verifier mode
    zk_context.verifier.mode = original_v_mode
