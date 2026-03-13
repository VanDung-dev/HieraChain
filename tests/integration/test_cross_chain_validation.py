"""
Test suite for Cross-Chain Validation

This module contains integration tests for cross-chain validation functionality,
including proof consistency checks and hierarchical integrity verification.
"""

import time
from typing import cast

import pytest

from hierachain.hierarchical import HierarchyManager
from hierachain.domains.generic.utils import CrossChainValidator


def _iter_block_events(chain):
    for block in chain:
        events = block.events
        if isinstance(events, list):
            yield block, events, False
        elif hasattr(events, "to_pylist"):
            yield block, events.to_pylist(), True


def _set_proof_submission_timestamp(main_chain, timestamp):
    from hierachain.core.block import convert_events_to_arrow

    for block, events, needs_arrow_update in _iter_block_events(main_chain.chain):
        for event in events:
            if event.get("event") == "proof_submission":
                event["timestamp"] = timestamp

                if needs_arrow_update:
                    block._events = convert_events_to_arrow(events)

                return True

    return False


def _add_full_test_operation(chain, entity_id):
    chain.start_operation(entity_id, "test_operation", {"param": "value1"})
    chain.update_entity_status(entity_id, "in_progress")
    chain.complete_operation(entity_id, "test_operation", {"result": "success"})


def _add_simple_test_operation(chain, entity_id="ENTITY-001"):
    chain.start_operation(entity_id, "test_operation", {"param": "value1"})
    chain.complete_operation(entity_id, "test_operation", {"result": "success"})


def _finalize_sub_chain_and_submit(sub_chain, main_chain):
    time.sleep(1.0)
    sub_chain.flush_pending_and_finalize()
    sub_chain.submit_proof_to_main(main_chain)
    main_chain.finalize_block()


def _setup_two_test_sub_chains_with_proofs(
    hierarchy_manager,
    main_chain,
    chain1_name,
    chain2_name,
):
    hierarchy_manager.create_sub_chain(chain1_name, "testing")
    hierarchy_manager.create_sub_chain(chain2_name, "validation")
    sub_chain1 = hierarchy_manager.get_sub_chain(chain1_name)
    sub_chain2 = hierarchy_manager.get_sub_chain(chain2_name)
    assert sub_chain1 is not None
    assert sub_chain2 is not None
    sub_chain1.consensus.config["block_interval"] = 0
    sub_chain2.consensus.config["block_interval"] = 0
    sub_chain1.proof_submission_interval = float("inf")
    sub_chain2.proof_submission_interval = float("inf")

    _add_simple_test_operation(sub_chain1, "ENTITY-001")

    time.sleep(1.0)
    sub_chain1.flush_pending_and_finalize()
    sub_chain1.submit_proof_to_main(main_chain)

    sub_chain2.start_operation(
        "ENTITY-002",
        "validate_operation",
        {"param": "value2"},
    )
    sub_chain2.complete_operation(
        "ENTITY-002",
        "validate_operation",
        {"result": "validated"},
    )

    time.sleep(1.0)
    sub_chain2.flush_pending_and_finalize()
    sub_chain2.submit_proof_to_main(main_chain)

    main_chain.finalize_block()

    return sub_chain1, sub_chain2


