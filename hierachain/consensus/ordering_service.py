"""
Independent Ordering Service for HieraChain Framework.

This module implements a decoupled event ordering service that significantly improves 
scalability and reduces communication bandwidth. The ordering service separates event 
ordering from consensus validation, enabling enterprise-scale event volumes.
"""

import time
import hashlib
import json
import threading
import logging
from queue import Queue, Empty
from typing import Any, Callable
from dataclasses import dataclass
from enum import Enum
import concurrent.futures
import pyarrow as pa
import asyncio

from hierachain.core.block import Block
from hierachain.core import schemas
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.core.performance import process_pool
from hierachain.config.settings import Settings
from hierachain.core.utils import (
    compute_leaves_from_events_standalone,
    MerkleTree
)
from hierachain.security.security_utils import verify_batch_signatures


logger = logging.getLogger(__name__)

class OrderingStatus(Enum):
    """Ordering service status enumeration"""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    LOCKDOWN = "lockdown"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class EventStatus(Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    ORDERED = "ordered"
    CERTIFIED = "certified"
    REJECTED = "rejected"


@dataclass
class OrderingNode:
    """Ordering service node configuration"""
    node_id: str
    endpoint: str
    is_leader: bool
    weight: float
    status: OrderingStatus
    last_heartbeat: float
    
    def is_healthy(self, timeout: float = 30.0) -> bool:
        """Check if node is healthy based on heartbeat"""
        return (time.time() - self.last_heartbeat) < timeout


@dataclass
class PendingEvent:
    """Event waiting to be ordered"""
    event_id: str
    event_data: dict[str, Any]
    channel_id: str
    submitter_org: str
    received_at: float
    status: EventStatus
    certification_result: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_id": self.event_id,
            "event_data": self.event_data,
            "channel_id": self.channel_id,
            "submitter_org": self.submitter_org,
            "received_at": self.received_at,
            "status": self.status.value,
            "certification_result": self.certification_result
        }


class EventCertifier:
    """Event certification and validation"""
    
    def __init__(self):
        self.validation_rules: list[Callable] = []
        self.certified_events: dict[str, dict[str, Any]] = {}
        
    def add_validation_rule(self, rule: Callable[[dict[str, Any]], bool]) -> None:
        """Add a validation rule for events"""
        self.validation_rules.append(rule)
        
    def validate(self, event: PendingEvent) -> dict[str, Any]:
        """
        Validate and certify an event.
        
        Args:
            event: Event to validate
            
        Returns:
            Certification result with validation details
        """
        certification: dict[str, Any] = {
            "event_id": event.event_id,
            "certified_at": time.time(),
            "valid": True,
            "validation_errors": [],
            "metadata": {}
        }
        
        # Apply validation rules
        for rule in self.validation_rules:
            try:
                if not rule(event.event_data):
                    certification["valid"] = False
                    certification["validation_errors"].append(
                        f"Validation rule failed: {rule.__name__}"
                    )
            except Exception as e:
                certification["valid"] = False
                certification["validation_errors"].append(f"Validation error: {str(e)}")
        
        # Basic structural validation
        if not self._validate_structure(event.event_data):
            certification["valid"] = False
            certification["validation_errors"].append("Invalid event structure")
        
        # Check for required fields
        required_fields = ["entity_id", "event", "timestamp"]
        for field in required_fields:
            if field not in event.event_data:
                certification["valid"] = False
                certification["validation_errors"].append(f"Missing required field: {field}")
        
        # Store certification result
        self.certified_events[event.event_id] = certification
        
        return certification
    
    @staticmethod
    def _validate_structure(event_data: Any) -> bool:
        """Validate basic event structure"""
        # Support for Arrow objects
        if isinstance(event_data, (pa.Table, pa.RecordBatch)):
            return event_data.schema.equals(schemas.get_event_schema())

        if not isinstance(event_data, dict):
            return False
            
        # Check timestamp is reasonable
        timestamp = event_data.get("timestamp", 0)
        current_time = time.time()
        if abs(timestamp - current_time) > 3600:  # 1 hour tolerance
            return False
            
        return True
    
    def get_certification(self, event_id: str) -> dict[str, Any] | None:
        """Get certification result for an event"""
        return self.certified_events.get(event_id)


