"""Durability gates for the Redis ledger; block/recovery tests use real Redis."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from hierachain.adapters.database.redis_adapter import RedisStorageError
from hierachain.adapters.database.redis_ledger import RedisLedgerAdapter
from hierachain.consensus.ordering.storage import OrderingStorageHandler


@pytest.fixture
def client() -> MagicMock:
    client = MagicMock()
    client.config_get.return_value = {
        "appendonly": "yes", "appendfsync": "always", "no-appendfsync-on-rewrite": "no",
        "maxmemory-policy": "noeviction", "aof-load-truncated": "no",
    }
    client.info.side_effect = lambda section: (
        {"aof_enabled": 1, "aof_last_write_status": "ok"} if section == "persistence" else {"role": "master"}
    )
    return client


@pytest.mark.parametrize("field,value", [
    ("appendonly", "no"), ("appendfsync", "everysec"), ("appendfsync", "no"),
    ("no-appendfsync-on-rewrite", "yes"), ("maxmemory-policy", "allkeys-lru"),
    ("aof-load-truncated", "yes"),
])
def test_unsafe_persistence_configuration_is_rejected(client: MagicMock, field: str, value: str) -> None:
    client.config_get.return_value[field] = value
    with patch.object(RedisLedgerAdapter, "client", new_callable=PropertyMock, return_value=client):
        with pytest.raises(RedisStorageError, match="requires AOF"):
            RedisLedgerAdapter()
    client.rpush.assert_not_called()


@pytest.mark.parametrize("section,response", [
    ("persistence", {"aof_enabled": 0, "aof_last_write_status": "ok"}),
    ("persistence", {"aof_enabled": 1, "aof_last_write_status": "err"}),
    ("replication", {"role": "slave"}),
])
def test_unhealthy_or_replica_storage_is_rejected(client: MagicMock, section: str, response: dict) -> None:
    healthy = client.info.side_effect
    client.info.side_effect = lambda name: response if name == section else healthy(name)
    with patch.object(RedisLedgerAdapter, "client", new_callable=PropertyMock, return_value=client):
        with pytest.raises(RedisStorageError):
            RedisLedgerAdapter()


def test_runtime_policy_change_blocks_registry_writes(client: MagicMock) -> None:
    with patch.object(RedisLedgerAdapter, "client", new_callable=PropertyMock, return_value=client):
        adapter = RedisLedgerAdapter()
        client.config_get.return_value["appendfsync"] = "everysec"
        with pytest.raises(RedisStorageError, match="requires AOF"):
            adapter.save_hierarchy_registry({"_revision": "new"})
        client.pipeline.assert_not_called()


def test_cache_cleanup_cannot_prune_ledger_history(client: MagicMock) -> None:
    with patch.object(RedisLedgerAdapter, "client", new_callable=PropertyMock, return_value=client):
        with pytest.raises(RedisStorageError, match="cannot be pruned"):
            RedisLedgerAdapter().cleanup_old_data()
    client.delete.assert_not_called()


def test_orderer_selects_redis_when_configured() -> None:
    with patch("hierachain.adapters.database.redis_ledger.RedisLedgerAdapter") as adapter:
        handler = OrderingStorageHandler({"storage_backend": "redis", "trusted_public_keys": {}})
        assert handler.storage is adapter.return_value
        handler.close()
        adapter.return_value.close.assert_called_once()
