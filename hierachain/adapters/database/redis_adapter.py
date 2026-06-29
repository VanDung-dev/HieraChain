"""
Redis Storage Adapter for HieraChain Ledger.

Provides Redis persistence for blockchain data with the same public interface
as SQLBase adapters. Supports store/load chains, blocks, events, and proofs.
"""

import orjson
import time
import logging
from typing import Any
import redis as redis_mod

from hierachain.core.blockchain import Blockchain
from hierachain.config.settings import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "hierachain"


def _k(*parts: str) -> str:
    """Build a colon-delimited Redis key."""
    return f"{_KEY_PREFIX}:{':'.join(parts)}"


def _now() -> float:
    return time.time()


class RedisChainManager:
    """Manages blockchain structure and blocks operations."""

    def __init__(self, client_provider: Any) -> None:
        self._provider = client_provider

    @property
    def client(self) -> Any:
        return self._provider.client

    def store_chain(self, chain: Blockchain) -> bool:
        try:
            chain_type = "main" if hasattr(chain, "resolve_sub_proof") or "MainChain" in chain.__class__.__name__ else "sub"
            domain_type = getattr(chain, "domain_type", None)
            data = {
                "name": chain.name,
                "chain_type": chain_type,
                "domain_type": domain_type,
                "created_at": _now(),
                "updated_at": _now(),
            }
            self.client.hset(_k("chain", chain.name), mapping=data)
            return True
        except redis_mod.RedisError as e:
            logger.error("Redis store_chain failed: %s", e)
            return False

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        try:
            data = self.client.hgetall(_k("chain", chain_name))
            if not data:
                return None
            blocks = self.load_blocks(chain_name)
            return {
                "name": data.get("name", chain_name),
                "chain_type": data.get("chain_type"),
                "domain_type": data.get("domain_type"),
                "chain": blocks,
                "pending_events": [],
            }
        except Exception as e:
            logger.error("Redis load_chain failed: %s", e)
            return None

    def load_blocks(self, chain_name: str) -> list[dict[str, Any]]:
        block_hashes = self.client.lrange(_k("chain", chain_name, "blocks"), 0, -1)
        blocks = []
        for bh in block_hashes:
            raw = self.client.get(_k("block", bh))
            if raw:
                block_dict = orjson.loads(raw)
                events = self._load_block_events(bh)
                block_dict["events"] = events
                blocks.append(block_dict)
        return blocks

    def _load_block_events(self, block_hash: str) -> list[dict[str, Any]]:
        raw = self.client.get(_k("block", block_hash, "events"))
        if raw:
            return orjson.loads(raw)
        return []


