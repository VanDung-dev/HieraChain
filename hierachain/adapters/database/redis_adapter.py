"""
Redis Storage Adapter for HieraChain Ledger.

Provides Redis persistence for blockchain data with the same public interface
as SQLBase adapters. Supports store/load chains, blocks, events, and proofs.
"""

import json
import time
import logging
from typing import Any

from hierachain.core.blockchain import Blockchain
from hierachain.config.settings import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "hierachain"


def _k(*parts: str) -> str:
    """Build a colon-delimited Redis key."""
    return f"{_KEY_PREFIX}:{':'.join(parts)}"


def _now() -> float:
    return time.time()


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
        import redis as redis_mod

        self._host = host or settings.REDIS_HOST
        self._port = port or settings.REDIS_PORT
        self._db = db or settings.REDIS_DB
        self._client: redis_mod.Redis | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            import redis as redis_mod
            self._client = redis_mod.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
            )
        return self._client

    # --- Chain operations ---

    def store_chain(self, chain: Blockchain) -> bool:
        try:
            chain_type = "main" if "MainChain" in str(type(chain)) else "sub"
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
        except Exception as e:
            logger.error("Redis store_chain failed: %s", e)
            return False

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        try:
            data = self.client.hgetall(_k("chain", chain_name))
            if not data:
                return None
            blocks = self._load_blocks(chain_name)
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

    def _load_blocks(self, chain_name: str) -> list[dict[str, Any]]:
        block_hashes = self.client.lrange(_k("chain", chain_name, "blocks"), 0, -1)
        blocks = []
        for bh in block_hashes:
            raw = self.client.get(_k("block", bh))
            if raw:
                block_dict = json.loads(raw)
                events = self._load_block_events(bh)
                block_dict["events"] = events
                blocks.append(block_dict)
        return blocks

    def _load_block_events(self, block_hash: str) -> list[dict[str, Any]]:
        raw = self.client.get(_k("block", block_hash, "events"))
        if raw:
            return json.loads(raw)
        return []

    # --- Event queries ---

    def get_entity_events(
        self, entity_id: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            pattern = _k("event", "entity", entity_id) + ":*"
            keys = self.client.keys(pattern)
            results = []
            for key in keys:
                raw = self.client.get(key)
                if raw:
                    ev = json.loads(raw)
                    if chain_name and ev.get("chain_name") != chain_name:
                        continue
                    results.append(ev)
            results.sort(key=lambda e: e.get("timestamp", 0))
            return results
        except Exception as e:
            logger.error("Redis get_entity_events failed: %s", e)
            return []

    def get_events_by_type(
        self, event_type: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            pattern = _k("event", "type", event_type) + ":*"
            keys = self.client.keys(pattern)
            results = []
            for key in keys:
                raw = self.client.get(key)
                if raw:
                    ev = json.loads(raw)
                    if chain_name and ev.get("chain_name") != chain_name:
                        continue
                    results.append(ev)
            results.sort(key=lambda e: e.get("timestamp", 0))
            return results
        except Exception as e:
            logger.error("Redis get_events_by_type failed: %s", e)
            return []

    # --- Proof operations ---

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
                "metadata": json.dumps(metadata),
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
                        "metadata": json.loads(data.get("metadata", "{}")),
                        "submitted_at": float(data.get("submitted_at", 0)),
                    })
            return proofs
        except Exception as e:
            logger.error("Redis get_proof_history failed: %s", e)
            return []

    # --- Statistics ---

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        try:
            chain_data = self.client.hgetall(_k("chain", chain_name))
            if not chain_data:
                return {}
            block_hashes = self.client.llen(_k("chain", chain_name, "blocks"))
            # Count events across all blocks
            total_events = 0
            unique_entities: set[str] = set()
            event_types: dict[str, int] = {}
            for bh in self.client.lrange(_k("chain", chain_name, "blocks"), 0, -1):
                raw = self.client.get(_k("block", bh, "events"))
                if raw:
                    events = json.loads(raw)
                    total_events += len(events)
                    for ev in events:
                        eid = ev.get("entity_id")
                        if eid:
                            unique_entities.add(eid)
                        etype = ev.get("event", "unknown")
                        event_types[etype] = event_types.get(etype, 0) + 1
            return {
                "chain_name": chain_name,
                "chain_type": chain_data.get("chain_type"),
                "domain_type": chain_data.get("domain_type"),
                "total_blocks": block_hashes,
                "total_events": total_events,
                "unique_entities": len(unique_entities),
                "event_types": event_types,
                "created_at": chain_data.get("created_at"),
                "updated_at": chain_data.get("updated_at"),
            }
        except Exception as e:
            logger.error("Redis get_chain_statistics failed: %s", e)
            return {}

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        try:
            cutoff = _now() - (days_to_keep * 86400)
            deleted = 0
            for key in self.client.scan_iter(match=_k("event", "*")):
                raw = self.client.get(key)
                if raw:
                    try:
                        ev = json.loads(raw)
                        if ev.get("timestamp", 0) < cutoff:
                            self.client.delete(key)
                            deleted += 1
                    except (json.JSONDecodeError, TypeError):
                        pass

            for key in self.client.scan_iter(match=_k("proof", "*")):
                ts = self.client.hget(key, "submitted_at")
                if ts and float(ts) < cutoff:
                    self.client.delete(key)
                    deleted += 1

            for key in self.client.scan_iter(match=_k("block", "*")):
                raw = self.client.get(key)
                if raw:
                    try:
                        bd = json.loads(raw)
                        if bd.get("timestamp", 0) < cutoff:
                            self.client.delete(key)
                            deleted += 1
                    except (json.JSONDecodeError, TypeError):
                        pass

            logger.info("Redis cleanup completed", extra={"deleted": deleted})
            return True
        except Exception as e:
            logger.error("Redis cleanup failed: %s", e)
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __str__(self) -> str:
        return f"RedisStorageAdapter(host={self._host}, port={self._port}, db={self._db})"

    def __repr__(self) -> str:
        return str(self)
