"""
Base Blockchain implementation for HieraChain Ledger.

This module implements the base Blockchain class that serves as the foundation
for both Main Chain and Sub-Chain implementations, following Ledger guidelines:
- Event-based model (not transactions)
- Multiple events per block
- Proper chain validation and integrity
"""

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from copy import deepcopy
from typing import Any, cast

from hierachain.core.block import Block
from hierachain.core.utils import validate_event_structure
from hierachain.security.identity_loader import NodeIdentity, require_block_identity
from hierachain.security.verify.block_verifier import get_block_verifier, sign_block
from hierachain.serialization import dumps_canonical_json

logger = logging.getLogger(__name__)


class Blockchain:
    """
    Base blockchain class for the hierarchical Ledger.

    This class provides the fundamental blockchain operations and will be
    extended by MainChain and SubChain classes. It follows the Ledger
    guidelines by using events (not transactions) and supporting multiple
    events per block.
    """
    __slots__ = (
        'chain',
        'entity_event_index',
        'event_type_counts',
        'event_type_index',
        'lock',
        'name',
        'node_identity',
        'pending_events',
        'query_engine',
        'total_events',
        'trusted_public_keys',
    )

    def __init__(
        self,
        name: str = "Blockchain",
        node_identity: NodeIdentity | None = None,
        trusted_public_keys: dict[str, bytes] | None = None,
    ) -> None:
        self.node_identity, self.trusted_public_keys = require_block_identity(
            node_identity, trusted_public_keys
        )
        self.name = name
        self.lock = threading.RLock()
        self.chain: list[Block] = []
        self.pending_events: list[dict[str, Any]] = []
        self.total_events: int = 0
        self.event_type_counts: dict[str, int] = {}
        self.event_type_index: dict[str, list[int]] = {}
        self.entity_event_index: dict[str, list[dict[str, Any]]] = {}
        self.query_engine = BlockchainQueryEngine(self)
        with self.lock:
            self.create_genesis_block()

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
        self._sign_block(genesis_block)
        
        self._index_block_events(genesis_block)
        self.chain.append(genesis_block)

    def _sign_block(self, block: Block) -> None:
        """Sign a block created by this chain with its fixed node identity."""
        sign_block(
            block, self.node_identity.node_id, self.node_identity.signing_keypair
        )

    def _index_block_events(self, block: Block) -> None:
        """Update counters and indexing for all events in the given block."""
        with self.lock:
            events = (
                block.to_event_list()
                if hasattr(block, "to_event_list")
                else block.events
            )
            self.total_events += len(events)
            seen_types: set[str] = set()
            for event in events:
                etype = event.get("event", "unknown")
                self.event_type_counts[etype] = self.event_type_counts.get(etype, 0) + 1
                if etype not in seen_types:
                    seen_types.add(etype)
                    if etype not in self.event_type_index:
                        self.event_type_index[etype] = []
                    self.event_type_index[etype].append(block.index)

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
            self.event_type_index.clear()
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
    
    def add_event(self, event: dict[str, Any]) -> str:
        """
        Add an event to the pending events list.
        
        Args:
            event: Event dictionary with required metadata

        Returns:
            The event identifier string
        """
        with self.lock:
            # Validate event structure
            if not isinstance(event, dict):
                raise ValueError("Event must be a dictionary")
            
            event = deepcopy(event)

            # Add timestamp if not present
            if "timestamp" not in event:
                event["timestamp"] = time.time()

            if not validate_event_structure(event):
                raise ValueError("Invalid event structure")
            
            self.pending_events.append(event)
            event_id = event.get("event_id")
            if not event_id:
                try:
                    event_bytes = dumps_canonical_json(event)
                except (TypeError, ValueError):
                    event_bytes = str(sorted(event.items())).encode()
                event_id = f"evt-{hashlib.sha256(event_bytes).hexdigest()[:16]}"
            return event_id
    
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
            self._sign_block(new_block)
            
            return new_block
    
    def add_block(
        self, block: Block, public_key: bytes | None = None
    ) -> bool:
        """
        Add a block to the blockchain after validation.
        
        Args:
            block: Block to add to the chain
            public_key: Optional PEM key; must match the configured trusted key.
            
        Returns:
            True if block was added successfully, False otherwise
        """
        with self.lock:
            if self.is_valid_new_block(block, public_key=public_key):
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
            
            events = self.pending_events.copy()
            new_block = self.create_block(events)
            if self.add_block(new_block):
                self.pending_events = self.pending_events[len(events):]
                return new_block
            return None
    
    def is_valid_new_block(
        self, block: Block, public_key: bytes | None = None
    ) -> bool:
        """
        Validate a new block before adding it to the chain.
        
        Uses BlockVerifier for comprehensive validation including:
        - Block hash verification
        - Merkle root verification
        - Chain link verification
        - Required block signature verification
        
        Args:
            block: Block to validate
            public_key: Optional PEM key; must match the configured trusted key.
            
        Returns:
            True if block is valid, False otherwise
        """
        latest_block = self.get_latest_block()
        
        # Use BlockVerifier for comprehensive validation
        verifier = get_block_verifier()
        trusted_key = self.trusted_public_keys.get(block.creator_id)
        if public_key is not None and public_key != trusted_key:
            logger.warning("Block %s supplied an untrusted creator key", block.index)
            return False
        result = verifier.verify_block(
            block, latest_block, public_key=trusted_key
        )
        
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
    
    def is_chain_valid(
        self, trusted_public_keys: dict[str, bytes] | None = None
    ) -> bool:
        """
        Validate the entire blockchain.

        Args:
            trusted_public_keys: Trusted PEM keys by creator_id for signed blocks.

        Returns:
            True if the entire chain is valid, False otherwise
        """
        with self.lock:
            return (
                all(block.validate_structure() for block in self.chain[1:])
                and get_block_verifier().verify_chain(
                    self.chain,
                    trusted_public_keys=(
                        trusted_public_keys if trusted_public_keys is not None
                        else self.trusted_public_keys
                    ),
                ).is_valid
            )
    
    def get_events_by_entity(self, entity_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific entity across the entire chain."""
        return self.query_engine.get_events_by_entity(entity_id)

    def get_indexed_entity_events(self, entity_id: str) -> list[dict[str, Any]]:
        """Get indexed events with block metadata for a specific entity."""
        return self.query_engine.get_indexed_entity_events(entity_id)
    
    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get all events of a specific type across the entire chain."""
        return self.query_engine.get_events_by_type(event_type)

    def get_events_by_filter(
        self, filter_func: Callable[[dict[str, Any]], bool]
    ) -> list[dict[str, Any]]:
        """Get all events that match a custom filter function."""
        return self.query_engine.get_events_by_filter(filter_func)
    
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
    def from_dict(
        cls,
        data: dict[str, Any],
        trusted_public_keys: dict[str, bytes] | None = None,
        node_identity: NodeIdentity | None = None,
    ) -> 'Blockchain':
        """
        Create a Blockchain instance from dictionary data.
        
        Args:
            data: Dictionary containing blockchain data
            trusted_public_keys: Trusted PEM keys by creator_id for signed blocks.
            node_identity: Fixed local identity used for subsequent blocks.
            
        Returns:
            Blockchain instance
        """
        blockchain = cls(
            name=data["name"],
            node_identity=node_identity,
            trusted_public_keys=trusted_public_keys,
        )
        
        # Clear genesis block and rebuild from data
        blockchain.chain.clear()
        
        for block_data in data["chain"]:
            block = Block.from_dict(block_data)
            blockchain.chain.append(block)
        
        if not blockchain.is_chain_valid(trusted_public_keys):
            raise ValueError(
                f"Chain integrity check failed after loading '{data['name']}'"
            )

        blockchain.pending_events = data.get("pending_events", [])
        blockchain._rebuild_event_indexes()
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


class BlockchainQueryEngine:
    """Helper class to query events from Blockchain."""

    def __init__(self, blockchain: Blockchain) -> None:
        self.blockchain = blockchain

    def get_events_by_entity(self, entity_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific entity across the entire chain."""
        with self.blockchain.lock:
            if (
                hasattr(self.blockchain, 'entity_event_index')
                and entity_id in self.blockchain.entity_event_index
            ):
                indexed_events = self.blockchain.entity_event_index[entity_id]
                return deepcopy([e['event'] for e in indexed_events])

            events = []
            for block in self.blockchain.chain:
                events.extend(block.get_events_by_entity(entity_id))
            return events

    def get_indexed_entity_events(self, entity_id: str) -> list[dict[str, Any]]:
        """Get indexed events with block metadata for a specific entity."""
        with self.blockchain.lock:
            if hasattr(self.blockchain, 'entity_event_index'):
                return deepcopy(self.blockchain.entity_event_index.get(entity_id, []))
            return []

    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get all events of a specific type across the entire chain."""
        with self.blockchain.lock:
            idx = self.blockchain.event_type_index
            if event_type in idx:
                events = []
                for bi in idx[event_type]:
                    events.extend(
                        self.blockchain.chain[bi].get_events_by_type(event_type)
                    )
                return events
            return []

    def get_events_by_filter(
        self, filter_func: Callable[[dict[str, Any]], bool]
    ) -> list[dict[str, Any]]:
        """Get all events that match a custom filter function."""
        events = []
        for block in self.blockchain.chain:
            for event in block.to_event_list():
                if filter_func(event):
                    events.append(event)
        return events
