"""
Test suite for Utility Functions

This module contains unit tests for utility functions,
including hash generation, entity ID generation, and proof hash generation.
"""

import time
import random
import string
from hypothesis import given, strategies as st

from hierarchical_blockchain.core.utils import (
    generate_hash,
    generate_entity_id,
    generate_proof_hash,
    validate_proof_metadata
)


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


def test_generate_hash_edge_cases():
    """Test hash generation with edge cases"""
    # Test with None input - should handle gracefully
    try:
        hash_none = generate_hash(None)
        # If it doesn't raise exception, it should produce consistent result
        assert isinstance(hash_none, str)
        assert len(hash_none) == 64
    except (TypeError, ValueError):
        # Acceptable if function raises appropriate exception
        pass

    # Test with empty string
    hash_empty = generate_hash("")
    assert isinstance(hash_empty, str)
    assert len(hash_empty) == 64

    # Test with empty dict
    hash_empty_dict = generate_hash({})
    assert isinstance(hash_empty_dict, str)
    assert len(hash_empty_dict) == 64

    # Two empty inputs should produce same hash
    assert generate_hash("") == generate_hash("")


def test_generate_hash_performance(benchmark):
    """Test hash generation performance with large input"""
    def execute():
        # Create large data structure
        large_dict = {f"key_{i}": f"value_{i}" for i in range(10000)}  # 10k entries

        # Measure time to hash
        start_time = time.time()
        hash_result = generate_hash(large_dict)
        end_time = time.time()

        # Verify result
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 hash length

        # Performance check - should complete within reasonable time (less than 2 seconds)
        assert (end_time - start_time) < 2.0

        return hash_result, (end_time - start_time)

    benchmark(execute)


def test_generate_proof_hash_edge_cases():
    """Test proof hash generation edge cases"""
    # Normal case
    block_hash = "a1b2c3d4e5f6" * 4  # 64 chars
    metadata ={
        "domain_type": "manufacturing",
        "operations_count": 5
    }

    proof_hash =generate_proof_hash(block_hash, metadata)
    assert isinstance(proof_hash, str)
    assert len(proof_hash) == 64

    # Edge case: Empty metadata
    empty_metadata_proof = generate_proof_hash(block_hash, {})
    assert isinstance(empty_metadata_proof, str)
    assert len(empty_metadata_proof)== 64

    # Edge case: None metadata (if supported)
    try:
        none_metadata_proof = generate_proof_hash(block_hash, None)
        assert isinstance(none_metadata_proof, str)
        assert len(none_metadata_proof) == 64
    except (TypeError, ValueError):
        # Acceptable if function raises appropriate exception
        pass

    # Edge case: Very long block hash (should still work)
    long_block_hash = "a" * 128  # 128 chars
    long_hash_proof = generate_proof_hash(long_block_hash, metadata)
    assert isinstance(long_hash_proof, str)
    assert len(long_hash_proof) == 64


def test_validate_proof_metadata_edge_cases():
    """Test proof metadata validation edge cases"""
    # Edge case: Empty metadata
    assert validate_proof_metadata({}) is True

    # Edge case: None metadata
    try:
        result = validate_proof_metadata(None)
        # If it doesn't raise exception, should return boolean
        assert isinstance(result, bool)
    except (TypeError, ValueError):
        # Acceptable if function raises appropriate exception
        pass

    # Edge case: Metadata with various valid and invalid combinations
    valid_combinations = [
        {"domain_type": "test"},
        {"operations_count": 0},  # Zero count should be valid
        {"timestamp": time.time()},
        {"domain_type": "test", "operations_count": 10},
    ]

    for metadata in valid_combinations:
        assert validate_proof_metadata(metadata) is True # Invalid combinations with forbidden fields
    invalid_combinations = [
        {"full_details": {}},
        {"internal_data": "secret"},
        {"complete_log": []},
        {"domain_type": "test", "full_details": {}},  # Mixed valid/invalid
    ]

    for metadata in invalid_combinations:
        assert validate_proof_metadata(metadata) is False


# Property-based testing with Hypothesis
@given(st.text())
def test_generate_hash_property(text):
    """Property-based test: same input should always produce same hash"""
    hash1 = generate_hash(text)
    hash2 = generate_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64
    assert isinstance(hash1, str)


@given(st.dictionaries(st.text(), st.text()))
def test_generate_hash_dict_property(dictionary):
    """Property-based test for dictionary hashing consistency"""
    hash1 = generate_hash(dictionary)
    hash2 = generate_hash(dictionary)
    assert hash1 == hash2
    assert len(hash1) == 64
    assert isinstance(hash1, str)


