"""
Test suite for Cross-Chain Validation

This module contains integration tests for cross-chain validation functionality,
including proof consistency checks and hierarchical integrity verification.
"""

from hierarchical_blockchain.hierarchical.hierarchy_manager import HierarchyManager
from hierarchical_blockchain.domains.generic.utils.cross_chain_validator import CrossChainValidator


def test_cross_chain_validation():
    """Test cross-chain validation functionality"""
    # Create Hierarchy Manager with Main Chain
    hierarchy_manager = HierarchyManager("ValidationMainChain")
    main_chain = hierarchy_manager.main_chain
    
    # Create Sub-Chain and add to hierarchy using the create_sub_chain method
    hierarchy_manager.create_sub_chain("ValidationSubChain", "testing")
    sub_chain = hierarchy_manager.get_sub_chain("ValidationSubChain")
    sub_chain.connect_to_main_chain(main_chain)
    
    # Add operations to Sub-Chain
    sub_chain.start_operation("ENTITY-001", "test_operation", {"param": "value1"})
    sub_chain.update_entity_status("ENTITY-001", "in_progress", {"step": 1})
    sub_chain.complete_operation("ENTITY-001", "test_operation", {"result": "success"})
    
    # Finalize Sub-Chain block and submit proof
    sub_chain.finalize_sub_chain_block()
    sub_chain.submit_proof_to_main(main_chain)
    main_chain.finalize_block()
    
    # Create validator and run validation
    validator = CrossChainValidator(hierarchy_manager)
    validation_results = validator.validate_proof_consistency()
    
    # Check validation results
    assert validation_results["total_proofs_checked"] == 1
    assert validation_results["consistent_proofs"] == 1
    assert validation_results["missing_blocks"] == 0
    assert validation_results["inconsistent_proofs"] == 0
    assert validation_results["overall_consistent"] is True