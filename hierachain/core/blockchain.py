"""
Base Blockchain implementation for HieraChain Framework.

This module implements the base Blockchain class that serves as the foundation
for both Main Chain and Sub-Chain implementations, following framework guidelines:
- Event-based model (not transactions)
- Multiple events per block
- Proper chain validation and integrity
"""

import time
from typing import Any, Optional, Callable

from hierachain.core.block import Block


class Blockchain:
    """
    Base blockchain class for the hierarchical framework.
    
    This class provides the fundamental blockchain operations and will be
    extended by MainChain and SubChain classes. It follows the framework
    guidelines by using events (not transactions) and supporting multiple
    events per block.
    """
    
    def __init__(self, name: str = "Blockchain"):
        """
        Initialize a new blockchain.
        
        Args:
            name: Name identifier for this blockchain
        """
        self.name = name
        self.chain: list[Block] = []
        self.pending_events: list[dict[str, Any]] = []
        self.create_genesis_block()
    
    def create_genesis_block(self) -> None:
        """Create the genesis (first) block of the blockchain."""
        genesis_events = [{
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
        
        self.chain.append(genesis_block)
    
    def get_latest_block(self) -> Block:
        """
        Get the latest block in the chain.
        
        Returns:
            The most recent block in the blockchain
        """
        return self.chain[-1]
    
    def add_event(self, event: dict[str, Any]) -> None:
        """
        Add an event to the pending events list.
        
        Args:
            event: Event dictionary with required metadata
        """
        # Validate event structure
        if not isinstance(event, dict):
            raise ValueError("Event must be a dictionary")
        
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = time.time()
        
        self.pending_events.append(event)
    
    def create_block(self, events: Optional[list[dict[str, Any]]] = None) -> Block:
        """
        Create a new block with the given events or pending events.
        
        Args:
            events: List of events to include in the block (optional)
            
        Returns:
            The newly created block
        """
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
        if self.is_valid_new_block(block):
            self.chain.append(block)
            return True
        return False
    
    def finalize_block(self) -> Optional[Block]:
        """
        Finalize pending events into a new block and add it to the chain.
        
        Returns:
            The newly created and added block, or None if no pending events
        """
        if not self.pending_events:
            return None
        
        new_block = self.create_block()
        if self.add_block(new_block):
            return new_block
        return None
    
    def is_valid_new_block(self, block: Block) -> bool:
        """
        Validate a new block before adding it to the chain.
        
        Args:
            block: Block to validate
            
        Returns:
            True if block is valid, False otherwise
        """
        latest_block = self.get_latest_block()
        
        # Check block index
        if block.index != latest_block.index + 1:
            return False
        
        # Check previous hash
        if block.previous_hash != latest_block.hash:
            return False
        
        # Check block structure
        if not block.validate_structure():
            return False
        
        # Verify hash calculation
        if block.hash != block.calculate_hash():
            return False
        
        return True
    
    def is_chain_valid(self) -> bool:
        """
        Validate the entire blockchain.
        
        Returns:
            True if the entire chain is valid, False otherwise
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Check if current block is valid
            if not current_block.validate_structure():
                return False
            
            # Check if hash is correct
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if previous hash matches
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Check block index
            if current_block.index != previous_block.index + 1:
                return False
        
        return True
    
    def get_events_by_entity(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get all events for a specific entity across the entire chain.
        
        Args:
            entity_id: The entity identifier to search for
            
        Returns:
            List of events for the specified entity
        """
        events = []
        for block in self.chain:
            events.extend(block.get_events_by_entity(entity_id))
        return events
    
    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """
        Get all events of a specific type across the entire chain.
        
        Args:
            event_type: The event type to search for
            
        Returns:
            List of events of the specified type
        """
        events = []
        for block in self.chain:
            events.extend(block.get_events_by_type(event_type))
        return events
    
    def get_events_by_filter(self, filter_func: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        """
        Get all events that match a custom filter function.
        
        Args:
            filter_func: Function that takes an event and returns True if it matches
            
        Returns:
            List of events that match the filter
        """
        events = []
        for block in self.chain:
            block_events = block.to_dict()['events']
            for event in block_events:
                if filter_func(event):
                    events.append(event)
        return events
    
    def get_chain_stats(self) -> dict[str, Any]:
        """
        Get statistics about the blockchain.
        
        Returns:
            Dictionary containing chain statistics
        """
        total_events = sum(len(block.events) for block in self.chain)
        
        return {
            "name": self.name,
            "total_blocks": len(self.chain),
            "total_events": total_events,
            "pending_events": len(self.pending_events),
            "latest_block_hash": self.get_latest_block().hash,
            "chain_valid": self.is_chain_valid()
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
        
        return blockchain
    
    def __str__(self) -> str:
        """String representation of the blockchain."""
        return f"Blockchain(name={self.name}, blocks={len(self.chain)}, pending={len(self.pending_events)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the blockchain."""
        return (f"Blockchain(name={self.name}, blocks={len(self.chain)}, "
                f"pending_events={len(self.pending_events)}, valid={self.is_chain_valid()})")