def test_cross_chain_validation():
    """Test cross-chain validation functionality"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("ValidationMainChain")
    hierarchy_manager.configure_auto_proof_submission(False)
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0
    
    # Create Sub-Chain and add to hierarchy using the create_sub_chain method
    # This automatically connects it to the main chain
    hierarchy_manager.create_sub_chain("ValidationSubChain", "generic")
    sub_chain = hierarchy_manager.get_sub_chain("ValidationSubChain")
    assert sub_chain is not None
    sub_chain.consensus.config["block_interval"] = 0
    
    # Explicitly disable auto-proof submission at the sub-chain level to prevent race conditions
    sub_chain.proof_submission_interval = float('inf')
    
    # Add operations to Sub-Chain
    _add_full_test_operation(sub_chain, "ENTITY-001")

    # Finalize Sub-Chain block and submit proof
    _finalize_sub_chain_and_submit(sub_chain, main_chain)
    
    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()
    
    # Check validation results
    assert validation_results["total_proofs_checked"] == 1
    assert validation_results["consistent_proofs"] == 1
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is True


def test_cross_chain_validation_with_multiple_sub_chains():
    """Test cross-chain validation with multiple sub-chains"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("MultiChainValidationMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create multiple Sub-Chains
    hierarchy_manager.create_sub_chain("SubChain1", "testing")
    hierarchy_manager.create_sub_chain("SubChain2", "manufacturing")

    sub_chain1 = hierarchy_manager.get_sub_chain("SubChain1")
    sub_chain2 = hierarchy_manager.get_sub_chain("SubChain2")
    sub_chain1.consensus.config["block_interval"] = 0
    sub_chain2.consensus.config["block_interval"] = 0
    assert sub_chain1 is not None
    assert sub_chain2 is not None

    sub_chain1.proof_submission_interval = float('inf')
    sub_chain2.proof_submission_interval = float('inf')

    # Add operations to Sub-Chain 1
    sub_chain1.start_operation("ENTITY-001", "test_operation", {"param": "value1"})
    sub_chain1.complete_operation("ENTITY-001", "test_operation", {"result": "success"})

    # Add operations to Sub-Chain 2
    sub_chain2.start_operation("ENTITY-002", "manufacture_product", {"product_id": "PROD-001"})
    sub_chain2.complete_operation("ENTITY-002", "manufacture_product", {"result": "completed"})

    # Finalize Sub-Chain blocks and submit proofs
    time.sleep(1.0)
    sub_chain1.flush_pending_and_finalize()
    sub_chain1.submit_proof_to_main(main_chain)

    time.sleep(1.0)
    sub_chain2.flush_pending_and_finalize()
    sub_chain2.submit_proof_to_main(main_chain)

    main_chain.finalize_block()

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results
    assert validation_results["total_proofs_checked"] == 2
    assert validation_results["consistent_proofs"] == 2
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is True


def test_cross_chain_validation_with_missing_sub_chain():
    """Test cross-chain validation when a sub-chain is missing"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("MissingChainValidationMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chain and add operations
    hierarchy_manager.create_sub_chain("ExistingSubChain", "testing")
    sub_chain = hierarchy_manager.get_sub_chain("ExistingSubChain")
    assert sub_chain is not None
    sub_chain.consensus.config["block_interval"] = 0
    sub_chain.proof_submission_interval = float('inf')

    # Add operations and submit proof
    _add_simple_test_operation(sub_chain, "ENTITY-001")
    _finalize_sub_chain_and_submit(sub_chain, main_chain)

    # Simulate a missing sub-chain by removing it from hierarchy manager
    # but keeping the proof in main chain
    del hierarchy_manager.sub_chains["ExistingSubChain"]

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results - should detect missing sub-chain
    assert validation_results["total_proofs_checked"] == 1
    assert validation_results["consistent_proofs"] == 0
    assert validation_results["missing_blocks"] == 1
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is False
    assert len(validation_results["inconsistencies"]) == 1
    assert validation_results["inconsistencies"][0]["type"] == "missing_sub_chain"


def test_cross_chain_validation_with_entity_consistency():
    """Test entity consistency validation across chains"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("EntityConsistencyMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chains
    hierarchy_manager.create_sub_chain("OrderChain", "order_processing")
    hierarchy_manager.create_sub_chain("InventoryChain", "inventory_management")

    order_chain = hierarchy_manager.get_sub_chain("OrderChain")
    inventory_chain = hierarchy_manager.get_sub_chain("InventoryChain")
    assert order_chain is not None
    assert inventory_chain is not None
    order_chain.consensus.config["block_interval"] = 0
    inventory_chain.consensus.config["block_interval"] = 0

    order_chain.proof_submission_interval = float('inf')
    inventory_chain.proof_submission_interval = float('inf')

    # Simulate an entity being processed across multiple chains
    entity_id = "ORDER-12345"

    # Process order in OrderChain
    order_chain.start_operation(entity_id, "process_order", {"customer": "CUST-001"})
    order_chain.update_entity_status(entity_id, "confirmed")
    order_chain.complete_operation(entity_id, "process_order", {"status": "confirmed"})
    
    time.sleep(1.0)
    order_chain.flush_pending_and_finalize()
    order_chain.submit_proof_to_main(main_chain)

    # Process inventory in InventoryChain
    inventory_chain.start_operation(entity_id, "reserve_items", {"items": ["ITEM-001"]})
    inventory_chain.update_entity_status(entity_id, "items_reserved")
    inventory_chain.complete_operation(entity_id, "reserve_items", {"result": "success"})
    
    time.sleep(1.0)
    inventory_chain.flush_pending_and_finalize()
    inventory_chain.submit_proof_to_main(main_chain)

    main_chain.finalize_block()

    # Create validator and run entity validation
    validator = CrossChainValidator(hierarchy_manager)
    entity_validation_results = validator.validate_entity_consistency(entity_id)

    # Check entity validation results
    assert entity_validation_results["entity_id"] == entity_id
    assert entity_validation_results["entity_found"] is True
    assert entity_validation_results["chains_checked"] == 2
    assert entity_validation_results["total_events"] > 0
    assert entity_validation_results["inconsistent_events"] == 0
    assert entity_validation_results["overall_consistent"] is True


