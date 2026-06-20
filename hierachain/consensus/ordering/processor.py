"""
Ordering processor for the HieraChain ordering service.
"""

import time
import logging
import asyncio
from typing import Any
from queue import Empty

from hierachain.core.performance import process_pool
from hierachain.security.security_utils import verify_batch_signatures
from hierachain.consensus.ordering.types import (
    PendingEvent, EventStatus, OrderingStatus
)
from hierachain.consensus.ordering.block_manager import OrderingBlockManager
from hierachain.consensus.ordering.recovery import OrderingRecovery

logger = logging.getLogger(__name__)


def _should_process_batch(
    batch: list,
    is_full: bool,
    is_timeout: bool,
    is_forced: bool,
    block_timeout: bool,
) -> bool:
    """Decide whether the current batch cycle should trigger processing."""
    if batch and (is_full or is_timeout or is_forced):
        return True
    if not batch and block_timeout:
        return True
    return False


def _extract_verification_items(
    batch: list[PendingEvent]
) -> tuple[list[dict], list[PendingEvent]]:
    """Extract public keys, messages, and signatures for batch verification."""
    verification_items: list[dict] = []
    events_to_verify: list[PendingEvent] = []

    for event in batch:
        data = event.event_data
        if "signature" not in data or "sender" not in data:
            continue
        details = data.get("details", {})
        msg = (
            details.get("payload")
            if isinstance(details, dict)
            else None
        )
        if msg:
            verification_items.append({
                "public_key": data["sender"],
                "message": msg,
                "signature": data["signature"],
            })
            events_to_verify.append(event)

    return verification_items, events_to_verify


def _remove_pending(pending_events: dict, event_id: str) -> None:
    """Remove an event from pending_events if present."""
    pending_events.pop(event_id, None)


def _handle_certified_event(
    pending_event: PendingEvent,
    block_builder,
    storage_handler,
    pending_events: dict,
    metrics,
) -> list[dict[str, Any]] | None:
    """Mark event as certified and add to block builder.

    Returns raw_block_data if a block was formed, else None.
    """
    pending_event.status = EventStatus.CERTIFIED
    metrics.record_certified()
    raw_block_data = block_builder.add_event(pending_event)
    storage_handler.processed_events[pending_event.event_id] = pending_event
    _remove_pending(pending_events, pending_event.event_id)

    return raw_block_data


def _handle_rejected_event(pending_event: PendingEvent, metrics) -> None:
    """Mark event as rejected and record metric."""
    pending_event.status = EventStatus.REJECTED
    metrics.record_rejected()
    logger.debug(f"Event {pending_event.event_id} REJECTED")


