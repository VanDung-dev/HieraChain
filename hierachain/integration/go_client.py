"""
Go Engine gRPC Client for HieraChain Framework.

This module provides a Python client to communicate with the Go Engine
via gRPC for high-performance transaction processing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

import grpc
import grpc.aio

# Import generated protobuf stubs
from hierachain.integration.proto import hierachain_pb2 as pb
from hierachain.integration.proto import hierachain_pb2_grpc as pb_grpc


logger = logging.getLogger(__name__)


class GoEngineError(Exception):
    """Exception raised for Go Engine errors."""
    
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class GoEngineConnectionError(GoEngineError):
    """Exception raised when connection to Go Engine fails."""
    pass


class GoEngineUnavailableError(GoEngineError):
    """Exception raised when Go Engine is temporarily unavailable."""
    pass


@dataclass
class Transaction:
    """Transaction to submit to Go Engine."""
    
    tx_id: str
    entity_id: str
    event_type: str
    arrow_payload: bytes = b""
    signature: str = ""
    timestamp: float = field(default_factory=time.time)
    details: dict[str, str] = field(default_factory=dict)
    
    def to_proto(self) -> pb.Transaction:
        """Convert to protobuf message."""
        return pb.Transaction(
            tx_id=self.tx_id,
            entity_id=self.entity_id,
            event_type=self.event_type,
            arrow_payload=self.arrow_payload,
            signature=self.signature,
            timestamp=self.timestamp,
            details=self.details,
        )


@dataclass
class BatchResult:
    """Result of batch transaction processing."""
    
    success: bool
    message: str
    processed_tx_ids: list[str]
    processing_time_ms: int
    errors: list[dict[str, str]]
    
    @classmethod
    def from_proto(cls, result: pb.BatchResult) -> BatchResult:
        """Create from protobuf message."""
        return cls(
            success=result.success,
            message=result.message,
            processed_tx_ids=list(result.processed_tx_ids),
            processing_time_ms=result.processing_time_ms,
            errors=[
                {
                    "tx_id": e.tx_id,
                    "error_message": e.error_message,
                    "error_code": e.error_code,
                }
                for e in result.errors
            ],
        )


@dataclass
class TxStatus:
    """Status of a transaction."""
    
    tx_id: str
    status: str  # "PENDING", "CONFIRMED", "FAILED"
    timestamp: int
    block_hash: str = ""
    
    @classmethod
    def from_proto(cls, status: pb.TxStatus) -> TxStatus:
        """Create from protobuf message."""
        status_map = {
            pb.TxStatus.PENDING: "PENDING",
            pb.TxStatus.CONFIRMED: "CONFIRMED",
            pb.TxStatus.FAILED: "FAILED",
        }
        return cls(
            tx_id=status.tx_id,
            status=status_map.get(status.status, "UNKNOWN"),
            timestamp=status.timestamp,
            block_hash=status.block_hash,
        )


@dataclass
class HealthResponse:
    """Health status of the Go Engine."""
    
    healthy: bool
    version: str
    uptime_seconds: int
    stats: dict[str, Any]
    
    @classmethod
    def from_proto(cls, resp: pb.HealthResponse) -> HealthResponse:
        """Create from protobuf message."""
        stats = {}
        if resp.stats:
            stats = {
                "transactions_processed": resp.stats.transactions_processed,
                "blocks_created": resp.stats.blocks_created,
                "pending_transactions": resp.stats.pending_transactions,
                "avg_processing_time_ms": resp.stats.avg_processing_time_ms,
            }
        return cls(
            healthy=resp.healthy,
            version=resp.version,
            uptime_seconds=resp.uptime_seconds,
            stats=stats,
        )


class GoEngineClient:
    """
    Async gRPC client for communicating with Go Engine.
    
    Example:
        async with GoEngineClient("localhost:50051") as client:
            health = await client.health_check()
            print(f"Engine healthy: {health.healthy}")
            
            result = await client.submit_batch([
                Transaction(tx_id="tx-1", entity_id="e-1", event_type="created"),
            ])
            print(f"Processed: {result.processed_tx_ids}")
    """
    
    def __init__(
        self,
        address: str = "localhost:50051",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        """
        Initialize Go Engine client.
        
        Args:
            address: Server address in format "host:port".
            timeout_seconds: Default timeout for RPC calls.
            max_retries: Maximum number of retry attempts.
            retry_delay_seconds: Delay between retry attempts.
        """
        self.address = address
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay_seconds
        
        self._channel: grpc.aio.Channel | None = None
        self._stub: pb_grpc.HieraChainEngineStub | None = None
        self._connected = False
    
    async def __aenter__(self) -> GoEngineClient:
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def connect(self) -> None:
        """Establish connection to Go Engine."""
        if self._connected:
            return
        
        try:
            self._channel = grpc.aio.insecure_channel(self.address)
            self._stub = pb_grpc.HieraChainEngineStub(self._channel)
            
            # Verify connection with health check
            await self.health_check()
            self._connected = True
            logger.info(f"Connected to Go Engine at {self.address}")
            
        except grpc.aio.AioRpcError as e:
            self._connected = False
            raise GoEngineConnectionError(
                f"Failed to connect to Go Engine at {self.address}: {e.details()}"
            ) from e
    
    async def close(self) -> None:
        """Close connection to Go Engine."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            self._connected = False
            logger.info("Disconnected from Go Engine")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected
    
    async def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._connected:
            await self.connect()
    
    async def _call_with_retry(self, method, *args, **kwargs):
        """Execute RPC call with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                await self._ensure_connected()
                return await method(*args, **kwargs)
                
            except grpc.aio.AioRpcError as e:
                last_error = e
                
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    self._connected = False
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"Go Engine unavailable, retrying in {self.retry_delay}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(self.retry_delay)
                        continue
                
                # Non-retryable error
                raise GoEngineError(f"RPC error: {e.details()}", str(e.code())) from e
        
        raise GoEngineUnavailableError(
            f"Go Engine unavailable after {self.max_retries} attempts"
        ) from last_error
    
    async def health_check(self) -> HealthResponse:
        """
        Check health of Go Engine.
        
        Returns:
            HealthResponse with engine status and statistics.
            
        Raises:
            GoEngineError: If health check fails.
        """
        if not self._stub:
            raise GoEngineError("Not connected to Go Engine")
        
        try:
            response = await self._stub.HealthCheck(
                pb.Empty(),
                timeout=self.timeout,
            )
            return HealthResponse.from_proto(response)
            
        except grpc.aio.AioRpcError as e:
            raise GoEngineError(f"Health check failed: {e.details()}") from e
    
    async def submit_batch(
        self,
        transactions: list[Transaction] | list[dict],
    ) -> BatchResult:
        """
        Submit a batch of transactions for processing.
        
        Args:
            transactions: List of Transaction objects or dicts.
            
        Returns:
            BatchResult with processing results.
            
        Raises:
            GoEngineError: If batch submission fails.
        """
        # Convert dicts to Transaction objects
        tx_list = []
        for tx in transactions:
            if isinstance(tx, dict):
                tx = Transaction(**tx)
            tx_list.append(tx.to_proto())
        
        batch = pb.TransactionBatch(transactions=tx_list)
        
        async def _submit():
            return await self._stub.SubmitBatch(batch, timeout=self.timeout)
        
        response = await self._call_with_retry(_submit)
        return BatchResult.from_proto(response)
    
    async def stream_transactions(
        self,
        transactions: AsyncIterator[Transaction] | Iterator[Transaction],
    ) -> AsyncIterator[TxStatus]:
        """
        Stream transactions for real-time processing.
        
        Args:
            transactions: Iterator of transactions to stream.
            
        Yields:
            TxStatus for each processed transaction.
            
        Raises:
            GoEngineError: If streaming fails.
        """
        await self._ensure_connected()
        
        if not self._stub:
            raise GoEngineError("Not connected to Go Engine")
        
        async def tx_generator():
            async for tx in transactions if hasattr(transactions, '__anext__') else iter(transactions):
                yield tx.to_proto() if isinstance(tx, Transaction) else Transaction(**tx).to_proto()
        
        try:
            stream = self._stub.StreamTransactions(tx_generator())
            async for status in stream:
                yield TxStatus.from_proto(status)
                
        except grpc.aio.AioRpcError as e:
            raise GoEngineError(f"Stream error: {e.details()}") from e


class GoEngineClientSync:
    """
    Synchronous wrapper for GoEngineClient.
    
    Example:
        with GoEngineClientSync("localhost:50051") as client:
            health = client.health_check()
            print(f"Engine healthy: {health.healthy}")
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize sync client wrapper."""
        self._async_client = GoEngineClient(*args, **kwargs)
        self._loop = None
    
    def __enter__(self) -> GoEngineClientSync:
        """Context manager entry."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._async_client.connect())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if self._loop:
            self._loop.run_until_complete(self._async_client.close())
            self._loop.close()
            self._loop = None
    
    def _run(self, coro):
        """Run coroutine in event loop."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)
    
    def connect(self) -> None:
        """Connect to Go Engine."""
        self._run(self._async_client.connect())
    
    def close(self) -> None:
        """Close connection."""
        self._run(self._async_client.close())
    
    def health_check(self) -> HealthResponse:
        """Check health of Go Engine."""
        return self._run(self._async_client.health_check())
    
    def submit_batch(self, transactions: list) -> BatchResult:
        """Submit a batch of transactions."""
        return self._run(self._async_client.submit_batch(transactions))
