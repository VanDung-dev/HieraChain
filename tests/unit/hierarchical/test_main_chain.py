"""
Test suite for Main Chain functionality

The tests validate the core functionality of the HieraChain architecture
where the main chain stores proofs from registered sub-chains.
"""

from unittest.mock import Mock

import pytest

from hierachain.hierarchical import MainChain
from hierachain.security import get_zk_prover, reset_zk_prover
from hierachain.security.verify import get_zk_verifier, reset_zk_verifier
from hierachain.config.settings import settings


@pytest.fixture(autouse=True)
def _restore_zk_settings():
    original_enable = getattr(settings, "ENABLE_ZK_PROOFS", False)
    original_mode = getattr(settings, "ZK_MODE", "mock")
    yield
    settings.ENABLE_ZK_PROOFS = original_enable
    settings.ZK_MODE = original_mode
    reset_zk_prover()
    reset_zk_verifier()


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
    main_chain.consensus.config["block_interval"] = 0
    
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
    from hierachain.core.utils import validate_proof_metadata
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
    main_chain.consensus.config["block_interval"] = 0
    
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
    main_chain.consensus.config["block_interval"] = 0
    
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
    main_chain.consensus.config["block_interval"] = 0
    
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


# New tests for invalid inputs
def test_main_chain_creation_with_invalid_name():
    """Test MainChain creation with invalid name"""
    # Test with empty string
    main_chain = MainChain(name="")
    assert main_chain.name == ""
    
    # Test with special characters
    main_chain = MainChain(name="Test@#$%^&*()")
    assert main_chain.name == "Test@#$%^&*()"


def test_register_sub_chain_with_invalid_inputs():
    """Test registering Sub-Chains with invalid inputs"""
    main_chain = MainChain(name="InvalidInputTestMainChain")
    
    # Test with empty sub-chain name
    result = main_chain.register_sub_chain("", {"domain": "testing"})
    assert result is True  # Empty string is still a valid name
    
    # Test with None metadata
    result = main_chain.register_sub_chain("TestChain2", None)
    assert result is True
    assert main_chain.sub_chain_metadata["TestChain2"] == {}


def test_add_proof_with_invalid_inputs():
    """Test adding proofs with invalid inputs"""
    main_chain = MainChain(name="InvalidProofInputsTestMainChain")
    
    # Register a sub-chain first
    main_chain.register_sub_chain("TestSubChain", {"domain": "testing"})
    
    # Test with empty proof hash
    result = main_chain.add_proof("TestSubChain", "", {"count": 1})
    assert result is False  # Empty string should be rejected
    
    # Test with None metadata
    result = main_chain.add_proof("TestSubChain", "hash123", None)
    assert result is False  # None metadata should be rejected
    
    # Test with invalid metadata (detailed data)
    result = main_chain.add_proof("TestSubChain", "hash456", {"detailed_data": {"user_info": "private"}})
    assert result is False  # Detailed data should be rejected


def test_verify_proof_with_invalid_inputs():
    """Test verifying proofs with invalid inputs"""
    main_chain = MainChain(name="InvalidVerifyTestMainChain")
    
    # Test with empty proof hash
    result = main_chain.verify_proof("", "NonExistentChain")
    assert result is False
    
    # Test with empty sub-chain name
    result = main_chain.verify_proof("hash123", "")
    assert result is False


# Performance benchmark test
def test_main_chain_performance(benchmark):
    """Benchmark MainChain performance with multiple operations"""
    def run_performance_test():
        main_chain = MainChain(name="PerformanceTestMainChain")
        main_chain.consensus.config["block_interval"] = 0
        
        # Register multiple sub-chains
        for i in range(100):
            main_chain.register_sub_chain(f"SubChain{i}", {"domain": "testing", "id": i})
        
        # Add multiple proofs
        for i in range(1000):
            proof_hash = f"{i:08x}".zfill(64)
            main_chain.add_proof(f"SubChain{i % 100}", proof_hash, {"count": i})
        
        # Finalize blocks
        for _ in range(10):
            main_chain.finalize_block()
        
        return main_chain

    chain = benchmark(run_performance_test)
    
    # Basic assertions to ensure it worked
    assert len(chain.registered_sub_chains) == 100
    assert chain.proof_count == 1000


