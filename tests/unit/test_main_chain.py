"""
Test suite for Main Chain functionality

This module contains unit tests for the MainChain class, including:
- Main chain creation and initialization
- Sub-chain registration and management
- Proof submission and verification
- Chain statistics and summaries

The tests validate the core functionality of the hierarchical blockchain architecture
where the main chain stores proofs from registered sub-chains.
"""
import time
from hierarchical.main_chain import MainChain
from hierarchical.sub_chain import SubChain


def test_main_chain_creation():
    """Test basic MainChain creation"""
    main_chain = MainChain(name="TestMainChain")
    
    assert main_chain.name == "TestMainChain"
    assert len(main_chain.chain) == 1  # Genesis block
    assert len(main_chain.registered_sub_chains) == 0
    assert main_chain.proof_count == 0


def test_sub_chain_registration():
    """Test registering Sub-Chains with MainChain"""
    main_chain = MainChain(name="RegistrationTestMainChain")
    
    # Register a sub-chain
    metadata = {
        "domain_type": "manufacturing",
        "version": "1.0"
    }
    
    result = main_chain.register_sub_chain("ProductionChain", metadata)
    
    assert result is True
    assert "ProductionChain" in main_chain.registered_sub_chains
    assert "ProductionChain" in main_chain.consensus.authorities
    assert main_chain.sub_chain_metadata["ProductionChain"] == metadata
    
    # Try to register the same sub-chain again
    result2 = main_chain.register_sub_chain("ProductionChain", metadata)
    assert result2 is False


def test_proof_adding():
    """Test adding proofs from Sub-Chains"""
    main_chain = MainChain(name="ProofTestMainChain")
    
    # Register a sub-chain first
    main_chain.register_sub_chain("TestSubChain", {"domain": "testing"})
    
    # Add a proof
    proof_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    metadata = {
        "domain_type": "testing",
        "operations_count": 5
    }
    
    # Check if sub-chain is registered
    assert "TestSubChain" in main_chain.registered_sub_chains
    
    # Check metadata validation
    from core.utils import validate_proof_metadata
    assert validate_proof_metadata(metadata) is True
    
    result = main_chain.add_proof("TestSubChain", proof_hash, metadata)
    
    assert result is True, f"add_proof returned False. Check logs for details"
    assert main_chain.proof_count == 1
    
    # Finalize the block to move events from pending to chain
    main_chain.finalize_block()
    
    # Check that the proof event was added
    proof_events = main_chain.get_events_by_type("proof_submission")
    assert len(proof_events) == 1, f"Expected 1 proof event, found {len(proof_events)}"
    assert proof_events[0]["details"]["sub_chain_name"] == "TestSubChain"
    assert proof_events[0]["details"]["proof_hash"] == proof_hash


def test_invalid_proof_adding():
    """Test adding proofs from unregistered Sub-Chains"""
    main_chain = MainChain(name="InvalidProofTestMainChain")
    
    # Try to add proof from unregistered sub-chain
    proof_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    metadata = {"test": "data"}
    
    result = main_chain.add_proof("UnregisteredChain", proof_hash, metadata)
    
    assert result is False
    assert main_chain.proof_count == 0


def test_proof_verification():
    """Test verifying proofs in MainChain"""
    main_chain = MainChain(name="VerificationTestMainChain")
    
    # Register a sub-chain
    main_chain.register_sub_chain("VerificationSubChain", {"domain": "verification"})
    
    # Add a proof
    proof_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    metadata = {"domain_type": "verification", "count": 1}
    
    result = main_chain.add_proof("VerificationSubChain", proof_hash, metadata)
    assert result is True, "Failed to add proof"
    
    # Finalize the block
    main_chain.finalize_block()
    
    # Verify the proof
    result = main_chain.verify_proof(proof_hash, "VerificationSubChain")
    assert result is True, "Failed to verify proof"


def test_sub_chain_summary():
    """Test getting Sub-Chain summaries"""
    main_chain = MainChain(name="SummaryTestMainChain")
    
    # Register a sub-chain
    metadata = {"domain_type": "summary_test", "version": "1.0"}
    main_chain.register_sub_chain("SummarySubChain", metadata)
    
    # Add a proof
    proof_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    result = main_chain.add_proof("SummarySubChain", proof_hash, {"count": 1})
    assert result is True, "Failed to add proof"
    
    # Finalize the block
    main_chain.finalize_block()
    
    # Get summary
    summary = main_chain.get_sub_chain_summary("SummarySubChain")
    
    assert summary["sub_chain_name"] == "SummarySubChain"
    assert summary["registered"] is True
    assert summary["total_proofs"] == 1
    assert summary["metadata"] == metadata


def test_main_chain_stats():
    """Test MainChain statistics"""
    main_chain = MainChain(name="StatsTestMainChain")
    
    # Register a sub-chain and add proof
    main_chain.register_sub_chain("StatsSubChain", {"domain": "stats"})
    proof_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    result = main_chain.add_proof("StatsSubChain", proof_hash, {"count": 1})
    assert result is True, "Failed to add proof"
    
    # Finalize the block
    main_chain.finalize_block()
    
    # Get stats
    stats = main_chain.get_main_chain_stats()
    
    assert stats["name"] == "StatsTestMainChain"
    assert stats["registered_sub_chains"] == 1
    assert stats["total_proofs"] == 1
    assert "StatsSubChain" in stats["sub_chains"]