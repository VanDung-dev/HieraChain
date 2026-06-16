"""
Worker pool primitives for HieraChain parallel processing.

Provides configurable thread/process worker pools with task
submission, result tracking, and monitoring.
"""

import time
import threading
import logging
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import (
    ThreadPoolExecutor, ProcessPoolExecutor, Future
)


class ProcessingError(Exception):
    pass


class ProcessingPolicy(Enum):
    DEFAULT = "default"
    VALIDATION = "validation"
    INDEXING = "indexing"
    BATCH = "batch"
    PRIORITY = "priority"


@dataclass
class ProcessingTask:
    task_id: str
    data: Any
    processor_func: Callable
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    task_id: str
    success: bool
    result: Any = None
    error: str | None = None
    processing_time: float = 0.0
    worker_id: str | None = None


class WorkerPool:
    def __init__(
        self, pool_name: str, max_workers: int, pool_type: str = "thread"
    ) -> None:
        self.pool_name = pool_name
        self.max_workers = max_workers
        self.pool_type = pool_type
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.lock = threading.Lock()
        if pool_type == "process":
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(f"{__name__}.{pool_name}")

    def submit_task(self, task: ProcessingTask) -> Future:
        with self.lock:
            self.active_tasks += 1

        def wrapped_processor():
            start_time = time.time()
            worker_id = f"{self.pool_name}_{threading.current_thread().ident}"
            try:
                result = task.processor_func(task.data)
                processing_time = time.time() - start_time
                with self.lock:
                    self.active_tasks -= 1
                    self.completed_tasks += 1
                return ProcessingResult(
                    task_id=task.task_id,
                    success=True,
                    result=result,
                    processing_time=processing_time,
                    worker_id=worker_id
                )
            except Exception as e:
                processing_time = time.time() - start_time
                error_msg = str(e)
                with self.lock:
                    self.active_tasks -= 1
                    self.failed_tasks += 1
                self.logger.error(f"Task {task.task_id} failed: {error_msg}")
                return ProcessingResult(
                    task_id=task.task_id,
                    success=False,
                    error=error_msg,
                    processing_time=processing_time,
                    worker_id=worker_id
                )

        return self.executor.submit(wrapped_processor)

    def get_stats(self) -> dict[str, Any]:
        with self.lock:
            total_tasks = self.completed_tasks + self.failed_tasks
            success_rate = (
                (self.completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            )
            return {
                "pool_name": self.pool_name,
                "pool_type": self.pool_type,
                "max_workers": self.max_workers,
                "active_tasks": self.active_tasks,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "success_rate": round(success_rate, 2)
            }

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True)
        self.logger.info(f"Worker pool {self.pool_name} shutdown complete")
