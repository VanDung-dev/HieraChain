"""
Base Blockchain implementation for HieraChain Ledger.

This module implements the base Blockchain class that serves as the foundation
for both Main Chain and Sub-Chain implementations, following Ledger guidelines:
- Event-based model (not transactions)
- Multiple events per block
- Proper chain validation and integrity
"""

import time
import logging
import threading
from typing import Any, Callable, cast

from hierachain.core.block import Block
from hierachain.core.deadlock_detector import DeadlockDetector, get_deadlock_detector
from hierachain.security.verify.block_verifier import get_block_verifier

logger = logging.getLogger(__name__)


def _is_block_linked_correctly(current: Block, previous: Block) -> bool:
    """Check if current block is correctly linked to the previous block."""
    if not current.validate_structure():
        return False
    if current.hash != current.calculate_hash():
        return False
    if current.previous_hash != previous.hash:
        return False
    if current.index != previous.index + 1:
        return False
    return True


class Blockchain:
    """
    Base blockchain class for the hierarchical Ledger.

    This class provides the fundamental blockchain operations and will be
    extended by MainChain and SubChain classes. It follows the Ledger
    guidelines by using events (not transactions) and supporting multiple
    events per block.
    """

    def __init__(self, name: str = "Blockchain") -> None:
        """
        Initialize a new blockchain.
        
        Args:
            name: Name identifier for this blockchain
        """
        self.name = name
        self.lock = threading.RLock()
        self._lock_id = id(self.lock)
        self._deadlock_detector = get_deadlock_detector()
        self.chain: list[Block] = []
        self.pending_events: list[dict[str, Any]] = []
        self.total_events: int = 0
        self.event_type_counts: dict[str, int] = {}
        self.entity_event_index: dict[str, list[dict[str, Any]]] = {}
        with self.lock:
            self.create_genesis_block()
    
    def safe_lock(self, timeout: float = 5.0) -> bool:
        """
        Acquire lock with deadlock detection (Issue 14).
        
        Args:
            timeout: Maximum time to wait for lock
            
        Returns:
            True if lock acquired, False if timeout
        """
        wait_start = self._deadlock_detector.record_wait_start(self._lock_id)
        try:
            result = self.lock.acquire(blocking=True, timeout=timeout)
            wait_time = time.time() - wait_start
            self._deadlock_detector.record_wait_end(self._lock_id, wait_time)
            return result
        except RuntimeError:
            # Lock acquire failed due to runtime error
            logger.error("Lock acquisition failed with RuntimeError for %s", self.name)
            return False
    
    def safe_unlock(self):
        """Release lock safely."""
        try:
            self.lock.release()
        except RuntimeError:
            pass  # Lock not held
    
    def create_genesis_block(self) -> None:
        """Create the genesis (first) block of the blockchain."""
        genesis_events = [{
            "entity_id": "SYSTEM",
            "event": "genesis",
            "timestamp": time.time(),
            "details": {
                "chain_name": self.name,
                "created_at": time.time()
            }
        }]
        
        genesis_block = Block(
            index=0,
            events=genesis_events,
            timestamp=time.time(),
            previous_hash="0"
        )
        
        self._index_block_events(genesis_block)
        self.chain.append(genesis_block)

    def _index_block_events(self, block: Block) -> None:
        """Update counters and indexing for all events in the given block."""
        with self.lock:
            events = (
                block.to_event_list()
                if hasattr(block, "to_event_list")
                else block.events
            )
            self.total_events += len(events)
            for event in events:
                etype = event.get("event", "unknown")
                self.event_type_counts[etype] = self.event_type_counts.get(etype, 0) + 1

                # Update entity index
                entity_id = event.get("entity_id")
                if entity_id:
                    safe_id = cast(str, entity_id)
                    if safe_id not in self.entity_event_index:
                        self.entity_event_index[safe_id] = []
                    self.entity_event_index[safe_id].append({
                        "block_index": block.index,
                        "event": event,
                        "timestamp": event.get("timestamp", time.time())
                    })

    def _rebuild_event_indexes(self) -> None:
        """Rebuild total_events, event_type_counts, and entity_event_index
        from scratch based on the current chain."""
        with self.lock:
            self.total_events = 0
            self.event_type_counts.clear()
            self.entity_event_index.clear()
            for block in self.chain:
                self._index_block_events(block)

    def get_latest_block(self) -> Block:
        """
        Get the latest block in the chain.
        
        Returns:
            The most recent block in the blockchain
        """
        with self.lock:
            return self.chain[-1]
    
    def add_event(self, event: dict[str, Any]) -> None:
        """
        Add an event to the pending events list.
        
        Args:
            event: Event dictionary with required metadata
        """
        with self.lock:
            # Validate event structure
            if not isinstance(event, dict):
                raise ValueError("Event must be a dictionary")
            
            # Add timestamp if not present
            if "timestamp" not in event:
                event["timestamp"] = time.time()
            
            self.pending_events.append(event)
    
    def create_block(self, events: list[dict[str, Any]] | None = None) -> Block:
        """
        Create a new block with the given events or pending events.
        
        Args:
            events: List of events to include in the block (optional)
            
        Returns:
            The newly created block
        """
        with self.lock:
            if events is None:
                events = self.pending_events.copy()
                self.pending_events.clear()
            
            if not events:
                raise ValueError("Cannot create block without events")
            
            latest_block = self.get_latest_block()
            new_block = Block(
                index=latest_block.index + 1,
                events=events,
                timestamp=time.time(),
                previous_hash=latest_block.hash
            )
            
            return new_block
    
    def add_block(self, block: Block) -> bool:
        """
        Add a block to the blockchain after validation.
        
        Args:
            block: Block to add to the chain
            
        Returns:
            True if block was added successfully, False otherwise
        """
        with self.lock:
            if self.is_valid_new_block(block):
                self._index_block_events(block)
                self.chain.append(block)
                return True
            return False
    
    def finalize_block(self) -> Block | None:
        """
        Finalize pending events into a new block and add it to the chain.
        
        Returns:
            The newly created and added block, or None if no pending events
        """
        with self.lock:
            if not self.pending_events:
                return None
            
            new_block = self.create_block()
            if self.add_block(new_block):
                return new_block
            return None
    
    def is_valid_new_block(self, block: Block) -> bool:
        """
        Validate a new block before adding it to the chain.
        
        Uses BlockVerifier for comprehensive validation including:
        - Block hash verification
        - Merkle root verification
        - Chain link verification
        - Block signature verification (if present)
        
        Args:
            block: Block to validate
            
        Returns:
            True if block is valid, False otherwise
        """
        latest_block = self.get_latest_block()
        
        # Use BlockVerifier for comprehensive validation
        verifier = get_block_verifier(strict_mode=False)
        result = verifier.verify_block(block, latest_block)
        
        if not result.is_valid:
            logger.warning(
                "Block %s validation failed: %s", block.index, result.message
            )
            if result.details:
                logger.debug("Validation details: %s", result.details)
            return False
        
        # Additional structure validation
        if hasattr(block, 'validate_structure') and not block.validate_structure():
            logger.warning("Block %d structure validation failed", block.index)
            return False
        
        logger.debug("Block %d validated successfully", block.index)
        return True
    
    def is_chain_valid(self) -> bool:
        """
        Validate the entire blockchain.

        Returns:
            True if the entire chain is valid, False otherwise
        """
        with self.lock:
            return all(
                _is_block_linked_correctly(self.chain[i], self.chain[i - 1])
                for i in range(1, len(self.chain))
            )
    
    def get_events_by_entity(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get all events for a specific entity across the entire chain.
        
        Args:
            entity_id: The entity identifier to search for
            
        Returns:
            List of events for the specified entity
        """
        # Use pre-calculated entity index for O(1) access
        with self.lock:
            if (
                hasattr(self, 'entity_event_index')
                and entity_id in self.entity_event_index
            ):
                indexed_events = self.entity_event_index[entity_id]
                # Format to match original output (list of events only)
                return [e['event'] for e in indexed_events]
                
            events = []
            for block in self.chain:
                events.extend(block.get_events_by_entity(entity_id))
            return events

    def get_indexed_entity_events(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get indexed events with block metadata for a specific entity.
        
        Args:
            entity_id: The entity identifier to search for
            
        Returns:
            List of dictionaries containing block_index, event, and timestamp
        """
        with self.lock:
            if hasattr(self, 'entity_event_index'):
                return self.entity_event_index.get(entity_id, [])
            return []
    
    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """
        Get all events of a specific type across the entire chain.
        
        Args:
            event_type: The event type to search for
            
        Returns:
            List of events of the specified type
        """
        with self.lock:
            events = []
            for block in self.chain:
                events.extend(block.get_events_by_type(event_type))
            return events

    def get_events_by_filter(
        self, filter_func: Callable[[dict[str, Any]], bool]
    ) -> list[dict[str, Any]]:
        """
        Get all events that match a custom filter function.
        
        Args:
            filter_func: Function that takes an event and returns True if it matches
            
        Returns:
            List of events that match the filter
        """
        events = []
        for block in self.chain:
            for event in block.to_event_list():
                if filter_func(event):
                    events.append(event)
        return events
    
    def get_chain_stats(self) -> dict[str, Any]:
        """
        Get statistics about the blockchain.
        
        Returns:
            Dictionary containing chain statistics
        """
        return {
            "name": self.name,
            "total_blocks": len(self.chain),
            "total_events": self.total_events,
            "pending_events": len(self.pending_events),
            "latest_block_hash": self.get_latest_block().hash,
            "chain_valid": self.is_chain_valid(),
            "event_types": self.event_type_counts.copy()
        }
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert blockchain to dictionary representation.
        
        Returns:
            Dictionary representation of the blockchain
        """
        return {
            "name": self.name,
            "chain": [block.to_dict() for block in self.chain],
            "pending_events": self.pending_events
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Blockchain':
        """
        Create a Blockchain instance from dictionary data.
        
        Args:
            data: Dictionary containing blockchain data
            
        Returns:
            Blockchain instance
        """
        blockchain = cls(name=data["name"])
        
        # Clear genesis block and rebuild from data
        blockchain.chain.clear()
        
        for block_data in data["chain"]:
            block = Block.from_dict(block_data)
            blockchain.chain.append(block)
        
        blockchain.pending_events = data.get("pending_events", [])
        blockchain._rebuild_event_indexes()

        # Validate chain integrity after loading
        if not blockchain.is_chain_valid():
            logger.error(
                "Chain integrity check FAILED after loading '%s' from dictionary!",
                data["name"]
            )

        return blockchain
    
    def __str__(self) -> str:
        """String representation of the blockchain."""
        return (
            f"Blockchain(name={self.name}, "
            f"blocks={len(self.chain)}, "
            f"pending={len(self.pending_events)})"
        )
    
    def __repr__(self) -> str:
        """Detailed string representation of the blockchain."""
        return (
            f"Blockchain(name={self.name}, blocks={len(self.chain)}, "
            f"pending_events={len(self.pending_events)}, valid={self.is_chain_valid()})"
        )
