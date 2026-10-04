"""
Concurrent scheduler for ERP Integration sync tasks.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from hierachain.integration.types import IntegrationError, SyncResult, SyncStatus

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Schedules and manages synchronization tasks"""
    
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        timer_factory: Callable[..., Any] = threading.Timer,
    ) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        self._shutdown = False
        self._clock = clock
        self._timer_factory = timer_factory
        self._generation_counter = 0
        self._timer_counter = 0
    
    def schedule_task(
        self,
        profile_name: str,
        task_func: Callable,
        interval_seconds: int,
    ) -> str:
        """Schedule a synchronization task"""
        with self.lock:
            if self._shutdown:
                raise IntegrationError("Scheduler is shutdown")
            
            # Stop existing task if any
            if profile_name in self.tasks:
                self._stop_task_internal(profile_name)

            self._generation_counter += 1
            generation = self._generation_counter
            now = self._clock()
            task_id = f"{profile_name}_{generation}"
            
            # Create new task
            task_info = {
                "task_id": task_id,
                "profile_name": profile_name,
                "generation": generation,
                "task_func": task_func,
                "interval": interval_seconds,
                "last_sync": 0,
                "next_sync": now + interval_seconds,
                "status": SyncStatus.IDLE,
                "retry_count": 0,
                "max_retries": 3,
                "retry_exhausted": False,
                "events_processed": 0,
                "errors": [],
                "timer": None,
                "timer_token": None,
                "future": None,
                "created_at": now,
            }
            
            self.tasks[profile_name] = task_info
            
            # Start the task
            self._schedule_next_execution(profile_name, generation)
            
            return task_id
    
    def _schedule_next_execution(
        self, profile_name: str, generation: int | None = None
    ) -> None:
        """Start one timer bound to the current task generation."""
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if self._shutdown or task_info is None:
                return
            if generation is None:
                generation = task_info["generation"]
            if task_info["generation"] != generation:
                return
            next_sync = task_info["next_sync"]
            if next_sync is None:
                return

            delay = max(0.0, next_sync - self._clock())
            existing_timer = task_info.get("timer")
            if existing_timer is not None:
                existing_timer.cancel()
            self._timer_counter += 1
            timer_token = self._timer_counter
            timer = self._timer_factory(
                delay,
                self._submit_task_execution,
                args=(profile_name, generation, timer_token),
            )
            timer.daemon = True
            task_info["timer"] = timer
            task_info["timer_token"] = timer_token
            timer.start()

    def _submit_task_execution(
        self, profile_name: str, generation: int, timer_token: int
    ) -> None:
        """Submit a timer callback only if its task generation remains current."""
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if (
                self._shutdown
                or task_info is None
                or task_info["generation"] != generation
                or task_info["timer_token"] != timer_token
                or task_info["status"] == SyncStatus.SYNCING
            ):
                return
            task_info["timer"] = None
            task_info["timer_token"] = None
            try:
                future = self.executor.submit(
                    self._run_task_execution, profile_name, generation
                )
            except RuntimeError as exc:
                self._handle_execution_error(profile_name, exc, generation)
                return
            task_info["future"] = future

    def _run_task_execution(
        self, profile_name: str, generation: int | None = None
    ) -> None:
        """Execute the task and schedule exactly one outcome-based next run."""
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if self._shutdown or task_info is None:
                return
            if generation is None:
                generation = task_info["generation"]
            if task_info["generation"] != generation:
                return

            task_info["status"] = SyncStatus.SYNCING
            task_info["next_sync"] = None
            task_info["timer"] = None
            task_info["timer_token"] = None
            task_info["future"] = None
            task_func = task_info["task_func"]

        try:
            result = task_func()
            if not isinstance(result, SyncResult):
                raise TypeError("Scheduled task must return SyncResult")
        except Exception as exc:
            self._handle_execution_error(profile_name, exc, generation)
            return

        self._handle_execution_result(profile_name, result, generation)

    def _handle_execution_result(
        self,
        profile_name: str,
        result: SyncResult,
        generation: int | None = None,
    ) -> None:
        """Expose the result and choose a normal interval or retry deadline."""
        should_schedule = False
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if task_info is None or self._shutdown:
                return
            if generation is None:
                generation = task_info["generation"]
            if task_info["generation"] != generation:
                return

            now = self._clock()
            task_info["last_sync"] = now
            task_info["events_processed"] = result.events_processed
            task_info["errors"] = list(result.errors)
            if result.status == SyncStatus.COMPLETED and not result.errors:
                task_info["status"] = SyncStatus.COMPLETED
                task_info["retry_count"] = 0
                task_info["retry_exhausted"] = False
                task_info["next_sync"] = now + task_info["interval"]
                should_schedule = True
            else:
                task_info["status"] = SyncStatus.FAILED
                if not task_info["errors"]:
                    task_info["errors"] = ["Scheduled task returned a failed result"]
                should_schedule = self._set_retry_deadline(task_info, now)

        if should_schedule:
            self._schedule_next_execution(profile_name, generation)

    def _handle_execution_error(
        self,
        profile_name: str,
        error: Exception,
        generation: int | None = None,
    ) -> None:
        """Expose an exception and schedule a bounded retry when available."""
        should_schedule = False
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if task_info is None or self._shutdown:
                return
            if generation is None:
                generation = task_info["generation"]
            if task_info["generation"] != generation:
                return

            now = self._clock()
            task_info["status"] = SyncStatus.FAILED
            task_info["last_sync"] = now
            task_info["errors"] = [f"{type(error).__name__}: {error}"]
            should_schedule = self._set_retry_deadline(task_info, now)
            self.logger.error("Task execution failed for %s: %s", profile_name, error)

        if should_schedule:
            self._schedule_next_execution(profile_name, generation)

    def _set_retry_deadline(self, task_info: dict[str, Any], now: float) -> bool:
        """Record one bounded exponential retry or mark the task exhausted."""
        retry_count = task_info["retry_count"]
        if retry_count >= task_info["max_retries"]:
            task_info["retry_exhausted"] = True
            task_info["next_sync"] = None
            return False

        delay = min(300, 30 * (2 ** retry_count))
        task_info["retry_count"] = retry_count + 1
        task_info["retry_exhausted"] = False
        task_info["next_sync"] = now + delay
        self.logger.info(
            "Scheduling retry for %s in %d seconds", task_info["profile_name"], delay
        )
        return True
    
    def stop_task(self, profile_name: str) -> bool:
        """Stop a scheduled task"""
        with self.lock:
            return self._stop_task_internal(profile_name)
    
    def _stop_task_internal(self, profile_name: str) -> bool:
        """Internal method to stop a task"""
        if profile_name in self.tasks:
            task_info = self.tasks.pop(profile_name)
            timer = task_info.get("timer")
            if timer is not None:
                timer.cancel()
            future = task_info.get("future")
            if future is not None:
                future.cancel()
            self.logger.info("Stopped sync task for %s", profile_name)
            return True
        return False
    
    def update_last_sync(self, profile_name: str, timestamp: float) -> None:
        """Update last sync timestamp"""
        with self.lock:
            if profile_name in self.tasks:
                self.tasks[profile_name]["last_sync"] = timestamp
    
    def schedule_retry(self, profile_name: str) -> None:
        """Manually request the next retry within the configured limit."""
        generation: int | None = None
        should_schedule = False
        with self.lock:
            task_info = self.tasks.get(profile_name)
            if task_info is None or self._shutdown:
                return
            future = task_info.get("future")
            if task_info["status"] == SyncStatus.SYNCING:
                return
            if future is not None and not future.done():
                return
            timer = task_info.get("timer")
            if timer is not None:
                timer.cancel()
                task_info["timer"] = None
                task_info["timer_token"] = None
            task_info["status"] = SyncStatus.FAILED
            generation = task_info["generation"]
            should_schedule = self._set_retry_deadline(task_info, self._clock())

        if should_schedule and generation is not None:
            self._schedule_next_execution(profile_name, generation)
    
    def get_status(self, profile_name: str) -> dict[str, Any]:
        """Get task status"""
        with self.lock:
            if profile_name not in self.tasks:
                return {"error": "Task not found"}
            
            return self._task_status(profile_name, self.tasks[profile_name])

    @staticmethod
    def _task_status(profile_name: str, task_info: dict[str, Any]) -> dict[str, Any]:
        """Build a detached status snapshot while the caller holds the lock."""
        return {
            "task_id": task_info["task_id"],
            "profile_name": profile_name,
            "status": task_info["status"].value,
            "interval": task_info["interval"],
            "last_sync": task_info["last_sync"],
            "next_sync": task_info["next_sync"],
            "retry_count": task_info["retry_count"],
            "max_retries": task_info["max_retries"],
            "retry_exhausted": task_info["retry_exhausted"],
            "events_processed": task_info["events_processed"],
            "errors": list(task_info["errors"]),
            "created_at": task_info["created_at"],
        }
    
    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get status of all tasks"""
        with self.lock:
            return [self._task_status(name, task_info) for name, task_info in self.tasks.items()]
    
    def shutdown(self) -> None:
        """Shutdown the scheduler"""
        with self.lock:
            self._shutdown = True
            for task_info in self.tasks.values():
                timer = task_info.get("timer")
                if timer is not None:
                    timer.cancel()
                    task_info["timer_token"] = None
                future = task_info.get("future")
                if future is not None:
                    future.cancel()
            self.tasks.clear()
        
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.logger.info("Sync scheduler shutdown complete")
