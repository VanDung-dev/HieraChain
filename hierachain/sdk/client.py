"""
HieraChain SDK - Python Client Library.

This module provides a resilient client library for interacting with
HieraChain API endpoints. Features include:
- Automatic retry with exponential backoff
- Circuit breaker pattern for fail-fast behavior
- Both sync and async client variants
- Connection pooling support
"""

import time
import logging
import asyncio
import aiohttp
import requests
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from http import HTTPStatus

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class HieraChainClientConfig:
    """Configuration for HieraChain client."""
    base_url: str = "http://localhost:2661"
    timeout: float = 30.0
    max_retries: int = 5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0
    api_key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for fail-fast behavior.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject immediately
    - HALF_OPEN: Testing if service recovered
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, handling timeout transitions."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker opened after %d failures",
                self._failure_count
            )

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        state = self.state  # Triggers state transition check
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow test request
        return False  # OPEN state

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class HieraChainAPIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ServiceUnavailableError(HieraChainAPIError):
    """Service returned 503 - system overloaded or in lockdown."""
    pass


class LockdownError(HieraChainAPIError):
    """Node is in lockdown mode."""
    pass


@dataclass
class EventResult:
    """Result of submitting an event."""
    event_id: str
    status: str
    message: str = ""


@dataclass
class NodeStatus:
    """Status of the HieraChain node (API v3)."""
    status: str
    version: str
    chains_active: int
    license_active: bool
    uptime: str


@dataclass
class ChainStats:
    """Statistics for a specific chain."""
    chain_name: str
    total_blocks: int
    total_events: int
    unique_entities: int = 0
    proof_count: int | None = None
    registered_sub_chains: int | None = None


@dataclass
class EntityTrace:
    """Trace result for an entity."""
    entity_id: str
    chains: list[str]
    events: list[dict[str, Any]]


