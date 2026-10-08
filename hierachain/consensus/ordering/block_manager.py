"""
Block builder for the HieraChain ordering service.
"""

import asyncio
import logging
import time
from typing import Any

from hierachain.consensus.ordering.types import OrderingPausedError, OrderingStatus
from hierachain.core.block import Block
from hierachain.core.merkle_tree import (
    MerkleTree,
    compute_leaves_from_events_standalone,
)
from hierachain.security.verify.block_verifier import sign_block

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
        
        # Serialize persistence with lockdown and status transitions.
        self._block_index_lock = service._commit_lock

    async def create_block_async(self, events: list[dict[str, Any]]) -> None:
        """Create a block asynchronously by offloading Merkle tree calculation."""
        if not events:
            return

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
        while not self.service.should_stop.is_set():
            try:
                self.commit_block(block)
            except OrderingPausedError:
                # Keep the cut batch intact while maintenance freezes commits.
                await asyncio.sleep(0.05)
            else:
                return
        raise RuntimeError("Ordering service is stopping")

    def _require_commit_allowed(self) -> None:
        if self.service.status == OrderingStatus.LOCKDOWN:
            raise OrderingPausedError("Ordering service is in lockdown")
        if self.service.should_stop.is_set() or self.service.status in (
            OrderingStatus.SHUTDOWN, OrderingStatus.ERROR,
        ):
            raise RuntimeError("Ordering service is stopping or unavailable")

    def commit_block(self, block: Block) -> None:
        """Commit a completed block to the commit queue and persistent storage"""
        
        # Use lock to ensure thread-safe block index assignment
        with self._block_index_lock:
            self._require_commit_allowed()
            try:
                previous_block = self.storage_handler.last_block
                block.index = self.service.blocks_created
                block.previous_hash = previous_block.hash if previous_block else "0"
                block.creator_id = self.service.node_identity.node_id
                block.hash = block.calculate_hash()
                finalizer = getattr(self.service, "block_finalizer", None)
                if finalizer is not None:
                    block = finalizer(block, previous_block)
                self._require_commit_allowed()
                sign_block(
                    block,
                    self.service.node_identity.node_id,
                    self.service.node_identity.signing_keypair,
                )
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
                bootstrap = getattr(self.service, "_bootstrap_blocks", None)
                if bootstrap is not None:
                    bootstrap.append(block)
                self.commit_queue.put(block)
                logger.info("Block #%d committed with %d events", block.index, event_count)
            except Exception as e:
                logger.error("Failed to commit block #%d: %s", block.index, e)
                if self.service.status not in (
                    OrderingStatus.LOCKDOWN, OrderingStatus.SHUTDOWN, OrderingStatus.ERROR,
                ):
                    self.service.status = OrderingStatus.MAINTENANCE
                raise

    async def check_timeout_block_creation(self, force: bool = False) -> None:
        """Check if block needs to be created due to timeout or forced"""
        if force or self.is_block_timeout():
            raw_block_data = self.block_builder.force_create_block()
            if raw_block_data:
                await self.create_block_async(raw_block_data)

    def is_block_timeout(self) -> bool:
        """Check if block timeout occurred in block builder"""
        return self.block_builder.is_batch_ready()
