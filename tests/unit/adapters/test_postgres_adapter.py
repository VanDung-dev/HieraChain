"""
Unit tests for PostgreSQL adapter.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from hierachain.adapters.database import PostgresAdapter as ExportedPostgresAdapter
from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.core import Blockchain
from hierachain.core.block import Block


@pytest.fixture(autouse=True)
def no_database_connection(monkeypatch):
    """Keep dialect unit tests independent from a running PostgreSQL server."""
    monkeypatch.setattr(PostgresAdapter, "_init_pool", lambda self: None)


def test_export():
    """Test PostgresAdapter is exported from database adapters package."""
    assert ExportedPostgresAdapter is PostgresAdapter


def test_initialization():
    """Test PostgresAdapter initialization with mock pool."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    assert adapter.database_url == "postgresql://user:pass@localhost:5432/testdb"
    assert str(adapter).startswith("PostgresAdapter(database_url=")
    adapter.close()


def test_store_chain_with_mock_conn():
    """Test storing chain with PostgreSQL dialect."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    chain = Blockchain("TestPGChain")
    result = adapter._execute_store_chain(mock_conn, chain)

    assert result is True
    assert mock_cursor.execute.called
    # Check that SQL uses ON CONFLICT DO UPDATE
    sql_executed = mock_cursor.execute.call_args[0][0]
    assert "ON CONFLICT (name) DO UPDATE" in sql_executed
    mock_conn.commit.assert_called_once()


def test_save_block_with_mock_conn():
    """Test saving block and events with PostgreSQL dialect."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    block_data = {
        "chain_name": "TestPGChain",
        "index": 1,
        "hash": "hash_123456",
        "previous_hash": "hash_000000",
        "timestamp": 1234567890.0,
        "nonce": 42,
        "events": [
            {
                "event_id": "ev-1",
                "entity_id": "ent-1",
                "event": "create",
                "timestamp": 1234567890.0,
                "data": {"key": "val"},
                "sender_id": "user-1",
            },
            {
                "event_id": "ev-2",
                "entity_id": "ent-2",
                "event": "update",
                "timestamp": 1234567891.0,
                "data": {"status": "ok"},
                "sender_id": "user-2",
            },
        ],
        "metadata": {"merkle_root": "mrk_123"},
    }

    result = adapter._execute_save_block(mock_conn, block_data)
    assert result is True
    assert mock_cursor.execute.call_count == 3
    assert mock_cursor.execute.call_args_list[1].args[0].lstrip().startswith(
        "DELETE FROM events"
    )
    assert 'ON CONFLICT (chain_name, "index") DO UPDATE' in (
        mock_cursor.execute.call_args_list[2].args[0]
    )
    mock_cursor.executemany.assert_called_once()
    assert len(mock_cursor.executemany.call_args.args[1]) == 2
    assert mock_cursor.execute.call_args_list[2].args[1][7] == '{"merkle_root":"mrk_123"}'
    mock_conn.commit.assert_called_once()