# Mock dependency tests
def test_main_chain_with_mock_consensus():
    """Test MainChain with mocked consensus"""
    main_chain = MainChain(name="MockConsensusTestMainChain")
    
    # Mock the consensus object
    mock_consensus = Mock()
    mock_consensus.name = "MockPoA"
    mock_consensus.authorities = {"mock_authority"}
    main_chain.consensus = mock_consensus
    
    # Register a sub-chain
    main_chain.register_sub_chain("TestSubChain", {"domain": "testing"})
    
    # Verify mock was called
    mock_consensus.add_authority.assert_called()
    
    # Add a proof
    proof_hash = "a" * 64
    result = main_chain.add_proof("TestSubChain", proof_hash, {"count": 1})
    assert result is True


# Regression: ZK mock proof with real sub_chain_name must pass verification
def test_add_proof_with_zk_mock_proof_and_real_sub_chain_name():
    """add_proof accepts a mock ZK proof generated with the real sub-chain name."""
    settings.ENABLE_ZK_PROOFS = True
    settings.ZK_MODE = "mock"

    main_chain = MainChain(name="ZKProofMainChain")
    main_chain.consensus.config["block_interval"] = 0
    main_chain.register_sub_chain("ZKSupplyChain", {"domain": "zk_test"})

    prover = get_zk_prover()
    proof = prover.generate_proof(
        "a" * 64, "b" * 64, 5, sub_chain_name="ZKSupplyChain"
    )
    assert proof.success is True

    metadata = {
        "previous_merkle_root": "a" * 64,
        "latest_merkle_root": "b" * 64,
        "latest_block_index": 5,
    }
    result = main_chain.add_proof(
        "ZKSupplyChain", "b" * 64, metadata, zk_proof=proof.proof
    )
    assert result is True, "ZK mock proof with real sub_chain_name was rejected"


def test_add_proof_with_zk_mock_proof_and_wrong_state_root_rejected():
    """add_proof rejects a mock ZK proof whose state roots don't match metadata."""
    settings.ENABLE_ZK_PROOFS = True
    settings.ZK_MODE = "mock"

    main_chain = MainChain(name="ZKRejectMainChain")
    main_chain.consensus.config["block_interval"] = 0
    main_chain.register_sub_chain("ZKSupplyChain", {"domain": "zk_test"})

    prover = get_zk_prover()
    proof = prover.generate_proof(
        "a" * 64, "b" * 64, 5, sub_chain_name="ZKSupplyChain"
    )

    metadata = {
        "previous_merkle_root": "c" * 64,  # tampered: wrong old root
        "latest_merkle_root": "b" * 64,
        "latest_block_index": 5,
    }
    result = main_chain.add_proof(
        "ZKSupplyChain", "b" * 64, metadata, zk_proof=proof.proof
    )
    assert result is False, "Tampered ZK proof should be rejected"


def test_zk_verifier_rejects_fake_mock_proof_prefix():
    """ZK verification must reject a proof with a bare 'mock_proof' prefix."""
    settings.ENABLE_ZK_PROOFS = True
    settings.ZK_MODE = "mock"

    verifier = get_zk_verifier()
    public_inputs = {
        "old_state_root": "a" * 64,
        "new_state_root": "b" * 64,
        "block_index": 5,
        "sub_chain_name": "ZKSupplyChain",
    }
    assert verifier.verify(b"mock_proof" + b"x" * 32, public_inputs) is False


# Regression: empty chain must not crash proof submission
def test_submit_proof_with_empty_chain_returns_false():
    """submit_proof_to_main on a sub-chain with an empty chain must return False, not raise."""
    from hierachain.hierarchical.sub_chain.proof import _submit_proof_for_sub_chain

    sub_chain = Mock()
    sub_chain.chain = []
    sub_chain.name = "EmptyChain"
    sub_chain.domain_type = "generic"
    sub_chain.completed_operations = 0

    result = _submit_proof_for_sub_chain(sub_chain, Mock(), None)
    assert result is False
    sub_chain.get_latest_block.assert_not_called()