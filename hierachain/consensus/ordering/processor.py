"""
Ordering processor for the HieraChain ordering service.
"""

import time
import logging
import asyncio
from queue import Empty

from hierachain.core.performance import process_pool
from hierachain.security.security_utils import verify_batch_signatures
from hierachain.consensus.ordering.types import PendingEvent, EventStatus, OrderingStatus
from hierachain.consensus.ordering.block_manager import OrderingBlockManager
from hierachain.consensus.ordering.recovery import OrderingRecovery

logger = logging.getLogger(__name__)

class OrderingProcessor:
    """Handles background event processing and loop coordination"""
    def __init__(self, service):
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

    async def run_async(self):
        """Main async processing loop"""
        await self._initialize_service()

        batch: list[PendingEvent] = []
        last_batch_time = time.time()
        batch_size = self.config.get("batch_size", 100)
        
        while not self.should_stop.is_set():
            try:
                await self._collect_next_event(batch)
                last_batch_time = await self._handle_batch_logic(batch, last_batch_time, batch_size)
            except Exception as e:
                logger.error(f"Error in processor loop: {e}")
                await asyncio.sleep(0.1)

    async def _initialize_service(self):
        """Perform service initialization and state recovery"""
        await self.recovery.recover_state_async()
        self.service.status = OrderingStatus.ACTIVE
        logger.info("Ordering Service is now ACTIVE")

    async def _collect_next_event(self, batch: list[PendingEvent]):
        """Try to collect the next event from the pool"""
        try:
            pending_event = self.event_pool.get_nowait()
            batch.append(pending_event)
        except Empty:
            await asyncio.sleep(0.01)

    async def _handle_batch_logic(self, batch: list[PendingEvent], last_batch_time: float, batch_size: int) -> float:
        """Decide if a batch should be processed or if timeout blocks should be checked"""
        is_full = len(batch) >= batch_size
        is_timeout = (time.time() - last_batch_time) > self.config.get("batch_timeout", 0.1)
        
        if (batch and (is_full or is_timeout)) or (not batch and self.block_manager.is_block_timeout()):
            if batch:
                await self._process_batch(list(batch))
                batch.clear()
                last_batch_time = time.time()
            await self.block_manager.check_timeout_block_creation()
            
        return last_batch_time

    async def _process_batch(self, batch: list[PendingEvent]):
        """Process a batch of events with parallel signature verification"""
        verification_items, events_to_verify = self._extract_verification_items(batch)
        
        if verification_items:
            await self._verify_batch_signatures_async(verification_items, events_to_verify)

        await self._handle_processed_batch(batch)

    @staticmethod
    def _extract_verification_items(batch: list[PendingEvent]) -> tuple[list[dict], list[PendingEvent]]:
        """Extract public keys, messages, and signatures for batch verification."""
        verification_items = []
        events_to_verify = []

        for event in batch:
            data = event.event_data
            if "signature" in data and "sender" in data:
                details = data.get("details", {})
                msg = details.get("payload") if isinstance(details, dict) else None
                if msg:
                    verification_items.append({
                        "public_key": data["sender"],
                        "message": msg,
                        "signature": data["signature"]
                    })
                    events_to_verify.append(event)
        
        return verification_items, events_to_verify

    async def _verify_batch_signatures_async(self, verification_items: list[dict], events_to_verify: list[PendingEvent]) -> None:
        """Execute parallel batch signature verification using the process pool."""
        try:
            results = await process_pool.run_task(verify_batch_signatures, verification_items)
            for event, is_valid in zip(events_to_verify, results):
                if not is_valid:
                    event.status = EventStatus.REJECTED
                    self.metrics.record_rejected()
                    logger.warning(f"Event {event.event_id} rejected (invalid signature)")
        except Exception as e:
            logger.error(f"Batch verification failed: {e}")

    async def _handle_processed_batch(self, batch: list[PendingEvent]) -> None:
        """Process each event in the batch after verification is complete."""
        for event in batch:
            if event.status == EventStatus.REJECTED:
                if event.event_id in self.pending_events:
                    del self.pending_events[event.event_id]
                continue
            await self.process_single_event(event)

    async def process_single_event(self, pending_event: PendingEvent) -> None:
        """Process a single event through certification and ordering"""
        try:
            pending_event.status = EventStatus.PROCESSING
            certification_result = self.certifier.validate(pending_event)
            pending_event.certification_result = certification_result
            
            if certification_result["valid"]:
                pending_event.status = EventStatus.CERTIFIED
                self.metrics.record_certified()
                
                raw_block_data = self.block_builder.add_event(pending_event)
                if raw_block_data:
                    await self.block_manager.create_block_async(raw_block_data)
                    
                self.storage_handler.processed_events[pending_event.event_id] = pending_event
                if pending_event.event_id in self.pending_events:
                    del self.pending_events[pending_event.event_id]
            else:
                pending_event.status = EventStatus.REJECTED
                self.metrics.record_rejected()
                logger.error(f"Event {pending_event.event_id} REJECTED")
                
        except Exception as e:
            logger.error(f"Error processing event {pending_event.event_id}: {e}")
            pending_event.status = EventStatus.REJECTED
            self.metrics.record_rejected()
