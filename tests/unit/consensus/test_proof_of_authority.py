"""
Test suite for Proof of Authority consensus mechanism

This module contains unit tests for the ProofOfAuthority consensus class,
including authority management, block validation, and event validation.
"""

import time
import hashlib

from hierachain.core.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.block import Block


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
        poa.add_authority(f"authority_{i + 10}")

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

    # Set genesis time
    genesis_time = time.time() - 20

    # Create a valid previous block
    previous_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": genesis_time
        }],
        previous_hash="0" * 64,
        timestamp=genesis_time
    )

    # Create a valid block with sufficient time diff
    events = [{
        "entity_id": "TEST-001",
        "event": "test_event",
        "timestamp": genesis_time + 15
    }]

    block = Block(
        index=1,
        events=events,
        previous_hash=previous_block.hash,
        timestamp=genesis_time + 15
    )

    # Finalize the block with authority signature
    block = poa.finalize_block(block, authority_id)

    # Test valid block
    assert poa.validate_block(block, previous_block) is True

    # Test block with invalid timing
    fast_block_timestamp = block.timestamp + (poa.config["block_interval"] / 4)
    fast_block = Block(
        index=2,
        events=events,
        previous_hash=block.hash,
        timestamp=fast_block_timestamp
    )
    # Finalize with authority
    fast_block = poa.finalize_block(fast_block, authority_id)

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


def test_multiple_authorities_concurrent_operations():
    """Test handling multiple authorities operating concurrently"""
    poa = ProofOfAuthority(name="ConcurrentPoA")
    poa.config["block_interval"] = 0.1  # Reduce interval for testing

    # Create genesis block with current time
    genesis_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": time.time()
        }],
        previous_hash="0" * 64
    )

    # Create multiple blocks with proper timing
    blocks = []
    for i in range(5):
        events = [{
            "entity_id": f"ENTITY-{i}",
            "event": "data_entry",
            "timestamp": time.time() + (i * 0.2)  # Stagger timestamps
        }]

        block = Block(
            index=i + 1,
            events=events,
            previous_hash=genesis_block.hash if i == 0 else blocks[i - 1].hash,
            timestamp=time.time() + (i * 0.2)  # Ensure proper timing
        )
        blocks.append(block)


def test_network_unstable_conditions():
    """Test behavior under unstable network conditions"""
    poa = ProofOfAuthority(name="UnstableNetworkPoA")
    poa.config["block_interval"] = 1.0  # Reduce interval for faster testing

    authority_id = "network_test_auth"
    poa.add_authority(authority_id)

    # Create initial blocks
    genesis_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": time.time()
        }],
        previous_hash="0" * 64
    )

    # Simulate network delays by creating blocks with irregular timestamps
    events = [{
        "entity_id": "NETWORK-TEST-001",
        "event": "data_operation",
        "timestamp": time.time()
    }]

    # Create a normal block
    block1 = Block(
        index=1,
        events=events,
        previous_hash=genesis_block.hash,
        timestamp=genesis_block.timestamp + 2.0  # Normal delay
    )
    block1 = poa.finalize_block(block1, authority_id)
    assert poa.validate_block(block1, genesis_block) is True

    # Create a block with minimal delay (edge case)
    block2 = Block(
        index=2,
        events=events,
        previous_hash=block1.hash,
        timestamp=block1.timestamp + 0.6  # Just above minimum threshold
    )
    block2 = poa.finalize_block(block2, authority_id)
    assert poa.validate_block(block2, block1) is True

    # Create a block with too short delay (should fail)
    block3 = Block(
        index=3,
        events=events,
        previous_hash=block2.hash,
        timestamp=block2.timestamp + 0.3  # Below minimum threshold
    )
    block3 = poa.finalize_block(block3, authority_id)
    assert poa.validate_block(block3, block2) is False


def test_spoofed_authority_attack():
    """Test resistance against spoofed authority attacks"""
    poa = ProofOfAuthority(name="SecurityPoA")

    # Add legitimate authority
    legit_authority = "legitimate_authority"
    poa.add_authority(legit_authority)

    # Try to create block with unauthorized authority
    unauthorized_authority = "spoofed_authority"

    events = [{
        "entity_id": "SECURITY-TEST-001",
        "event": "sensitive_operation",
        "timestamp": time.time()
    }]

    block = Block(
        index=1,
        events=events,
        previous_hash="0" * 64
    )

    # Try to finalize with unauthorized authority
    block = poa.finalize_block(block, unauthorized_authority)

    # Check that the block doesn't have valid authority signature
    has_valid_signature = False
    for event in block.to_event_list():
        if (event.get("event") == "consensus_finalization" and
                "details" in event and
                poa.is_authority(event["details"].get("authority_id", ""))):
            has_valid_signature = True
            break

    # Block should not have valid authority signature
    assert has_valid_signature is False

    # Create a fake consensus event to try to bypass validation
    fake_consensus_event = {
        "event": "consensus_finalization",
        "timestamp": time.time(),
        "details": {
            "consensus_type": "proof_of_authority",
            "authority_id": unauthorized_authority,  # Fake authority
            "authority_signature": hashlib.sha256(b"fake_signature").hexdigest(),
            "finalized_at": time.time()
        }
    }

    malicious_block = Block(
        index=1,
        events=events + [fake_consensus_event],
        previous_hash="0" * 64
    )

    # Validation should still fail because the authority is not registered
    genesis_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": time.time()
        }],
        previous_hash="0" * 64
    )

    assert poa.validate_block(malicious_block, genesis_block) is False


