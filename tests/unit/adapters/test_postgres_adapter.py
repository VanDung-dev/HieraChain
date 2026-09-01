"""
Unit tests for PostgreSQL adapter.
"""

from unittest.mock import MagicMock

from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.adapters.database import PostgresAdapter as ExportedPostgresAdapter
from hierachain.core import Blockchain


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
            }
        ],
        "metadata_json": {"merkle_root": "mrk_123"},
    }

    result = adapter._execute_save_block(mock_conn, block_data)
    assert result is True
    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()


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
    """Test querying events with dynamic filter and PostgreSQL dialect."""
    adapter = PostgresAdapter(database_url="postgresql://user:pass@localhost:5432/testdb")
    
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {
            "chain_name": "SubChain-1",
            "entity_id": "item-100",
            "event_type": "update",
            "timestamp": 1234567890.0,
            "data": '{"status": "ok"}',
        }
    ]

    events = adapter._execute_query_events_filter(
        mock_cursor,
        chain_name="SubChain-1",
        entity_id="item-100",
        event_type="update",
        start_time=1000.0,
        end_time=2000.0,
        limit=10,
    )

    assert len(events) == 1
    assert events[0]["entity_id"] == "item-100"
    sql = mock_cursor.execute.call_args[0][0]
    assert "chain_name = %s" in sql
    assert "entity_id = %s" in sql
    assert "LIMIT %s" in sql
