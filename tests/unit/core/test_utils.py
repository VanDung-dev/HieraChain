"""
Test suite for Utility Functions

This module contains unit tests for utility functions,
including hash generation, entity ID generation, and proof hash generation.
"""

import time

from hierarchical_blockchain.core.utils import generate_hash, generate_entity_id, generate_proof_hash, validate_proof_metadata


def test_generate_hash():
    """Test hash generation function"""
    # Test string hashing
    hash1 = generate_hash("test_string")
    hash2 = generate_hash("test_string")
    assert hash1 == hash2  # Same input should produce same hash
    assert len(hash1) == 64  # SHA-256 produces 64-character hex string
    
    # Test dictionary hashing
    dict1 = {"key": "value", "number": 42}
    dict2 = {"number": 42, "key": "value"}  # Same content, different order
    hash3 = generate_hash(dict1)
    hash4 = generate_hash(dict2)
    assert hash3 == hash4  # Should be same regardless of key order
    
    # Test different inputs produce different hashes
    hash5 = generate_hash("different_string")
    assert hash1 != hash5


def test_generate_entity_id():
    """Test entity ID generation"""
    # Test default prefix
    entity_id1 = generate_entity_id()
    entity_id2 = generate_entity_id()
    assert entity_id1.startswith("ENTITY-")
    assert entity_id2.startswith("ENTITY-")
    assert entity_id1 != entity_id2  # Should be unique
    
    # Test custom prefix
    custom_id = generate_entity_id("PRODUCT")
    assert custom_id.startswith("PRODUCT-")


def test_generate_proof_hash():
    """Test proof hash generation"""
    block_hash = "a1b2c3d4e5f6" * 4  # 64 chars
    metadata = {
        "domain_type": "manufacturing",
        "operations_count": 5
    }
    
    proof_hash1 = generate_proof_hash(block_hash, metadata)
    proof_hash2 = generate_proof_hash(block_hash, metadata)
    
    # Should be same for same inputs
    assert proof_hash1 == proof_hash2
    assert len(proof_hash1) == 64  # SHA-256 hash length
    
    # Different inputs should produce different hashes
    different_metadata = {"domain_type": "quality_control", "operations_count": 3}
    proof_hash3 = generate_proof_hash(block_hash, different_metadata)
    assert proof_hash1 != proof_hash3


def test_validate_proof_metadata():
    """Test proof metadata validation"""
    # Valid metadata
    valid_metadata = {
        "domain_type": "manufacturing",
        "operations_count": 5,
        "timestamp": time.time()
    }
    assert validate_proof_metadata(valid_metadata) is True
    
    # Invalid metadata - contains forbidden detailed fields
    invalid_metadata = {
        "domain_type": "manufacturing",
        "full_details": {"some": "data"}  # This is forbidden
    }
    assert validate_proof_metadata(invalid_metadata) is False
    
    # Valid metadata - missing some fields (not required)
    valid_metadata2 = {
        "operations_count": 5
    }
    assert validate_proof_metadata(valid_metadata2) is True