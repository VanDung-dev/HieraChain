"""
Ordering service for the HieraChain.
Coordinates between specialized components to provide ordering functionality.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

from hierachain.config.settings import Settings
from hierachain.consensus.ordering import admission, idempotency
from hierachain.consensus.ordering.block_builder import BlockBuilder
from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.journal_lookup import JournalEventLookup
from hierachain.consensus.ordering.lifecycle import OrderingLifecycleMixin
from hierachain.consensus.ordering.maintenance import OrderingMaintenance
from hierachain.consensus.ordering.metrics import OrderingMetrics
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.consensus.ordering.types import (
    EventStatus,
    OrderingStatus,
    PendingEvent,
)
from hierachain.consensus.ordering.utils import generate_event_id, make_serializable
from hierachain.core.block import Block
from hierachain.error_mitigation.journal import EventJournal

logger = logging.getLogger(__name__)


class OrderingService(OrderingLifecycleMixin):
    """
    Facade for the Ordering Service package.
    Coordinates between specialized components to provide ordering functionality.
    """
    def __init__(
        self,
        config: dict[str, Any],
        nodes: list[Any] | None = None,
        node_identity: Any | None = None,
        genesis_block: Block | None = None,
        block_finalizer: Callable[[Block, Block | None], Block] | None = None,
        retain_bootstrap: bool = False,
    ):
        self.config = config
        self.enqueue_timeout = float(config.get("enqueue_timeout", 1.0))
        if not 0 < self.enqueue_timeout <= 60:
            raise ValueError("enqueue_timeout must be between 0 and 60 seconds")
        self.block_finalizer = block_finalizer
        self.nodes = nodes or []
        from hierachain.security.identity_loader import require_block_identity

        self.node_identity, self.trusted_public_keys = require_block_identity(
            node_identity, config.get("trusted_public_keys")
        )
        self.config["trusted_public_keys"] = self.trusted_public_keys
        self._commit_lock = threading.RLock()
        self._status = OrderingStatus.MAINTENANCE
        self.should_stop = threading.Event()
        self.event_pool: Queue[PendingEvent] = Queue(
            maxsize=Settings.EVENT_POOL_MAX_SIZE
        )
        self.pending_events: dict[str, PendingEvent] = {}
        self.commit_queue: Queue[Block] = Queue()
        self.processing_thread: threading.Thread | None = None

        # Component Initialization
        self.metrics = OrderingMetrics()
        self.storage_handler = OrderingStorageHandler(config)

        # Initialize blocks_created from DB to ensure continuity after restart
        # Verify links before journal replay can append to a damaged chain.
        try:
            persisted_blocks = self.storage_handler.get_blocks_from_db(0)
            latest_block = self.storage_handler.get_latest_block_from_db()
            if latest_block is not None and (
                not persisted_blocks or persisted_blocks[-1].hash != latest_block.hash
            ):
                raise ValueError("Persisted chain is incomplete or changed during ordering startup")
        except Exception:
            self.storage_handler.close()
            raise
        if latest_block is None and genesis_block is not None:
            self.storage_handler.save_block(
                genesis_block, self.storage_handler.chain_name
            )
            latest_block = genesis_block
            persisted_blocks = [genesis_block]
        if latest_block:
            self.storage_handler.last_block = latest_block
        self.blocks_created = (latest_block.index + 1) if latest_block else 0
        self._bootstrap_blocks: list[Block] | None = persisted_blocks if retain_bootstrap else None
        logger.info(
            "Initialized ordering service state: blocks_created=%s",
            self.blocks_created
        )

        # Configure journal based on storage_dir and node_id for persistence
        storage_dir = config.get("storage_dir", "journal")
        node_id = nodes[0].node_id if nodes else "unknown"
        active_log_name = f"node_{node_id}_journal.arrow"
        self.journal = EventJournal(
            storage_dir=storage_dir, active_log_name=active_log_name
        )
        self._journal_lookup = JournalEventLookup(
            self.journal, idempotency.event_content_fingerprint
        )

        batch_timeout = config.get("batch_timeout", 2.0)
        if not isinstance(batch_timeout, (int, float)) or not (0.1 <= batch_timeout <= 60.0):
            logger.warning(
                "Invalid batch_timeout %s, using default 2.0. Must be between 0.1 and 60.0",
                batch_timeout
            )
            batch_timeout = 2.0
        self.config["batch_timeout"] = batch_timeout

        self.certifier = EventCertifier()
        self.block_builder = BlockBuilder(self.config)

        # Complex Logic Handlers
        self.processor = OrderingProcessor(self)
        self.maintenance = OrderingMaintenance(self)

        # The processor replays the journal in recover_state_async().
        self._start_processing_thread()

    def receive_event(
        self, event_data: dict[str, Any], channel_id: str, submitter_org: str
    ) -> str:
        """Submit a new event for ordering"""
        if self.status == OrderingStatus.MAINTENANCE:
            self.wait_for_active()

        if self.status != OrderingStatus.ACTIVE:
            status_str = self.status.value
            raise RuntimeError(f"Ordering service is in {status_str} mode")

        # Validate event_data is a dictionary
        if not isinstance(event_data, dict):
            raise ValueError(  # noqa: TRY004 - preserve the existing API error contract
                f"event_data must be a dictionary, got {type(event_data).__name__}"
            )

        self.metrics.record_received()
        # Snapshot before deriving an ID or publishing to the queue. Nested
        # caller mutations must not change the journal/block payload later.
        enriched_data = make_serializable(copy.deepcopy(event_data))
        supplied_event_id = enriched_data.get("event_id")
        if supplied_event_id is not None:
            if not isinstance(supplied_event_id, str) or not supplied_event_id.strip():
                raise ValueError("event_id must be a non-empty string when supplied")
            event_id = supplied_event_id
            existing_kind, journal_row = self._find_stable_event(
                event_id, channel_id, enriched_data
            )
            if existing_kind in {"pending", "batch", "processed", "stored"}:
                return event_id
            if existing_kind == "journal":
                if journal_row is None:
                    raise ValueError(f"Missing journal record for event ID {event_id}")
                # A prior journal append may have succeeded before the caller
                # lost its acknowledgement. Requeue that exact durable record.
                journal_body = idempotency.event_body_from_journal(journal_row)
                pending_event = PendingEvent(
                    event_id=event_id,
                    event_data=journal_body,
                    channel_id=channel_id,
                    submitter_org=submitter_org,
                    received_at=time.time(),
                    status=EventStatus.PENDING,
                )
                self._enqueue_event(pending_event)
                return event_id
        else:
            event_id = generate_event_id(enriched_data, channel_id)
        enriched_data["event_id"] = event_id

        pending_event = PendingEvent(
            event_id=event_id,
            event_data=enriched_data,
            channel_id=channel_id,
            submitter_org=submitter_org,
            received_at=time.time(),
            status=EventStatus.PENDING
        )

        logged_data = {**enriched_data, "channel_id": channel_id}
        self._enqueue_event(pending_event, logged_data)

        return event_id

    def _find_stable_event(
        self,
        event_id: str,
        channel_id: str,
        candidate_data: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Find an existing stable ID and validate its content across all tiers."""
        return idempotency.find_stable_event(
            self, event_id, channel_id, candidate_data
        )

    def _enqueue_event(self, event: PendingEvent, journal_data: dict[str, Any] | None = None) -> None:
        """Reserve queue capacity before the durable write, then publish atomically."""
        return admission.enqueue_event(self, event, journal_data)

    def reconcile_journal_event(self, event_data: dict[str, Any]) -> str:
        """Requeue a durable journal event without appending a second copy."""
        if not isinstance(event_data, dict):
            raise ValueError("event_data must be a dictionary")

        snapshot = make_serializable(copy.deepcopy(event_data))
        event_id = snapshot.get("event_id")
        channel_id = snapshot.get("channel_id")
        if (
            not isinstance(event_id, str)
            or not event_id.strip()
            or not isinstance(channel_id, str)
            or not channel_id.strip()
        ):
            raise ValueError("journal event must contain event_id and channel_id")

        existing_kind, journal_row = self._find_stable_event(
            event_id, channel_id, snapshot
        )
        if existing_kind in {"pending", "batch", "processed", "stored"}:
            return event_id
        if existing_kind != "journal" or journal_row is None:
            raise ValueError(f"Event ID {event_id} is not present in the journal")

        if self.status != OrderingStatus.ACTIVE:
            raise RuntimeError(
                f"Ordering service is in {self.status.value} mode"
            )

        pending_event = PendingEvent(
            event_id=event_id,
            event_data=idempotency.event_body_from_journal(journal_row),
            channel_id=channel_id,
            submitter_org="recovery",
            received_at=time.time(),
            status=EventStatus.PENDING,
        )
        self._enqueue_event(pending_event)

        return event_id

    def get_latest_block(self) -> Block | None:
        """Retrieve the latest block for the current chain"""
        return self.storage_handler.get_latest_block_from_db()

    def take_bootstrap_blocks(self) -> list[Block] | None:
        """Transfer the verified startup snapshot once; later syncs read storage."""
        with self._commit_lock:
            blocks, self._bootstrap_blocks = self._bootstrap_blocks, None
            return blocks

    def get_blocks(self, start_index: int = 0) -> list[Block]:
        """Retrieve blocks starting from index"""
        return self.storage_handler.get_blocks(start_index)

    def get_next_block(self, timeout: float | None = None) -> Block | None:
        """Get next committed block from queue"""
        try:
            return (
                self.commit_queue.get(timeout=timeout)
                if timeout else self.commit_queue.get_nowait()
            )
        except Empty:
            return None

    @property
    def block_history(self):
        return self.storage_handler.block_history

    @block_history.setter
    def block_history(self, value):
        self.storage_handler.block_history = value

    def get_statistics(self) -> dict[str, Any]:
        """Get current service metrics"""
        return self.metrics.get_stats()

    def force_block_creation(self, timeout: float = 3.0) -> None:
        """
        Force the creation of a block from pending events.

        Args:
            timeout: Maximum time to wait for completion.
        """
        if not hasattr(self, "loop") or not self.loop.is_running():
            logger.warning(
                "Ordering service loop NOT running. Cannot force block creation."
            )
            return

        future = asyncio.run_coroutine_threadsafe(
            self.processor.force_process_batch_async(),
            self.loop
        )
        try:
            future.result(timeout=timeout)
            logger.debug(
                "Forced block creation completed. QM=%s BC=%s",
                self.commit_queue.qsize(),
                self.blocks_created
            )
        except TimeoutError as e:
            logger.error(f"Error forcing block creation: {e}")

    def lockdown(self, reason: str = "Manual lockdown") -> bool:
        """Enter lockdown mode"""
        return self.maintenance.lockdown(reason)

    def resume(self) -> bool:
        """Resume from lockdown/maintenance"""
        return self.maintenance.resume()

    def flush_pool(self) -> int:
        """Emergency clear of event pool"""
        return self.maintenance.flush_pool()

    def get_service_status(self) -> dict[str, Any]:
        """Get comprehensive service status information"""
        healthy_nodes = sum(1 for n in self.nodes if n.is_healthy())
        leader_node = next((n.node_id for n in self.nodes if n.is_leader), None)

        return {
            "status": str(self.status.value),
            "nodes": {
                "total": len(self.nodes),
                "healthy": healthy_nodes,
                "leader": leader_node
            },
            "queues": {
                "pending_events": len(self.pending_events),
                "event_pool_size": self.event_pool.qsize(),
                "commit_queue_size": self.commit_queue.qsize()
            },
            "blocks_created": self.blocks_created,
            "configuration": {
                "block_size": self.config.get("block_size", 500),
                "batch_timeout": self.config.get("batch_timeout", 2.0),
                "worker_threads": self.config.get("worker_threads", 4)
            },
            "statistics": self.metrics.get_stats()
        }

    def get_event_status(self, event_id: str) -> dict[str, Any] | None:
        """Get the status of a specific event"""
        # Check pending events first
        if event_id in self.pending_events:
            pending = self.pending_events[event_id]
            return {
                "event_id": event_id,
                "status": str(pending.status.value),
                "received_at": pending.received_at,
                "channel_id": pending.channel_id,
                "submitter_org": pending.submitter_org,
                "certification_result": pending.certification_result
            }

        # Check processed events in storage handler
        if event_id in self.storage_handler.processed_events:
            processed = self.storage_handler.processed_events[event_id]
            return {
                "event_id": event_id,
                "status": str(processed.status.value),
                "received_at": processed.received_at,
                "channel_id": processed.channel_id,
                "submitter_org": processed.submitter_org,
                "certification_result": processed.certification_result
            }

        # Check certified events in certifier
        certification = self.certifier.get_certification(event_id)
        if certification:
            return {
                "event_id": event_id,
                "status": "certified" if certification.get("valid") else "rejected",
                "certification_result": certification
            }

        stored = self.storage_handler.storage.get_event_by_id(event_id)
        if stored is not None and stored.get("chain_name") == self.storage_handler.chain_name:
            return {"event_id": event_id, "status": "ordered", "certification_result": None}
        return None

    def add_validation_rule(self, rule: Callable) -> None:
        """Add a custom validation rule for events"""
        self.certifier.add_validation_rule(rule)
