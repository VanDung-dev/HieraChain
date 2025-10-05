"""
Test suite for Proof of Authority consensus mechanism

This module contains unit tests for the ProofOfAuthority consensus class,
including authority management, block validation, and event validation.
"""

import time
from core.consensus.proof_of_authority import ProofOfAuthority
from core.block import Block


def test_poa_authority_management():
    """Test adding and removing authorities in PoA consensus"""
    poa = ProofOfAuthority(name="TestPoA")
    
    # Test adding authorities
    assert poa.add_authority("authority_1") is True
    assert poa.add_authority("authority_2", {"role": "validator"}) is True
    assert len(poa.authorities) == 2
    assert "authority_1" in poa.authorities
    assert "authority_2" in poa.authorities
    assert poa.authority_metadata["authority_2"]["role"] == "validator"
    
    # Test adding too many authorities
    for i in range(98):
        poa.add_authority(f"authority_{i+10}")
    
    # Should fail when trying to add more than max (100)
    assert poa.add_authority("overflow_authority") is False
    
    # Test removing authorities
    assert poa.remove_authority("authority_1") is True
    assert "authority_1" not in poa.authorities
    assert len(poa.authorities) == 99  # 1 removed, 98 added (2 initial - 1 removed)
    
    # Test removing non-existent authority
    assert poa.remove_authority("non_existent") is False


def test_poa_block_validation():
    """Test PoA block validation"""
    poa = ProofOfAuthority(name="TestPoA")
    authority_id = "test_authority"
    poa.add_authority(authority_id)
    
    # Create a valid previous block
    previous_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": time.time()
        }],
        previous_hash="0" * 64
    )
    
    # Create a valid block
    events = [{
        "entity_id": "TEST-001",
        "event": "test_event",
        "timestamp": time.time()
    }]
    
    block = Block(
        index=1,
        events=events,
        previous_hash=previous_block.hash
    )
    
    # Finalize the block with authority signature
    block = poa.finalize_block(block, authority_id)
    
    # Manually update timestamp to satisfy timing constraint
    block.timestamp = previous_block.timestamp + poa.config["block_interval"] + 1  # Adding extra time
    previous_block.timestamp = block.timestamp - poa.config["block_interval"] - 1  # Make sure previous is consistent
    
    # Test valid block
    assert poa.validate_block(block, previous_block) is True
    
    # Test block with invalid timing
    fast_block = Block(
        index=2,
        events=events,
        previous_hash=block.hash
    )
    # Finalize with authority
    fast_block = poa.finalize_block(fast_block, authority_id)
    # Set timestamp too close to previous
    fast_block.timestamp = block.timestamp + (poa.config["block_interval"] / 4)
    
    # Should be False because it's too fast
    assert poa.validate_block(fast_block, block) is False


def test_poa_event_validation():
    """Test PoA event validation"""
    poa = ProofOfAuthority(name="TestPoA")
    
    # Valid event
    valid_event = {
        "entity_id": "VALID-001",
        "event": "operation_start",
        "timestamp": time.time(),
        "details": {"process": "assembly"}
    }
    assert poa.validate_event_for_consensus(valid_event) is True
    
    # Invalid event with cryptocurrency terms
    invalid_event = {
        "entity_id": "INVALID-001",
        "event": "transaction",
        "timestamp": time.time(),
        "details": {"amount": 100}
    }
    assert poa.validate_event_for_consensus(invalid_event) is False
    
    # Invalid event with mining term
    invalid_event2 = {
        "entity_id": "INVALID-002",
        "event": "mining_start",
        "timestamp": time.time()
    }
    assert poa.validate_event_for_consensus(invalid_event2) is False
    
    # Valid custom event
    valid_custom_event = {
        "entity_id": "CUSTOM-001",
        "event": "quality_inspection",
        "timestamp": time.time(),
        "details": {"result": "pass"}
    }
    assert poa.validate_event_for_consensus(valid_custom_event) is True