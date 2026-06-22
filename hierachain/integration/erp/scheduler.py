"""
Concurrent scheduler for ERP Integration sync tasks.
"""

import time
import threading
import logging
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor

from hierachain.integration.types import IntegrationError, SyncStatus, SyncResult

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Schedules and manages synchronization tasks"""
    
    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._shutdown = False
    
    def schedule_task(
        self,
        profile_name: str,
        task_func: Callable,
        interval_seconds: int
    ) -> str:
        """Schedule a synchronization task"""
        with self.lock:
            if self._shutdown:
                raise IntegrationError("Scheduler is shutdown")
            
            task_id = f"{profile_name}_{int(time.time())}"
            
            # Stop existing task if any
            if profile_name in self.tasks:
                self._stop_task_internal(profile_name)
            
            # Create new task
            task_info = {
                "task_id": task_id,
                "profile_name": profile_name,
                "task_func": task_func,
                "interval": interval_seconds,
                "last_sync": 0,
                "next_sync": time.time() + interval_seconds,
                "status": SyncStatus.IDLE,
                "retry_count": 0,
                "max_retries": 3,
                "created_at": time.time()
            }
            
            self.tasks[profile_name] = task_info
            
            # Start the task
            self._schedule_next_execution(profile_name)
            
            return task_id
    
    def _schedule_next_execution(self, profile_name: str):
        """Schedule next execution of a task"""
        if self._shutdown or profile_name not in self.tasks:
            return
        
        task_info = self.tasks[profile_name]
        delay = max(0, task_info["next_sync"] - time.time())
        
        # Schedule with thread pool and timer
        self.executor.submit(
            lambda: threading.Timer(
                delay, 
                self._run_task_execution, 
                args=[profile_name]
            ).start()
        )

    def _run_task_execution(self, profile_name: str):
        """Execute the task and handle its lifecycle"""
        if self._shutdown or profile_name not in self.tasks:
            return
            
        task_info = self.tasks[profile_name]
        task_info["status"] = SyncStatus.SYNCING
        
        try:
            # Execute the task function
            result = task_info["task_func"]()
            self._handle_execution_result(profile_name, result)
        except Exception as e:
            self._handle_execution_error(profile_name, e)
        finally:
            self._reschedule_if_active(profile_name)

    def _handle_execution_result(self, profile_name: str, result: SyncResult):
        """Handle the result of a task execution"""
        if profile_name not in self.tasks:
            return
            
        task_info = self.tasks[profile_name]
        task_info["last_sync"] = time.time()
        
        if result.status == SyncStatus.COMPLETED:
            task_info["status"] = SyncStatus.COMPLETED
            task_info["retry_count"] = 0
        else:
            task_info["status"] = SyncStatus.FAILED
            task_info["retry_count"] += 1

    def _handle_execution_error(self, profile_name: str, error: Exception):
        """Handle exceptions during task execution"""
        if profile_name not in self.tasks:
            return
            
        task_info = self.tasks[profile_name]
        task_info["status"] = SyncStatus.FAILED
        task_info["retry_count"] += 1
        task_info["last_sync"] = time.time()
        self.logger.error(
            "Task execution failed for %s: %s", profile_name, error
        )

    def _reschedule_if_active(self, profile_name: str):
        """Reschedule the next execution if the scheduler is still active"""
        if not self._shutdown and profile_name in self.tasks:
            task_info = self.tasks[profile_name]
            task_info["next_sync"] = time.time() + task_info["interval"]
            self._schedule_next_execution(profile_name)
    
    def stop_task(self, profile_name: str) -> bool:
        """Stop a scheduled task"""
        with self.lock:
            return self._stop_task_internal(profile_name)
    
    def _stop_task_internal(self, profile_name: str) -> bool:
        """Internal method to stop a task"""
        if profile_name in self.tasks:
            del self.tasks[profile_name]
            self.logger.info("Stopped sync task for %s", profile_name)
            return True
        return False
    
    def update_last_sync(self, profile_name: str, timestamp: float) -> None:
        """Update last sync timestamp"""
        with self.lock:
            if profile_name in self.tasks:
                self.tasks[profile_name]["last_sync"] = timestamp
    
    def schedule_retry(self, profile_name: str) -> None:
        """Schedule retry for failed sync"""
        with self.lock:
            if profile_name not in self.tasks:
                return
            
            task_info = self.tasks[profile_name]
            if task_info["retry_count"] < task_info["max_retries"]:
                # Exponential backoff
                delay = min(300, 30 * (2 ** task_info["retry_count"]))
                task_info["next_sync"] = time.time() + delay
                self.logger.info(
                    "Scheduling retry for %s in %d seconds", profile_name, delay
                )
    
    def get_status(self, profile_name: str) -> dict[str, Any]:
        """Get task status"""
        with self.lock:
            if profile_name not in self.tasks:
                return {"error": "Task not found"}
            
            task_info = self.tasks[profile_name]
            return {
                "task_id": task_info["task_id"],
                "profile_name": profile_name,
                "status": task_info["status"].value,
                "interval": task_info["interval"],
                "last_sync": task_info["last_sync"],
                "next_sync": task_info["next_sync"],
                "retry_count": task_info["retry_count"],
                "max_retries": task_info["max_retries"],
                "created_at": task_info["created_at"]
            }
    
    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get status of all tasks"""
        with self.lock:
            return [self.get_status(profile_name) for profile_name in self.tasks.keys()]
    
    def shutdown(self):
        """Shutdown the scheduler"""
        with self.lock:
            self._shutdown = True
            self.tasks.clear()
        
        self.executor.shutdown(wait=True)
        self.logger.info("Sync scheduler shutdown complete")
