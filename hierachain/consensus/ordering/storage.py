"""
Ordering storage handler for the HieraChain ordering service.
"""

import time
from collections import deque
from typing import Any
from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.consensus.ordering.types import PendingEvent


def _block_from_dict(data: dict[str, Any]) -> Block:
    """Create a Block from dictionary data without recalculating hash."""
    block = object.__new__(Block)
    block.index = data["index"]
    block.timestamp = data["timestamp"]
    block.previous_hash = data["previous_hash"]
    block.nonce = data.get("nonce", 0)
    block.creator_id = data.get("creator_id")
    block.signature = data.get("signature")
    block.hash = data["hash"]
    block.merkle_root = data.get("merkle_root") or ""
    block._events = convert_events_to_arrow(data["events"])
    return block


class OrderingStorageHandler:
    """Manages persistent storage and caching for blocks and events"""
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.storage = SqlStorageBackend(connection_string=config.get("db_url"))
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