class RedisEventManager:
    """Manages events querying and filtering."""

    def __init__(self, client_provider: Any) -> None:
        self._provider = client_provider

    @property
    def client(self) -> Any:
        return self._provider.client

    @staticmethod
    def _parse_and_filter_event(raw: Any, chain_name: str | None) -> dict[str, Any] | None:
        try:
            ev = orjson.loads(raw)
            if chain_name and ev.get("chain_name") != chain_name:
                return None
            return ev
        except (orjson.JSONDecodeError, TypeError, AttributeError):
            return None

    def get_events_by_pattern(self, pattern: str, chain_name: str | None = None) -> list[dict[str, Any]]:
        keys = self.client.keys(pattern)
        if not keys:
            return []
        
        raw_events = self.client.mget(keys)
        results = []
        for raw in raw_events:
            if raw:
                ev = self._parse_and_filter_event(raw, chain_name)
                if ev is not None:
                    results.append(ev)
        results.sort(key=lambda e: e.get("timestamp", 0))
        return results

    def get_entity_events(
        self, entity_id: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            pattern = _k("event", "entity", entity_id) + ":*"
            return self.get_events_by_pattern(pattern, chain_name)
        except Exception as e:
            logger.error("Redis get_entity_events failed: %s", e)
            return []

    def get_events_by_type(
        self, event_type: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            pattern = _k("event", "type", event_type) + ":*"
            return self.get_events_by_pattern(pattern, chain_name)
        except Exception as e:
            logger.error("Redis get_events_by_type failed: %s", e)
            return []


class RedisProofManager:
    """Manages saving and reading proof history."""

    def __init__(self, client_provider: Any) -> None:
        self._provider = client_provider

    @property
    def client(self) -> Any:
        return self._provider.client

    def store_proof(
        self,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any],
    ) -> bool:
        try:
            proof_key = _k("proof", sub_chain_name, str(block_index))
            data = {
                "main_chain_name": main_chain_name,
                "sub_chain_name": sub_chain_name,
                "proof_hash": proof_hash,
                "block_index": block_index,
                "metadata": orjson.dumps(metadata).decode('utf-8'),
                "submitted_at": _now(),
                "created_at": _now(),
            }
            self.client.hset(proof_key, mapping=data)
            self.client.lpush(_k("proofs", sub_chain_name), proof_key)
            return True
        except Exception as e:
            logger.error("Redis store_proof failed: %s", e)
            return False

    def get_proof_history(self, sub_chain_name: str) -> list[dict[str, Any]]:
        try:
            proof_keys = self.client.lrange(_k("proofs", sub_chain_name), 0, -1)
            proofs = []
            for pk in proof_keys:
                data = self.client.hgetall(pk)
                if data:
                    proofs.append({
                        "main_chain_name": data.get("main_chain_name"),
                        "sub_chain_name": data.get("sub_chain_name"),
                        "proof_hash": data.get("proof_hash"),
                        "block_index": int(data.get("block_index", 0)),
                        "metadata": orjson.loads(data.get("metadata", "{}")),
                        "submitted_at": float(data.get("submitted_at", 0)),
                    })
            return proofs
        except Exception as e:
            logger.error("Redis get_proof_history failed: %s", e)
            return []


class RedisStatsManager:
    """Manages statistics aggregation and old data cleanup."""

    def __init__(self, client_provider: Any) -> None:
        self._provider = client_provider

    @property
    def client(self) -> Any:
        return self._provider.client

    @staticmethod
    def _parse_and_accumulate_events(
        raw: Any, unique_entities: set[str], event_types: dict[str, int]
    ) -> int:
        """Parses block event data and updates stats. Returns event count."""
        try:
            events = orjson.loads(raw)
            for ev in events:
                eid = ev.get("entity_id")
                if eid:
                    unique_entities.add(eid)
                etype = ev.get("event", "unknown")
                event_types[etype] = event_types.get(etype, 0) + 1
            return len(events)
        except (orjson.JSONDecodeError, TypeError, AttributeError):
            return 0

    @classmethod
    def _aggregate_events_stats(cls, raw_blocks_events: list[Any]) -> tuple[int, int, dict[str, int]]:
        total_events = 0
        unique_entities: set[str] = set()
        event_types: dict[str, int] = {}

        for raw in raw_blocks_events:
            if raw:
                total_events += cls._parse_and_accumulate_events(raw, unique_entities, event_types)

        return total_events, len(unique_entities), event_types

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        try:
            chain_data = self.client.hgetall(_k("chain", chain_name))
            if not chain_data:
                return {}
            
            block_hashes_list = self.client.lrange(_k("chain", chain_name, "blocks"), 0, -1)
            block_keys = [_k("block", bh, "events") for bh in block_hashes_list]
            raw_blocks_events = self.client.mget(block_keys) if block_keys else []
            
            total_events, unique_entity_count, event_types = self._aggregate_events_stats(raw_blocks_events)
            
            return {
                "chain_name": chain_name,
                "chain_type": chain_data.get("chain_type"),
                "domain_type": chain_data.get("domain_type"),
                "total_blocks": len(block_hashes_list),
                "total_events": total_events,
                "unique_entities": unique_entity_count,
                "event_types": event_types,
                "created_at": chain_data.get("created_at"),
                "updated_at": chain_data.get("updated_at"),
            }
        except Exception as e:
            logger.error("Redis get_chain_statistics failed: %s", e)
            return {}

    def _get_key_timestamp(self, key: str, is_hash: bool, ts_field: str) -> float | None:
        try:
            if is_hash:
                ts = self.client.hget(key, ts_field)
                return float(ts) if ts else None
            raw = self.client.get(key)
            return orjson.loads(raw).get(ts_field) if raw else None
        except (orjson.JSONDecodeError, ValueError, TypeError, redis_mod.RedisError):
            return None

    def _cleanup_keys(
        self, pattern: str, cutoff: float, is_hash: bool = False, ts_field: str = "timestamp"
    ) -> int:
        keys_to_delete = []
        for key in self.client.scan_iter(match=pattern):
            val = self._get_key_timestamp(key, is_hash, ts_field)
            if val is not None and val < cutoff:
                keys_to_delete.append(key)

        if keys_to_delete:
            self.client.delete(*keys_to_delete)
        return len(keys_to_delete)

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        try:
            cutoff = _now() - (days_to_keep * 86400)
            deleted = 0
            deleted += self._cleanup_keys(_k("event", "*"), cutoff)
            deleted += self._cleanup_keys(_k("proof", "*"), cutoff, is_hash=True, ts_field="submitted_at")
            deleted += self._cleanup_keys(_k("block", "*"), cutoff)

            logger.info("Redis cleanup completed", extra={"deleted": deleted})
            return True
        except Exception as e:
            logger.error("Redis cleanup failed: %s", e)
            return False


class RedisStorageAdapter:
    """
    Redis-based storage for blockchain data.

    Same public interface as SQLiteAdapter but uses Redis key-value store.
    Designed as a drop-in replacement via DEFAULT_STORAGE_BACKEND setting.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        db: int | None = None,
    ) -> None:
        self._host = host or settings.REDIS_HOST
        self._port = port or settings.REDIS_PORT
        self._db = db or settings.REDIS_DB
        self._client: redis_mod.Redis | None = None

        # Initialize the helper managers
        self._chain_mgr = RedisChainManager(self)
        self._event_mgr = RedisEventManager(self)
        self._proof_mgr = RedisProofManager(self)
        self._stats_mgr = RedisStatsManager(self)

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = redis_mod.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
            )
        return self._client

    # --- Chain operations delegated ---

    def store_chain(self, chain: Blockchain) -> bool:
        return self._chain_mgr.store_chain(chain)

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        return self._chain_mgr.load_chain(chain_name)

    def get_entity_events(
        self, entity_id: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._event_mgr.get_entity_events(entity_id, chain_name)

    def get_events_by_type(
        self, event_type: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._event_mgr.get_events_by_type(event_type, chain_name)

    # --- Proof operations delegated ---

    def store_proof(
        self,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any],
    ) -> bool:
        return self._proof_mgr.store_proof(
            main_chain_name, sub_chain_name, proof_hash, block_index, metadata
        )

    def get_proof_history(self, sub_chain_name: str) -> list[dict[str, Any]]:
        return self._proof_mgr.get_proof_history(sub_chain_name)

    # --- Statistics & Cleanup delegated ---

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        return self._stats_mgr.get_chain_statistics(chain_name)

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        return self._stats_mgr.cleanup_old_data(days_to_keep)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except redis_mod.RedisError:
                pass
            self._client = None

    def __str__(self) -> str:
        return f"RedisStorageAdapter(host={self._host}, port={self._port}, db={self._db})"

    def __repr__(self) -> str:
        return str(self)
