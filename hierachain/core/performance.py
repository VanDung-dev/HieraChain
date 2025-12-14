"""
Performance Optimization Module for HieraChain.

This module handles multi-processing capabilities to bypass the Python GIL
for heavy CPU operations (hashing, signature verification).
"""

import os
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

class ProcessPoolManager:
    """
    Singleton manager for a ProcessPoolExecutor (multiprocessing).
    
    Logic:
    - Default workers = 50% of available CPU cores.
    - Configurable via settings (in a real app, passing config here).
    """
    
    _instance = None
    _executor: Optional[ProcessPoolExecutor] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProcessPoolManager, cls).__new__(cls)
        return cls._instance

    def initialize(self, max_workers: int = None):
        """
        Initialize the process pool.
        
        Args:
            max_workers: Explicit override for number of processes.
                         If None, uses 50% of CPU cores (min 1).
        """
        if self._executor:
            return

        if max_workers is None:
            cpu_count = os.cpu_count() or 1
            # Secure default: 50% of cores, at least 1, at most cpu_count
            max_workers = max(1, cpu_count // 2)
        
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        logger.info(f"ProcessPool initialized with {max_workers} worker(s) (Total CPU: {os.cpu_count()})")

    async def run_task(self, func: Callable, *args) -> Any:
        """
        Run a CPU-bound function in a separate process and await result.
        
        Args:
            func: The function to run (MUST be picklable/top-level).
            args: Arguments for the function.
        """
        if not self._executor:
            self.initialize()
            
        loop = asyncio.get_running_loop()
        # run_in_executor runs blocking code in the pool without blocking the async loop
        return await loop.run_in_executor(self._executor, func, *args)

    def shutdown(self):
        """Shutdown the pool."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
            logger.info("ProcessPool shutdown.")

# Global instance
process_pool = ProcessPoolManager()