def test_block_event_round_trip_preserves_full_event_payload():
    """PostgreSQL block recovery restores saved events and their Merkle root."""
    adapter = PostgresAdapter(
        database_url="postgresql://user:pass@localhost:5432/testdb"
    )
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    events = [
        {
            "event_id": "ev-full",
            "entity_id": "ent-full",
            "event": "update",
            "timestamp": 1234567890.0,
            "data": {"version": 2},
            "details": {"state": "ready"},
            "details_cid": "cid:details-1",
            "details_nonce": "nonce-1",
            "signature": "sig-1",
            "sender_id": "user-1",
            "submitted_by": "service-1",
        },
        {
            "event_id": "ev-legacy",
            "entity_id": "ent-legacy",
            "event": "create",
            "timestamp": 1234567891.0,
            "data": {"key": "value"},
        },
    ]
    block = Block(index=1, timestamp=1234567890.0, previous_hash="prev", events=events)
    chain = Blockchain("TestPGChain")
    chain._sign_block(block)
    block_data = {
        "chain_name": "TestPGChain",
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

    adapter._execute_save_block(conn, block_data)
    saved_rows = cursor.executemany.call_args.args[1]
    assert json.loads(saved_rows[0][6]) == events[0]
    assert saved_rows[0][7] == "service-1"

    # Cover both JSONB objects and drivers that return JSON text.
    cursor.fetchall.return_value = [
        {
            "chain_name": row[0],
            "block_hash": row[1],
            "event_id": row[2],
            "entity_id": row[3],
            "event_type": row[4],
            "timestamp": row[5],
            "data": json.loads(row[6]) if row[2] == "ev-full" else row[6],
        }
        for row in saved_rows
    ]
    cursor.fetchone.return_value = {
        "index": 1,
        "hash": block.hash,
        "previous_hash": block.previous_hash,
        "timestamp": block_data["timestamp"],
        "nonce": block.nonce,
        "metadata_json": block_data["metadata"],
    }
    fetched = adapter._execute_get_block_by_index(cursor, 1, "TestPGChain")

    assert fetched["events"] == events
    restored = _block_from_dict(fetched, chain.trusted_public_keys)
    assert restored.to_event_list() == events
    assert restored.calculate_merkle_root() == block.merkle_root


def test_get_event_by_id_decodes_jsonb_object():
    cursor = MagicMock()
    event_data = {"event_id": "ev-jsonb", "entity_id": "ent-jsonb", "event": "create"}
    cursor.fetchone.return_value = {
        "chain_name": "TestPGChain",
        "entity_id": "ent-jsonb",
        "event_type": "create",
        "timestamp": 1234567890.0,
        "data": event_data,
    }

    event = PostgresAdapter._execute_get_event_by_id(cursor, "ev-jsonb")

    assert event is not None
    assert event["data"] == event_data


def test_get_block_by_index_returns_events_with_base_contract():
    """Test PostgreSQL block reads match SQLBase's normalized block shape."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "index": 1,
        "hash": "hash_123456",
        "previous_hash": "hash_000000",
        "timestamp": 1234567890.0,
        "nonce": 42,
        "metadata_json": {"merkle_root": "mrk_123"},
    }
    cursor.fetchall.return_value = [
        {
            "chain_name": "TestPGChain",
            "entity_id": "ent-1",
            "event_type": "create",
            "timestamp": 1234567890.0,
            "data": {"key": "val"},
        }
    ]

    adapter = PostgresAdapter(
        database_url="postgresql://user:pass@localhost:5432/testdb"
    )
    block = adapter._execute_get_block_by_index(
        cursor, 1, "TestPGChain"
    )

    assert block["index"] == 1
    assert block["events"] == [
        {
            "chain_name": "TestPGChain",
            "entity_id": "ent-1",
            "event": "create",
            "timestamp": 1234567890.0,
            "data": {"key": "val"},
        }
    ]
    assert cursor.execute.call_args_list[0].args[1] == (1, "TestPGChain")


def test_get_latest_block_returns_events_with_base_contract():
    """Test PostgreSQL latest-block reads return the normalized block shape."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "index": 2,
        "hash": "hash_222222",
        "previous_hash": "hash_111111",
        "timestamp": 1234567891.0,
        "nonce": 43,
        "metadata_json": None,
    }
    cursor.fetchall.return_value = []
    adapter = PostgresAdapter(
        database_url="postgresql://user:pass@localhost:5432/testdb"
    )

    block = adapter._execute_get_latest_block(cursor, "TestPGChain")

    assert block["index"] == 2
    assert block["events"] == []
    assert cursor.execute.call_args_list[0].args[1] == ("TestPGChain",)


def test_store_proof_with_mock_conn():
    """Test storing proof with PostgreSQL dialect."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    result = adapter._execute_store_proof(
        mock_conn,
        "MainChain",
        "SubChain-1",
        "proof_hash_abc",
        10,
        {"summary": "test"},
        1234567890.0,
        1234567890.0,
    )
    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_query_events_filter_with_mock_conn():
    """Inherited event filters use the PostgreSQL dialect and shared signature."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        {
            "chain_name": "SubChain-1",
            "entity_id": "item-100",
            "event_type": "update",
            "timestamp": 1234567890.0,
            "data": '{"status": "ok"}',
        }
    ]

    @contextmanager
    def connection():
        yield mock_conn

    adapter._get_connection = connection
    events = adapter.get_entity_events("item-100", "SubChain-1")

    assert len(events) == 1
    assert events[0]["entity_id"] == "item-100"
    sql = mock_cursor.execute.call_args[0][0]
    assert "entity_id = %s" in sql
    assert "chain_name = %s" in sql
    assert "block_index" not in sql
    assert "details" not in sql
    assert mock_cursor.execute.call_args[0][1] == ("item-100", "SubChain-1")

    assert adapter.get_events_by_type("update") == events
    assert mock_cursor.execute.call_args[0][1] == ("update",)

    mock_cursor.execute.side_effect = ValueError("database query failed")
    with pytest.raises(RuntimeError, match="get_entity_events failed") as error:
        adapter.get_entity_events("item-100", "SubChain-1")
    assert isinstance(error.value.__cause__, ValueError)
