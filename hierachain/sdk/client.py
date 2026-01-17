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
    base_url: str = "http://localhost:8000"
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
                f"Circuit breaker opened after {self._failure_count} failures"
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
class ChainStatus:
    """Status of the blockchain."""
    node_id: str
    is_healthy: bool
    block_height: int
    pending_events: int
    is_lockdown: bool = False


class HieraChainClient:
    """
    Synchronous client for HieraChain API.

    Features:
    - Automatic retry with exponential backoff
    - Circuit breaker for fail-fast
    - Handles 503 and lockdown responses

    Example:
        client = HieraChainClient(config)
        result = client.submit_event({"type": "transfer", "amount": 100})
        status = client.get_chain_status()
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
                import requests
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

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic and circuit breaker.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            Response JSON as dictionary

        Raises:
            CircuitOpenError: If circuit breaker is open
            HieraChainAPIError: For API errors after retries exhausted
        """
        if not self._circuit.allow_request():
            raise CircuitOpenError(
                f"Circuit breaker is open. Retry after "
                f"{self.config.circuit_recovery_timeout}s"
            )

        url = f"{self.config.base_url}{endpoint}"
        session = self._get_session()
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.config.timeout,
                )

                # Handle specific status codes
                if response.status_code == HTTPStatus.SERVICE_UNAVAILABLE:
                    raise ServiceUnavailableError(
                        "Service unavailable (503)",
                        status_code=503
                    )

                # Check for lockdown header or response
                if response.headers.get("X-Lockdown-Mode") == "true":
                    raise LockdownError("Node is in lockdown mode", status_code=503)

                if response.status_code >= 500:
                    response.raise_for_status()

                # Success
                self._circuit.record_success()
                return response.json()

            except (ServiceUnavailableError, LockdownError) as e:
                self._circuit.record_failure()
                last_error = e

                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Request failed ({e}), retry {attempt + 1}/"
                        f"{self.config.max_retries} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                else:
                    raise

            except Exception as e:
                self._circuit.record_failure()
                last_error = e

                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Request error ({e}), retry {attempt + 1}/"
                        f"{self.config.max_retries} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                else:
                    raise HieraChainAPIError(str(e)) from last_error

        raise HieraChainAPIError(f"Request failed after {self.config.max_retries} retries")

    def submit_event(self, event_data: dict[str, Any]) -> EventResult:
        """
        Submit an event to the blockchain.

        Args:
            event_data: Event data dictionary

        Returns:
            EventResult with event_id and status
        """
        response = self._request("POST", "/api/v1/events", data=event_data)
        return EventResult(
            event_id=response.get("event_id", ""),
            status=response.get("status", "unknown"),
            message=response.get("message", ""),
        )

    def get_block(self, block_id: str) -> dict[str, Any]:
        """
        Get a block by ID or index.

        Args:
            block_id: Block ID or index

        Returns:
            Block data dictionary
        """
        return self._request("GET", f"/api/v1/blocks/{block_id}")

    def get_chain_status(self) -> ChainStatus:
        """
        Get current blockchain status.

        Returns:
            ChainStatus object
        """
        response = self._request("GET", "/api/v1/status")
        return ChainStatus(
            node_id=response.get("node_id", "unknown"),
            is_healthy=response.get("is_healthy", False),
            block_height=response.get("block_height", 0),
            pending_events=response.get("pending_events", 0),
            is_lockdown=response.get("is_lockdown", False),
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
        except Exception:
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
            result = await client.submit_event({"type": "transfer"})
            status = await client.get_chain_status()
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
            try:
                import aiohttp
                headers = dict(self.config.headers)
                if self.config.api_key:
                    headers["X-API-Key"] = self.config.api_key
                self._session = aiohttp.ClientSession(headers=headers)
            except ImportError:
                raise ImportError("aiohttp library required: pip install aiohttp")
        return self._session

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        return min(delay, self.config.max_delay)

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make async HTTP request with retry logic."""
        if not self._circuit.allow_request():
            raise CircuitOpenError(
                f"Circuit breaker is open. Retry after "
                f"{self.config.circuit_recovery_timeout}s"
            )

        url = f"{self.config.base_url}{endpoint}"
        session = await self._get_session()

        for attempt in range(self.config.max_retries + 1):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.config.timeout,
                ) as response:
                    if response.status == HTTPStatus.SERVICE_UNAVAILABLE:
                        raise ServiceUnavailableError("Service unavailable", 503)

                    if response.headers.get("X-Lockdown-Mode") == "true":
                        raise LockdownError("Node is in lockdown mode", 503)

                    if response.status >= 500:
                        response.raise_for_status()

                    self._circuit.record_success()
                    return await response.json()

            except (ServiceUnavailableError, LockdownError) as e:
                self._circuit.record_failure()
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Request failed ({e}), retry in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    raise

            except Exception as e:
                self._circuit.record_failure()
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Request error ({e}), retry in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    raise HieraChainAPIError(str(e)) from e

        raise HieraChainAPIError(f"Request failed after {self.config.max_retries} retries")

    async def submit_event(self, event_data: dict[str, Any]) -> EventResult:
        """Submit an event to the blockchain."""
        response = await self._request("POST", "/api/v1/events", data=event_data)
        return EventResult(
            event_id=response.get("event_id", ""),
            status=response.get("status", "unknown"),
            message=response.get("message", ""),
        )

    async def get_block(self, block_id: str) -> dict[str, Any]:
        """Get a block by ID or index."""
        return await self._request("GET", f"/api/v1/blocks/{block_id}")

    async def get_chain_status(self) -> ChainStatus:
        """Get current blockchain status."""
        response = await self._request("GET", "/api/v1/status")
        return ChainStatus(
            node_id=response.get("node_id", "unknown"),
            is_healthy=response.get("is_healthy", False),
            block_height=response.get("block_height", 0),
            pending_events=response.get("pending_events", 0),
            is_lockdown=response.get("is_lockdown", False),
        )

    async def health_check(self) -> bool:
        """Check if the node is healthy."""
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "healthy"
        except Exception:
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
