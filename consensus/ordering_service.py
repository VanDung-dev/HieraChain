"""
Independent Ordering Service for Hierarchical Blockchain Framework.

This module implements a decoupled event ordering service that significantly improves 
scalability and reduces communication bandwidth. The ordering service separates event 
ordering from consensus validation, enabling enterprise-scale event volumes.
"""

import time
import hashlib
import json
import threading
from queue import Queue, Empty
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import concurrent.futures


class OrderingStatus(Enum):
    """Ordering service status enumeration"""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    STOPPED = "stopped"
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
    event_data: Dict[str, Any]
    channel_id: str
    submitter_org: str
    received_at: float
    status: EventStatus
    certification_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
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
        self.validation_rules: List[Callable] = []
        self.certified_events: Dict[str, Dict[str, Any]] = {}
        
    def add_validation_rule(self, rule: Callable[[Dict[str, Any]], bool]) -> None:
        """Add a validation rule for events"""
        self.validation_rules.append(rule)
        
    def validate(self, event: PendingEvent) -> Dict[str, Any]:
        """
        Validate and certify an event.
        
        Args:
            event: Event to validate
            
        Returns:
            Certification result with validation details
        """
        certification = {
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
                    certification["validation_errors"].append(f"Validation rule failed: {rule.__name__}")
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
    def _validate_structure(event_data: Dict[str, Any]) -> bool:
        """Validate basic event structure"""
        if not isinstance(event_data, dict):
            return False
            
        # Check timestamp is reasonable
        timestamp = event_data.get("timestamp", 0)
        current_time = time.time()
        if abs(timestamp - current_time) > 3600:  # 1 hour tolerance
            return False
            
        return True
    
    def get_certification(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get certification result for an event"""
        return self.certified_events.get(event_id)


class BlockBuilder:
    """Builds blocks from ordered events"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize block builder.
        
        Args:
            config: Block building configuration
        """
        self.config = config
        self.block_size = config.get("block_size", 500)
        self.batch_timeout = config.get("batch_timeout", 2.0)  # seconds
        self.current_batch: List[PendingEvent] = []
        self.batch_start_time = time.time()
        
    def add_event(self, event: PendingEvent) -> Optional[Dict[str, Any]]:
        """
        Add event to current batch.
        
        Args:
            event: Certified event to add
            
        Returns:
            Complete block if batch is ready, None otherwise
        """
        self.current_batch.append(event)
        
        # Check if batch is ready
        if self._is_batch_ready():
            return self._create_block()
        
        return None
    
    def force_create_block(self) -> Optional[Dict[str, Any]]:
        """Force creation of block from current batch"""
        if not self.current_batch:
            return None
            
        return self._create_block()
    
    def _is_batch_ready(self) -> bool:
        """Check if current batch is ready for block creation"""
        # Check batch size
        if len(self.current_batch) >= self.block_size:
            return True
            
        # Check timeout
        if (time.time() - self.batch_start_time) >= self.batch_timeout:
            return True
            
        return False
    
    def _create_block(self) -> Optional[Dict[str, Any]]:
        """Create block from current batch"""
        if not self.current_batch:
            return None
            
        # Convert events to block format
        block_events: List[Dict[str, Any]] = []
        for pending_event in self.current_batch:
            block_events.append({
                **pending_event.event_data,
                "ordering_metadata": {
                    "event_id": pending_event.event_id,
                    "ordered_at": time.time(),
                    "channel_id": pending_event.channel_id,
                    "submitter_org": pending_event.submitter_org
                }
            })
        
        # Create block
        block: Dict[str, Any] = {
            "events": block_events,
            "event_count": len(block_events),
            "created_at": time.time(),
            "batch_info": {
                "batch_start": self.batch_start_time,
                "batch_duration": time.time() - self.batch_start_time,
                "events_processed": len(self.current_batch)
            }
        }
        
        # Calculate block hash
        block_data = json.dumps(block_events, sort_keys=True, separators=(',', ':'))
        block["hash"] = hashlib.sha256(block_data.encode()).hexdigest()
        
        # Reset batch
        self.current_batch.clear()
        self.batch_start_time = time.time()
        
        return block


class OrderingService:
    """
    Decoupled event ordering service for improved scalability.
    
    This service separates event ordering from consensus validation, enabling 
    higher throughput and reduced latency for enterprise-scale operations.
    """
    
    def __init__(self, nodes: List[OrderingNode], config: Dict[str, Any]):
        """
        Initialize ordering service.
        
        Args:
            nodes: List of ordering service nodes
            config: Service configuration parameters
        """
        self.nodes = {node.node_id: node for node in nodes}
        self.config = config
        self.status = OrderingStatus.ACTIVE
        
        # Event processing components
        self.event_pool: Queue = Queue()
        self.block_builder = BlockBuilder(config)
        self.commit_queue: Queue = Queue()
        self.certifier = EventCertifier()
        
        # Processing state
        self.pending_events: Dict[str, PendingEvent] = {}
        self.processed_events: Dict[str, PendingEvent] = {}
        self.blocks_created = 0
        self.events_processed = 0
        
        # Threading for concurrent processing
        self.processing_thread = None
        self.should_stop = threading.Event()
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.get("worker_threads", 4)
        )
        
        # Statistics
        self.statistics = {
            "events_received": 0,
            "events_certified": 0,
            "events_rejected": 0,
            "blocks_created": 0,
            "average_batch_size": 0,
            "average_processing_time": 0
        }
        
        # Initialize validation rules
        self._setup_default_validation_rules()
        
        # Start processing
        self.start()
    
    def receive_event(self, event_data: Dict[str, Any], channel_id: str, 
                     submitter_org: str) -> str:
        """
        Receive event from client or application channel.
        
        Args:
            event_data: Event data to order
            channel_id: Channel where event originated
            submitter_org: Organization submitting the event
            
        Returns:
            Event ID for tracking
        """
        # Generate unique event ID
        event_id = self._generate_event_id(event_data, channel_id)
        
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
    
    def get_event_status(self, event_id: str) -> Optional[Dict[str, Any]]:
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
    
    def get_next_block(self) -> Optional[Dict[str, Any]]:
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
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        healthy_nodes = [n for n in self.nodes.values() if n.is_healthy()]
        
        return {
            "status": self.status.value,
            "nodes": {
                "total": len(self.nodes),
                "healthy": len(healthy_nodes),
                "leader": next((n.node_id for n in self.nodes.values() if n.is_leader), None)
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
    
    def add_validation_rule(self, rule: Callable[[Dict[str, Any]], bool]) -> None:
        """Add custom validation rule for events"""
        self.certifier.add_validation_rule(rule)
    
    def start(self) -> None:
        """Start the ordering service"""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.should_stop.clear()
            self.processing_thread = threading.Thread(target=self._process_events)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            self.status = OrderingStatus.ACTIVE
    
    def stop(self) -> None:
        """Stop the ordering service"""
        self.should_stop.set()
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        self.executor.shutdown(wait=True)
        self.status = OrderingStatus.STOPPED
    
    def _process_events(self) -> None:
        """Main event processing loop"""
        while not self.should_stop.is_set():
            try:
                # Get event from queue with timeout
                try:
                    pending_event = self.event_pool.get(timeout=1.0)
                except Empty:
                    # Check for timeout-based block creation
                    self._check_timeout_block_creation()
                    continue
                
                # Process event
                self._process_single_event(pending_event)
                
            except Exception as e:
                print(f"Error in event processing: {str(e)}")
                # Continue processing other events
    
    def _process_single_event(self, pending_event: PendingEvent) -> None:
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
                
                # Add to block builder
                block = self.block_builder.add_event(pending_event)
                if block:
                    self._commit_block(block)
                    
                # Move to processed events
                self.processed_events[pending_event.event_id] = pending_event
                if pending_event.event_id in self.pending_events:
                    del self.pending_events[pending_event.event_id]
                    
            else:
                pending_event.status = EventStatus.REJECTED
                self.statistics["events_rejected"] += 1
                
        except Exception as e:
            pending_event.status = EventStatus.REJECTED
            pending_event.certification_result = {
                "valid": False,
                "error": str(e)
            }
            self.statistics["events_rejected"] += 1
    
    def _check_timeout_block_creation(self) -> None:
        """Check if a block should be created due to timeout"""
        block = self.block_builder.force_create_block()
        if block:
            self._commit_block(block)
    
    def _commit_block(self, block: Dict[str, Any]) -> None:
        """Commit a completed block to the commit queue"""
        # Add block metadata
        block["block_number"] = self.blocks_created
        block["ordering_service_id"] = list(self.nodes.keys())[0]  # Use first node ID
        block["committed_at"] = time.time()
        
        # Put in commit queue
        self.commit_queue.put(block)
        
        # Update statistics
        self.blocks_created += 1
        self.statistics["blocks_created"] = self.blocks_created
        self.statistics["average_batch_size"] = (
            (self.statistics["average_batch_size"] * (self.blocks_created - 1) + 
             block["event_count"]) / self.blocks_created
        )
    
    @staticmethod
    def _generate_event_id(event_data: Dict[str, Any], channel_id: str) -> str:
        """Generate unique event ID"""
        data = f"{channel_id}:{json.dumps(event_data, sort_keys=True)}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _setup_default_validation_rules(self) -> None:
        """Setup default validation rules"""
        def validate_non_empty_entity_id(event_data: Dict[str, Any]) -> bool:
            entity_id = event_data.get("entity_id", "")
            return isinstance(entity_id, str) and len(entity_id.strip()) > 0
        
        def validate_event_type(event_data: Dict[str, Any]) -> bool:
            event_type = event_data.get("event", "")
            return isinstance(event_type, str) and len(event_type.strip()) > 0
        
        def validate_timestamp_format(event_data: Dict[str, Any]) -> bool:
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