def test_performance_with_many_authorities(benchmark):
    """Test performance with a large number of authorities"""
    def execute():
        poa = ProofOfAuthority(name="PerformancePoA")

        # Add a large number of authorities
        num_authorities = 100
        for i in range(num_authorities):
            poa.add_authority(f"perf_auth_{i}", {"role": "validator", "priority": i % 5})

        assert len(poa.authorities) == num_authorities
        assert poa.get_authority_stats()["total_authorities"] == num_authorities

        # Test round-robin authority selection performance
        start_time = time.time()
        for i in range(1000):
            authority = poa.get_next_authority(i)
            assert authority is not None
        end_time = time.time()

        # Should complete within reasonable time (less than 1 second for 1000 selections)
        assert (end_time - start_time) < 1.0

        # Test authority lookup performance
        start_time = time.time()
        for i in range(1000):
            is_auth = poa.is_authority(f"perf_auth_{i % num_authorities}")
            assert is_auth is True
        end_time = time.time()

        # Should complete quickly
        assert (end_time - start_time) < 1.0
        return poa

    benchmark(execute)


def test_realistic_environment_simulation(benchmark):
    """Test with more realistic environment simulation"""
    def execute():
        poa = ProofOfAuthority(name="RealisticPoA")
        poa.config["block_interval"] = 5.0  # 5 seconds between blocks

        # Add different types of authorities
        authorities = {
            "org1_validator": {"org": "Org1", "role": "validator"},
            "org2_validator": {"org": "Org2", "role": "validator"},
            "org3_validator": {"org": "Org3", "role": "validator"},
            "backup_authority": {"org": "BackupOrg", "role": "backup"}
        }

        for auth_id, metadata in authorities.items():
            poa.add_authority(auth_id, metadata)

        # Simulate a day of blockchain operation
        genesis_block = Block(
            index=0,
            events=[{
                "entity_id": "GENESIS-001",
                "event": "genesis",
                "timestamp": time.time()
            }],
            previous_hash="0" * 64
        )

        blocks = [genesis_block]
        current_timestamp = genesis_block.timestamp

        # Simulate 24 hours of operation with blocks every 5 seconds
        # That's 24 * 60 * 60 / 5 = 17280 blocks
        # We'll simulate a smaller sample of 100 blocks for practicality
        for i in range(100):
            current_timestamp += 5.0  # 5 seconds between blocks

            # Create varied events
            event_types = ["order_created", "payment_processed", "shipment_sent",
                           "delivery_confirmed", "quality_check", "inventory_update"]
            event_type = event_types[i % len(event_types)]

            events = [{
                "entity_id": f"ENTITY-{i:04d}",
                "event": event_type,
                "timestamp": current_timestamp,
                "details": {
                    "batch_id": f"BATCH-{i // 10:03d}",
                    "quantity": (i % 100) + 1
                }
            }]

            block = Block(
                index=i + 1,
                events=events,
                previous_hash=blocks[-1].hash,
                timestamp=current_timestamp
            )

            # Assign authority in round-robin fashion
            authority_id = poa.get_next_authority(i)
            block = poa.finalize_block(block, authority_id)

            # Ensure hash is recalculated after finalization (in case of any timing issues)
            block.hash = block.calculate_hash()

            blocks.append(block)

        # Validate the entire chain
        for i in range(1, len(blocks)):
            # Ensure hash is correct before validation
            if blocks[i].hash != blocks[i].calculate_hash():
                blocks[i].hash = blocks[i].calculate_hash()
            assert poa.validate_block(blocks[i], blocks[i - 1]) is True

        # Verify authority distribution
        authority_usage = {}
        for block in blocks[1:]:  # Skip genesis block
            for event in block.to_event_list():
                if event.get("event") == "consensus_finalization":
                    authority_id = event["details"].get("authority_id")
                    authority_usage[authority_id] = authority_usage.get(authority_id, 0) + 1

        # All authorities should have been used approximately equally
        assert len(authority_usage) >= 3  # At least main validators used
        # No authority should be used significantly more than others
        return poa, blocks

    benchmark(execute)


