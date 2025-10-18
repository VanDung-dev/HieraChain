"""
Ordering Service for Hierarchical Blockchain Framework

This service implements a decoupled event ordering mechanism designed for the
hierarchical blockchain architecture. It provides event certification, ordering,
and block creation capabilities that align with the enterprise-focused design
principles.
"""

import time
from queue import Queue
from typing import List, Dict, Any
from core.block import Block


class EventCertifier:
    """Certifies and validates events before they enter the ordering pool"""
    
    @staticmethod
    def validate(event: Dict[str, Any]) -> bool:
        """
        Validate an event
        
        Args:
            event: The event to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Check if event has required fields
        required_fields = ['entity_id', 'event', 'timestamp']
        for field in required_fields:
            if field not in event:
                return False
        
        # Check timestamp is not in the future
        if event['timestamp'] > time.time() + 60:  # Allow 1 minute tolerance
            return False
            
        return True


class BlockBuilder:
    """Builds blocks from ordered events"""
    
    def __init__(self, block_size: int = 500):
        """
        Initialize BlockBuilder
        
        Args:
            block_size: Maximum number of events per block
        """
        self.block_size = block_size
    
    @staticmethod
    def create_block(events: List[Dict[str, Any]], index: int = 0,
                     previous_hash: str = "0") -> Block:
        """
        Create a new block from events
        
        Args:
            events: List of events
            index: Block index
            previous_hash: Previous block hash
            
        Returns:
            Block: New block containing the events
        """
        # Create block with events
        block = Block(
            index=index,
            events=events,
            timestamp=time.time(),
            previous_hash=previous_hash
        )
        
        return block


class OrderingService:
    """Decoupled event ordering service for improved scalability"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize OrderingService
        
        Args:
            config: Service configuration parameters
        """
        self.config = config or {
            "block_size": 500,
            "batch_size": 100
        }
        self.event_pool: List[Dict[str, Any]] = []
        self.block_builder = BlockBuilder(self.config.get("block_size", 500))
        self.commit_queue = Queue()
        self.certifier = EventCertifier()
        self.block_index = 0
        self.last_block_hash = "0"
    
    def receive_event(self, event: Dict[str, Any]):
        """
        Receive event from client or application channel
        
        Args:
            event: Event to order
        """
        if self.certifier.validate(event):
            self.event_pool.append(event)
            self._attempt_block_creation()
    
    def _attempt_block_creation(self):
        """Create blocks when threshold is reached"""
        batch_size = self.config.get("batch_size", 100)
        if len(self.event_pool) >= batch_size:
            # Take a batch of events
            batch = self.event_pool[:batch_size]
            
            # Create block from batch
            block = self.block_builder.create_block(
                batch,
                index=self.block_index,
                previous_hash=self.last_block_hash
            )
            
            # Update state
            self.block_index += 1
            self.last_block_hash = block.hash
            
            # Add to commit queue
            self.commit_queue.put(block)
            
            # Remove processed events
            self.event_pool = self.event_pool[batch_size:]
    
    def get_next_block(self) -> Block | None:
        """
        Get the next block from the commit queue if available
        
        Returns:
            Block: Next block to commit, or None if queue is empty
        """
        if not self.commit_queue.empty():
            return self.commit_queue.get()
        return None
    
    def pool_size(self) -> int:
        """
        Get current size of event pool

        Returns:
            int: Number of events in pool
        """
        return len(self.event_pool)