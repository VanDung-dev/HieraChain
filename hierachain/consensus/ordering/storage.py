"""
Ordering storage handler for the HieraChain ordering service.
"""

import time
from collections import deque
from typing import Any
from hierachain.core.block import Block
from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.consensus.ordering.types import PendingEvent

class OrderingStorageHandler:
    """Manages persistent storage and caching for blocks and events"""
    def __init__(self, config: dict[str, Any]):
        self.storage = SqlStorageBackend(connection_string=config.get("db_url"))
        cache_size = config.get("block_cache_size", 100)
        self.block_history: deque[Block] = deque(maxlen=cache_size)
        self.last_block: Block | None = None
        self.processed_events: dict[str, PendingEvent] = {}

    def save_block(self, block: Block, chain_name: str | None):
        block_data = {
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "timestamp": block.timestamp,
            "events": block.to_event_list(),
            "metadata": {},
            "chain_name": chain_name
        }
        self.storage.save_block(block_data)
        self.block_history.append(block)
        self.last_block = block
        
        # Calculate block latency for metrics before clearing
        current_time = time.time()
        block_latency = sum(current_time - e.received_at for e in self.processed_events.values())
        event_count = len(self.processed_events)
        self.processed_events.clear()
        return event_count, block_latency

    def get_blocks(self, start_index: int) -> list[Block]:
        if start_index < 0: start_index = 0
        if self.block_history and start_index >= self.block_history[0].index:
            offset = start_index - self.block_history[0].index
            return list(self.block_history)[offset:]
        return self._load_from_db(start_index)

    def _load_from_db(self, start_index: int) -> list[Block]:
        blocks = []
        current_index = start_index
        while True:
            data = self.storage.get_block_by_index(current_index)
            if not data: break
            block = Block(index=data["index"], events=data["events"], previous_hash=data["previous_hash"])
            block.hash, block.timestamp = data["hash"], data["timestamp"]
            blocks.append(block)
            current_index += 1
        return blocks

    def close(self):
        self.storage.close()