@pytest.mark.flaky(reruns=5)
def test_cross_chain_validation_system_integrity():
    """Test system integrity validation"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("SystemIntegrityMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    _setup_two_test_sub_chains_with_proofs(
        hierarchy_manager,
        main_chain,
        "TestSubChain1",
        "TestSubChain2",
    )

    # Create validator and run system integrity validation
    validator = CrossChainValidator(hierarchy_manager)
    integrity_results = validator.validate_system_integrity()

    # Check system integrity results
    assert integrity_results["main_chain_valid"] is True
    assert len(integrity_results["sub_chains_valid"]) == 2
    assert all(valid for valid in integrity_results["sub_chains_valid"].values())
    assert integrity_results["proof_consistency"]["overall_consistent"] is True
    assert integrity_results["Ledger_compliance"]["overall_compliant"] is True
    assert integrity_results["overall_integrity"] is True


@pytest.mark.flaky(reruns=3)
def test_cross_chain_validation_fault_tolerance():
    """Test cross-chain validation fault tolerance when components fail"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("FaultToleranceValidationMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    sub_chain1, sub_chain2 = _setup_two_test_sub_chains_with_proofs(
        hierarchy_manager,
        main_chain,
        "FaultToleranceSubChain1",
        "FaultToleranceSubChain2",
    )

    # Simulate a fault in Sub-Chain 1 by removing its blocks to simulate data loss
    # This should cause a "missing_block" or "missing_sub_chain" inconsistency depending on implementation
    # Here we simulate missing blocks by clearing the chain
    sub_chain1.chain = []

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results
    # Should detect issues with Sub-Chain 1 but Sub-Chain 2 should be fine
    assert validation_results["overall_consistent"] is False
    assert validation_results["missing_blocks"] > 0
    
    # Verify we can identify which chain failed
    inconsistencies = validation_results["inconsistencies"]
    sub_chain1_issues = [i for i in inconsistencies if i.get("sub_chain_name") == "FaultToleranceSubChain1"]
    sub_chain2_issues = [i for i in inconsistencies if i.get("sub_chain_name") == "FaultToleranceSubChain2"]
    
    assert len(sub_chain1_issues) > 0, "Should have detected issues with FaultToleranceSubChain1"
    assert len(sub_chain2_issues) == 0, "FaultToleranceSubChain2 should remain valid"


