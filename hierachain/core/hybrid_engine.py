"""
Hybrid Processing Engine for HieraChain Framework.

This module provides a hybrid engine that attempts to use the Go Engine
for high-performance processing, with automatic fallback to Python
when Go Engine is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from hierachain.core.parallel_engine import (
    ParallelProcessingEngine,
    ProcessingTask,
    ProcessingResult,
)
from hierachain.integration.types import (
    Transaction as GoTransaction,
    BatchResult,
)
from hierachain.integration.arrow_client import ArrowClient


logger = logging.getLogger(__name__)


class EngineMode(Enum):
    """Current engine mode."""
    GO = "go"
    PYTHON = "python"
    HYBRID = "hybrid"


@dataclass
class HybridEngineConfig:
    """Configuration for the hybrid engine."""
    use_go_engine: bool = field(
        default_factory=lambda: os.getenv("HIE_USE_GO_ENGINE", "false").lower() == "true"
    )
    use_arrow: bool = field(
        default_factory=lambda: os.getenv("HIE_USE_ARROW_TRANSPORT", "false").lower() == "true"
    )
    go_engine_address: str = field(
        default_factory=lambda: os.getenv("HIE_GO_ENGINE_ADDRESS", "localhost:50051")
    )
    go_engine_timeout: float = field(
        default_factory=lambda: float(os.getenv("HIE_GO_ENGINE_TIMEOUT", "30.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("HIE_GO_ENGINE_RETRIES", "3"))
    )
    python_workers: int = field(
        default_factory=lambda: int(os.getenv("HIE_PYTHON_WORKERS", "4"))
    )
    fallback_enabled: bool = True
    health_check_interval: float = 30.0


@dataclass
class HybridResult:
    """Result from hybrid engine processing."""
    success: bool
    processed_count: int
    failed_count: int
    processing_time_ms: float
    engine_used: EngineMode
    errors: list[dict[str, str]] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)


class HybridEngine:
    """
    Hybrid processing engine that uses Go Engine when available,
    with automatic fallback to Python ParallelProcessingEngine.

    Example:
        async with HybridEngine() as engine:
            result = await engine.process_transactions([
                {"tx_id": "tx-1", "entity_id": "e-1", "event_type": "created"},
            ])
            print(f"Engine used: {result.engine_used}")
            print(f"Processed: {result.processed_count}")
    """

    def __init__(self, config: HybridEngineConfig | None = None):
        """
        Initialize hybrid engine.

        Args:
            config: Configuration object. If None, uses environment variables.
        """
        self.config = config or HybridEngineConfig()
        self._arrow_client: ArrowClient | None = None
        self._python_engine: ParallelProcessingEngine | None = None
        self._go_available: bool = False
        self._last_health_check: float = 0
        self._mode = EngineMode.HYBRID if self.config.use_go_engine else EngineMode.PYTHON
        self._stats = {
            "go_requests": 0,
            "python_requests": 0,
            "go_failures": 0,
            "fallback_count": 0,
        }

    async def __aenter__(self) -> HybridEngine:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()

    async def start(self) -> None:
        """Initialize and start the engine."""
        # Initialize Python fallback engine
        self._python_engine = ParallelProcessingEngine(
            max_workers=self.config.python_workers
        )
        logger.info("Python engine initialized")

        # Try to connect to Go engine if enabled
        if self.config.use_go_engine:
            await self._try_connect_go()

    async def _try_connect_go(self) -> bool:
        """Attempt to connect to Go Engine (via Arrow TCP)."""
        try:
            # Address format "host:port", split for ArrowClient
            host, port = "localhost", 50051
            if ":" in self.config.go_engine_address:
                parts = self.config.go_engine_address.split(":")
                host = parts[0]
                port = int(parts[1])
            
            self._arrow_client = ArrowClient(host=host, port=port)
            # ArrowClient.connect is sync, run in executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._arrow_client.connect)
            
            self._go_available = True
            self._last_health_check = time.time()
            logger.info(f"Connected to Go Engine (Arrow) at {self.config.go_engine_address}")
            return True

        except Exception as e:
            self._go_available = False
            logger.warning(f"Go Engine unavailable: {e}. Using Python fallback.")
            return False

    async def _check_go_health(self) -> bool:
        """Check if Go Engine is healthy."""
        if not self._arrow_client:
            return False

        try:
            # For now assume healthy if connected (or implement simple ping later)
            self._go_available = True 
            self._last_health_check = time.time()
            return True

        except Exception:
            self._go_available = False
            return False

    async def _ensure_go_connection(self) -> bool:
        """Ensure Go connection is available, reconnect if needed."""
        # Check if health check is due
        if (
            self.config.use_go_engine
            and time.time() - self._last_health_check > self.config.health_check_interval
        ):
            if self._go_available:
                await self._check_go_health()
            else:
                await self._try_connect_go()

        return self._go_available

    async def process_transactions(
        self,
        transactions: list[dict[str, Any]],
        force_python: bool = False,
    ) -> HybridResult:
        """
        Process a batch of transactions.

        Args:
            transactions: List of transaction dicts with tx_id, entity_id, event_type.
            force_python: If True, skip Go Engine and use Python directly.

        Returns:
            HybridResult with processing results.
        """
        start_time = time.time()

        # Check if we should use Go
        use_go = (
            not force_python
            and self.config.use_go_engine
            and await self._ensure_go_connection()
        )

        if use_go:
            result = await self._process_with_go(transactions)
            if result is not None:
                return result

            # Go failed, try fallback
            if self.config.fallback_enabled:
                self._stats["fallback_count"] += 1
                logger.warning("Go Engine failed, falling back to Python")
                return await self._process_with_python(transactions, start_time)
            else:
                return HybridResult(
                    success=False,
                    processed_count=0,
                    failed_count=len(transactions),
                    processing_time_ms=(time.time() - start_time) * 1000,
                    engine_used=EngineMode.GO,
                    errors=[{"error": "Go Engine unavailable and fallback disabled"}],
                )

        # Use Python engine
        return await self._process_with_python(transactions, start_time)

    async def _process_with_go(
        self,
        transactions: list[dict[str, Any]],
    ) -> HybridResult | None:
        """Process transactions with Go Engine."""
        if not self._go_available or not self._arrow_client:
            return None

        try:
            # Convert to Go transactions
            go_txs = [
                GoTransaction(
                    tx_id=tx.get("tx_id", tx.get("id", "")),
                    entity_id=tx.get("entity_id", ""),
                    event_type=tx.get("event_type", ""),
                    details={
                        k: str(v) for k, v in tx.items()
                        if k not in ("tx_id", "id", "entity_id", "event_type")
                    },
                )
                for tx in transactions
            ]

            # Use Arrow Client (Sync wrapped in Async)
            loop = asyncio.get_running_loop()
            resp_bytes = await loop.run_in_executor(None, self._arrow_client.submit_batch, go_txs)
            
            result: BatchResult
            # Mock result from "OK" response
            if resp_bytes == b"OK" or len(resp_bytes) > 0:
                result = BatchResult(
                    success=True,
                    message="Processed via Arrow",
                    processed_tx_ids=[tx.tx_id for tx in go_txs],
                    processing_time_ms=0,
                    errors=[],
                )
            else:
                    raise Exception("Empty or invalid response from Arrow Server")

            self._stats["go_requests"] += 1

            return HybridResult(
                success=result.success,
                processed_count=len(result.processed_tx_ids),
                failed_count=len(result.errors),
                processing_time_ms=result.processing_time_ms,
                engine_used=EngineMode.GO,
                errors=result.errors,
                results=result.processed_tx_ids,
            )

        except Exception as e:
            self._go_available = False
            self._stats["go_failures"] += 1
            logger.error(f"Go Engine error: {e}")
            return None

    async def _process_with_python(
        self,
        transactions: list[dict[str, Any]],
        start_time: float,
    ) -> HybridResult:
        """Process transactions with Python engine."""
        if not self._python_engine:
            return HybridResult(
                success=False,
                processed_count=0,
                failed_count=len(transactions),
                processing_time_ms=(time.time() - start_time) * 1000,
                engine_used=EngineMode.PYTHON,
                errors=[{"error": "Python engine not initialized"}],
            )

        self._stats["python_requests"] += 1

        # Process transactions using Python engine
        def process_tx(tx: dict) -> dict:
            # Placeholder processing logic
            return {"tx_id": tx.get("tx_id", tx.get("id")), "status": "processed"}

        results = self._python_engine.process_batch(
            transactions,
            process_tx,
            policy="default",
        )

        processed = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        return HybridResult(
            success=len(failed) == 0,
            processed_count=len(processed),
            failed_count=len(failed),
            processing_time_ms=(time.time() - start_time) * 1000,
            engine_used=EngineMode.PYTHON,
            errors=[{"tx_id": r.task_id, "error": r.error or ""} for r in failed],
            results=[r.result for r in processed],
        )

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "mode": self._mode.value,
            "go_available": self._go_available,
            "config": {
                "use_go_engine": self.config.use_go_engine,
                "go_engine_address": self.config.go_engine_address,
                "fallback_enabled": self.config.fallback_enabled,
            },
            "stats": self._stats.copy(),
        }

    @property
    def current_mode(self) -> EngineMode:
        """Get current engine mode."""
        if self._go_available:
            return EngineMode.GO
        return EngineMode.PYTHON

    async def shutdown(self) -> None:
        """Shutdown the engine."""
        if self._arrow_client:
            self._arrow_client.close()
            self._arrow_client = None

        if self._python_engine:
            self._python_engine.shutdown()
            self._python_engine = None

        logger.info("Hybrid engine shut down")


class HybridEngineSync:
    """
    Synchronous wrapper for HybridEngine.

    Example:
        with HybridEngineSync() as engine:
            result = engine.process_transactions([...])
    """

    def __init__(self, config: HybridEngineConfig | None = None):
        """Initialize sync engine wrapper."""
        self._async_engine = HybridEngine(config)
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self) -> HybridEngineSync:
        """Context manager entry."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._async_engine.start())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if self._loop:
            self._loop.run_until_complete(self._async_engine.shutdown())
            self._loop.close()
            self._loop = None

    def _run(self, coro):
        """Run coroutine in event loop."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)

    def process_transactions(
        self,
        transactions: list[dict],
        force_python: bool = False,
    ) -> HybridResult:
        """Process transactions."""
        return self._run(
            self._async_engine.process_transactions(transactions, force_python)
        )

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return self._async_engine.get_stats()
