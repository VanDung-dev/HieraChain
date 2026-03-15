"""
Block builder for the HieraChain ordering service.
"""

import time
from typing import Any
from hierachain.consensus.ordering.types import PendingEvent

class BlockBuilder:
    """Builds blocks from ordered events"""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.block_size = config.get("block_size", 100)
        self.batch_timeout = config.get("batch_timeout", 0.5)
        self.current_batch: list[PendingEvent] = []
        self.current_batch_ids: set[str] = set()
        self.batch_start_time = time.time()

    def add_event(self, event: PendingEvent) -> list[dict[str, Any]] | None:
        """Add event to current batch."""
        if event.event_id in self.current_batch_ids:
            return None

        if not self.current_batch:
            self.batch_start_time = time.time()

        self.current_batch.append(event)
        self.current_batch_ids.add(event.event_id)

        if self.is_batch_ready():
            return self._finalize_batch()
        
        return None

    def force_create_block(self) -> list[dict[str, Any]] | None:
        """Force creation of block from current batch"""
        return self._finalize_batch()
    
    def is_batch_ready(self) -> bool:
        """Check if current batch is ready for block creation"""
        if len(self.current_batch) >= self.block_size:
            return True
        if (time.time() - self.batch_start_time) >= self.batch_timeout:
            return True
        return False

    def _finalize_batch(self) -> list[dict[str, Any]] | None:
        """Return current batch event data and reset"""
        if not self.current_batch:
            return None
        events_list = [pending.event_data for pending in self.current_batch]
        self.current_batch.clear()
        self.current_batch_ids.clear()
        self.batch_start_time = time.time()
        return events_list
