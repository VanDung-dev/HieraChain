"""
Ordering state recovery from the transaction journal for the HieraChain
ordering service.
"""

import time
import logging
from typing import Any, cast
from hierachain.consensus.ordering.types import PendingEvent, EventStatus
from hierachain.consensus.ordering.utils import make_serializable, generate_event_id

logger = logging.getLogger(__name__)


def _get_event_id(event_data: dict) -> str:
    """Extract event ID from event data"""
    channel_id = event_data.get("channel_id", "recovery")
    return generate_event_id(event_data, channel_id)


def _is_block_cut_marker(event_data: dict) -> bool:
    """Check if event is a system block cut marker"""
    return event_data.get("event") == "$SYSTEM_BLOCK_CUT"


def _extract_block_index(event_data: dict) -> int | None:
    """Extract block index from block cut marker event data"""
    details = event_data.get("details", {})
    block_index_raw = details.get("block_index")

    if block_index_raw is None:
        return None

    try:
        return int(cast(Any, block_index_raw))
    except (ValueError, TypeError) as e:
        logger.warning("Invalid block_index in marker: %s", e)
        return None


class OrderingRecovery:
    """Handles state recovery from the transaction journal"""
    def __init__(self, service, processor):
        self.service = service
        self.processor = processor
        self.journal = service.journal
        self.block_manager = processor.block_manager

    async def recover_state_async(self):
        """Recover state from transaction journal by replaying events"""
        logger.info(
            "Recovering state from Transaction Journal... Skipping blocks < %s",
            self.service.blocks_created
        )
        
        # Replay events with counters
        count, skipped_events = await self._replay_journal_events()
        
        # Finalize recovery
        await self.block_manager.check_timeout_block_creation()
        logger.info(
            "Journal recovery complete. Restored %s events, "
            "skipped %s already committed.",
            count, skipped_events
        )

    async def _replay_journal_events(self) -> tuple[int, int]:
        """Replay all events from journal, returning (restored_count, skipped_count)"""
        count = 0
        skipped_events = 0
        
        for event_data in self.journal.replay():
            result = await self._process_single_journal_entry(event_data)
            if result == "restored":
                count += 1
            elif result == "skipped":
                skipped_events += 1
                
        return count, skipped_events

    async def _process_single_journal_entry(self, event_data: dict) -> str:
        """
        Process a single journal entry.
        Returns: "restored", "skipped", or "error"
        """
        # Validate event data early
        if event_data is None:
            logger.warning("Skipping null event in journal")
            return "skipped"
        
        event_id = "unknown"
        try:
            event_data = make_serializable(event_data)
            event_id = _get_event_id(event_data)
            
            # Handle block cut marker
            if _is_block_cut_marker(event_data):
                await self._handle_block_cut_marker_async(event_data)
                return "skipped"
            
            # Skip events already in DB
            if self._is_event_already_stored(event_id):
                return "skipped"
            
            # Replay the event
            await self._replay_event(event_data, event_id)
            return "restored"
            
        except Exception as e:
            logger.error("Failed to recover event %s: %s", event_id, e)
            return "error"

    def _is_event_already_stored(self, event_id: str) -> bool:
        """Check if event already exists in storage"""
        return self.service.storage_handler.storage.get_event_by_id(event_id) is not None

    async def _replay_event(self, event_data: dict, event_id: str) -> None:
        """Replay a single event through the processor"""
        channel_id = event_data.get("channel_id", "recovery")
        
        pending_event = PendingEvent(
            event_id=event_id,
            event_data=event_data,
            channel_id=channel_id,
            submitter_org="recovery",
            received_at=time.time(),
            status=EventStatus.PENDING
        )
        await self.processor.process_single_event(pending_event)

    async def _handle_block_cut_marker_async(self, event_data: dict) -> None:
        """Handle block cut markers during recovery"""
        block_index = _extract_block_index(event_data)
        
        if block_index is None:
            return
            
        # Skip if block already committed
        if block_index < self.service.blocks_created:
            logger.debug(
                "Recovery: Skipping already committed block #%s",
                block_index
            )
            self.service.block_builder.force_create_block()
            return
        
        # Process block that needs creation
        if block_index >= self.service.blocks_created:
            await self.block_manager.check_timeout_block_creation(force=True)
