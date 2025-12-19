"""
Sub-Chain implementation for HieraChain Framework.

This module implements the Sub-Chain class that handles domain-specific
business operations and submits proofs to the Main Chain, following
framework guidelines for HieraChain structure.
"""

import time
import threading
import logging
import re
from typing import Any, Optional, Callable

from hierachain.core.blockchain import Blockchain
from hierachain.core.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.consensus.proof_of_federation import ProofOfFederation
from hierachain.config.settings import settings
from hierachain.core.utils import sanitize_metadata_for_main_chain, create_event
from hierachain.consensus.ordering_service import OrderingService, OrderingNode, OrderingStatus

logger = logging.getLogger(__name__)

class SubChain(Blockchain):
    """
    Sub-Chain implementation for the HieraChain framework.
    
    Sub-Chains act as domain experts (like department heads) and:
    - Handle domain-specific business operations
    - Store detailed domain events and data
    - Submit cryptographic proofs to Main Chain
    - Use entity_id as metadata field within events (not as block identifier)
    """
    
    def __init__(self, name: str, domain_type: str = "generic", config: Optional[dict[str, Any]] = None):
        """
        Initialize a Sub-Chain.
        
        Args:
            name: Name identifier for the Sub-Chain
            domain_type: Type of domain this Sub-Chain handles
            config: Optional configuration override for underlying services
        """
        if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
            raise ValueError(f"Invalid SubChain name '{name}'. Allowed: alphanumeric, underscore, hyphen.")

        super().__init__(name)
        self.domain_type = domain_type
        self.custom_config = config
        
        # Dynamic Consensus Loading
        if settings.CONSENSUS_TYPE == "proof_of_federation":
            self.consensus = ProofOfFederation(f"{name}_PoF")
        else:
            self.consensus = ProofOfAuthority(f"{name}_PoA")
            
        self.main_chain_connection: Optional[Any] = None
        self.proof_submission_interval: float = 60.0  # Submit proofs every 60 seconds
        self.last_proof_submission: float = 0.0
        self.completed_operations: int = 0
        
        # Register Sub-Chain as authority for its own operations
        if hasattr(self.consensus, 'add_authority'):
            self.consensus.add_authority(name, {
                "role": "sub_chain_authority",
                "domain_type": domain_type,
                "permissions": ["domain_operations", "event_creation"],
                "created_at": time.time()
            })
        
        # Initialize Ordering Service
        self._init_ordering_service()

        # Chain Synchronization (Rehydration)
        self.sync_chain()

        # Start Block Consumer Thread
        self.running = True
        self.consumer_thread = threading.Thread(target=self._block_consumer_loop, daemon=True)
        self.consumer_thread.start()

    def is_valid_new_block(self, block) -> bool:
        """
        Validate a new block including consensus rules.
        """
        # 1. Base structural validation
        if not super().is_valid_new_block(block):
            return False
            
        # 2. Consensus validation
        previous_block = self.get_latest_block()
        
        if not self.consensus.validate_block(block, previous_block):
            # Log warning but don't crash - useful for debugging consensus failures
            logger.warning(f"Consensus validation failed for block {block.index}")
            return False
            
        return True

    def stop(self):
        """Stop the background block consumer."""
        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2.0)
        
        # Also stop ordering service
        if hasattr(self, 'ordering_service'):
            self.ordering_service.shutdown()

    def _init_ordering_service(self):
        """Initialize the local Ordering Service for this Sub-Chain."""
        # Create a single local node for the ordering service
        local_node = OrderingNode(
            node_id=f"{self.name}_orderer",
            endpoint="localhost",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )
        
        # Service configuration
        default_config = {
            "storage_dir": f"data/{self.name}/journal",
            "block_size": 50, # Smaller batches for lower latency in demo
            "batch_timeout": 1.0,
            "worker_threads": 2
        }

        # Merge defaults with custom config if provided
        config = default_config.copy()
        if hasattr(self, 'custom_config') and self.custom_config:
            config.update(self.custom_config)
        
        self.ordering_service = OrderingService(nodes=[], config=config)
        
        # Sync OrderingService with local chain state (Genesis)
        if self.chain:
            latest = self.chain[-1]
            # OrderingService uses block_history to determine previous_hash
            self.ordering_service.block_history = [latest]
            # OrderingService uses blocks_created to determine next index
            self.ordering_service.blocks_created = latest.index + 1

    def add_event(self, event: dict[str, Any]) -> str:
        """Add event to Sub-Chain."""
        # Add timestamp if missing
        if "timestamp" not in event:
            event["timestamp"] = time.time()
            
        # Ensure required fields for OrderingService
        if "entity_id" not in event:
            event["entity_id"] = event.get("sender", "system")
        if "event" not in event:
            event["event"] = event.get("type", "generic_event")
            
        logger.debug(f"SubChain {self.name} adding event: {event.get('event')}")
        self.ordering_service.receive_event(
            event_data=event,
            channel_id=self.name,
            submitter_org=self.name
        )

        return f"tx-{hash(str(event))}"
    
    def connect_to_main_chain(self, main_chain: Any) -> bool:
        """
        Connect this Sub-Chain to a Main Chain.
        
        Args:
            main_chain: Main Chain instance to connect to
            
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Register with Main Chain
            metadata = {
                "domain_type": self.domain_type,
                "sub_chain_name": self.name,
                "connected_at": time.time(),
                "capabilities": ["domain_operations", "proof_submission"]
            }
            
            if main_chain.register_sub_chain(self.name, metadata):
                self.main_chain_connection = main_chain
                
                # Create connection event
                connection_event = {
                    "event": "main_chain_connection",
                    "timestamp": time.time(),
                    "details": {
                        "main_chain_name": getattr(main_chain, 'name', str(main_chain)),
                        "connected_at": time.time(),
                        "status": "connected"
                    }
                }
                
                self.add_event(connection_event)
                return True
        except (AttributeError, TypeError, ValueError):
            pass
        
        return False
    
    def start_operation(self, entity_id: str, operation_type: str, details: Optional[dict[str, Any]] = None) -> bool:
        """
        Start a domain-specific operation for an entity.
        
        This follows the guidelines pattern where entity_id is used as metadata
        field within events, not as block identifier.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to start
            details: Additional operation details
            
        Returns:
            True if operation was started successfully, False otherwise
        """
        # Create properly structured event following guidelines
        event = create_event(
            entity_id=entity_id,  # Metadata field, not block identifier
            event_type="operation_start",
            details={
                "operation_type": operation_type,
                "domain_type": self.domain_type,
                "started_by": self.name,
                "operation_details": details or {},
                "started_at": time.time()
            }
        )
        
        self.add_event(event)
        return True
    
    def complete_operation(self, entity_id: str, operation_type: str, result: Optional[dict[str, Any]] = None) -> bool:
        """
        Complete a domain-specific operation for an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation being completed
            result: Operation result data
            
        Returns:
            True if operation was completed successfully, False otherwise
        """
        # Create completion event
        event = create_event(
            entity_id=entity_id,  # Metadata field
            event_type="operation_complete",
            details={
                "operation_type": operation_type,
                "domain_type": self.domain_type,
                "completed_by": self.name,
                "result": result or {},
                "completed_at": time.time()
            }
        )
        
        self.add_event(event)
        self.completed_operations += 1
        return True
    
    def update_entity_status(self, entity_id: str, status: str, details: Optional[dict[str, Any]] = None) -> bool:
        """
        Update the status of an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            status: New status for the entity
            details: Additional status details
            
        Returns:
            True if status was updated successfully, False otherwise
        """
        event = create_event(
            entity_id=entity_id,  # Metadata field
            event_type="status_update",
            details={
                "new_status": status,
                "domain_type": self.domain_type,
                "updated_by": self.name,
                "status_details": details or {},
                "updated_at": time.time()
            }
        )
        
        self.add_event(event)
        return True
    
    def submit_proof_to_main(self, main_chain: Any, metadata_filter: Optional[Callable] = None) -> bool:
        """
        Submit cryptographic proof to Main Chain.
        
        This follows the guidelines pattern for proof submission where
        Sub-Chains submit proofs with summary metadata, not detailed data.
        
        Args:
            main_chain: Main Chain to submit proof to
            metadata_filter: Optional function to generate custom metadata
            
        Returns:
            True if proof was submitted successfully, False otherwise
        """
        
        # Get latest block for proof
        latest_block = self.get_latest_block()
        logger.warning(f"DEBUG: SubChain {self.name} submitting proof. Chain length: {len(self.chain)}. Latest block index: {latest_block.index}")

        if not self.chain or len(self.chain) <= 1:  # Only genesis block
            logger.debug("SubChain has only genesis block. Aborting proof submission.")
            return False
        
        # Generate summary metadata (not detailed domain data)
        if metadata_filter:
            metadata = metadata_filter(self)
        else:
            metadata = self._generate_default_proof_metadata()
        
        # Submit proof to Main Chain
        success = main_chain.add_proof(
            sub_chain_name=self.name,
            proof_hash=latest_block.hash,
            metadata=metadata
        )
        logger.debug(f"MainChain.add_proof returned: {success}")
        
        if success:
            self.last_proof_submission = time.time()
            
            # Create proof submission event in Sub-Chain
            proof_event = {
                "event": "proof_submitted",
                "timestamp": time.time(),
                "details": {
                    "main_chain_name": getattr(main_chain, 'name', str(main_chain)),
                    "proof_hash": latest_block.hash,
                    "block_index": latest_block.index,
                    "submitted_at": time.time()
                }
            }
            
            self.add_event(proof_event)
        
        return success
    
    def _generate_default_proof_metadata(self) -> dict[str, Any]:
        """
        Generate default proof metadata for Main Chain submission.
        
        This creates summary metadata only, no detailed domain data.
        
        Returns:
            Summary metadata suitable for Main Chain
        """
        latest_block = self.get_latest_block()
        
        # Count different event types in recent blocks
        recent_events = []
        for block in self.chain[-5:]:  # Last 5 blocks
            # Use to_event_list() if available to handle Arrow Tables
            events = block.to_event_list() if hasattr(block, 'to_event_list') else block.events
            recent_events.extend(events)
        
        event_counts = {}
        entity_count = set()
        
        for event in recent_events:
            event_type = event.get("event", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if event.get("entity_id") is not None:
                entity_count.add(event["entity_id"])
        
        # Create summary metadata (following guidelines)
        metadata = {
            "domain_type": self.domain_type,
            "latest_block_index": latest_block.index,
            "total_blocks": len(self.chain),
            "recent_events": len(recent_events),
            "unique_entities": len(entity_count),
            "completed_operations": self.completed_operations,
            "event_types": list(event_counts.keys()),
            "proof_timestamp": time.time()
        }
        
        return sanitize_metadata_for_main_chain(metadata)
    
    def should_submit_proof(self) -> bool:
        """
        Check if it's time to submit a proof to Main Chain.
        
        Returns:
            True if proof should be submitted, False otherwise
        """
        current_time = time.time()
        time_since_last = current_time - self.last_proof_submission
        
        # Check ordering service for pending events
        has_pending = False
        if hasattr(self, 'ordering_service'):
            has_pending = len(self.ordering_service.pending_events) > 0
            
        return (time_since_last >= self.proof_submission_interval and has_pending)
    
    def auto_submit_proof_if_needed(self) -> bool:
        """
        Automatically submit proof if conditions are met.
        
        Returns:
            True if proof was submitted, False otherwise
        """
        if self.should_submit_proof() and self.main_chain_connection:
            return self.submit_proof_to_main(self.main_chain_connection)
        return False
    
    def get_entity_history(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get complete history of events for a specific entity.
        
        Args:
            entity_id: Entity identifier to search for
            
        Returns:
            List of events for the specified entity, ordered by timestamp
        """
        entity_events = self.get_events_by_entity(entity_id)
        
        # Sort by timestamp
        entity_events.sort(key=lambda x: x.get("timestamp", 0))
        
        return entity_events
    
    def get_domain_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive statistics about this Sub-Chain's domain operations.
        
        Returns:
            Dictionary containing domain statistics
        """
        base_stats = self.get_chain_stats()
        
        # Count entities and operations
        all_events = []
        for block in self.chain:
            # Use to_event_list() if available to handle Arrow Tables
            events = block.to_event_list() if hasattr(block, 'to_event_list') else block.events
            all_events.extend(events)
        
        unique_entities = set()
        operation_types = {}
        
        for event in all_events:
            if event.get("entity_id") is not None:
                unique_entities.add(event["entity_id"])
            
            event_type = event.get("event", "unknown")
            operation_types[event_type] = operation_types.get(event_type, 0) + 1
        
        return {
            **base_stats,
            "domain_type": self.domain_type,
            "unique_entities": len(unique_entities),
            "completed_operations": self.completed_operations,
            "operation_types": operation_types,
            "main_chain_connected": self.main_chain_connection is not None,
            "last_proof_submission": self.last_proof_submission,
            "proof_submission_interval": self.proof_submission_interval
        }
    
    def finalize_sub_chain_block(self) -> Optional[dict[str, Any]]:
        """
        Pull ordered blocks from Ordering Service and finalize them.
        """
        new_blocks = []
        
        while True:
            block = self.ordering_service.get_next_block()
            if not block:
                logger.debug(f"DEBUG: No block returned from get_next_block. Queue {id(self.ordering_service.commit_queue)} empty.")
                break
            
            logger.debug(f"DEBUG: Got block {block.index} from ordering service. Queue {id(self.ordering_service.commit_queue)}")
            
            # 2. Stitch block into local chain
            latest_block = self.get_latest_block()
            
            # Re-index to match local chain
            block.index = latest_block.index + 1
            block.previous_hash = latest_block.hash
            
            # Recalculate hash with new metadata
            block.hash = block.calculate_hash()
            
            # 3. Finalize with consensus (signatures)
            finalized_block = self.consensus.finalize_block(block, self.name)
            
            # 4. Add to chain
            if self.add_block(finalized_block):
                new_blocks.append(finalized_block)
                # Auto-submit proof if needed
                self.auto_submit_proof_if_needed()
            else:
                logger.error(f"Failed to add ordered block {block.index}")
                
        if not new_blocks:
            return None
            
        last_block = new_blocks[-1]
        
        return {
            "block_index": last_block.index,
            "block_hash": last_block.hash,
            "events_count": len(last_block.events),
            "finalized_at": time.time(),
            "domain_type": self.domain_type
        }

    def flush_pending_and_finalize(self, timeout: float = 3.0) -> Optional[dict[str, Any]]:
        """
        Flush pending events and finalize the block.

        Args:
            timeout: Timeout for waiting for block to be finalized

        Returns:
            Finalized block details or None if timeout
        """
        logger.debug(f"flush_pending_and_finalize for {self.name}")
        start_time = time.time()

        while not self.ordering_service.event_pool.empty():
            if time.time() - start_time > timeout:
                break

        # Capture initial chain length
        initial_len = len(self.chain)

        # Force block creation in the ordering service thread
        loop = getattr(self.ordering_service, 'loop', None)
        if loop and loop.is_running():
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                self.ordering_service._check_timeout_block_creation(force=True),
                loop
            )
            try:
                # Wait for block creation to complete
                future.result(timeout=timeout)
                logger.error(f"DEBUG: Block creation future completed. QM={self.ordering_service.commit_queue.qsize()} QID={id(self.ordering_service.commit_queue)} BC={self.ordering_service.blocks_created}")
            except Exception as e:
                logger.error(f"Error forcing block creation: {e}")

        # Try to consume result manually first
        result = self.finalize_sub_chain_block()
        if result:
            return result
            
        # If no result, maybe background consumer took it? Wait for chain to grow.
        wait_start = time.time()
        while len(self.chain) == initial_len:
            if time.time() - wait_start > timeout:
                logger.warning("Timeout waiting for block to appear in chain during flush")
                break
            time.sleep(0.1)

        if len(self.chain) > initial_len:
            last_block = self.chain[-1]
            return {
                "block_index": last_block.index,
                "block_hash": last_block.hash,
                "events_count": len(last_block.events),
                "finalized_at": time.time(),
                "domain_type": self.domain_type
            }
            
        return None
    
    def _block_consumer_loop(self):
        """Background thread to continuously pull blocks."""
        while self.running:
            try:
                # Attempt to finalize blocks
                result = self.finalize_sub_chain_block()
                if not result:
                    # If no blocks, sleep a bit to avoid busy waiting
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in block consumer loop: {e}")
                time.sleep(1.0)

    def sync_chain(self):
        """
        Synchronize local chain with Ordering Service (Rehydration).
        Fetch missing blocks from history.
        """
        try:
            latest_index = self.get_latest_block().index
            missing_blocks = self.ordering_service.get_blocks(start_index=latest_index)
            
            # Using simple iteration
            count = 0
            for block in missing_blocks:
                if self.add_block(block):
                    count += 1
                
            if count > 0:
                logger.info(f"Synced/Rehydrated {count} blocks from Ordering Service.")
                
        except Exception as e:
            logger.error(f"Sync failed: {e}")

    def __str__(self) -> str:
        """String representation of the Sub-Chain."""
        return f"SubChain(name={self.name}, domain={self.domain_type}, blocks={len(self.chain)}, operations={self.completed_operations})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Sub-Chain."""
        return (f"SubChain(name={self.name}, domain_type={self.domain_type}, "
                f"blocks={len(self.chain)}, operations={self.completed_operations}, "
                f"main_chain_connected={self.main_chain_connection is not None})")