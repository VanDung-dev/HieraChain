"""
Tests for consensus integration in the hierarchical chain. (PoA/PoF)

This includes:
- Testing the finalization process in SubChain.
- Ensuring that blocks without proper consensus finalization are rejected.
- Testing tampering detection in the consensus process.
"""


import time

from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.core.block import Block

def test_unfinalized_block_rejection():
    """
    Test that a block without proper consensus finalization (signature)
    is rejected by is_valid_new_block.
    """
    chain = MainChain("TestChain_Consensus")

    latest_block = chain.get_latest_block()
    new_index = latest_block.index + 1
    previous_hash = latest_block.hash

    # Create a basic block
    fake_block = Block(
        index=new_index,
        events=[{"event": "fake_event", "timestamp": time.time()}],
        previous_hash=previous_hash
    )
    fake_block.calculate_hash()

    # Verify rejection
    assert chain.is_valid_new_block(fake_block) is False, "MainChain should reject unfinalized block"

def test_sub_chain_consensus_flow():
    """
    Test the full flow of creating and finalizing a block in SubChain
    with consensus integration.
    """
    sub_chain = SubChain("TestSubChain_PoA", "testing")

    # Add some operations
    sub_chain.start_operation("ENTITY-1", "test_op")
    sub_chain.complete_operation("ENTITY-1", "test_op", {"result": "success"})

    # This calls finalize_sub_chain_block -> consensus.finalize_block -> add_block
    finalized_block_info = sub_chain.flush_pending_and_finalize()

    assert finalized_block_info is not None

    # Get the actual added block
    latest_block = sub_chain.get_latest_block()

    # Verify it has consensus event
    events = latest_block.to_event_list()
    consensus_events = [e for e in events if e.get("event") == "consensus_finalization"]
    assert len(consensus_events) == 1

    consensus_data = consensus_events[0]["details"]

    # Check for signature
    assert "authority_signature" in consensus_data
    assert "authority_id" in consensus_data
    assert consensus_data["consensus_type"] == "proof_of_authority"

def test_signature_tampering_detection():
    """
    Test that tampering with a finalized block's signature
    causes it to be rejected.
    """
    chain = SubChain("TamperTestChain", "testing")

    # Create a block
    chain.start_operation("ENTITY-X", "test_op")

    # 1. Create raw block
    latest_block = chain.get_latest_block()
    block = Block(
        index=latest_block.index + 1,
        events=[{"event": "valid_event", "timestamp": time.time()}],
        previous_hash=latest_block.hash
    )
    block.calculate_hash()

    # 2. Finalize it properly
    finalized_block = chain.consensus.finalize_block(block, chain.name)

    # Verify it IS valid initially
    assert chain.is_valid_new_block(finalized_block) is True

    # 3. Tamper with signature
    events = finalized_block.to_event_list()
    for e in events:
        if e.get("event") == "consensus_finalization":
            e["details"] = dict(e["details"]) # ensure it's a dict
            e["details"]["authority_signature"] = "tampered_signature"

    # Recreate block with tampered events
    tampered_block = Block(
        index=finalized_block.index,
        events=events,
        previous_hash=finalized_block.previous_hash,
        timestamp=finalized_block.timestamp,
        nonce=finalized_block.nonce
    )
    tampered_block.calculate_hash()

    # 4. Verify rejection
    # Tamper ID to unauthorized one
    for e in events:
        if e.get("event") == "consensus_finalization":
            e["details"]["authority_id"] = "unauthorized_node"

    tampered_id_block = Block(
        index=finalized_block.index,
        events=events,
        previous_hash=finalized_block.previous_hash,
        timestamp=finalized_block.timestamp
    )

    assert chain.is_valid_new_block(tampered_id_block) is False, "Chain should reject block from unauthorized signer"

def test_content_tampering_detection():
    """
    Test that tampering with block content (hash) invalidates the signature verification.
    """
    chain = SubChain("ContentTamperChain", "testing")
    chain.start_operation("ENTITY-Y", "test_op")

    latest_block = chain.get_latest_block()
    block = Block(
        index=latest_block.index + 1,
        events=[{"event": "valid_event", "timestamp": time.time()}],
        previous_hash=latest_block.hash
    )
    block.calculate_hash()

    # Finalize
    finalized_block = chain.consensus.finalize_block(block, chain.name)

    # Let's change the Hash but keep signature.
    finalized_block.hash = "0000000000000000000000000000000000000000000000000000000000000000"

    # This might fail Base Validation (hash mismatch) OR Consensus (signature mismatch).
    assert chain.is_valid_new_block(finalized_block) is False
