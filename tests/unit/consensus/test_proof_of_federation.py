"""
Test suite for Proof of Federation consensus mechanism

This module contains unit tests for the ProofOfFederation consensus class,
including validator management, round-robin leader selection, and block validation.
"""

import time
from hierachain.core.consensus.proof_of_federation import ProofOfFederation
from hierachain.core.block import Block

def test_pof_validator_management():
    """Test adding and removing validators in PoF consensus"""
    pof = ProofOfFederation(name="TestPoF")

    # Test adding validators
    assert pof.add_validator("validator_1") is True
    assert pof.add_validator("validator_2", {"org": "Org2"}) is True
    assert len(pof.validators) == 2
    assert "validator_1" in pof.validators
    assert "validator_2" in pof.validators
    
    # Validators should be sorted
    assert pof.validators == sorted(["validator_1", "validator_2"])

    # Test removing validators
    assert pof.remove_validator("validator_1") is True
    assert "validator_1" not in pof.validators
    assert len(pof.validators) == 1
    
    # Test removing non-existent validator
    assert pof.remove_validator("non_existent") is False


def test_pof_round_robin_leader_selection():
    """Test the deterministic round-robin leader selection"""
    pof = ProofOfFederation(name="TestPoF")
    
    # Add 3 validators
    validators = ["val_A", "val_B", "val_C"]
    for v in validators:
        pof.add_validator(v)
        
    # Expected order is sorted: val_A, val_B, val_C
    sorted_vals = sorted(validators)
    
    # Test leader selection for various block heights
    # Height 0 % 3 = 0 -> val_A
    assert pof.get_current_leader(0) == sorted_vals[0]
    # Height 1 % 3 = 1 -> val_B
    assert pof.get_current_leader(1) == sorted_vals[1]
    # Height 2 % 3 = 2 -> val_C
    assert pof.get_current_leader(2) == sorted_vals[2]
    # Height 3 % 3 = 0 -> val_A (Loop back)
    assert pof.get_current_leader(3) == sorted_vals[0]


def test_pof_block_validation_correct_leader():
    """Test that blocks must be signed by the correct rotating leader"""
    pof = ProofOfFederation(name="TestPoF")
    validators = ["val_A", "val_B"] # sorted: val_A, val_B
    for v in validators:
        pof.add_validator(v)
        
    # Block 1 should be signed by val_B (1 % 2 = 1)
    expected_leader = "val_B"
    
    previous_block = Block(
        index=0,
        events=[{"entity_id": "GENESIS", "event": "genesis", "timestamp": time.time()}],
        previous_hash="0" * 64
    )
    
    # Create block for height 1
    block = Block(
        index=1,
        events=[{"entity_id": "TEST", "event": "test", "timestamp": time.time()}],
        previous_hash=previous_block.hash
    )
    
    # 1. Sign with CORRECT leader
    valid_block = pof.finalize_block(block, expected_leader)
    # Update timestamp to meet interval
    valid_block.timestamp = previous_block.timestamp + pof.config["block_interval"] + 1
    
    # Mocking check: finalize_block adds the "consensus_finalization" event.
    assert pof.validate_block(valid_block, previous_block) is True
    
    # 2. Sign with WRONG leader (val_A)
    wrong_leader = "val_A"
    invalid_block = Block(
        index=1,
        events=[{"entity_id": "TEST", "event": "test", "timestamp": time.time()}],
        previous_hash=previous_block.hash,
        timestamp=previous_block.timestamp + pof.config["block_interval"] + 1
    )
    # We force finalize with wrong leader
    invalid_block = pof.finalize_block(invalid_block, wrong_leader)
    
    assert pof.validate_block(invalid_block, previous_block) is False


def test_pof_validation_min_validators():
    """Test that consensus enforces minimum validator count"""
    pof = ProofOfFederation(name="TestPoF")
    pof.config["min_validators"] = 3
    
    # Only 2 validators
    pof.add_validator("val_1")
    pof.add_validator("val_2")
    
    previous_block = Block(index=0, events=[], previous_hash="0"*64)
    block = Block(index=1, events=[], previous_hash=previous_block.hash)
    
    # Even if signed by correct leader, should fail if not enough validators
    # Leader for 1 is val_2 (sorted: val_1, val_2. 1%2=1)
    leader = "val_2"
    block = pof.finalize_block(block, leader)

    assert pof.can_create_block("val_1") is False

def test_pof_event_validation():
    """Test PoF event validation (inherits basics from BaseConsensus/PoA-like logic)"""
    pof = ProofOfFederation(name="TestPoF")
    
    valid_event = {
        "entity_id": "VALID-001",
        "event": "operation_start",
        "timestamp": time.time()
    }
    assert pof.validate_event_for_consensus(valid_event) is True
    
    invalid_event = {
        "entity_id": "INVALID",
        "event": "mining_start", # Forbidden term
        "timestamp": time.time()
    }
    assert pof.validate_event_for_consensus(invalid_event) is False
