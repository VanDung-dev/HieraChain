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
        logger.info("Recovering state from Transaction Journal...")
        count = 0
        for event_data in self.journal.replay():
            try:
                event_data = make_serializable(event_data)
                if event_data.get("event") == "$SYSTEM_BLOCK_CUT":
                    await self.block_manager.check_timeout_block_creation(force=True)
                    continue

                channel_id = "recovery"
                event_id = generate_event_id(event_data, channel_id)
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
        logger.info(f"Journal recovery complete. Restored {count} events.")