class BlockBuilder:
    """Builds blocks from ordered events"""
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize block builder.
        
        Args:
            config: Block building configuration
        """
        self.config = config
        self.block_size = config.get("block_size", 500)
        self.batch_timeout = config.get("batch_timeout", 2.0)  # seconds
        self.current_batch: list[PendingEvent] = []
        self.current_batch_ids: set[str] = set()
        self.batch_start_time = time.time()

    def add_event(self, event: PendingEvent) -> list[dict[str, Any]] | None:
        """
        Add event to current batch.
        
        Args:
            event: Certified event to add
            
        Returns:
            List of event data if batch is ready, None otherwise
        """
        if event.event_id in self.current_batch_ids:
            return None

        # Start timer on first event in batch
        if not self.current_batch:
            self.batch_start_time = time.time()

        self.current_batch.append(event)
        self.current_batch_ids.add(event.event_id)

        # Check if batch is ready
        if self.is_batch_ready():
            return self._finalize_batch()
        
        return None

    def force_create_block(self) -> list[dict[str, Any]] | None:
        """Force creation of block from current batch"""
        if not self.current_batch:
            return None
            
        return self._finalize_batch()
    
    def is_batch_ready(self) -> bool:
        """Check if current batch is ready for block creation"""
        # Check batch size
        if len(self.current_batch) >= self.block_size:
            return True
            
        # Check timeout
        if (time.time() - self.batch_start_time) >= self.batch_timeout:
            return True
            
        return False

    def _finalize_batch(self) -> list[dict[str, Any]] | None:
        """Return current batch event data and reset"""
        if not self.current_batch:
            return None

        # Extract event data for batch creation
        events_list = [pending.event_data for pending in self.current_batch]

        # Reset batch
        self.current_batch.clear()
        self.current_batch_ids.clear()
        self.batch_start_time = time.time()
        
        return events_list


class OrderingService:
    """
    Decoupled event ordering service for improved scalability.
    
    This service separates event ordering from consensus validation, enabling 
    higher throughput and reduced latency for enterprise-scale operations.
    """
    
    def __init__(self, nodes: list[OrderingNode], config: dict[str, Any]):
        """
        Initialize ordering service.
        
        Args:
            nodes: List of ordering service nodes
            config: Service configuration parameters
        """
        self.nodes = {node.node_id: node for node in nodes}
        self.config = config
        self.status = OrderingStatus.MAINTENANCE
        
        # Event processing components
        self.event_pool: Queue = Queue()
        self.block_builder = BlockBuilder(config)
        self.commit_queue: Queue = Queue()
        self.certifier = EventCertifier()
        
        # Durability Layer (Transaction Journal)
        self.journal = TransactionJournal(
            storage_dir=config.get("storage_dir", "data/journal"),
            active_log_name=f"node_{self._get_node_id()}_journal.log"
        )
        
        # Processing state
        self.pending_events: dict[str, PendingEvent] = {}

        # Replaced in-memory list with SQL Backend
        # Replaced in-memory list with SQL Backend
        # Keep as cache only if needed, or remove.
        self.processed_events: dict[str, PendingEvent] = {}
        self.storage = SqlStorageBackend()
        
        self.block_history: list[Block] = []
        self.blocks_created = 0
        self.events_processed = 0
        
        # Threading for concurrent processing
        self.processing_thread = None
        self.should_stop = threading.Event()
        self.loop = None # Asyncio loop for processing thread
        
        # Initialize Process Pool
        # Default to 50% CPU unless specified
        max_workers = config.get("max_workers", Settings.MAX_WORKERS) 
        process_pool.initialize(max_workers=max_workers)
        
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers or 4
        )
        
        # Statistics
        self.statistics = {
            "events_received": 0,
            "events_certified": 0,
            "events_rejected": 0,
            "blocks_created": 0,
            "average_batch_size": 0,
            "average_processing_time": 0,
            "total_latency": 0,
            "events_committed": 0
        }
        
        # Initialize validation rules
        self._setup_default_validation_rules()
        
        # Start processing
        # State recovery is now performed asynchronously in the processing thread
        self.start()

    def _get_node_id(self) -> str:
        """Get current node ID or default"""
        # Simple heuristic to find local node ID
        for node in self.nodes.values():
            if node.endpoint in ["localhost", "127.0.0.1"]: # Simplified check
                return node.node_id
        return "unknown_node"

    async def _recover_state_async(self):
        """Recover state from transaction journal"""
        print("Recovering state from Transaction Journal...")
        count = 0
        
        # Replay events from journal
        for event_data in self.journal.replay():
            try:
                # Sanitize event data (Arrow/Journal might return bytes or non-JSON types)
                event_data = self._make_serializable(event_data)

                # Check for Block Cut event
                if event_data.get("event") == "$SYSTEM_BLOCK_CUT":
                    await self._check_timeout_block_creation()
                    continue

                # Reconstruct PendingEvent
                channel_id = "recovery"
                submitter = "recovery"
                
                event_id = self._generate_event_id(event_data, channel_id)
                
                pending_event = PendingEvent(
                    event_id=event_id,
                    event_data=event_data,
                    channel_id=channel_id,
                    submitter_org=submitter,
                    received_at=time.time(),
                    status=EventStatus.PENDING
                )
                
                # Process directly
                await self._process_single_event(pending_event)
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to recover event: {e}")
                
        # Force block creation for any remaining events
        await self._check_timeout_block_creation()
        print(f"Journal recovery check complete. Found {count} entries.")
        
        print(f"Journal recovery complete. Restored {count} events and {self.blocks_created} blocks.")

    def get_blocks(self, start_index: int = 0) -> list[Block]:
        """
        Get list of blocks starting from a specific index.
        Used for synchronization/rehydration.
        
        Args:
            start_index: Block index to start from

        Returns:
            List of blocks
        """
        if start_index < 0:
            start_index = 0
            
        if start_index >= len(self.block_history):
            return []
            
        return self.block_history[start_index:]

    def receive_event(self, event_data: dict[str, Any], channel_id: str, submitter_org: str) -> str:
        """
        Receive event from client or application channel.
        
        Args:
            event_data: Event data to order
            channel_id: Channel where event originated
            submitter_org: Organization submitting the event
            
        Returns:
            Event ID for tracking
        """
        # Enforce status check
        if self.status == OrderingStatus.LOCKDOWN:
            raise PermissionError("Service is in LOCKDOWN mode. Write operations are suspended.")
        if self.status != OrderingStatus.ACTIVE:
            raise RuntimeError(f"Service is not ACTIVE (current status: {self.status.value})")

        if not isinstance(event_data, dict):
            raise ValueError("Event data must be a dictionary")

        # Sanitize event data to ensure JSON compatibility (e.g. bytes -> hex)
        event_data = self._make_serializable(event_data)

        # Generate unique event ID
        event_id = self._generate_event_id(event_data, channel_id)

        # Transaction Journal
        if not self.journal.log_event(event_data):
            raise RuntimeError("Failed to persist event to Transaction Journal")
        
        # Create pending event
        pending_event = PendingEvent(
            event_id=event_id,
            event_data=event_data,
            channel_id=channel_id,
            submitter_org=submitter_org,
            received_at=time.time(),
            status=EventStatus.PENDING
        )
        
        # Add to processing queue
        self.event_pool.put(pending_event)
        self.pending_events[event_id] = pending_event
        
        # Update statistics
        self.statistics["events_received"] += 1
        
        return event_id
    
    def get_event_status(self, event_id: str) -> dict[str, Any] | None:
        """
        Get status of a specific event.
        
        Args:
            event_id: Event ID to query
            
        Returns:
            Event status information
        """
        # Check pending events
        if event_id in self.pending_events:
            event = self.pending_events[event_id]
            return {
                "event_id": event_id,
                "status": event.status.value,
                "received_at": event.received_at,
                "channel_id": event.channel_id,
                "certification_result": event.certification_result
            }
        
        # Check processed events
        if event_id in self.processed_events:
            event = self.processed_events[event_id]
            return {
                "event_id": event_id,
                "status": event.status.value,
                "processed_at": event.received_at,
                "channel_id": event.channel_id,
                "certification_result": event.certification_result
            }
        
        return None

    def get_next_block(self) -> Block | None:
        """
        Get next completed block from the commit queue.
        
        Returns:
            Block data if available, None otherwise
        """
        try:
            block = self.commit_queue.get_nowait()
            return block
        except Empty:
            return None
    
    def get_service_status(self) -> dict[str, Any]:
        """Get comprehensive service status"""
        healthy_nodes = [n for n in self.nodes.values() if n.is_healthy()]
        
        return {
            "status": self.status.value,
            "nodes": {
                "total": len(self.nodes),
                "healthy": len(healthy_nodes),
                "leader": next(
                    (n.node_id for n in self.nodes.values() if n.is_leader),
                    None
                )
            },
            "queues": {
                "pending_events": self.event_pool.qsize(),
                "commit_queue": self.commit_queue.qsize(),
                "processing_events": len(self.pending_events)
            },
            "statistics": self.statistics,
            "configuration": {
                "block_size": self.block_builder.block_size,
                "batch_timeout": self.block_builder.batch_timeout,
                "worker_threads": self.config.get("worker_threads", 4)
            }
        }
    
    def add_validation_rule(self, rule: Callable[[dict[str, Any]], bool]) -> None:
        """Add custom validation rule for events"""
        self.certifier.add_validation_rule(rule)
    
    def start(self) -> None:
        """Start the ordering service"""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.should_stop.clear()
            self.processing_thread = threading.Thread(target=self._process_events)
            self.processing_thread.daemon = True
            self.processing_thread.start()

        # Status will be set to ACTIVE by the processing thread after recovery
        # Wait for service to become ACTIVE (with timeout) to ensure it's ready
        if self.config.get("wait_for_active", True):
            start_time = time.time()
            timeout = self.config.get("start_timeout", 5.0)
            while self.status != OrderingStatus.ACTIVE:
                if time.time() - start_time > timeout:
                    logger.warning("Service start timed out waiting for ACTIVE status")
                    break
                time.sleep(0.01)

    def lockdown(self) -> None:
        """Enter LOCKDOWN mode"""
        self.status = OrderingStatus.LOCKDOWN

    def resume(self) -> None:
        """Resume ACTIVE mode from LOCKDOWN or other states."""
        self.status = OrderingStatus.ACTIVE

    def shutdown(self) -> None:
        """Shutdown the ordering service"""
        self.should_stop.set()
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        self.executor.shutdown(wait=True)
        # Close the journal to flush any pending data
        if self.journal:
            self.journal.close()
        self.status = OrderingStatus.SHUTDOWN
    
    async def _process_events_async(self):
        """Async event processing loop"""
        # Recover state before processing new events
        await self._recover_state_async()

        # Enable ACTIVE mode after recovery
        self.status = OrderingStatus.ACTIVE
        logger.info("Ordering Service is now ACTIVE and ready to process events")

        batch = []
        last_batch_time = time.time()
        batch_size = 100 # Configurable batch size for multiprocessing
        
        while not self.should_stop.is_set():
            try:
                # 1. Collect Batch
                try:
                    # Non-blocking get for loop
                    pending_event = self.event_pool.get_nowait()
                    batch.append(pending_event)
                except Empty:
                    await asyncio.sleep(0.01) # Yield to event loop
                
                # 2. Process Batch if full or timeout
                is_full = len(batch) >= batch_size
                is_timeout = (time.time() - last_batch_time) > 0.1 # 100ms latency target
                
                if (batch and (is_full or is_timeout)) or (not batch and self._is_block_timeout()):
                    
                    if batch:
                        # Offload certification to ProcessPool
                        await self._process_batch(batch)
                        batch = []
                        last_batch_time = time.time()
                    
                    # Always check for block timeout
                    await self._check_timeout_block_creation()
                    
            except Exception as e:
                logger.error(f"Error in async event loop: {e}")
                
    def _process_events(self) -> None:
        """Main event processing loop (entry point for thread)"""
        # Create new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._process_events_async())
        finally:
            self.loop.close()

    async def _create_and_commit_block_async(self, events: list[dict[str, Any]]) -> None:
        """
        Create a block asynchronously by offloading Merkle tree calculation.
        """
        if not events:
            return

        try:
            # Offload Merkle leaf calculation (serialization + hashing)
            merkle_leaves = await process_pool.run_task(
                compute_leaves_from_events_standalone, events
            )

            # Build Merkle Tree from leaves (MAIN THREAD - fast)
            merkle_tree = MerkleTree(leaves=merkle_leaves)
            merkle_root = merkle_tree.root

            # Create Block (MAIN THREAD)
            previous_hash = self.block_history[-1].hash if self.block_history else "0"
            
            block = Block(
                index=self.blocks_created, 
                events=events,
                previous_hash=previous_hash,
                merkle_root=merkle_root
            )

            # Commit Block
            self._commit_block(block)
        except Exception as e:
            logger.error(f"Error creating block asynchronously: {e}")

    async def _process_batch(self, batch: list[PendingEvent]):
        """Process a batch of events with parallel signature verification"""
        # Batch signature verification
        verification_items = []
        events_to_verify = []

        for event in batch:
            data = event.event_data
            # Check for signature and sender
            if "signature" in data and "sender" in data:
                # Extract payload from details if available (matching benchmark)
                msg = None
                if "details" in data and isinstance(data["details"], dict):
                    msg = data["details"].get("payload")
                
                if msg:
                    verification_items.append({
                        "public_key": data["sender"],
                        "message": msg,
                        "signature": data["signature"]
                    })
                    events_to_verify.append(event)
        
        # Run batch verification if needed
        if verification_items:
            try:
                results = await process_pool.run_task(verify_batch_signatures, verification_items)
                
                for event, is_valid in zip(events_to_verify, results):
                    if not is_valid:
                        event.status = EventStatus.REJECTED
                        self.statistics["events_rejected"] += 1
                        logger.warning(f"Event {event.event_id} rejected due to invalid signature")
            except Exception as e:
                logger.error(f"Batch verification failed: {e}")

        for event in batch:
            if event.status == EventStatus.REJECTED:
                if event.event_id in self.pending_events:
                    del self.pending_events[event.event_id]
                continue
                
            await self._process_single_event(event)

    async def _check_timeout_block_creation(self, force: bool = False) -> None:
        """
        Check if block needs to be created due to timeout.
        
        Args:
            force: If True, force creation regardless of timeout
        """
        if force or self._is_block_timeout():
            if force:
                logger.debug("Forcing block creation")
            else:
                logger.debug("Block timeout reached, forcing creation")
                
            raw_block_data = self.block_builder.force_create_block()
            if raw_block_data:
                await self._create_and_commit_block_async(raw_block_data)

    async def _process_single_event(self, pending_event: PendingEvent) -> None:
        """Process a single event through certification and ordering"""
        try:
            # Update status
            pending_event.status = EventStatus.PROCESSING
            
            # Certify the event
            certification_result = self.certifier.validate(pending_event)
            pending_event.certification_result = certification_result
            
            if certification_result["valid"]:
                pending_event.status = EventStatus.CERTIFIED
                self.statistics["events_certified"] += 1
                logger.error(f"Event {pending_event.event_id} CERTIFIED. Adding to block builder.")
                
                # Add to block builder
                raw_block_data = self.block_builder.add_event(pending_event)
                if raw_block_data:
                    await self._create_and_commit_block_async(raw_block_data)
                    
                # Move to processed events
                self.processed_events[pending_event.event_id] = pending_event
                if pending_event.event_id in self.pending_events:
                    del self.pending_events[pending_event.event_id]
                    
            else:
                pending_event.status = EventStatus.REJECTED
                self.statistics["events_rejected"] += 1
                logger.error(f"Event {pending_event.event_id} REJECTED: {certification_result['validation_errors']}")
                
        except Exception as e:
            logger.error(f"Exception processing event {pending_event.event_id}: {e}")
            pending_event.status = EventStatus.REJECTED
            pending_event.certification_result = {
                "valid": False,
                "error": str(e)
            }
            self.statistics["events_rejected"] += 1
    
    def _is_block_timeout(self) -> bool:
        """Check if block timeout occurred"""
        return self.block_builder.is_batch_ready()

    def _commit_block(self, block: Block) -> None:
        """Commit a completed block to the commit queue"""
        # Add block metadata - Update Block object attributes
        block.index = self.blocks_created
        block.calculate_hash()

        # Save to Persistent Storage
        try:
            block_data = {
                "index": block.index,
                "hash": block.hash,
                "previous_hash": block.previous_hash,
                "timestamp": block.timestamp,
                "events": block.to_event_list(),
                "metadata": {}
            }
            self.storage.save_block(block_data)
            
            # Calculate Latency
            current_time = time.time()
            block_latency = 0.0
            block_event_count = 0
            
            for event in self.processed_events.values():
                block_latency += (current_time - event.received_at)
                block_event_count += 1
            
            # Update Statistics
            self.statistics["total_latency"] += block_latency
            self.statistics["events_committed"] += block_event_count
            
            if self.statistics["events_committed"] > 0:
                total_latency = self.statistics["total_latency"]
                events_committed = self.statistics["events_committed"]
                self.statistics["average_processing_time"] = (total_latency / events_committed)
            
            # Clear in-memory processed events cache
            self.processed_events.clear()
            
        except Exception as e:
            logger.error(f"Failed to save block to DB: {e}")

        # Log Block Cut event to Journal for deterministic recovery (only if ACTIVE)
        if self.status == OrderingStatus.ACTIVE:
            try:
                system_event = {
                    "event": "$SYSTEM_BLOCK_CUT",
                    "entity_id": "SYSTEM",
                    "timestamp": time.time(),
                    "details": {"block_index": block.index, "block_hash": block.hash}
                }
                self.journal.log_event(system_event)
            except Exception as e:
                logger.error(f"Failed to log block cut event: {e}")

        # Put in commit queue
        logger.error(f"DEBUG: Committing block {block.index} to queue {id(self.commit_queue)}. Queue size before: {self.commit_queue.qsize()}")
        self.commit_queue.put(block)
        logger.error(f"DEBUG: Block {block.index} committed. Queue {id(self.commit_queue)} size after: {self.commit_queue.qsize()}")
        
        # Add to history
        self.block_history.append(block)
        
        # Update statistics
        self.blocks_created += 1
        self.statistics["blocks_created"] = self.blocks_created

        # Update average batch size
        event_count = len(block.events)

        prev_avg = self.statistics["average_batch_size"]
        total_events = prev_avg * (self.blocks_created - 1) + event_count
        self.statistics["average_batch_size"] = total_events / self.blocks_created

    @staticmethod
    def _make_serializable(obj: Any) -> Any:
        """Recursively make object JSON serializable"""
        if isinstance(obj, bytes):
            return obj.hex()
        if isinstance(obj, dict):
            return {k: OrderingService._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [OrderingService._make_serializable(v) for v in obj]
        # Basic JSON types
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        # Fallback
        return str(obj)

    @staticmethod
    def _generate_event_id(event_data: dict[str, Any], channel_id: str) -> str:
        """Generate unique event ID"""
        clean_data = OrderingService._make_serializable(event_data)
        json_str = json.dumps(clean_data, sort_keys=True, separators=(',', ':'))
        data = f"{channel_id}:{json_str}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _setup_default_validation_rules(self) -> None:
        """Setup default validation rules"""
        def validate_non_empty_entity_id(event_data: dict[str, Any]) -> bool:
            entity_id = event_data.get("entity_id", "")
            return isinstance(entity_id, str) and len(entity_id.strip()) > 0
        
        def validate_event_type(event_data: dict[str, Any]) -> bool:
            event_type = event_data.get("event", "")
            return isinstance(event_type, str) and len(event_type.strip()) > 0
        
        def validate_timestamp_format(event_data: dict[str, Any]) -> bool:
            timestamp = event_data.get("timestamp")
            return isinstance(timestamp, (int, float)) and timestamp > 0
        
        # Add default rules
        self.certifier.add_validation_rule(validate_non_empty_entity_id)
        self.certifier.add_validation_rule(validate_event_type)
        self.certifier.add_validation_rule(validate_timestamp_format)
    
    def __str__(self) -> str:
        """String representation of ordering service"""
        return f"OrderingService(nodes={len(self.nodes)}, status={self.status.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"OrderingService(nodes={len(self.nodes)}, "
                f"status='{self.status.value}', "
                f"events_processed={self.events_processed})")
