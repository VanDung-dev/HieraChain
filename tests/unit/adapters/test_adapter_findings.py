"""Focused regressions for SQL and Redis adapter findings."""

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hierachain.adapters.database import SQLiteAdapter
from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.adapters.database.redis_adapter import (
    RedisEventManager,
    RedisProofManager,
    RedisStatsManager,
    RedisStorageError,
)
from hierachain.core import Blockchain


class _MemoryRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[Any]] = {}
        self.values: dict[str, Any] = {}
        self.fail_lpush = False

    def lpush(self, key: str, value: Any) -> int:
        if self.fail_lpush:
            raise OSError("Redis write unavailable")
        values = self.lists.setdefault(key, [])
        values.insert(0, value)
        return len(values)

    def lrange(self, key: str, start: int, end: int) -> list[Any]:
        values = self.lists.get(key, [])
        stop = len(values) if end == -1 else end + 1
        return values[start:stop]

    def hgetall(self, _key: str) -> dict[str, str]:
        return {}

    def keys(self, _pattern: str) -> list[str]:
        if isinstance(self.values, Exception):
            raise self.values
        return list(self.values)

    def mget(self, keys: list[str]) -> list[Any]:
        return [self.values[key] for key in keys]

    def scan_iter(self, match: str) -> list[str]:
        if match == "hierachain:proofs:*":
            return list(self.lists)
        return []

    def lrem(self, key: str, count: int, value: Any) -> int:
        values = self.lists.get(key, [])
        removed = 0
        matches = [index for index, item in enumerate(values) if item == value]
        indexes = matches if count == 0 else matches[:count] if count > 0 else matches[count:]
        for index in reversed(indexes):
            values.pop(index)
            removed += 1
        return removed


class _MissingRecordRedis(_MemoryRedis):
    def keys(self, _pattern: str) -> list[str]:
        return ["hierachain:event:type:created:missing"]

    def mget(self, _keys: list[str]) -> list[Any]:
        return [None]


def test_sqlite_delete_chain_removes_proofs_referencing_either_chain(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(str(tmp_path / "chains.sqlite"))
    for name in ("main", "sub", "other"):
        assert adapter.store_chain(Blockchain(name))
    assert adapter.store_proof("main", "sub", "proof-sub", 1, {})
    assert adapter.store_proof("main", "other", "proof-other", 2, {})

    assert adapter.delete_chain("sub")
    assert adapter.get_proof_history("sub") == []

    # The explicit cleanup order also works if the caller enables SQLite FK checks.
    with adapter._get_connection() as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert SQLBase._execute_delete_chain(connection, "main")
    assert adapter.get_proof_history("other") == []
    adapter.close()


def test_redis_proof_history_keeps_same_index_submissions_and_single_write_failure_atomic() -> None:
    client = _MemoryRedis()
    manager = RedisProofManager(SimpleNamespace(client=client))

    assert manager.store_proof("main", "sub", "first", 7, {"revision": 1})
    assert manager.store_proof("main", "sub", "second", 7, {"revision": 2})
    history = manager.get_proof_history("sub")
    assert [proof["proof_hash"] for proof in history] == ["second", "first"]
    assert [proof["metadata"]["revision"] for proof in history] == [2, 1]

    failing_client = _MemoryRedis()
    failing_client.fail_lpush = True
    failing_manager = RedisProofManager(SimpleNamespace(client=failing_client))
    assert not failing_manager.store_proof("main", "failed", "partial", 8, {})
    assert failing_client.lists == {}


def test_redis_cleanup_retains_inline_proof_retention_behavior() -> None:
    client = _MemoryRedis()
    client.lists["hierachain:proofs:sub"] = [
        json.dumps({"submission_id": "recent", "submitted_at": time.time()}),
        json.dumps({"submission_id": "expired", "submitted_at": 1.0}),
    ]
    manager = RedisStatsManager(SimpleNamespace(client=client))

    assert manager.cleanup_old_data(days_to_keep=30)
    assert len(client.lists["hierachain:proofs:sub"]) == 1


def test_redis_event_queries_distinguish_empty_outage_and_corrupt_records() -> None:
    empty_manager = RedisEventManager(SimpleNamespace(client=_MemoryRedis()))
    assert empty_manager.get_events_by_type("created") == []

    outage_client = _MemoryRedis()
    outage_client.values = OSError("connection refused")
    outage_manager = RedisEventManager(SimpleNamespace(client=outage_client))
    with pytest.raises(RedisStorageError, match="query failed"):
        outage_manager.get_events_by_type("created")

    corrupt_client = _MemoryRedis()
    corrupt_client.values["hierachain:event:type:created:1"] = b"{invalid-json"
    corrupt_manager = RedisEventManager(SimpleNamespace(client=corrupt_client))
    with pytest.raises(RedisStorageError, match="Invalid stored Redis event JSON"):
        corrupt_manager.get_events_by_type("created")

    missing_manager = RedisEventManager(SimpleNamespace(client=_MissingRecordRedis()))
    with pytest.raises(RedisStorageError, match="index references a missing record"):
        missing_manager.get_events_by_type("created")
