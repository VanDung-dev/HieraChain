"""
Tests for the 2PC implementation in HierarchyManager.

This module contains tests for the 2PC implementation in HierarchyManager.
It includes tests for both successful and failed 2PC transactions.
"""

import pytest

from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.hierarchical.transaction_manager import TransactionState


def _assert_2pc_outcome(hierarchy, tx_id, source_chain, dest_chain, expected_state):
    assert tx_id is not None
    tx = hierarchy.transaction_manager.get_transaction(tx_id)
    assert tx.state == expected_state
    assert len(source_chain.pending_transactions) == 0
    assert len(dest_chain.pending_transactions) == 0


@pytest.fixture
def hierarchy_setup():
    hierarchy = HierarchyManager("TestMainChain")
    # Create Source Chain
    hierarchy.create_sub_chain("SourceChain", "generic")
    # Create Dest Chain
    hierarchy.create_sub_chain("DestChain", "generic")
    
    source_chain = hierarchy.get_sub_chain("SourceChain")
    dest_chain = hierarchy.get_sub_chain("DestChain")

    # Register entities
    source_chain.register_entity("item-123", {"owner": "Alice"})
    dest_chain.register_entity("item-123", {"owner": "None"})  # Pre-register on dest for validation
    
    source_chain.register_entity("item-fail", {"owner": "Bob"})
    dest_chain.register_entity("item-fail", {"owner": "None"})
    
    return hierarchy, source_chain, dest_chain


def test_2pc_success(hierarchy_setup):
    """Test a successful 2PC transaction."""
    hierarchy, source_chain, dest_chain = hierarchy_setup
    
    payload = {
        "entity_id": "item-123",
        "operation_type": "transfer",
        "details": {"amount": 100}
    }
    
    # Initiate transaction
    tx_id = hierarchy.initiate_cross_chain_transaction(
        "SourceChain", "DestChain", payload
    )
    
    _assert_2pc_outcome(
        hierarchy,
        tx_id,
        source_chain,
        dest_chain,
        TransactionState.COMMITTED,
    )


def test_2pc_prepare_failure(hierarchy_setup):
    """Test failure during prepare phase (e.g. invalid domain rule)."""
    hierarchy, source_chain, dest_chain = hierarchy_setup
    
    # Add a rule to SourceChain that rejects this operation
    # Note: We use the fact that add_domain_rule adds to self.domain_rules
    source_chain.add_domain_rule("fail_prepare", lambda *args, **kwargs: False)

    payload = {
        "entity_id": "item-fail",
        "operation_type": "transfer",
        "details": {}
    }
    
    tx_id = hierarchy.initiate_cross_chain_transaction(
        "SourceChain", "DestChain", payload
    )
    
    _assert_2pc_outcome(
        hierarchy,
        tx_id,
        source_chain,
        dest_chain,
        TransactionState.ROLLED_BACK,
    )
