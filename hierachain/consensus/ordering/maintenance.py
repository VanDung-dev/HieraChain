"""
Ordering maintenance and emergency operations for the HieraChain ordering service.
"""

import logging
from hierachain.consensus.ordering.types import OrderingStatus
from hierachain.consensus.ordering.utils import dump_forensic_data

logger = logging.getLogger(__name__)

class OrderingMaintenance:
    """Handles emergency and maintenance operations for the ordering service"""
    def __init__(self, service):
        self.service = service

    def lockdown(self, reason: str = "Unspecified maintenance") -> bool:
        """Freeze all ordering operations and dump state for forensics"""
        if self.service.status == OrderingStatus.LOCKDOWN:
            return True

        logger.critical(f"SYSTEM LOCKDOWN INITIATED: {reason}")
        self.service.status = OrderingStatus.LOCKDOWN
        
        # Capture current state for forensic analysis
        dump_forensic_data(self.service.pending_events, self.service.event_pool)
        return True

    def resume(self) -> bool:
        """Attempt to resume operations from lockdown/maintenance"""
        if self.service.status == OrderingStatus.ACTIVE:
            return True

        logger.info("Resuming ordering operations...")
        self.service.status = OrderingStatus.ACTIVE
        return True

    def flush_pool(self) -> int:
        """Clear all pending events from the pool (emergency use only)"""
        count = 0
        while not self.service.event_pool.empty():
            try:
                self.service.event_pool.get_nowait()
                count += 1
            except Exception:
                break
        
        self.service.pending_events.clear()
        logger.warning(f"Event pool flushed. {count} events discarded.")
        return count
