"""
Sub-Chain implementation for HieraChain Ledger.

This module implements the Sub-Chain class that handles domain-specific
business operations and submits proofs to the Main Chain, following
Ledger guidelines for HieraChain structure.
"""

import time
import threading
import logging
import re
import os
from typing import Any, Callable

from hierachain.core.blockchain import Blockchain
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.consensus.proof_of_federation import ProofOfFederation
from hierachain.config.settings import settings
from hierachain.core.utils import sanitize_metadata_for_main_chain, create_event
from hierachain.consensus import OrderingService, OrderingNode, OrderingStatus
from hierachain.security.zk_prover import ZKProver

logger = logging.getLogger(__name__)


def _generate_zk_proof(name: str, chain: list[Any], latest_block: Any) -> bytes | None:
    """Generate ZK proof for the latest block transition with retries."""
    if not settings.ENABLE_ZK_PROOFS:
        return None

    # Get state roots for ZK proof
    previous_block = chain[-2] if len(chain) > 1 else None
    old_state_root = previous_block.merkle_root if previous_block else "genesis"
    new_state_root = latest_block.merkle_root or latest_block.hash

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Generate ZK proof
            prover = ZKProver(mode=settings.ZK_MODE)
            result = prover.generate_proof(
                old_state_root=old_state_root,
                new_state_root=new_state_root,
                block_index=latest_block.index,
                events=latest_block.to_event_list()
                if hasattr(latest_block, "to_event_list")
                else [],
                sub_chain_name=name,
            )

            if result.success:
                logger.info(
                    "Generated ZK proof for block %d in %.2fms (Attempt %d/%d)",
                    latest_block.index, result.generation_time_ms, attempt + 1, max_attempts
                )
                return result.proof

            logger.warning(
                "ZK proof generation failed for block %d on attempt %d/%d: %s",
                latest_block.index, attempt + 1, max_attempts, result.error,
            )
            
            if attempt < max_attempts - 1:
                time.sleep(1.0 * (attempt + 1))  # Exponential-ish backoff

        except Exception as e:
            logger.error(
                "ZK proof generation error for block %d on attempt %d/%d: %s",
                latest_block.index, attempt + 1, max_attempts, e,
            )
            if attempt < max_attempts - 1:
                time.sleep(1.0 * (attempt + 1))
            
    logger.error("Failed to generate ZK proof for block %d after %d attempts", latest_block.index, max_attempts)
    return None


