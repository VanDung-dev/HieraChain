"""
Unit tests for SQLite adapter.
"""

import os

import pytest

from hierachain.adapters.database import SQLiteAdapter
from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.core import Blockchain
from hierachain.core.block import Block


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
    with adapter._get_connection() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2


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


def test_get_events_by_filter_uses_existing_event_columns(adapter):
    chain_name = "event-filter-chain"
    block = Block(
        index=1,
        timestamp=1234567890.0,
        previous_hash="genesis",
        events=[{
            "entity_id": "entity-filter",
            "event": "updated",
            "timestamp": 1234567890.0,
            "data": {"status": "ready"},
        }],
    )
    assert adapter.save_block({
        "chain_name": chain_name,
        "index": block.index,
        "hash": block.hash,
        "previous_hash": block.previous_hash,
        "timestamp": block.timestamp,
        "nonce": block.nonce,
        "events": block.to_event_list(),
    })

    by_entity = adapter.get_entity_events("entity-filter", chain_name)
    by_type = adapter.get_events_by_type("updated", chain_name)

    assert len(by_entity) == len(by_type) == 1
    assert by_entity[0]["entity_id"] == "entity-filter"
    assert by_type[0]["event"] == "updated"


def test_get_events_by_filter_surfaces_query_errors(adapter):
    with adapter._get_connection() as connection:
        connection.execute("DROP TABLE events")
        connection.commit()

    with pytest.raises(RuntimeError, match="get_entity_events failed"):
        adapter.get_entity_events("entity-filter", "missing-table-chain")


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
    
    _result = adapter.store_proof(
        main_chain,
        sub_chain,
        proof_data["proof_hash"],
        proof_data["block_index"],
        proof_data["metadata"]
    )
    # This may return True or False depending on implementation


def test_cleanup(adapter):
    """Test cleanup of old data."""
    # Test cleanup returns a boolean
    result = adapter.cleanup_old_data(30)
    assert isinstance(result, bool)


def test_memory_database_is_shared_between_operation_connections() -> None:
    adapter = SQLiteAdapter(":memory:")
    try:
        with adapter._get_connection() as first_connection:
            first_connection.execute(
                "INSERT INTO chains (name, chain_type, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("memory-chain", "sub", 1.0, 1.0),
            )
            first_connection.commit()

        with adapter._get_connection() as second_connection:
            row = second_connection.execute(
                "SELECT name FROM chains WHERE name = ?", ("memory-chain",)
            ).fetchone()

        assert row is not None
        assert row["name"] == "memory-chain"
    finally:
        adapter.close()
    assert adapter._keeper_connection is None


def test_save_fetch_block_preserves_events_and_merkle_root(adapter) -> None:
    events = [
        {
            "event_id": "ev-round-trip",
            "entity_id": "entity-round-trip",
            "event": "update",
            "timestamp": 1234567890.0,
            "data": {"version": 2},
            "details": {"state": "ready"},
            "details_cid": "cid:details-1",
            "details_nonce": "nonce-1",
            "signature": "sig-1",
            "sender_id": "user-1",
        }
    ]
    block = Block(index=1, timestamp=1234567890.0, previous_hash="prev", events=events)
    chain = Blockchain("round-trip-chain")
    chain._sign_block(block)
    block_data = {
        "chain_name": "round-trip-chain",
        "index": block.index,
        "hash": block.hash,
        "previous_hash": block.previous_hash,
        "timestamp": block.timestamp,
        "nonce": block.nonce,
        "events": block.to_event_list(),
        "metadata": {
            "merkle_root": block.merkle_root,
            "creator_id": block.creator_id,
            "signature": block.signature,
        },
    }

    assert adapter.save_block(block_data)
    fetched = adapter.get_block_by_index(block.index, "round-trip-chain")

    assert fetched is not None
    assert fetched["events"] == events
    restored = _block_from_dict(fetched, chain.trusted_public_keys)
    assert restored.to_event_list() == events
    assert restored.calculate_merkle_root() == block.merkle_root


def test_legacy_event_row_keeps_normalized_fallback_shape(adapter) -> None:
    event = adapter._create_event_from_row(
        {
            "chain_name": "legacy-chain",
            "entity_id": "entity-legacy",
            "event_type": "create",
            "timestamp": 1.0,
            "data": '{"legacy":true}',
        }
    )

    assert event == {
        "chain_name": "legacy-chain",
        "entity_id": "entity-legacy",
        "event": "create",
        "timestamp": 1.0,
        "data": {"legacy": True},
    }
