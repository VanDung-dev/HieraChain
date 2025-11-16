"""
Parallel Processing Engine for Hierarchical Blockchain Framework

This module provides a sophisticated parallel processing system with configurable
worker pools, chunk-based processing, and specialized processing policies for
blockchain operations. Enables efficient parallel validation, indexing, and
batch processing.
"""

import os
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future, as_completed
import queue


class ProcessingError(Exception):
    """Exception raised for processing-related errors"""
    pass


class ProcessingPolicy(Enum):
    """Processing policies for different operations"""
    DEFAULT = "default"
    VALIDATION = "validation"
    INDEXING = "indexing"
    BATCH = "batch"
    PRIORITY = "priority"


@dataclass
class ProcessingTask:
    """Individual processing task"""
    task_id: str
    data: Any
    processor_func: Callable
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of a processing operation"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    worker_id: Optional[str] = None


class WorkerPool:
    """Configurable worker pool for parallel processing"""
    
    def __init__(self, pool_name: str, max_workers: int, pool_type: str = "thread"):
        """
        Initialize worker pool
        
        Args:
            pool_name: Name of the worker pool
            max_workers: Maximum number of workers
            pool_type: "thread" or "process"
        """
        self.pool_name = pool_name
        self.max_workers = max_workers
        self.pool_type = pool_type
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.lock = threading.Lock()
        
        # Create executor based on type
        if pool_type == "process":
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        self.logger = logging.getLogger(f"{__name__}.{pool_name}")
    
    def submit_task(self, task: ProcessingTask) -> Future:
        """Submit a task to the worker pool"""
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        with self.lock:
            total_tasks = self.completed_tasks + self.failed_tasks
            success_rate = (self.completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            return {
                "pool_name": self.pool_name,
                "pool_type": self.pool_type,
                "max_workers": self.max_workers,
                "active_tasks": self.active_tasks,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "success_rate": round(success_rate, 2)
            }
    
    def shutdown(self):
        """Shutdown the worker pool"""
        self.executor.shutdown(wait=True)
        self.logger.info(f"Worker pool {self.pool_name} shutdown complete")


class ParallelProcessingEngine:
    """Parallel processing engine for blockchain operations"""
    
    def __init__(self, max_workers: Optional[int] = None, chunk_size: int = 100):
        """
        Initialize parallel processing engine
        
        Args:
            max_workers: Maximum number of worker threads
            chunk_size: Size of data chunks for parallel processing
        """
        self.max_workers = max_workers or (os.cpu_count() or 4) * 2
        self.chunk_size = chunk_size
        self.worker_pools: Dict[str, WorkerPool] = {}
        self.processing_policies: Dict[str, Callable] = {}
        self.task_queue = queue.PriorityQueue()
        self.results_cache: Dict[str, ProcessingResult] = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Initialize default worker pools
        self._initialize_default_pools()
        
        # Register default processing policies
        self.register_default_policies()
        
        # Start task dispatcher
        self._start_task_dispatcher()
    
    def _initialize_default_pools(self):
        """Initialize default worker pools"""
        # High-priority thread pool
        self.create_worker_pool("priority", max(2, self.max_workers // 4), "thread")
        
        # General processing thread pool
        self.create_worker_pool("general", self.max_workers // 2, "thread")
        
        # CPU-intensive process pool
        self.create_worker_pool("cpu_intensive", max(2, os.cpu_count() or 4), "process")
        
        # Validation-specific pool
        self.create_worker_pool("validation", max(4, self.max_workers // 3), "thread")
        
        self.logger.info(f"Initialized {len(self.worker_pools)} worker pools")
    
    def create_worker_pool(self, pool_name: str, max_workers: int, 
                          pool_type: str = "thread") -> WorkerPool:
        """Create a new worker pool"""
        with self.lock:
            if pool_name in self.worker_pools:
                self.logger.warning(f"Worker pool {pool_name} already exists, replacing")
                self.worker_pools[pool_name].shutdown()
            
            pool = WorkerPool(pool_name, max_workers, pool_type)
            self.worker_pools[pool_name] = pool
            
            self.logger.info(f"Created worker pool '{pool_name}' with {max_workers} {pool_type} workers")
            return pool
    
    def register_default_policies(self):
        """Register default processing policies"""
        self.register_policy("default", self._default_processing_policy)
        self.register_policy("validation", self._validation_policy)
        self.register_policy("indexing", self._indexing_policy)
        self.register_policy("batch", self._batch_policy)
        self.register_policy("priority", self._priority_policy)
    
    def register_policy(self, policy_name: str, policy_func: Callable):
        """Register a processing policy"""
        with self.lock:
            self.processing_policies[policy_name] = policy_func
            self.logger.info(f"Registered processing policy: {policy_name}")
    
    def process_batch(self, data_batch: List[Any], processor_func: Callable, 
                     policy: str = "default", **kwargs) -> List[ProcessingResult]:
        """
        Process a batch of data in parallel
        
        Args:
            data_batch: List of data items to process
            processor_func: Function to process each item
            policy: Processing policy to use
            **kwargs: Additional arguments for policy
        
        Returns:
            List of processing results
        """
        if not data_batch:
            return []
        
        # Get processing policy
        policy_func = self.processing_policies.get(policy, self._default_processing_policy)
        
        # Apply policy to determine processing strategy
        processing_config = policy_func(data_batch, processor_func, **kwargs)
        
        # Create tasks
        tasks = []
        for i, data_item in enumerate(data_batch):
            task = ProcessingTask(
                task_id=f"batch_{int(time.time())}_{i}",
                data=data_item,
                processor_func=processor_func,
                priority=processing_config.get("priority", 0)
            )
            tasks.append(task)
        
        # Process tasks
        return self._execute_tasks(tasks, processing_config)
    
    def process_chunks(self, data: List[Any], processor_func: Callable, 
                      policy: str = "default", **kwargs) -> List[ProcessingResult]:
        """
        Process data in chunks for better memory efficiency
        
        Args:
            data: List of data to process
            processor_func: Function to process each chunk
            policy: Processing policy to use
            **kwargs: Additional arguments
        """
        if not data:
            return []
        
        # Split data into chunks
        chunks = [data[i:i + self.chunk_size] for i in range(0, len(data), self.chunk_size)]
        
        # Process each chunk
        all_results = []
        for chunk_idx, chunk in enumerate(chunks):
            chunk_results = self.process_batch(
                chunk, processor_func, policy, 
                chunk_id=chunk_idx, **kwargs
            )
            all_results.extend(chunk_results)
        
        return all_results
    
    def _execute_tasks(self, tasks: List[ProcessingTask], 
                      processing_config: Dict[str, Any]) -> List[ProcessingResult]:
        """Execute a list of tasks according to processing configuration"""
        pool_name = processing_config.get("pool", "general")
        worker_pool = self.worker_pools.get(pool_name)
        
        if not worker_pool:
            self.logger.error(f"Worker pool {pool_name} not found, using general pool")
            worker_pool = self.worker_pools["general"]
        
        # Submit all tasks
        futures = []
        for task in tasks:
            future = worker_pool.submit_task(task)
            futures.append(future)
        
        # Collect results
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                
                # Cache result if requested
                if processing_config.get("cache_results", False):
                    self.results_cache[result.task_id] = result
                    
            except Exception as e:
                self.logger.error(f"Failed to get task result: {e}")
                results.append(ProcessingResult(
                    task_id="unknown",
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    def _start_task_dispatcher(self):
        """Start background task dispatcher for priority queue"""
        def dispatch_loop():
            while True:
                try:
                    # Get task from priority queue (blocks if empty)
                    priority, task = self.task_queue.get(timeout=1.0)
                    
                    # Process task with appropriate policy
                    policy_name = task.metadata.get("policy", "default")
                    policy_func = self.processing_policies.get(policy_name, self._default_processing_policy)
                    
                    # Execute task
                    processing_config = policy_func([task.data], task.processor_func)
                    results = self._execute_tasks([task], processing_config)
                    
                    # Store result
                    if results:
                        self.results_cache[task.task_id] = results[0]
                    
                    self.task_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Task dispatcher error: {e}")
        
        dispatcher_thread = threading.Thread(target=dispatch_loop, daemon=True)
        dispatcher_thread.start()
    
    # Processing Policies
    
    @staticmethod
    def _default_processing_policy(data_batch: List[Any], processor_func: Callable,
                                   **kwargs) -> Dict[str, Any]:
        """Default processing policy"""
        # Access parameters to avoid unused parameter warnings
        _ =  processor_func
        _ = kwargs

        batch_size = len(data_batch)
        
        if batch_size < 10:
            pool = "general"
        elif batch_size < 100:
            pool = "general"
        else:
            pool = "cpu_intensive"
        
        return {
            "pool": pool,
            "priority": 0,
            "cache_results": False,
            "timeout": 300  # 5 minutes
        }
    
    @staticmethod
    def _validation_policy(data_batch: List[Any], processor_func: Callable,
                           **kwargs) -> Dict[str, Any]:
        """Validation processing policy"""
        # Access parameters to avoid unused parameter warnings
        _ = data_batch
        _ = processor_func
        _ = kwargs
        
        return {
            "pool": "validation",
            "priority": 1,
            "cache_results": True,
            "timeout": 60,  # 1 minute
            "retry_count": 2
        }
    
    @staticmethod
    def _indexing_policy(data_batch: List[Any], processor_func: Callable,
                         **kwargs) -> Dict[str, Any]:
        """Indexing processing policy"""
        batch_size = len(data_batch)
        
        # Access parameters to avoid unused parameter warnings
        _ = processor_func
        _ = kwargs
        
        return {
            "pool": "cpu_intensive" if batch_size > 50 else "general",
            "priority": -1,  # Lower priority
            "cache_results": False,
            "timeout": 600,  # 10 minutes
            "chunk_parallel": batch_size > 1000
        }
    
    @staticmethod
    def _batch_policy(data_batch: List[Any], processor_func: Callable,
                      **kwargs) -> Dict[str, Any]:
        """Batch processing policy"""
        # Access parameters to avoid unused parameter warnings
        _ = data_batch
        _ = processor_func
        
        return {
            "pool": "cpu_intensive",
            "priority": 0,
            "cache_results": kwargs.get("cache", False),
            "timeout": 1800,  # 30 minutes
            "chunk_parallel": True
        }
    
    @staticmethod
    def _priority_policy(data_batch: List[Any], processor_func: Callable,
                         **kwargs) -> Dict[str, Any]:
        """Priority processing policy"""
        # Access parameters to avoid unused parameter warnings
        _ = data_batch
        _ = processor_func
        _ = kwargs
        
        return {
            "pool": "priority",
            "priority": 2,
            "cache_results": True,
            "timeout": 30,  # 30 seconds
            "immediate": True
        }
    
    # Specialized blockchain processing methods
    
    def validate_blocks_parallel(self, blocks: List[Any], validator_func: Callable) -> List[ProcessingResult]:
        """Validate multiple blocks in parallel"""
        return self.process_batch(blocks, validator_func, "validation")
    
    def index_events_parallel(self, events: List[Any], indexer_func: Callable) -> List[ProcessingResult]:
        """Index multiple events in parallel"""
        return self.process_chunks(events, indexer_func, "indexing")
    
    def process_entity_batch(self, entities: List[str], processor_func: Callable) -> List[ProcessingResult]:
        """Process entity batch with optimized settings"""
        return self.process_batch(entities, processor_func, "batch", cache=True)
    
    def priority_process(self, data: Any, processor_func: Callable) -> ProcessingResult:
        """Process single item with high priority"""
        results = self.process_batch([data], processor_func, "priority")
        return results[0] if results else ProcessingResult("failed", False, error="No result")
    
    # Monitoring and Management
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics"""
        with self.lock:
            pool_stats = {name: pool.get_stats() for name, pool in self.worker_pools.items()}
            
            # Calculate totals
            total_active = sum(stats["active_tasks"] for stats in pool_stats.values())
            total_completed = sum(stats["completed_tasks"] for stats in pool_stats.values())
            total_failed = sum(stats["failed_tasks"] for stats in pool_stats.values())
            
            return {
                "engine": {
                    "max_workers": self.max_workers,
                    "chunk_size": self.chunk_size,
                    "total_pools": len(self.worker_pools),
                    "registered_policies": len(self.processing_policies),
                    "cached_results": len(self.results_cache),
                    "queue_size": self.task_queue.qsize()
                },
                "totals": {
                    "active_tasks": total_active,
                    "completed_tasks": total_completed,
                    "failed_tasks": total_failed,
                    "total_tasks": total_completed + total_failed,
                    "overall_success_rate": round(
                        (total_completed / (total_completed + total_failed) * 100) 
                        if (total_completed + total_failed) > 0 else 0, 2
                    )
                },
                "pools": pool_stats
            }
    
    def optimize_engine(self):
        """Optimize engine performance"""
        with self.lock:
            # Clear old results cache
            if len(self.results_cache) > 10000:
                # Keep only recent results
                sorted_results = sorted(
                    self.results_cache.items(), 
                    key=lambda x: x[1].processing_time,
                    reverse=True
                )
                self.results_cache = dict(sorted_results[:5000])
            
            self.logger.info("Engine optimization completed")
    
    def get_pool_utilization(self) -> Dict[str, float]:
        """Get utilization percentage for each pool"""
        utilization = {}
        
        with self.lock:
            for name, pool in self.worker_pools.items():
                with pool.lock:
                    util_pct = (pool.active_tasks / pool.max_workers * 100) if pool.max_workers > 0 else 0
                    utilization[name] = round(util_pct, 2)
        
        return utilization
    
    def shutdown(self):
        """Shutdown all worker pools and engine"""
        self.logger.info("Shutting down parallel processing engine")
        
        with self.lock:
            # Shutdown all worker pools
            for pool in self.worker_pools.values():
                pool.shutdown()
            
            # Clear resources
            self.worker_pools.clear()
            self.results_cache.clear()
            
            # Empty task queue
            while not self.task_queue.empty():
                try:
                    self.task_queue.get_nowait()
                except queue.Empty:
                    break
        
        self.logger.info("Parallel processing engine shutdown complete")


# Factory functions and utilities

def create_parallel_engine(max_workers: Optional[int] = None, 
                          chunk_size: int = 100) -> ParallelProcessingEngine:
    """Create parallel processing engine with default configuration"""
    return ParallelProcessingEngine(max_workers, chunk_size)


def create_high_performance_engine() -> ParallelProcessingEngine:
    """Create high-performance parallel processing engine"""
    max_workers = (os.cpu_count() or 4) * 4  # Aggressive worker count
    engine = ParallelProcessingEngine(max_workers, chunk_size=50)
    
    # Add additional high-performance pools
    engine.create_worker_pool("high_priority", max(4, max_workers // 4), "thread")
    engine.create_worker_pool("bulk_processing", max(2, os.cpu_count() or 4), "process")
    
    return engine


def parallel_map(data: List[Any], func: Callable, max_workers: Optional[int] = None) -> List[Any]:
    """Simple parallel map function"""
    engine = create_parallel_engine(max_workers)
    
    try:
        results = engine.process_batch(data, func)
        return [r.result for r in results if r.success]
    finally:
        engine.shutdown()


def parallel_filter(data: List[Any], predicate: Callable, 
                   max_workers: Optional[int] = None) -> List[Any]:
    """Parallel filter function"""
    def filter_func(item):
        return item if predicate(item) else None
    
    engine = create_parallel_engine(max_workers)
    
    try:
        results = engine.process_batch(data, filter_func)
        return [r.result for r in results if r.success and r.result is not None]
    finally:
        engine.shutdown()