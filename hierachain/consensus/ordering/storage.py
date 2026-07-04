"""
Ordering storage handler for the HieraChain ordering service.
"""

import time
import logging
from collections import deque
from typing import Any
from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.consensus.ordering.types import PendingEvent


logger = logging.getLogger(__name__)


def _db_url_to_path(url: str | None) -> str:
    """Convert a sqlite:/// connection string to a plain file path.

    Falls back to 'hierachain.db' if no URL is provided.
    """
    if not url:
        return "hierachain.db"
    for prefix in ("sqlite:///", "sqlite://"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return url


def _verify_chain_links(blocks: list[Block]) -> None:
    """Verify that each block's previous_hash matches the preceding block's hash."""
    for i in range(1, len(blocks)):
        if blocks[i].previous_hash != blocks[i - 1].hash:
            raise ValueError(
                f"Chain link BROKEN at block={blocks[i].index} "
                f"previous_hash={blocks[i].previous_hash[:16]} "
                f"expected={blocks[i - 1].hash[:16]}"
            )


def _block_from_dict(data: dict[str, Any]) -> Block:
    """Create a Block from dictionary data with hash verification."""
    block = object.__new__(Block)
    block.index = data["index"]
    block.timestamp = data["timestamp"]
    block.previous_hash = data["previous_hash"]
    block.nonce = data.get("nonce", 0)
    block.creator_id = data.get("creator_id")
    block.signature = data.get("signature")
    block.merkle_root = data.get("merkle_root") or ""
    block._events = convert_events_to_arrow(data["events"])
    block._cached_events = None

    # Recompute hash and compare with stored hash.
    # Hash includes merkle_root, so verifying hash also protects event integrity.
    stored_hash = data["hash"]
    computed_hash = block.calculate_hash()
    if stored_hash != computed_hash:
        raise ValueError(
            f"Block hash MISMATCH! block={block.index} "
            f"stored={stored_hash[:16]} computed={computed_hash[:16]}"
        )
    block.hash = stored_hash
    return block


class OrderingStorageHandler:
    """Manages persistent storage and caching for blocks and events"""
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.storage = SQLiteAdapter(
            database_path=_db_url_to_path(config.get("db_url"))
        )
        cache_size = config.get("block_cache_size", 100)
        self.block_history: deque[Block] = deque(maxlen=cache_size)
        self.last_block: Block | None = None
        self.processed_events: dict[str, PendingEvent] = {}
        self.chain_name = config.get("chain_name")

    def save_block(self, block: Block, chain_name: str | None):
        block_data = {
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "timestamp": block.timestamp,
            "events": block.to_event_list(),
            "metadata": {"merkle_root": block.merkle_root},
            "merkle_root": block.merkle_root,
            "chain_name": chain_name
        }
        self.storage.save_block(block_data)
        self.block_history.append(block)
        self.last_block = block
        
        # Calculate block latency for metrics before clearing
        current_time = time.time()
        block_latency = sum(
            current_time - e.received_at for e in self.processed_events.values()
        )
        event_count = len(self.processed_events)
        self.processed_events.clear()
        return event_count, block_latency

    def get_blocks(self, start_index: int) -> list[Block]:
        if start_index < 0:
            start_index = 0
        if self.block_history and start_index >= self.block_history[0].index:
            offset = start_index - self.block_history[0].index
            return list(self.block_history)[offset:]
        return self._load_from_db(start_index)

    def _load_from_db(self, start_index: int) -> list[Block]:
        blocks = []
        current_index = start_index
        
        while True:
            # We need to know which chain we are loading blocks for
            data = self.storage.get_block_by_index(
                current_index, chain_name=self.chain_name
            )
            if not data:
                break
            # Create block directly to avoid recalculating hash
            blocks.append(_block_from_dict(data))
            current_index += 1

        # Verify chain integrity: every block's previous_hash must match
        # the preceding block's hash
        if len(blocks) > 1 and start_index == 0:
            _verify_chain_links(blocks)

        return blocks

    def get_blocks_from_db(self, start_index: int) -> list[Block]:
        """Always load from DB, bypassing in-memory cache.
        
        Used during rehydration to ensure we get the persisted state
        rather than any in-memory blocks that may have diverged.
        """
        if start_index < 0:
            start_index = 0
        return self._load_from_db(start_index)

    def get_latest_block_from_db(self) -> Block | None:
        """Retrieve the latest block for this chain from DB."""
        data = self.storage.get_latest_block(chain_name=self.chain_name)
        if not data:
            return None
        return _block_from_dict(data)

    def close(self) -> None:
        self.storage.close()