class HieraChainClient:
    """
    Synchronous client for HieraChain API.

    Features:
    - Automatic retry with exponential backoff
    - Circuit breaker for fail-fast
    - Handles 503 and lockdown responses

    Example:
        client = HieraChainClient(config)
        result = client.submit_event("supply_chain", {"type": "quality_check", "entity_id": "P-1"})
        status = client.get_node_status()
    """

    def __init__(self, config: HieraChainClientConfig | None = None):
        """Initialize client with configuration."""
        self.config = config or HieraChainClientConfig()
        self._circuit = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
        )
        self._session: Any = None

    def _get_session(self) -> Any:
        """Get or create HTTP session."""
        if self._session is None:
            try:
                self._session = requests.Session()
                self._session.headers.update(self.config.headers)
                if self.config.api_key:
                    self._session.headers["X-API-Key"] = self.config.api_key
            except ImportError:
                raise ImportError("requests library required: pip install requests")
        return self._session

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff."""
        delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        return min(delay, self.config.max_delay)

    def _check_circuit_breaker(self) -> None:
        """Check if request should be allowed by circuit breaker."""
        if not self._circuit.allow_request():
            raise CircuitOpenError(
                f"Circuit breaker is open. Retry after "
                f"{self.config.circuit_recovery_timeout}s"
            )

    def _handle_response(self, response: Any) -> dict[str, Any]:
        """Handle HTTP response and check for errors."""
        if response.status_code == HTTPStatus.SERVICE_UNAVAILABLE:
            raise ServiceUnavailableError("Service unavailable (503)", status_code=503)

        if response.headers.get("X-Lockdown-Mode") == "true":
            raise LockdownError("Node is in lockdown mode", status_code=503)

        if response.status_code >= 500:
            response.raise_for_status()

        self._circuit.record_success()
        return response.json()

    def _execute_request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Perform a single HTTP request and handle the response."""
        session = self._get_session()
        response = session.request(
            method=method,
            url=url,
            json=data,
            params=params,
            timeout=self.config.timeout,
        )
        return self._handle_response(response)

    def _handle_request_error(self, e: Exception, attempt: int) -> None:
        """Handle request failure, record to circuit breaker and sleep if needed."""
        self._circuit.record_failure()

        if attempt >= self.config.max_retries:
            if isinstance(e, (ServiceUnavailableError, LockdownError)):
                raise e
            raise HieraChainAPIError(str(e)) from e

        delay = self._calculate_delay(attempt)
        logger.warning(
            "Request failed (%s: %s), "
            "retry %d/%d in %.1fs",
            type(e).__name__, e,
            attempt + 1, self.config.max_retries, delay
        )
        time.sleep(delay)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic and circuit breaker.
        """
        self._check_circuit_breaker()
        url = f"{self.config.base_url}{endpoint}"

        for attempt in range(self.config.max_retries + 1):
            try:
                return self._execute_request(method, url, data, params)
            except Exception as e:
                self._handle_request_error(e, attempt)

        raise HieraChainAPIError(
            f"Request failed after {self.config.max_retries} retries"
        )

    def submit_event(self, chain_name: str, event_data: dict[str, Any]) -> EventResult:
        """
        Submit an event to a specific sub-chain.

        Args:
            chain_name: Name of the chain
            event_data: Event data dictionary

        Returns:
            EventResult with event_id and status
        """
        url = f"/api/v1/chains/{chain_name}/events"
        response = self._request("POST", url, data=event_data)
        return EventResult(
            event_id=response.get("event_id", ""),
            status=response.get("status", "unknown"),
            message=response.get("message", ""),
        )

    def get_block(
        self,
        chain_name: str,
        index_or_hash: str | int,
        resolve_cid: bool = False
    ) -> dict[str, Any]:
        """
        Get a specific block by index or hash.

        Args:
            chain_name: Name of the chain
            index_or_hash: Block index or hash
            resolve_cid: Whether to resolve IPFS CIDs

        Returns:
            Block data dictionary
        """
        params = {"resolve_cid": str(resolve_cid).lower()}
        url = f"/api/v1/chains/{chain_name}/blocks/{index_or_hash}"
        return self._request("GET", url, params=params)

    def get_node_status(self) -> NodeStatus:
        """
        Get current node status (API v3).

        Returns:
            NodeStatus object
        """
        response = self._request("GET", "/api/v3/status")
        return NodeStatus(
            status=response.get("status", "unknown"),
            version=response.get("version", "unknown"),
            chains_active=response.get("chains_active", 0),
            license_active=response.get("license_active", False),
            uptime=response.get("uptime", "unknown"),
        )

    def get_chain_stats(self, chain_name: str) -> ChainStats:
        """
        Get statistics for a specific chain.

        Args:
            chain_name: Name of the chain

        Returns:
            ChainStats object
        """
        response = self._request("GET", f"/api/v1/chains/{chain_name}/stats")
        return ChainStats(
            chain_name=response.get("chain_name", chain_name),
            total_blocks=response.get("total_blocks", 0),
            total_events=response.get("total_events", 0),
            unique_entities=response.get("unique_entities", 0),
            proof_count=response.get("proof_count"),
            registered_sub_chains=response.get("registered_sub_chains")
        )

    def submit_proof(self, chain_name: str) -> dict[str, Any]:
        """
        Submit proof from sub-chain to main chain.

        Args:
            chain_name: Name of the sub-chain

        Returns:
            API response dictionary
        """
        return self._request("POST", f"/api/v1/chains/{chain_name}/submit-proof")

    def trace_entity(
        self,
        entity_id: str,
        chain_name: str | None = None,
        resolve_cid: bool = False
    ) -> EntityTrace:
        """
        Trace an entity across chains.

        Args:
            entity_id: ID of the entity to trace
            chain_name: Optional chain name filter
            resolve_cid: Whether to resolve IPFS CIDs

        Returns:
            EntityTrace object
        """
        params = {"resolve_cid": str(resolve_cid).lower()}
        if chain_name:
            params["chain_name"] = chain_name

        url = f"/api/v1/entities/{entity_id}/trace"
        response = self._request("GET", url, params=params)
        return EntityTrace(
            entity_id=response.get("entity_id", entity_id),
            chains=response.get("chains", []),
            events=response.get("events", [])
        )

    def health_check(self) -> bool:
        """
        Check if the node is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._request("GET", "/health")
            return response.get("status") == "healthy"
        except (HieraChainAPIError, CircuitOpenError):
            return False

    def close(self) -> None:
        """Close the client session."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> "HieraChainClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class HieraChainAsyncClient:
    """
    Asynchronous client for HieraChain API.

    Same features as HieraChainClient but with async/await support.

    Example:
        async with HieraChainAsyncClient(config) as client:
            result = await client.submit_event("supply_chain", {"type": "quality_check"})
            status = await client.get_node_status()
    """

    def __init__(self, config: HieraChainClientConfig | None = None):
        """Initialize async client with configuration."""
        self.config = config or HieraChainClientConfig()
        self._circuit = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
        )
        self._session: Any = None

    async def _get_session(self) -> Any:
        """Get or create aiohttp session."""
        if self._session is None:
            headers = dict(self.config.headers)
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        return min(delay, self.config.max_delay)

    def _check_circuit_breaker(self) -> None:
        """Check if request should be allowed by circuit breaker."""
        if not self._circuit.allow_request():
            raise CircuitOpenError(
                f"Circuit breaker is open. Retry after "
                f"{self.config.circuit_recovery_timeout}s"
            )

    async def _handle_response(self, response: Any) -> dict[str, Any]:
        """Handle async HTTP response and check for errors."""
        if response.status == HTTPStatus.SERVICE_UNAVAILABLE:
            raise ServiceUnavailableError("Service unavailable", 503)

        if response.headers.get("X-Lockdown-Mode") == "true":
            raise LockdownError("Node is in lockdown mode", 503)

        if response.status >= 500:
            response.raise_for_status()

        self._circuit.record_success()
        return await response.json()

    async def _execute_request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Perform a single async HTTP request and handle the response."""
        session = await self._get_session()
        async with session.request(
            method=method,
            url=url,
            json=data,
            params=params,
            timeout=self.config.timeout,
        ) as response:
            return await self._handle_response(response)

    async def _handle_request_error(self, e: Exception, attempt: int) -> None:
        """
        Handle async request failure, record to circuit breaker and sleep if needed.
        """
        self._circuit.record_failure()

        if attempt >= self.config.max_retries:
            if isinstance(
                e, (ServiceUnavailableError, LockdownError, HieraChainAPIError)
            ):
                raise e
            raise HieraChainAPIError(str(e)) from e

        delay = self._calculate_delay(attempt)
        logger.warning(
            "Request failed (%s: %s), "
            "retry %d/%d in %.1fs",
            type(e).__name__, e,
            attempt + 1, self.config.max_retries, delay
        )
        await asyncio.sleep(delay)

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make async HTTP request with retry logic."""
        self._check_circuit_breaker()
        url = f"{self.config.base_url}{endpoint}"

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self._execute_request(method, url, data, params)
            except Exception as e:
                await self._handle_request_error(e, attempt)

        raise HieraChainAPIError(
            f"Request failed after {self.config.max_retries} retries"
        )

    async def submit_event(self, chain_name: str, event_data: dict[str, Any]) -> EventResult:
        """Submit an event to the blockchain."""
        url = f"/api/v1/chains/{chain_name}/events"
        response = await self._request("POST", url, data=event_data)
        return EventResult(
            event_id=response.get("event_id", ""),
            status=response.get("status", "unknown"),
            message=response.get("message", ""),
        )

    async def get_block(
        self,
        chain_name: str,
        index_or_hash: str | int,
        resolve_cid: bool = False
    ) -> dict[str, Any]:
        """Get a specific block by index or hash."""
        params = {"resolve_cid": str(resolve_cid).lower()}
        url = f"/api/v1/chains/{chain_name}/blocks/{index_or_hash}"
        return await self._request("GET", url, params=params)

    async def get_node_status(self) -> NodeStatus:
        """Get current node status (API v3)."""
        response = await self._request("GET", "/api/v3/status")
        return NodeStatus(
            status=response.get("status", "unknown"),
            version=response.get("version", "unknown"),
            chains_active=response.get("chains_active", 0),
            license_active=response.get("license_active", False),
            uptime=response.get("uptime", "unknown"),
        )

    async def get_chain_stats(self, chain_name: str) -> ChainStats:
        """Get statistics for a specific chain."""
        response = await self._request("GET", f"/api/v1/chains/{chain_name}/stats")
        return ChainStats(
            chain_name=response.get("chain_name", chain_name),
            total_blocks=response.get("total_blocks", 0),
            total_events=response.get("total_events", 0),
            unique_entities=response.get("unique_entities", 0),
            proof_count=response.get("proof_count"),
            registered_sub_chains=response.get("registered_sub_chains")
        )

    async def submit_proof(self, chain_name: str) -> dict[str, Any]:
        """Submit proof from sub-chain to main chain."""
        return await self._request("POST", f"/api/v1/chains/{chain_name}/submit-proof")

    async def trace_entity(
        self,
        entity_id: str,
        chain_name: str | None = None,
        resolve_cid: bool = False
    ) -> EntityTrace:
        """Trace an entity across chains."""
        params = {"resolve_cid": str(resolve_cid).lower()}
        if chain_name:
            params["chain_name"] = chain_name

        url = f"/api/v1/entities/{entity_id}/trace"
        response = await self._request("GET", url, params=params)
        return EntityTrace(
            entity_id=response.get("entity_id", entity_id),
            chains=response.get("chains", []),
            events=response.get("events", [])
        )

    async def health_check(self) -> bool:
        """Check if the node is healthy."""
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "healthy"
        except (HieraChainAPIError, CircuitOpenError):
            return False

    async def close(self) -> None:
        """Close the async client session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "HieraChainAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