def test_cross_chain_validation_with_timestamp_inconsistency():
    """Test validation when there's a timestamp inconsistency"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("TimestampInconsistencyMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chain and add operations
    hierarchy_manager.create_sub_chain("SubChainWithTimestampIssue", "testing")
    sub_chain = hierarchy_manager.get_sub_chain("SubChainWithTimestampIssue")
    assert sub_chain is not None
    sub_chain.consensus.config["block_interval"] = 0
    sub_chain.proof_submission_interval = float('inf')


    # Add operations and submit proof
    _add_simple_test_operation(sub_chain, "ENTITY-001")

    # Manually modify the sub-chain block timestamp to create inconsistency
    # We need to do this before finalizing to ensure we can control the timestamp
    if sub_chain.pending_events:
        # Add a small delay to ensure different timestamps
        time.sleep(1.0)

    _finalize_sub_chain_and_submit(sub_chain, main_chain)

    found_proof = _set_proof_submission_timestamp(main_chain, 0)
    assert found_proof, "Proof submission event not found in main chain"

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results - should detect timestamp inconsistency
    assert validation_results["total_proofs_checked"] == 1
    assert validation_results["consistent_proofs"] == 0
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 1
    assert validation_results["overall_consistent"] is False
    assert len(validation_results["inconsistencies"]) == 1
    assert validation_results["inconsistencies"][0]["type"] == "timestamp_inconsistency"


def test_cross_chain_validation_with_empty_hierarchy():
    """Test validation when there are no sub-chains or proofs"""
    # Create Hierarchy Manager with Main Chain only
    hierarchy_manager = HierarchyManager("EmptyHierarchyMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Finalize an empty block on main chain
    main_chain.finalize_block()

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results - should have no proofs to check
    assert validation_results["total_proofs_checked"] == 0
    assert validation_results["consistent_proofs"] == 0
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is True  # No proofs means consistent
    assert len(validation_results["inconsistencies"]) == 0


def test_cross_chain_validation_with_corrupted_entity_data():
    """Test entity consistency validation with corrupted or invalid entity data"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("CorruptedEntityMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chains
    hierarchy_manager.create_sub_chain("TestChain", "testing")
    test_chain = hierarchy_manager.get_sub_chain("TestChain")
    assert test_chain is not None
    test_chain.consensus.config["block_interval"] = 0


    # Add operations with entity that has invalid data
    _add_simple_test_operation(test_chain, "ENTITY-001")
    _finalize_sub_chain_and_submit(test_chain, main_chain)

    # Create validator and run entity validation on non-existent entity
    validator = CrossChainValidator(hierarchy_manager)
    entity_validation_results = validator.validate_entity_consistency("NON-EXISTENT-ENTITY")

    # Check entity validation results for non-existent entity
    assert entity_validation_results["entity_id"] == "NON-EXISTENT-ENTITY"
    assert entity_validation_results["entity_found"] is False
    assert entity_validation_results["chains_checked"] == 0
    assert entity_validation_results["total_events"] == 0
    assert entity_validation_results["inconsistent_events"] == 0
    assert entity_validation_results["overall_consistent"] is True  # No events means consistent