class OrderingProcessor:
    """Handles background event processing and loop coordination"""

    def __init__(self, service) -> None:
        self.service = service
        self.should_stop = service.should_stop
        self.event_pool = service.event_pool
        self.pending_events = service.pending_events
        self.metrics = service.metrics
        self.storage_handler = service.storage_handler
        self.block_builder = service.block_builder
        self.certifier = service.certifier
        self.config = service.config
        
        # Internal components
        self.block_manager = OrderingBlockManager(service)
        self.recovery = OrderingRecovery(service, self)
        
        # Batch management
        self.current_batch: list[PendingEvent] = []
        self.last_batch_time = time.time()
        self.force_process = asyncio.Event()

    async def run_async(self):
        """Main async processing loop"""
        await self._initialize_service()

        # Use block_size as fallback for batch_size to maintain consistency
        batch_size = (
            self.config.get("batch_size") or self.config.get("block_size") or 100
        )
        
        while not self.should_stop.is_set():
            try:
                await self._collect_next_event(self.current_batch)
                self.last_batch_time = await self._handle_batch_logic(
                    self.current_batch,
                    self.last_batch_time,
                    batch_size,
                )
            except Exception as e:
                logger.error(f"Error in processor loop: {e}")
                await asyncio.sleep(0.1)

    async def _initialize_service(self):
        """Perform service initialization and state recovery"""
        await self.recovery.recover_state_async()
        self.service.status = OrderingStatus.ACTIVE
        logger.info("Ordering Service is now ACTIVE")

    async def _collect_next_event(self, batch: list[PendingEvent]):
        """Try to collect events from the pool. Drains queue elements synchronously. Sleeps if batch has items, blocks if empty."""
        if self.should_stop.is_set():
            return
        
        # Drain ready events synchronously
        batch_size = self.config.get("batch_size") or self.config.get("block_size") or 100
        while len(batch) < batch_size:
            try:
                pending_event = self.event_pool.get_nowait()
                batch.append(pending_event)
            except Empty:
                break

        # If batch is still not full
        if len(batch) < batch_size:
            if not batch:
                # If batch is empty, wait for the next event on background thread
                try:
                    timeout = self.config.get("batch_timeout", 0.1)
                    pending_event = await asyncio.to_thread(self.event_pool.get, timeout=timeout)
                    batch.append(pending_event)
                    
                    # Drain any other events that arrived in the meantime
                    while len(batch) < batch_size:
                        try:
                            pending_event = self.event_pool.get_nowait()
                            batch.append(pending_event)
                        except Empty:
                            break
                except Empty:
                    pass
                except RuntimeError as e:
                    if "shutdown" in str(e).lower() or "event loop is closed" in str(e).lower():
                        pass
                    else:
                        raise e
            else:
                # If batch has elements but is not full, do a very short sleep to let more events arrive
                # and avoid busy-waiting or blocking on the queue
                await asyncio.sleep(0.001)



    async def _handle_batch_logic(
        self,
        batch: list[PendingEvent],
        last_batch_time: float,
        batch_size: int,
    ) -> float:
        """
        Decide if a batch should be processed or if timeout blocks should be checked.
        """
        is_full = len(batch) >= batch_size
        batch_timeout = self.config.get("batch_timeout", 0.1)
        is_timeout = (time.time() - last_batch_time) > batch_timeout
        is_forced = self.force_process.is_set()

        should_act = _should_process_batch(
            batch, is_full,
            is_timeout,
            is_forced,
            self.block_manager.is_block_timeout(),
        )

        if not should_act:
            return last_batch_time

        if batch:
            await self._process_batch(list(batch))
            batch.clear()

        await self.block_manager.check_timeout_block_creation(force=is_forced)

        if is_forced:
            self.force_process.clear()

        return time.time()

    async def _process_batch(self, batch: list[PendingEvent]):
        """Process a batch of events with parallel signature verification"""
        verification_items, events_to_verify = (_extract_verification_items(batch))

        if verification_items:
            await self._verify_batch_signatures_async(
                verification_items, events_to_verify
            )

        await self._handle_processed_batch(batch)

    async def _verify_batch_signatures_async(
        self,
        verification_items: list[dict],
        events_to_verify: list[PendingEvent],
    ) -> None:
        """Execute parallel batch signature verification using the process pool."""
        try:
            if len(verification_items) < 15:
                results = verify_batch_signatures(verification_items)
            else:
                results = await asyncio.to_thread(
                    verify_batch_signatures, verification_items
                )
            for event, is_valid in zip(events_to_verify, results):
                if not is_valid:
                    event.status = EventStatus.REJECTED
                    self.metrics.record_rejected()
                    logger.warning(
                        "Event %s rejected (invalid signature)", event.event_id
                    )
                else:
                    event.signature_verified = True
        except Exception as e:
            logger.error("Batch verification failed: %s", e)


    async def _handle_processed_batch(self, batch: list[PendingEvent]) -> None:
        """
        Process each event in the batch after verification is complete.
        Uses asyncio.gather for parallel processing of independent events.
        """
        # Process independent events in parallel using asyncio.gather
        tasks = []
        for event in batch:
            if event.status == EventStatus.REJECTED:
                _remove_pending(self.pending_events, event.event_id)
                continue
            tasks.append(self.process_single_event(event))
        
        if tasks:
            await asyncio.gather(*tasks)

    async def process_single_event(self, pending_event: PendingEvent,) -> None:
        """Process a single event through certification and ordering"""
        try:
            pending_event.status = EventStatus.PROCESSING
            certification_result = self.certifier.validate(pending_event)
            pending_event.certification_result = certification_result

            if certification_result["valid"]:
                raw_block_data = _handle_certified_event(
                    pending_event,
                    self.block_builder,
                    self.storage_handler,
                    self.pending_events,
                    self.metrics,
                )
                if raw_block_data:
                    await self.block_manager.create_block_async(raw_block_data)
            else:
                _handle_rejected_event(pending_event, self.metrics)

        except Exception as e:
            logger.error("Error processing event %s: %s", pending_event.event_id, e)

    async def force_process_batch_async(self) -> None:
        """Force immediate processing of current batch and block creation"""
        self.force_process.set()
        # Give the loop a chance to pick it up
        await asyncio.sleep(0.05)
