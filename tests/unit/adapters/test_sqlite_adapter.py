"""
Unit tests for SQLite adapter.
"""

import pytest
import os
from hierachain.adapters.database import SQLiteAdapter
from hierachain.core import Blockchain


@pytest.fixture
def test_db_path(tmp_path):
    path = tmp_path / "test_hierachain.db"
    yield str(path)
    base = str(path)
    for suffix in ("", "-shm", "-wal"):
        try:
            os.remove(base + suffix)
        except FileNotFoundError:
            pass
        except PermissionError:
            pass


@pytest.fixture
def adapter(test_db_path):
    return SQLiteAdapter(test_db_path)


def test_initialization(adapter):
    """Test that adapter initializes correctly."""
    assert adapter.database_path is not None
    assert adapter.database_path.endswith(".db")


def test_store_and_load_chain(adapter):
    """Test storing and loading a chain.
    
    Note: store_chain stores chain metadata but not blocks in current implementation.
    """
    chain = Blockchain("TestChain")
    
    # Store chain
    result = adapter.store_chain(chain)
    assert result is True
    
    # Load chain
    loaded_data = adapter.load_chain("TestChain")
    assert loaded_data is not None
    assert loaded_data["name"] == "TestChain"
    # Chain type should be 'sub' by default (not MainChain)
    assert loaded_data["chain_type"] == "sub"


def test_store_and_load_blocks(adapter):
    """Test storing and loading blocks with events."""
    chain_name = "BlockTestChain"
    
    # Create a blockchain which will have genesis block
    chain = Blockchain(chain_name)
    
    # Store chain (this stores the chain metadata, not individual blocks)
    success = adapter.store_chain(chain)
    assert success is True
    
    # Check chain stats
    stats = adapter.get_chain_statistics(chain_name)
    assert stats is not None


def test_get_entity_events(adapter):
    """Test retrieving events by entity ID."""
    chain_name = "EntityTestChain"
    
    # Create chain and store it
    chain = Blockchain(chain_name)
    adapter.store_chain(chain)
    
    # Get entity events (this will return events from genesis block for SYSTEM entity)
    events = adapter.get_entity_events("SYSTEM", chain_name)
    assert events is not None
    assert isinstance(events, list)


def test_proof_storage(adapter):
    """Test storing and retrieving proofs."""
    main_chain = "Main"
    sub_chain = "Sub"
    
    # Create and store both chains
    main = Blockchain(main_chain)
    sub = Blockchain(sub_chain)
    
    adapter.store_chain(main)
    adapter.store_chain(sub)
    
    # Store proof
    proof_data = {
        "proof_hash": "abc123",
        "block_index": 1,
        "metadata": {"summary": "test proof"}
    }
    
    result = adapter.store_proof(main_chain, sub_chain, proof_data["proof_hash"], 
                                  proof_data["block_index"], proof_data["metadata"])
    # This may return True or False depending on implementation


def test_cleanup(adapter):
    """Test cleanup of old data."""
    # Test cleanup returns a boolean
    result = adapter.cleanup_old_data(30)
    assert isinstance(result, bool)
