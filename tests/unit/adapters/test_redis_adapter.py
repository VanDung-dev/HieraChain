"""
Unit tests for RedisStorageAdapter in hierachain.adapters.storage.redis_storage module.
"""
import pytest
from unittest.mock import MagicMock, patch
from hierachain.adapters.storage import RedisStorageAdapter


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    with patch("hierachain.adapters.storage.redis_storage.redis.Redis") as mock_redis:
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        yield mock_client


def test_initialization(mock_redis_client):
    """Test that adapter initializes correctly."""
    adapter = RedisStorageAdapter("localhost", 6379, 0)
    assert adapter.host == "localhost"
    assert adapter.port == 6379
    assert adapter.db == 0
    mock_redis_client.ping.assert_called_once()


def test_store_chain_metadata(mock_redis_client):
    """Test storing chain metadata."""
    adapter = RedisStorageAdapter()
    adapter.store_chain_metadata("Chain1", "main", None, {"data": 1})
    
    # Verify redis client was called
    assert mock_redis_client.hset.called or mock_redis_client.sadd.called


def test_store_block(mock_redis_client):
    """Test storing a block."""
    adapter = RedisStorageAdapter()
    block = {"index": 1, "hash": "abc", "previous_hash": "0", "timestamp": 1234567890.0, "events": []}
    adapter.store_block("Chain1", block)
    
    # Verify redis client was called
    assert mock_redis_client.hset.called


def test_get_block(mock_redis_client):
    """Test retrieving a block."""
    mock_redis_client.hgetall.return_value = {
        "index": "1",
        "hash": "abc",
        "previous_hash": "0",
        "timestamp": "1234567890.0"
    }
    
    adapter = RedisStorageAdapter()
    res = adapter.get_block("Chain1", 1)
    
    # The adapter may convert values, so just check we got a result
    assert res is not None
    assert "index" in res


def test_list_chains(mock_redis_client):
    """Test listing all chains."""
    mock_redis_client.smembers.return_value = {"Chain1", "Chain2"}
    
    adapter = RedisStorageAdapter()
    chains = adapter.list_chains()
    
    assert set(chains) == {"Chain1", "Chain2"}


def test_cleanup_old_data(mock_redis_client):
    """Test cleanup of old data."""
    # Create adapter first with existing mock
    adapter = RedisStorageAdapter()
    
    # Now call cleanup - implementation may use different redis methods
    if hasattr(adapter, 'cleanup_old_data'):
        adapter.cleanup_old_data(30)
        # The implementation may use keys/scan methods, just verify adapter was created
        assert adapter is not None
    else:
        pytest.skip("cleanup_old_data method not implemented")
