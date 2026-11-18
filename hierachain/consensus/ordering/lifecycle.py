"""Ordering status transitions, processor watchdog and shutdown contract."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Protocol

from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.types import OrderingStatus

logger = logging.getLogger(__name__)


class OrderingLifecycleHost(Protocol):
    config: dict[str, Any]
    should_stop: threading.Event
    processor: Any
    processing_thread: threading.Thread | None
    loop: Any
    event_pool: Any
    storage_handler: Any
    journal: Any
    _status: OrderingStatus
    _commit_lock: threading.RLock


class OrderingLifecycleMixin(OrderingLifecycleHost):
    @property
    def status(self) -> OrderingStatus:
        return self._status

    @status.setter
    def status(self, value: OrderingStatus) -> None:
        with self._commit_lock:
            self._status = value

    def _start_processing_thread(self) -> None:
        """Start the processor, which replays the journal before accepting events."""
        thread = threading.Thread(
            target=self._init_processing_thread,
            daemon=True,
            name="OrderingProcessor"
        )
        self.processing_thread = thread
        thread.start()

    def _init_processing_thread(self):
        """Entry point for the background processing thread with watchdog restart."""
        max_restarts = int(self.config.get("processor_max_restarts", 5))
        failures = 0
        while not self.should_stop.is_set():
            was_active = self.status == OrderingStatus.ACTIVE
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self.processor.run_async())
                return
            except Exception as exc:
                if self.should_stop.is_set():
                    return
                failures = 1 if was_active else failures + 1
                logger.error(
                    "Ordering processor stopped unexpectedly; restart %d/%d: %s",
                    failures, max_restarts, exc,
                )
                self.status = OrderingStatus.MAINTENANCE
                if failures > max_restarts:
                    self.status = OrderingStatus.ERROR
                    logger.critical(
                        "Ordering processor exceeded %d restarts; manual intervention required",
                        max_restarts,
                    )
                    return
                self.processor = OrderingProcessor(self)
                delay = min(2 ** (failures - 1), 30)
                if self.should_stop.wait(delay):
                    return
            finally:
                self.loop.close()

    def wait_for_active(self, timeout: float | None = 5.0) -> bool:
        """
        Wait for the service to become active.

        Args:
            timeout: Maximum time to wait in seconds, or None to finish recovery.

        Returns:
            True if active, False on timeout, shutdown, or processor failure.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if self.should_stop.is_set() or not self.processing_thread or not self.processing_thread.is_alive():
                return False
            if self.status == OrderingStatus.ACTIVE:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def start(self) -> None:
        """Start or restart the ordering service"""
        if self.status == OrderingStatus.ACTIVE:
            logger.warning("Ordering service is already active")
            return

        logger.info("Starting ordering service...")
        self.should_stop.clear()
        self.status = OrderingStatus.MAINTENANCE

        if self.processing_thread is None or not self.processing_thread.is_alive():
            self._start_processing_thread()
        logger.info("Ordering service started")

    def shutdown(self):
        """Graceful service shutdown"""
        logger.info("Ordering service shutting down...")
        self.status = OrderingStatus.SHUTDOWN
        self.should_stop.set()
        with self.event_pool.not_full:
            self.event_pool.not_full.notify_all()
        if self.processing_thread and self.processing_thread.is_alive():
            # In-flight processing must finish before releasing its storage and writer lease.
            self.processing_thread.join()
        self.storage_handler.close()
        self.journal.close()
        logger.info("Ordering service shutdown complete.")
