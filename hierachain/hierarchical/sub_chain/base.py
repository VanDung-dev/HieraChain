"""
SubChain class — domain-specific blockchain for HieraChain.
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
from hierachain.core.utils import create_event
from hierachain.consensus import OrderingService, OrderingNode, OrderingStatus
from hierachain.state.world_state import WorldState

from hierachain.hierarchical.sub_chain.proof import (
    _submit_proof_for_sub_chain,
    _connect_sub_chain_to_main,
)
from hierachain.hierarchical.sub_chain.block import (
    _finalize_sub_chain_block_for_chain,
    _process_and_finalize_single_block,
    _flush_pending_and_finalize_for_sub_chain,
    _consumer_loop,
    _force_block_creation,
)
from hierachain.hierarchical.sub_chain.ordering import (
    _sync_chain_for_sub_chain,
)
from hierachain.hierarchical.sub_chain.stats import (
    _get_domain_stats_summary,
)

logger = logging.getLogger(__name__)


class SubChain(Blockchain):
    """
    Sub-Chain implementation for the HieraChain Ledger.

    Sub-Chains act as domain experts (like department heads) and:
    - Handle domain-specific business operations
    - Store detailed domain events and data
    - Submit cryptographic proofs to Main Chain
    - Use entity_id as metadata field within events (not as block identifier)
    """
    __slots__ = (
        'domain_type', 'custom_config', 'node_identity',
        'consensus', 'main_chain_connection',
        'proof_submission_interval', 'last_proof_submission',
        'completed_operations', 'ordering_service', 'world_state',
        '_block_processing_lock', '_async_sync_lock', 'running',
        '_shutdown_event', 'consumer_thread',
    )

    def __init__(
        self,
        name: str,
        domain_type: str = "generic",
        config: dict[str, Any] | None = None,
        node_identity: Any | None = None,
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
        self.node_identity = node_identity

        # Dynamic Consensus Loading
        if settings.CONSENSUS_TYPE == "proof_of_federation":
            new_consensus = ProofOfFederation(f"{name}_PoF")
        else:
            new_consensus = ProofOfAuthority(f"{name}_PoA", block_interval=settings.BLOCK_INTERVAL)
        self.consensus: Any = new_consensus

        self.main_chain_connection: Any | None = None
        self.proof_submission_interval: float = 60.0
        self.last_proof_submission: float = time.time()
        self.completed_operations: int = 0

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

        self._init_ordering_service()

        if not self.ordering_service.get_latest_block():
            self.ordering_service.storage_handler.save_block(self.chain[0], self.name)
            logger.info("SubChain %s: Persisted genesis block to storage.", self.name)

        self.world_state = WorldState()

        self.ordering_service.wait_for_active(timeout=10.0)

        self.sync_chain()

        self._block_processing_lock = threading.Lock()
        self._async_sync_lock = threading.Lock()

        self.running = True
        self._shutdown_event = threading.Event()
        self.consumer_thread = threading.Thread(
            target=_consumer_loop, args=(self,), daemon=True
        )
        self.consumer_thread.start()

    def is_valid_new_block(self, block) -> bool:
        if not super().is_valid_new_block(block):
            return False
        previous_block = self.get_latest_block()
        if not self.consensus.validate_block(block, previous_block):
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

        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()

    @property
    def is_shutting_down(self) -> bool:
        return hasattr(self, '_shutdown_event') and self._shutdown_event.is_set()

    @property
    def block_processing_lock(self):
        return self._block_processing_lock

    def shutdown(self) -> None:
        """Shutdown the sub-chain and cleanup resources."""
        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2.0)
        if hasattr(self, "ordering_service"):
            self.ordering_service.shutdown()

    def _init_ordering_service(self):
        """Initialize the local Ordering Service for this Sub-Chain."""
        local_node = OrderingNode(
            node_id=f"{self.name}_orderer",
            endpoint="localhost",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )

        db_url = settings.DATABASE_URL
        db_dir = "data"
        if db_url.startswith("sqlite:///"):
            base_data_dir = os.path.realpath("data")
            safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", self.name)
            db_dir = os.path.normpath(os.path.join(base_data_dir, safe_name))

            if not db_dir.startswith(base_data_dir):
                raise ValueError("Invalid SubChain name: path traversal detected")
            os.makedirs(db_dir, exist_ok=True)
            db_url = f"sqlite:///{db_dir}/hierachain.db"

        default_config = {
            "storage_dir": os.path.join(db_dir, "journal"),
            "block_size": 50,
            "batch_timeout": 1.0,
            "worker_threads": 2,
            "db_url": db_url,
            "chain_name": self.name,
        }

        config = default_config.copy()
        if hasattr(self, "custom_config") and self.custom_config:
            config.update(self.custom_config)

        self.ordering_service = OrderingService(nodes=[local_node], config=config, node_identity=self.node_identity)

    def add_event(self, event: dict[str, Any]) -> str:
        """Add event to Sub-Chain."""
        if "timestamp" not in event:
            event["timestamp"] = time.time()

        if "entity_id" not in event:
            event["entity_id"] = event.get("sender", "system")
        if "event" not in event:
            event["event"] = event.get("type", "generic_event")

        logger.debug("SubChain %s adding event: %s", self.name, event.get("event"))

        self.ordering_service.receive_event(
            event_data=event, channel_id=self.name, submitter_org=self.name
        )

        with self.lock:
            if event not in self.pending_events:
                self.pending_events.append(event)

        return f"tx-{hash(str(event))}"

    def connect_to_main_chain(self, main_chain: Any) -> bool:
        return _connect_sub_chain_to_main(self, main_chain)

    def start_operation(
        self,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
        event = create_event(
            entity_id=entity_id,
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
        event = create_event(
            entity_id=entity_id,
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
        event = create_event(
            entity_id=entity_id,
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
        return _submit_proof_for_sub_chain(self, main_chain, metadata_filter)

    def should_submit_proof(self) -> bool:
        current_time = time.time()
        time_since_last = current_time - self.last_proof_submission

        has_pending = False
        if hasattr(self, 'ordering_service'):
            has_pending = len(self.ordering_service.pending_events) > 0

        return time_since_last >= self.proof_submission_interval and has_pending

    def auto_submit_proof_if_needed(self) -> bool:
        if self.should_submit_proof() and self.main_chain_connection:
            return self.submit_proof_to_main(self.main_chain_connection)
        return False

    def get_entity_history(self, entity_id: str) -> list[dict[str, Any]]:
        entity_events = self.get_events_by_entity(entity_id)
        entity_events.sort(key=lambda x: x.get("timestamp", 0))
        return entity_events

    def get_domain_statistics(self) -> dict[str, Any]:
        base_stats = self.get_chain_stats()
        domain_summary = _get_domain_stats_summary(
            self.chain, self.domain_type, self.completed_operations, sub_chain=self
        )

        return {
            **base_stats,
            **domain_summary,
            "main_chain_connected": self.main_chain_connection is not None,
            "last_proof_submission": self.last_proof_submission,
            "proof_submission_interval": self.proof_submission_interval,
        }

    def finalize_sub_chain_block(self) -> dict[str, Any] | None:
        with self._async_sync_lock:
            return _finalize_sub_chain_block_for_chain(self)

    def _process_and_finalize_block(self, block: Any) -> bool:
        return _process_and_finalize_single_block(self, block)

    def flush_pending_and_finalize(self, timeout: float = 3.0) -> dict[str, Any] | None:
        return _flush_pending_and_finalize_for_sub_chain(self, timeout)

    def _force_ordering_block_creation(self, timeout: float) -> None:
        _force_block_creation(self.ordering_service, timeout)

    def sync_chain(self):
        _sync_chain_for_sub_chain(self)

    def __str__(self) -> str:
        return (
            f"SubChain(name={self.name}, domain={self.domain_type}, "
            f"blocks={len(self.chain)}, "
            f"operations={self.completed_operations})"
        )

    def __repr__(self) -> str:
        return (
            f"SubChain(name={self.name}, domain_type={self.domain_type}, "
            f"blocks={len(self.chain)}, "
            f"operations={self.completed_operations}, "
            f"main_chain_connected={self.main_chain_connection is not None})"
        )
