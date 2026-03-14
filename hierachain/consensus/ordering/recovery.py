"""
Ordering state recovery from the transaction journal for the HieraChain ordering service.
"""

import time
import logging
from hierachain.consensus.ordering.types import PendingEvent, EventStatus
from hierachain.consensus.ordering.utils import make_serializable, generate_event_id

logger = logging.getLogger(__name__)

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
            f"Recovering state from Transaction Journal... Skipping blocks < {self.service.blocks_created}"
        )
        count = 0
        skipped_events = 0
        for event_data in self.journal.replay():
            try:
                event_data = make_serializable(event_data)
                
                # Check for block cut markers to track which events are already in blocks
                if event_data.get("event") == "$SYSTEM_BLOCK_CUT":
                    details = event_data.get("details", {})
                    block_index_raw = details.get("block_index")
                    block_index = int(block_index_raw) if block_index_raw is not None else None
                    
                    if block_index is not None and block_index < self.service.blocks_created:
                        # This block and all its events are already in the DB
                        logger.debug(f"Recovery: Skipping already committed block #{block_index}")
                        # Clear block builder as if they were processed
                        self.service.block_builder.force_create_block() 
                        continue
                    
                    if block_index is not None and block_index >= self.service.blocks_created:
                        # We've reached events that are NOT in the DB yet
                        await self.block_manager.check_timeout_block_creation(force=True)
                        continue

                channel_id = event_data.get("channel_id", "recovery")
                event_id = generate_event_id(event_data, channel_id)
                
                # Check if event already exists in DB (more expensive but precise)
                if self.service.storage_handler.storage.get_event_by_id(event_id):
                    skipped_events += 1
                    continue

                pending_event = PendingEvent(
                    event_id=event_id,
                    event_data=event_data,
                    channel_id=channel_id,
                    submitter_org="recovery",
                    received_at=time.time(),
                    status=EventStatus.PENDING
                )
                await self.processor.process_single_event(pending_event)
                count += 1
            except Exception as e:
                logger.error(f"Failed to recover event: {e}")
        
        await self.block_manager.check_timeout_block_creation()
        logger.info(
            f"Journal recovery complete. Restored {count} events, skipped {skipped_events} already committed."
        )
