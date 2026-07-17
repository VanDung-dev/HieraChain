"""
Block builder for the HieraChain ordering service.
"""

import time
import logging
import threading
import asyncio
from typing import Any

from hierachain.core.block import Block
from hierachain.core.merkle_tree import compute_leaves_from_events_standalone, MerkleTree
from hierachain.consensus.ordering.types import OrderingStatus

logger = logging.getLogger(__name__)


class OrderingBlockManager:
    """Manages block creation, hashing, and committing to storage"""
    def __init__(self, service):
        self.service = service
        self.storage_handler = service.storage_handler
        self.block_builder = service.block_builder
        self.metrics = service.metrics
        self.journal = service.journal
        self.commit_queue = service.commit_queue
        self.config = service.config
        
        # Lock for thread-safe block index assignment
        self._block_index_lock = threading.Lock()

    async def create_block_async(self, events: list[dict[str, Any]]) -> None:
        """Create a block asynchronously by offloading Merkle tree calculation."""
        if not events:
            return

        try:
            merkle_leaves = await asyncio.to_thread(
                compute_leaves_from_events_standalone, events
            )
            merkle_tree = MerkleTree(leaves=merkle_leaves)
            
            block = Block(
                index=0,
                events=events,
                previous_hash="",
                merkle_root=merkle_tree.root
            )
            self.commit_block(block)
        except Exception as e:
            logger.error("Error creating block asynchronously: %s", e)

    def commit_block(self, block: Block) -> None:
        """Commit a completed block to the commit queue and persistent storage"""
        
        # Use lock to ensure thread-safe block index assignment
        with self._block_index_lock:
            block.index = self.service.blocks_created
            block.previous_hash = (
                self.storage_handler.last_block.hash
                if self.storage_handler.last_block else "0"
            )
            block.hash = block.calculate_hash()

            try:
                chain_name = self.config.get("chain_name")
                event_count, block_latency = self.storage_handler.save_block(
                    block, chain_name
                )
                self.metrics.record_block_created(event_count, block_latency)
                
                if self.service.status == OrderingStatus.ACTIVE:
                    system_event = {
                        "event": "$SYSTEM_BLOCK_CUT",
                        "entity_id": "SYSTEM",
                        "timestamp": time.time(),
                        "details": {"block_index": block.index, "block_hash": block.hash}
                    }
                    self.journal.log_event(system_event)

                self.service.blocks_created += 1
                self.commit_queue.put(block)
                logger.info("Block #%d committed with %d events", block.index, event_count)
            except Exception as e:
                logger.error("Failed to commit block #%d: %s", block.index, e)
                self.service.status = OrderingStatus.MAINTENANCE

    async def check_timeout_block_creation(self, force: bool = False) -> None:
        """Check if block needs to be created due to timeout or forced"""
        if force or self.is_block_timeout():
            raw_block_data = self.block_builder.force_create_block()
            if raw_block_data:
                await self.create_block_async(raw_block_data)

    def is_block_timeout(self) -> bool:
        """Check if block timeout occurred in block builder"""
        return self.block_builder.is_batch_ready()