@given(st.text())
def test_entity_id_uniqueness_property(prefix):
    """Property-based test: entity IDs should be unique"""
    # Limit prefix length to prevent overly long IDs
    if len(prefix) > 50:
        prefix = prefix[:50]

    id1 = generate_entity_id(prefix)
    id2 = generate_entity_id(prefix)
    assert id1 != id2  # Should be unique
    expected_prefix = prefix if prefix else "ENTITY"
    if prefix == "":
        assert id1.startswith("-")  # Empty prefix results in IDs starting with "-"
    else:
        assert id1.startswith(expected_prefix)


# Performance/load testing
def test_utils_performance_under_load(benchmark):
    """Test utility functions performance under load"""
    def execute():
        # Test generate_hash with many iterations
        start_time = time.time()
        for i in range(10000):
            data = {"key": f"value_{i}", "index": i, "timestamp": time.time()}
            hash_result = generate_hash(data)
            assert len(hash_result) == 64
        hash_time = time.time() - start_time

        # Test generate_entity_id with many iterations
        start_time = time.time()
        for i in range(10000):
            entity_id = generate_entity_id("LOAD")
            assert entity_id.startswith("LOAD-")
        entity_id_time = time.time() - start_time

        # Test generate_proof_hash with many iterations
        start_time = time.time()
        block_hash = "a1b2c3d4e5f6" * 4
        for i in range(10000):
            metadata = {"index": i, "count": i % 100}
            proof_hash = generate_proof_hash(block_hash, metadata)
            assert len(proof_hash) == 64
        proof_hash_time = time.time() - start_time

        # Performance assertions (times may vary based on system)
        assert hash_time < 2.0  # Should hash 10k items in < 2 seconds
        assert entity_id_time < 1.0  # Should generate 10k IDs in < 1 second
        assert proof_hash_time < 1.0  # Should generate 10k proof hashes in < 1 second

        return hash_time, entity_id_time, proof_hash_time

    benchmark(execute)


# Fuzz testing
def test_utils_with_fuzzed_inputs():
    """Fuzz testing utility functions with random inputs"""
    for _ in range(1000):
        # Generate random data types for testing
        data_type = random.choice(["string", "dict", "list", "int", "float", "none"])

        if data_type == "string":
            data = ''.join(random.choices(string.printable, k=random.randint(0, 1000)))
        elif data_type == "dict":
            data = {f"key_{i}": random.random() for i in range(random.randint(0, 100))}
        elif data_type == "list":
            data = [random.random() for _ in range(random.randint(0, 100))]
        elif data_type == "int":
            data = random.randint(-1000000, 1000000)
        elif data_type == "float":
            data = random.uniform(-1000000.0, 1000000.0)
        else:  # none
            data = {}

        # Test generate_hash with fuzzed input
        try:
            hash_result = generate_hash(data)
            assert isinstance(hash_result, str)
            assert len(hash_result) == 64
        except (TypeError, ValueError):
            # Some inputs might cause exceptions, which is acceptable
            pass

        # Test generate_proof_hash with fuzzed inputs
        block_hash = ''.join(random.choices('0123456789abcdef', k=64))
        try:
            proof_hash = generate_proof_hash(block_hash, data if isinstance(data, dict) else {})
            assert isinstance(proof_hash, str)
            assert len(proof_hash) == 64
        except (TypeError, ValueError):
            # Some inputs might cause exceptions, which is acceptable
            pass


# Integration testing between utility functions
def test_utils_integration():
    """Integration test between different utility functions"""
    # Generate entity ID
    entity_id = generate_entity_id("INTEGRATION")
    assert entity_id.startswith("INTEGRATION-")

    # Create event data using the entity ID
    event_data = {
        "entity_id": entity_id,
        "event": "integration_test",
        "timestamp": time.time(),
        "details": {
            "test_type": "integration",
            "entity_reference": entity_id
        }
    }

    # Generate hash of the event data
    event_hash = generate_hash(event_data)
    assert len(event_hash) == 64

    # Create proof metadata
    proof_metadata = {
        "domain_type": "integration_testing",
        "operations_count": 1,
        "entity_summary": {
            "entity_id": entity_id,
            "event_count": 1
        }
    }

    # Validate proof metadata
    assert validate_proof_metadata(proof_metadata) is True

    # Generate proof hash
    proof_hash = generate_proof_hash(event_hash, proof_metadata)
    assert len(proof_hash) == 64

    # Verify consistency - same inputs should produce same outputs
    proof_hash2 = generate_proof_hash(event_hash, proof_metadata)
    assert proof_hash == proof_hash2
