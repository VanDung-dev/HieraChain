"""
Ordering service for the HieraChain.
Coordinates between specialized components to provide ordering functionality.
"""

from __future__ import annotations

import threading
import logging
import time
import asyncio
from queue import Queue, Empty
from typing import Any, Callable

from hierachain.core.block import Block
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.consensus.ordering.types import (
    PendingEvent, EventStatus, OrderingStatus
)
from hierachain.consensus.ordering.utils import generate_event_id
from hierachain.consensus.ordering.metrics import OrderingMetrics
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.block_builder import BlockBuilder
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.maintenance import OrderingMaintenance

logger = logging.getLogger(__name__)


class OrderingService:
    """
    Facade for the Ordering Service package.
    Coordinates between specialized components to provide ordering functionality.
    """
    def __init__(self, config: dict[str, Any], nodes: list[Any] | None = None, node_identity: Any | None = None):
        self.config = config
        self.nodes = nodes or []
        self.node_identity = node_identity
        self.status = OrderingStatus.MAINTENANCE
        self.should_stop = threading.Event()
        self.event_pool: Queue[PendingEvent] = Queue()
        self.pending_events: dict[str, PendingEvent] = {}
        self.commit_queue: Queue[Block] = Queue()
        self.processing_thread: threading.Thread | None = None

        # Component Initialization
        self.metrics = OrderingMetrics()
        self.storage_handler = OrderingStorageHandler(config)

        # Initialize blocks_created from DB to ensure continuity after restart
        latest_block = self.storage_handler.get_latest_block_from_db()
        if latest_block:
            self.storage_handler.last_block = latest_block
        self.blocks_created = (latest_block.index + 1) if latest_block else 0
        logger.info(
            "Initialized ordering service state: blocks_created=%s",
            self.blocks_created
        )

        # Configure journal based on storage_dir and node_id for persistence
        storage_dir = config.get("storage_dir", "journal")
        node_id = nodes[0].node_id if nodes else "unknown"
        active_log_name = f"node_{node_id}_journal.log"
        self.journal = TransactionJournal(
            storage_dir=storage_dir, active_log_name=active_log_name
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

        # Lightweight recovery: just logs, no raise — ordering recovery
        # re-plays journal events properly in recover_state_async() later.
        self._recover_pending_events_from_journal()

    def _recover_pending_events_from_journal(self) -> None:
        """Count uncommitted journal entries (recovery handled by OrderingRecovery)."""
        try:
            count = sum(1 for _ in self.journal.replay())
            if count:
                logger.info("Journal has %d uncommitted events for processor recovery.", count)
        except Exception as e:
            logger.error("Failed to read journal: %s", e)

        # Thread Management
        thread = threading.Thread(
            target=self._init_processing_thread,
            daemon=True,
            name="OrderingProcessor"
        )
        self.processing_thread = thread
        thread.start()

    def _init_processing_thread(self):
        """Entry point for the background processing thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.processor.run_async())
        finally:
            self.loop.close()

    def receive_event(
        self, event_data: dict[str, Any], channel_id: str, submitter_org: str
    ) -> str:
        """Submit a new event for ordering"""
        if self.status in [OrderingStatus.LOCKDOWN, OrderingStatus.SHUTDOWN]:
            status_str = str(self.status.value)
            raise Exception(f"Ordering service is in {status_str} mode")

        # Validate event_data is a dictionary
        if not isinstance(event_data, dict):
            raise ValueError(
                "event_data must be a dictionary, got %s",
                type(event_data).__name__
            )

        self.metrics.record_received()
        event_id = generate_event_id(event_data, channel_id)

        if event_id in self.pending_events:
            return event_id

        # Enrich event_data with event_id for journal and block storage
        enriched_data = {**event_data, "event_id": event_id}

        pending_event = PendingEvent(
            event_id=event_id,
            event_data=enriched_data,
            channel_id=channel_id,
            submitter_org=submitter_org,
            received_at=time.time(),
            status=EventStatus.PENDING
        )

        logged_data = {**enriched_data, "channel_id": channel_id}
        self.journal.log_event(logged_data)
        self.pending_events[event_id] = pending_event
        self.event_pool.put(pending_event)

        return event_id

    def get_latest_block(self) -> Block | None:
        """Retrieve the latest block for the current chain"""
        return self.storage_handler.get_latest_block_from_db()

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
        except Exception as e:
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

        return None

    def add_validation_rule(self, rule: Callable) -> None:
        """Add a custom validation rule for events"""
        self.certifier.add_validation_rule(rule)

    def wait_for_active(self, timeout: float = 5.0) -> bool:
        """
        Wait for the service to become active.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if service is active, False if timeout reached.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.status == OrderingStatus.ACTIVE:
                return True
            time.sleep(0.05)
        return self.status == OrderingStatus.ACTIVE

    def start(self) -> None:
        """Start or restart the ordering service"""
        if self.status == OrderingStatus.ACTIVE:
            logger.warning("Ordering service is already active")
            return

        logger.info("Starting ordering service...")
        self.should_stop.clear()
        self.status = OrderingStatus.MAINTENANCE

        # Start a new processing thread
        if self.processing_thread is None or not self.processing_thread.is_alive():
            thread = threading.Thread(
                target=self._init_processing_thread,
                daemon=True,
                name="OrderingProcessor"
            )
            self.processing_thread = thread
            thread.start()
        logger.info("Ordering service started")

    def shutdown(self):
        """Graceful service shutdown"""
        logger.info("Ordering service shutting down...")
        self.status = OrderingStatus.SHUTDOWN
        self.should_stop.set()
        self.storage_handler.close()
        self.journal.close()
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
        logger.info("Ordering service shutdown complete.")