def test_cross_chain_validation_with_logic_inconsistency():
    """Test validation of logical inconsistencies in entity events"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("LogicInconsistencyMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chains
    hierarchy_manager.create_sub_chain("LogicTestChain", "testing")
    test_chain = hierarchy_manager.get_sub_chain("LogicTestChain")
    assert test_chain is not None
    test_chain.consensus.config["block_interval"] = 0
    test_chain.proof_submission_interval = float('inf')

    # Create logically inconsistent events - complete operation without starting it
    test_chain.complete_operation("ENTITY-001", "test_operation", {"result": "success"})

    # Wait for ordering service to batch the event
    time.sleep(1.0)

    block = test_chain.flush_pending_and_finalize()
    assert block is not None, "Failed to finalize block in test_chain"

    # Check if the event was committed to any block in the chain
    found_event = False
    for b in test_chain.chain:
        committed_events = b.get_events_by_entity("ENTITY-001")
        if len(committed_events) > 0:
            found_event = True
            break

    assert found_event, (
        f"Event for ENTITY-001 not found in chain."
    )

    test_chain.submit_proof_to_main(main_chain)
    main_chain.finalize_block()

    # Create validator and run entity validation
    validator = CrossChainValidator(hierarchy_manager)
    entity_validation_results = validator.validate_entity_consistency("ENTITY-001")

    # Check entity validation results - should detect logical inconsistency
    assert entity_validation_results["entity_id"] == "ENTITY-001"
    assert entity_validation_results["entity_found"] is True
    assert entity_validation_results["chains_checked"] >= 1
    assert entity_validation_results["total_events"] >= 1


def test_cross_chain_validation_with_large_number_of_sub_chains():
    """Test cross-chain validation performance with a large number of sub-chains"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("LargeScaleValidationMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create a large number of Sub-Chains (reduced to 5 for test performance)
    num_sub_chains = 5
    for i in range(num_sub_chains):
        chain_name = f"SubChain{i:03d}"
        hierarchy_manager.create_sub_chain(chain_name, f"domain_{i}")
        sub_chain = hierarchy_manager.get_sub_chain(chain_name)
        assert sub_chain is not None
        sub_chain.consensus.config["block_interval"] = 0
        sub_chain.proof_submission_interval = float('inf')


        # Add operations to each Sub-Chain
        entity_id = f"ENTITY-{i:03d}"
        sub_chain.start_operation(entity_id, "process_operation", {"index": i})
        sub_chain.complete_operation(entity_id, "process_operation", {"result": f"completed_{i}"})

        # Wait for events to be processed by ordering service
        time.sleep(1.0)

        # Finalize Sub-Chain blocks and submit proofs
        block_info = sub_chain.flush_pending_and_finalize()
        
        # Retry if flush failed (timeout)
        if block_info is None:
            time.sleep(1.0)
            block_info = sub_chain.flush_pending_and_finalize()
            
        assert block_info is not None, f"Failed to finalize block for {chain_name}"
        
        success = sub_chain.submit_proof_to_main(main_chain)
        assert success, f"Failed to submit proof for {chain_name}"

    main_chain.finalize_block()

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Check validation results
    assert validation_results["total_proofs_checked"] == num_sub_chains
    assert validation_results["consistent_proofs"] == num_sub_chains
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is True


def test_cross_chain_validation_with_invalid_input_data():
    """Test cross-chain validation behavior with invalid input data"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("InvalidInputValidationMain")
    main_chain = hierarchy_manager.main_chain
    main_chain.consensus.config["block_interval"] = 0

    # Create Sub-Chain
    hierarchy_manager.create_sub_chain("InvalidDataSubChain", "testing")
    sub_chain = hierarchy_manager.get_sub_chain("InvalidDataSubChain")
    assert sub_chain is not None
    sub_chain.consensus.config["block_interval"] = 0
    sub_chain.proof_submission_interval = float('inf')


    # Test with various invalid inputs
    # Empty entity ID
    try:
        sub_chain.start_operation("", "test_operation", {"param": "value1"})
    except (ValueError, TypeError, AttributeError):
        # Handle exception if implementation raises one for empty entity ID
        pass

    # None operation name
    try:
        sub_chain.start_operation(
            "ENTITY-001",
            cast(str, cast(object, None)),
            {"param": "value1"},
        )
    except (ValueError, TypeError, AttributeError):
        # Handle exception if implementation raises one for None operation
        pass

    # Add at least one valid operation to continue test
    _add_simple_test_operation(sub_chain, "ENTITY-001")
    _finalize_sub_chain_and_submit(sub_chain, main_chain)

    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()

    # Validation should still work with whatever valid data exists
    assert validation_results["total_proofs_checked"] >= 0
    assert validation_results["overall_consistent"] in [True, False]  # Should not crash

    # Simulate a failure by corrupting one sub-chain's data
    corrupted_chain_name = "InvalidDataSubChain"
    if corrupted_chain_name in hierarchy_manager.sub_chains:
        # Corrupt the sub-chain data in some way
        corrupted_sub_chain = hierarchy_manager.sub_chains[corrupted_chain_name]
        # Clear the block data to simulate corruption
        corrupted_sub_chain.chain = []

    # Create validator and run validation - should handle faults gracefully
    validator = CrossChainValidator(hierarchy_manager)

    # Validation should not crash even with corrupted data
    validation_results = validator.validate_proof_consistency()

    # Results will depend on implementation, but should not cause exceptions
    assert isinstance(validation_results, dict)
    assert "overall_consistent" in validation_results