def _generate_default_proof_metadata(
    chain: list[Any],
    domain_type: str,
    latest_block_index: int,
    completed_ops: int
) -> dict[str, Any]:
    """Generate default proof metadata for Main Chain submission."""
    # Count different event types in recent blocks
    recent_events: list[dict[str, Any]] = []
    for block in chain[-5:]:  # Last 5 blocks
        # Use to_event_list() if available to handle Arrow Tables
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        recent_events.extend(events)

    event_counts: dict[str, int] = {}
    entity_count = set()

    for event in recent_events:
        event_type = event.get("event", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

        if event.get("entity_id") is not None:
            entity_count.add(event["entity_id"])

    # Create summary metadata (following guidelines)
    metadata = {
        "domain_type": domain_type,
        "latest_block_index": latest_block_index,
        "total_blocks": len(chain),
        "recent_events": len(recent_events),
        "unique_entities": len(entity_count),
        "completed_operations": completed_ops,
        "event_types": list(event_counts.keys()),
        "proof_timestamp": time.time(),
    }

    return sanitize_metadata_for_main_chain(metadata)


def _get_domain_stats_summary(
    chain: list[Any],
    domain_type: str,
    completed_ops: int
) -> dict[str, Any]:
    """Calculate domain-specific statistics summary."""
    # Count entities and operations
    all_events: list[dict[str, Any]] = []
    for block in chain:
        # Use to_event_list() if available to handle Arrow Tables
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        all_events.extend(events)

    unique_entities = set()
    operation_types: dict[str, int] = {}

    for event in all_events:
        if event.get("entity_id") is not None:
            unique_entities.add(event["entity_id"])

        event_type = event.get("event", "unknown")
        operation_types[event_type] = operation_types.get(event_type, 0) + 1

    return {
        "domain_type": domain_type,
        "unique_entities": len(unique_entities),
        "completed_operations": completed_ops,
        "operation_types": operation_types,
    }


def _force_block_creation(ordering_service: Any, timeout: float) -> None:
    """Force the ordering service to create a block from pending events."""
    try:
        ordering_service.force_block_creation(timeout=timeout)
    except Exception as e:
        logger.error("Error forcing block creation: %s", e)


def _consumer_loop(sub_chain: Any) -> None:
    """Background loop to continuously pull and finalize blocks."""
    while sub_chain.running:
        try:
            # Attempt to finalize blocks
            sub_chain.finalize_sub_chain_block()
            time.sleep(0.5)
        except Exception as e:
            logger.error("Error in block consumer loop: %s", e)
            time.sleep(1.0)


def _update_local_state_after_proof(
    sub_chain: Any,
    main_chain: Any,
    latest_block: Any,
    zk_proof: bytes | None
) -> None:
    """Update local state after successful proof submission."""
    sub_chain.last_proof_submission = time.time()

    # Create proof submission event in Sub-Chain
    proof_event = {
        "entity_id": sub_chain.name,
        "event": "proof_submitted",
        "timestamp": time.time(),
        "details": {
            "main_chain_name": getattr(main_chain, "name", str(main_chain)),
            "proof_hash": latest_block.hash,
            "block_index": latest_block.index,
            "submitted_at": time.time(),
            "zk_proof_included": zk_proof is not None,
        },
    }

    sub_chain.add_event(proof_event)


def _wait_for_growth(initial_len: int, chain: list[Any], timeout: float) -> bool:
    """Wait for the chain length to increase."""
    wait_start = time.time()
    while len(chain) == initial_len:
        if time.time() - wait_start > timeout:
            logger.warning("Timeout waiting for block to appear in chain")
            return False
        time.sleep(0.1)
    return True


def _connect_sub_chain_to_main(sub_chain: "SubChain", main_chain: Any) -> bool:
    """Connect a Sub-Chain to the Main Chain."""
    try:
        metadata = {
            "domain_type": sub_chain.domain_type,
            "sub_chain_name": sub_chain.name,
            "connected_at": time.time(),
            "capabilities": ["domain_operations", "proof_submission"],
        }

        if main_chain.register_sub_chain(sub_chain.name, metadata):
            sub_chain.main_chain_connection = main_chain

            connection_event = {
                "entity_id": sub_chain.name,
                "event": "main_chain_connection",
                "timestamp": time.time(),
                "details": {
                    "main_chain_name": getattr(main_chain, "name", str(main_chain)),
                    "connected_at": time.time(),
                    "status": "connected",
                },
            }

            sub_chain.add_event(connection_event)
            return True
    except (AttributeError, TypeError, ValueError):
        return False

    return False


def _submit_proof_for_sub_chain(
    sub_chain: "SubChain",
    main_chain: Any,
    metadata_filter: Callable | None,
) -> bool:
    """Submit a cryptographic proof to the Main Chain."""
    latest_block = sub_chain.get_latest_block()
    logger.debug(
        "SubChain %s submitting proof. "
        "Chain length: %d. Block index: %d",
        sub_chain.name, len(sub_chain.chain), latest_block.index,
    )

    if not sub_chain.chain or len(sub_chain.chain) <= 1:
        logger.debug("SubChain has only genesis block. Aborting proof.")
        return False

    metadata = (
        metadata_filter(sub_chain)
        if metadata_filter
        else _generate_default_proof_metadata(
            sub_chain.chain,
            sub_chain.domain_type,
            latest_block.index,
            sub_chain.completed_operations,
        )
    )

    zk_proof = _generate_zk_proof(sub_chain.name, sub_chain.chain, latest_block)
    if zk_proof is None and settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
        return False

    success = main_chain.add_proof(
        sub_chain_name=sub_chain.name,
        proof_hash=latest_block.hash,
        metadata=metadata,
        zk_proof=zk_proof,
    )
    logger.debug("MainChain.add_proof returned: %s", success,)

    if success:
        _update_local_state_after_proof(sub_chain, main_chain, latest_block, zk_proof)

    return success


def _process_and_finalize_single_block(sub_chain: "SubChain", block: Any) -> bool:
    """Process and finalize a single block."""
    latest_block = sub_chain.get_latest_block()

    block.index = latest_block.index + 1
    block.previous_hash = latest_block.hash

    block.hash = block.calculate_hash()

    finalized_block = sub_chain.consensus.finalize_block(block, sub_chain.name)

    if sub_chain.add_block(finalized_block):
        sub_chain.auto_submit_proof_if_needed()
        return True

    logger.error("Failed to add ordered block %d", block.index)
    return False


def _finalize_sub_chain_block_for_chain(sub_chain: "SubChain") -> dict[str, Any] | None:
    """Finalize and return a block for the Main Chain."""
    new_blocks: list[Any] = []

    while True:
        block = sub_chain.ordering_service.get_next_block()
        if not block:
            logger.debug(
                "No block from get_next_block. Queue %d empty.",
                id(sub_chain.ordering_service.commit_queue),
            )
            break

        logger.debug(
            f"Got block {block.index} from ordering service. "
            f"Queue {id(sub_chain.ordering_service.commit_queue)}"
        )

        if _process_and_finalize_single_block(sub_chain, block):
            new_blocks.append(block)

    if not new_blocks:
        return None

    last_block = new_blocks[-1]
    return {
        "block_index": last_block.index,
        "block_hash": last_block.hash,
        "events_count": len(last_block.events),
        "finalized_at": time.time(),
        "domain_type": sub_chain.domain_type,
    }


def _flush_pending_and_finalize_for_sub_chain(
    sub_chain: "SubChain", timeout: float
) -> dict[str, Any] | None:
    """Flush pending events and finalize the block."""
    logger.debug("flush_pending_and_finalize for %s", sub_chain.name)
    start_time = time.time()

    while not sub_chain.ordering_service.event_pool.empty():
        if time.time() - start_time > timeout:
            break

    initial_len = len(sub_chain.chain)

    _force_block_creation(sub_chain.ordering_service, timeout)

    result = _finalize_sub_chain_block_for_chain(sub_chain)
    if result:
        return result

    if _wait_for_growth(initial_len, sub_chain.chain, timeout):
        last_block = sub_chain.chain[-1]
        return {
            "block_index": last_block.index,
            "block_hash": last_block.hash,
            "events_count": len(last_block.events),
            "finalized_at": time.time(),
            "domain_type": sub_chain.domain_type,
        }
    return None


def _rehydrate_chain_from_ordering_service(
    sub_chain: "SubChain", _latest_block_os: Any
) -> None:
    """Rehydrate the local chain from the Ordering Service."""
    all_blocks = (
        sub_chain.ordering_service.storage_handler.get_blocks_from_db(start_index=0)
    )

    if not all_blocks:
        return

    # Check if local chain needs rehydration
    latest_local = sub_chain.get_latest_block()

    # If local chain already has more or equal blocks, skip rehydration
    if latest_local.index >= all_blocks[-1].index:
        logger.info(
            "Chain %s already up to date. Local index: %d, DB index: %d",
            sub_chain.name, latest_local.index, all_blocks[-1].index,
        )
        return

    logger.info(
        "Rehydrating chain %s from index %d to %d",
        sub_chain.name, latest_local.index, all_blocks[-1].index,
    )

    # Map out the temporary index to save events occurring during rehydration
    with sub_chain.lock:
        temp_entity_index = dict(sub_chain.entity_event_index)

        # Clear the locally created chain (including the newly created genesis block)
        sub_chain.chain.clear()
        sub_chain.total_events = 0
        sub_chain.event_type_counts.clear()
        sub_chain.entity_event_index.clear()

        # Add all blocks from DB to the chain with proper indexing
        for block in all_blocks:
            sub_chain.chain.append(block)
            _update_event_statistics(sub_chain, block)
            
        # Restore events added during rehydration
        for entity_id, events in temp_entity_index.items():
            if entity_id not in sub_chain.entity_event_index:
                sub_chain.entity_event_index[entity_id] = events

        # Also update the ordering service's block_history and blocks_created to match
        sub_chain.ordering_service.block_history = list(sub_chain.chain)
        sub_chain.ordering_service.blocks_created = all_blocks[-1].index + 1

    logger.info(
        "Rehydrated %d blocks from Ordering Service. Latest index: %d",
        len(all_blocks), all_blocks[-1].index if all_blocks else 0,
    )


def _update_event_statistics(sub_chain: "SubChain", block: Any) -> None:
    """Update event statistics for a block during rehydration."""
    events = (
        block.to_event_list()
        if hasattr(block, "to_event_list")
        else block.events
    )
    sub_chain.total_events += len(events)

    for event in events:
        etype = event.get("event", "unknown")
        sub_chain.event_type_counts[etype] = (
            sub_chain.event_type_counts.get(etype, 0) + 1
        )

        entity_id = event.get("entity_id")
        if entity_id:
            if entity_id not in sub_chain.entity_event_index:
                sub_chain.entity_event_index[entity_id] = []
            sub_chain.entity_event_index[entity_id].append({
                "block_index": block.index,
                "event": event,
            })


def _reset_ordering_service_state(sub_chain: "SubChain") -> None:
    """Reset the Ordering Service state."""
    latest_local = sub_chain.get_latest_block()
    sub_chain.ordering_service.block_history = list(sub_chain.chain)
    sub_chain.ordering_service.blocks_created = latest_local.index + 1
    logger.info(
        "Reset ordering service state: blocks_created = %d",
        sub_chain.ordering_service.blocks_created,
    )


def _sync_chain_for_sub_chain(sub_chain: "SubChain") -> None:
    """Synchronize local chain with Ordering Service (Rehydration)."""
    try:
        latest_block_os = sub_chain.ordering_service.get_latest_block()
        _rehydrate_chain_from_ordering_service(sub_chain, latest_block_os)
        _reset_ordering_service_state(sub_chain)
    except Exception as e:
        logger.error("Sync failed: %s", e)


class SubChain(Blockchain):
    """
    Sub-Chain implementation for the HieraChain Ledger.

    Sub-Chains act as domain experts (like department heads) and:
    - Handle domain-specific business operations
    - Store detailed domain events and data
    - Submit cryptographic proofs to Main Chain
    - Use entity_id as metadata field within events (not as block identifier)
    """

    def __init__(
        self,
        name: str,
        domain_type: str = "generic",
        config: dict[str, Any] | None = None,
    ):
        """Initialize a Sub-Chain."""
        if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
            raise ValueError(
                f"Invalid SubChain name '{name}'. "
                "Allowed: alphanumeric, underscore, hyphen."
            )

        super().__init__(name)
        self.domain_type = domain_type
        self.custom_config = config

        # Dynamic Consensus Loading
        if settings.CONSENSUS_TYPE == "proof_of_federation":
            new_consensus = ProofOfFederation(f"{name}_PoF")
        else:
            new_consensus = ProofOfAuthority(f"{name}_PoA")
        self.consensus: Any = new_consensus

        self.main_chain_connection: Any | None = None
        self.proof_submission_interval: float = 60.0  # Submit proofs every 60 seconds
        self.last_proof_submission: float = 0.0
        self.completed_operations: int = 0

        # Register Sub-Chain as authority for its own operations
        if hasattr(self.consensus, "add_authority"):
            self.consensus.add_authority(
                name,
                {
                    "role": "sub_chain_authority",
                    "domain_type": domain_type,
                    "permissions": ["domain_operations", "event_creation"],
                    "created_at": time.time(),
                },
            )

        # Initialize Ordering Service
        self._init_ordering_service()

        if not self.ordering_service.get_latest_block():
            self.ordering_service.storage_handler.save_block(self.chain[0], self.name)
            logger.info("SubChain %s: Persisted genesis block to storage.", self.name)

        # Wait for ordering service to become ACTIVE
        self.ordering_service.wait_for_active(timeout=10.0)

        self.sync_chain()

        # Start Block Consumer Thread
        self.running = True
        self.consumer_thread = threading.Thread(
            target=_consumer_loop, args=(self,), daemon=True
        )
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
            logger.warning("Consensus validation failed for block %d", block.index)
            return False

        return True

    def stop(self):
        """Stop the background block consumer."""
        try:
            while not self.ordering_service.commit_queue.empty():
                block = self.ordering_service.commit_queue.get_nowait()
                _process_and_finalize_single_block(self, block)
        except Exception as e:
            logger.warning("Error draining commit_queue during stop: %s", e)

        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2.0)

        # Also stop ordering service
        if hasattr(self, "ordering_service"):
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

        # Configure unique database URL if using default SQLite
        db_url = settings.DATABASE_URL
        db_dir = "data"
        if db_url.startswith("sqlite:///"):
            base_data_dir = os.path.realpath("data")
            safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", self.name)
            db_dir = os.path.join(base_data_dir, safe_name)

            if not os.path.realpath(db_dir).startswith(base_data_dir + os.sep):
                raise ValueError(f"Invalid SubChain name: path traversal detected")
            os.makedirs(db_dir, exist_ok=True)
            db_url = f"sqlite:///{db_dir}/hierachain.db"

        # Service configuration
        default_config = {
            "storage_dir": os.path.join(db_dir, "journal"),
            "block_size": 50,  # Smaller batches for lower latency in demo
            "batch_timeout": 1.0,
            "worker_threads": 2,
            "db_url": db_url,
            "chain_name": self.name,
        }

        # Merge defaults with custom config if provided
        config = default_config.copy()
        if hasattr(self, "custom_config") and self.custom_config:
            config.update(self.custom_config)

        self.ordering_service = OrderingService(nodes=[local_node], config=config)

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

        logger.debug("SubChain %s adding event: %s", self.name, event.get("event"))
        
        # Send to OrderingService first
        self.ordering_service.receive_event(
            event_data=event, channel_id=self.name, submitter_org=self.name
        )
        
        # Also add to Blockchain.pending_events for compatibility
        with self.lock:
            if event not in self.pending_events:
                self.pending_events.append(event)

        return f"tx-{hash(str(event))}"

    def connect_to_main_chain(self, main_chain: Any) -> bool:
        """
        Connect this Sub-Chain to a Main Chain.

        Args:
            main_chain: Main Chain instance to connect to

        Returns:
            True if connection was successful, False otherwise
        """
        return _connect_sub_chain_to_main(self, main_chain)

    def start_operation(
        self,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
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

    def complete_operation(
        self,
        entity_id: str,
        operation_type: str,
        result: dict[str, Any] | None = None,
    ) -> bool:
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

    def update_entity_status(
        self, entity_id: str, status: str, details: dict[str, Any] | None = None
    ) -> bool:
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

    def submit_proof_to_main(
        self, main_chain: Any, metadata_filter: Callable | None = None
    ) -> bool:
        """Submit cryptographic proof to Main Chain."""
        return _submit_proof_for_sub_chain(self, main_chain, metadata_filter)

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

        return time_since_last >= self.proof_submission_interval and has_pending

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
        """Get comprehensive statistics about this Sub-Chain's domain operations."""
        base_stats = self.get_chain_stats()
        domain_summary = _get_domain_stats_summary(
            self.chain, self.domain_type, self.completed_operations
        )

        return {
            **base_stats,
            **domain_summary,
            "main_chain_connected": self.main_chain_connection is not None,
            "last_proof_submission": self.last_proof_submission,
            "proof_submission_interval": self.proof_submission_interval,
        }

    def finalize_sub_chain_block(self) -> dict[str, Any] | None:
        """Pull ordered blocks from Ordering Service and finalize them."""
        return _finalize_sub_chain_block_for_chain(self)

    def _process_and_finalize_block(self, block: Any) -> bool:
        """Process, finalize and add a single block to the local chain."""
        return _process_and_finalize_single_block(self, block)

    def flush_pending_and_finalize(self, timeout: float = 3.0) -> dict[str, Any] | None:
        """Flush pending events and finalize the block."""
        return _flush_pending_and_finalize_for_sub_chain(self, timeout)

    def _force_ordering_block_creation(self, timeout: float) -> None:
        """Force the ordering service to create a block from pending events."""
        _force_block_creation(self.ordering_service, timeout)

    def sync_chain(self):
        """
        Synchronize local chain with Ordering Service (Rehydration).
        Fetch missing blocks from history.
        """
        _sync_chain_for_sub_chain(self)

    def __str__(self) -> str:
        """String representation of the Sub-Chain."""
        return (
            f"SubChain(name={self.name}, domain={self.domain_type}, "
            f"blocks={len(self.chain)}, "
            f"operations={self.completed_operations})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the Sub-Chain."""
        return (
            f"SubChain(name={self.name}, domain_type={self.domain_type}, "
            f"blocks={len(self.chain)}, "
            f"operations={self.completed_operations}, "
            f"main_chain_connected={self.main_chain_connection is not None})"
        )
