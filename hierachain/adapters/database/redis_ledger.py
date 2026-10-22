"""Append-only signed block storage on a durable, single-primary Redis instance."""

import hashlib
from typing import Any

import redis

from hierachain.adapters.database.redis_adapter import (
    RedisStorageAdapter,
    RedisStorageError,
    _k,
)
from hierachain.core.blockchain import Blockchain
from hierachain.serialization import dumps_json, loads_json


class RedisLedgerAdapter(RedisStorageAdapter):
    """Keep ledger records separate from disposable Redis indexes."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        try:
            self.require_durable_storage()
        except Exception:
            self.close()
            raise

    def require_durable_storage(self) -> None:
        """Refuse acknowledgements with a lossy persistence/eviction policy."""
        config = self.client.config_get(
            "appendonly", "appendfsync", "no-appendfsync-on-rewrite", "maxmemory-policy",
            "aof-load-truncated",
        )
        required = {
            "appendonly": "yes", "appendfsync": "always",
            "no-appendfsync-on-rewrite": "no", "maxmemory-policy": "noeviction",
            "aof-load-truncated": "no",
        }
        if any(config.get(key) != value for key, value in required.items()):
            raise RedisStorageError("Redis ledger requires AOF, fsync always, no eviction or truncated AOF loading")
        persistence = self.client.info("persistence")
        if persistence.get("aof_enabled") != 1 or persistence.get("aof_last_write_status") != "ok":
            raise RedisStorageError("Redis ledger AOF is unavailable or unhealthy")
        if self.client.info("replication").get("role") != "master":
            raise RedisStorageError("Redis ledger requires a writable primary")

    @staticmethod
    def _blocks_key(chain_name: str) -> str:
        return _k("ledger", "blocks", hashlib.sha256(chain_name.encode("utf-8")).hexdigest())

    @staticmethod
    def _decode_block(raw: str) -> dict[str, Any]:
        try:
            block = loads_json(raw)
            if not isinstance(block, dict) or not isinstance(block.get("events"), list):
                raise ValueError("Missing block or events")
            return block
        except (ValueError, TypeError) as exc:
            raise RedisStorageError("Invalid persisted Redis ledger block") from exc

    def store_chain(self, chain: Blockchain) -> bool:
        self.require_durable_storage()
        return super().store_chain(chain)

    def list_chains(self) -> list[dict[str, Any]]:
        chains = []
        for key in self.client.scan_iter(match=_k("chain", "*")):
            if self.client.type(key) != "hash":
                continue
            data = self.client.hgetall(key)
            if data.get("chain_type") == "sub":
                chains.append({
                    "name": data["name"], "chain_type": "sub", "domain_type": data.get("domain_type"),
                })
        return sorted(chains, key=lambda chain: chain["name"])

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        data = self.client.hgetall(_k("chain", chain_name))
        if not data:
            return None
        return {
            "name": data["name"], "chain_type": data["chain_type"], "domain_type": data.get("domain_type"),
            "chain": self.get_blocks_from_index(0, chain_name), "pending_events": [],
        }

    def list_block_chain_names(self) -> list[str]:
        names = []
        for key in self.client.scan_iter(match=_k("ledger", "blocks", "*")):
            raw = self.client.lindex(key, 0)
            if raw is None:
                raise RedisStorageError("Redis ledger block list is empty")
            names.append(self._decode_block(raw)["chain_name"])
        return sorted(names)

    def save_block(self, block_data: dict[str, Any]) -> bool:
        """Append one full record atomically; retry only an identical position."""
        data = dict(block_data)
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise RedisStorageError("Invalid signed Redis block metadata")
        for field in ("creator_id", "signature", "merkle_root"):
            value = data.get(field) or metadata.get(field)
            if not isinstance(value, str) or not value:
                raise RedisStorageError(f"Signed Redis block requires {field}")
            if field in metadata and metadata[field] != value:
                raise RedisStorageError(f"Conflicting signed block field: {field}")
            data[field] = value
        name, index = data.get("chain_name"), data.get("index")
        if (
            not isinstance(name, str) or not name or type(index) is not int or index < 0
            or not isinstance(data.get("events"), list) or not isinstance(data.get("hash"), str)
            or not isinstance(data.get("previous_hash"), str) or "timestamp" not in data
        ):
            raise RedisStorageError("Invalid signed Redis block data")
        data.setdefault("nonce", 0)
        encoded = dumps_json(data, sort_keys=True)
        key = self._blocks_key(name)
        self.require_durable_storage()
        try:
            with self.client.pipeline() as pipe:
                pipe.watch(key)
                length = pipe.llen(key)
                if pipe.ttl(key) != -1 and length:
                    raise RedisStorageError("Redis ledger block history must not expire")
                if index < length:
                    return pipe.lindex(key, index) == encoded
                if index != length:
                    return False
                if length and self._decode_block(pipe.lindex(key, -1))["hash"] != data["previous_hash"]:
                    return False
                pipe.multi()
                pipe.rpush(key, encoded)
                return pipe.execute()[0] == index + 1
        except redis.WatchError:
            return False

    def get_blocks_from_index(self, start_index: int, chain_name: str | None = None) -> list[dict[str, Any]]:
        names = [chain_name] if chain_name is not None else self.list_block_chain_names()
        blocks = []
        for name in names:
            key = self._blocks_key(name)
            length = self.client.llen(key)
            start = max(0, start_index)
            rows = self.client.lrange(key, start, length - 1) if start < length else []
            if len(rows) != max(0, length - start):
                raise RedisStorageError("Redis ledger history changed or is incomplete")
            for index, raw in enumerate(rows, start):
                block = self._decode_block(raw)
                if block.get("index") != index or block.get("chain_name") != name:
                    raise RedisStorageError("Redis ledger block sequence is invalid")
                blocks.append(block)
        return blocks

    def get_block_by_index(self, index: int, chain_name: str | None = None) -> dict[str, Any] | None:
        if index < 0:
            return None
        names = [chain_name] if chain_name is not None else self.list_block_chain_names()
        for name in names:
            raw = self.client.lindex(self._blocks_key(name), index)
            if raw is not None:
                block = self._decode_block(raw)
                if block.get("index") != index or block.get("chain_name") != name:
                    raise RedisStorageError("Redis ledger block sequence is invalid")
                return block
        return None

    def get_latest_block(self, chain_name: str | None = None) -> dict[str, Any] | None:
        names = [chain_name] if chain_name is not None else self.list_block_chain_names()
        tips = [self.get_block_by_index(self.client.llen(self._blocks_key(name)) - 1, name) for name in names]
        valid_tips = [tip for tip in tips if tip is not None]
        return max(valid_tips, key=lambda tip: tip["index"]) if valid_tips else None

    def get_entity_events(self, entity_id: str, chain_name: str | None = None) -> list[dict[str, Any]]:
        return self._query_events("entity_id", entity_id, chain_name)

    def get_events_by_type(self, event_type: str, chain_name: str | None = None) -> list[dict[str, Any]]:
        return self._query_events("event", event_type, chain_name)

    def _query_events(self, field: str, value: str, chain_name: str | None) -> list[dict[str, Any]]:
        # shortcut: Scan canonical blocks; add atomic derived indexes when history query volume grows.
        events = [
            event for block in self.get_blocks_from_index(0, chain_name)
            for event in block["events"] if event.get(field) == value
        ]
        return sorted(events, key=lambda event: event.get("timestamp", 0))

    def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        for block in self.get_blocks_from_index(0):
            for event in block["events"]:
                if event.get("event_id") == event_id:
                    return {
                        "event_id": event_id, "chain_name": block["chain_name"], "status": "ordered",
                        "block_hash": block["hash"], "timestamp": event.get("timestamp"), "data": event,
                    }
        return None

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        saved = self.load_chain(chain_name)
        if saved is None:
            return {}
        events = [event for block in saved["chain"] for event in block["events"]]
        event_types: dict[str, int] = {}
        for event in events:
            kind = event.get("event", "unknown")
            event_types[kind] = event_types.get(kind, 0) + 1
        return {
            "chain_name": chain_name, "chain_type": saved["chain_type"], "domain_type": saved["domain_type"],
            "total_blocks": len(saved["chain"]), "total_events": len(events),
            "unique_entities": len({event["entity_id"] for event in events if event.get("entity_id")}),
            "event_types": event_types,
        }

    def save_hierarchy_registry(self, state: dict[str, Any], **kwargs: Any) -> bool:
        self.require_durable_storage()
        return super().save_hierarchy_registry(state, **kwargs)

    def append_channel_record(self, channel_id: str, record: dict[str, Any], **kwargs: Any) -> bool:
        self.require_durable_storage()
        return super().append_channel_record(channel_id, record, **kwargs)

    def store_proof(self, *args: Any, **kwargs: Any) -> bool:
        self.require_durable_storage()
        return super().store_proof(*args, **kwargs)

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        raise RedisStorageError("Redis ledger history cannot be pruned by cache cleanup")