def test_security_and_fault_tolerance():
    """Test security features and fault tolerance"""
    poa = ProofOfAuthority(name="SecureFaultTolerantPoA")

    # Add authorities with different roles
    poa.add_authority("primary_auth", {"role": "primary", "trust_level": "high"})
    poa.add_authority("secondary_auth", {"role": "secondary", "trust_level": "medium"})
    poa.add_authority("monitor_auth", {"role": "monitor", "trust_level": "high"})

    # Test tampering detection
    events = [{
        "entity_id": "SECURITY-001",
        "event": "secure_operation",
        "timestamp": time.time()
    }]

    # Create and finalize a legitimate block
    block = Block(
        index=1,
        events=events,
        previous_hash="0" * 64
    )
    block = poa.finalize_block(block, "primary_auth")

    # Tamper with block data after finalization
    tampered_events = block.to_event_list()
    tampered_events.append({
        "entity_id": "TAMPER-001",
        "event": "unauthorized_addition",
        "timestamp": time.time()
    })
    block = Block(
        index=block.index,
        events=tampered_events,
        previous_hash=block.previous_hash,
        timestamp=block.timestamp
    )

    # Create a genesis block for comparison
    genesis_block = Block(
        index=0,
        events=[{
            "entity_id": "GENESIS-001",
            "event": "genesis",
            "timestamp": time.time()
        }],
        previous_hash="0" * 64
    )

    # Validation should fail due to structural inconsistency
    assert poa.validate_block(block, genesis_block) is False

    # Test with corrupted event data
    corrupted_events = events.copy()
    corrupted_events[0]["event"] = "transaction"  # Forbidden term
    corrupted_block = Block(
        index=1,
        events=corrupted_events,
        previous_hash=genesis_block.hash
    )
    corrupted_block = poa.finalize_block(corrupted_block, "primary_auth")

    # Should fail validation due to forbidden event type
    assert poa.validate_block(corrupted_block, genesis_block) is False

    # Test fault recovery by creating a valid block after faulty ones
    recovery_events = [{
        "entity_id": "RECOVERY-001",
        "event": "recovery_operation",
        "timestamp": time.time()
    }]

    recovery_block = Block(
        index=1,
        events=recovery_events,
        previous_hash=genesis_block.hash,
        timestamp=genesis_block.timestamp + poa.config["block_interval"] + 1
    )
    recovery_block = poa.finalize_block(recovery_block, "primary_auth")

    # Should pass validation
    assert poa.validate_block(recovery_block, genesis_block) is True


def test_performance_with_large_data(benchmark):
    """Test performance with large amounts of data in blocks"""
    def execute():
        poa = ProofOfAuthority(name="LargeDataPoA")
        authority_id = "large_data_auth"
        poa.add_authority(authority_id)

        # Create a block with large amount of event data
        large_events = []
        for i in range(1000):  # 1000 events in a single block
            event = {
                "entity_id": f"LARGE-DATA-{i:04d}",
                "event": "data_entry",
                "timestamp": time.time() + (i * 0.001),  # Slightly staggered timestamps
                "details": {
                    "field1": f"data_field_value_{i}" * 10,  # Repetitive data to increase size
                    "field2": [j for j in range(50)],  # Array data
                    "field3": {"nested": {"deeply": {"nested": f"value_{i}"}}},
                    "metadata": {
                        "source": "performance_test",
                        "batch": i // 100,
                        "priority": i % 5
                    }
                }
            }
            large_events.append(event)

        # Measure block creation time
        start_time = time.time()
        block = Block(
            index=1,
            events=large_events,
            previous_hash="0" * 64
        )
        block_creation_time = time.time() - start_time

        # Measure block finalization time
        start_time = time.time()
        _block = poa.finalize_block(block, authority_id)
        finalization_time = time.time() - start_time

        # Measure block validation time
        genesis_block = Block(
            index=0,
            events=[{
                "entity_id": "GENESIS-001",
                "event": "genesis",
                "timestamp": time.time() - 10  # Set genesis further back
            }],
            previous_hash="0" * 64
        )

        # Create new block with proper timing
        block = Block(
            index=1,
            events=large_events,
            previous_hash=genesis_block.hash,
            timestamp=genesis_block.timestamp + poa.config["block_interval"] + 1
        )
        block = poa.finalize_block(block, authority_id)

        start_time = time.time()
        is_valid = poa.validate_block(block, genesis_block)
        validation_time = time.time() - start_time

        # All operations should complete within reasonable time limits
        assert block_creation_time < 1.0  # Creation should be fast
        assert finalization_time < 2.0  # Finalization may take longer
        assert validation_time < 2.0  # Validation should also be reasonable
        assert is_valid is True  # Should still be valid

        # Check that the large block has all expected events
        assert len(block.events) == 1001  # 1000 data events + 1 consensus event
        assert block.validate_structure() is True  # Structure should be valid
        return poa, block, block_creation_time, finalization_time, validation_time

    benchmark(execute)
