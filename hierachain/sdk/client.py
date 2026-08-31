"""
HieraChain SDK — Synchronous HTTP client.

Provides a resilient sync client with automatic retry, exponential
backoff, and circuit breaker pattern.
"""

from __future__ import annotations

import time
import logging
from typing import Any
from http import HTTPStatus

import requests

from hierachain.sdk.types import (
    HieraChainClientConfig,
    CircuitBreaker,
    CircuitState,
    EventResult,
    NodeStatus,
    ChainStats,
    EntityTrace,
)
from hierachain.sdk.exceptions import (
    CircuitOpenError,
    HieraChainAPIError,
    ServiceUnavailableError,
    LockdownError,
)

# Backward-compat re-export — docs reference this symbol from client.py
from hierachain.sdk.async_client import HieraChainAsyncClient  # noqa: F401

logger = logging.getLogger(__name__)

__all__ = [
    "HieraChainClientConfig",
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "HieraChainAPIError",
    "ServiceUnavailableError",
    "LockdownError",
    "EventResult",
    "NodeStatus",
    "ChainStats",
    "EntityTrace",
    "HieraChainClient",
]


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
        self.config = config or HieraChainClientConfig()
        self._circuit = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
        )
        self._session: requests.Session | None = None

    def _get_session(self) -> requests.Session:
        if self._session is None:
            try:
                session = requests.Session()
                session.headers.update(self.config.headers)
                if self.config.api_key:
                    session.headers["X-API-Key"] = self.config.api_key
                self._session = session
            except ImportError:
                raise ImportError("requests library required: pip install requests")
        if self._session is None:
            raise RuntimeError("Failed to initialize requests Session")
        return self._session

    def _calculate_delay(self, attempt: int) -> float:
        delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        return min(delay, self.config.max_delay)

    def _check_circuit_breaker(self) -> None:
        if not self._circuit.allow_request():
            raise CircuitOpenError(
                f"Circuit breaker is open. Retry after "
                f"{self.config.circuit_recovery_timeout}s"
            )

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
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
        self._circuit.record_failure()
        if attempt >= self.config.max_retries:
            if isinstance(e, (ServiceUnavailableError, LockdownError)):
                raise e
            raise HieraChainAPIError(str(e)) from e
        delay = self._calculate_delay(attempt)
        logger.warning(
            "Request failed (%s: %s), retry %d/%d in %.1fs",
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
        url = f"/api/ledger/chains/{chain_name}/events"
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
        params = {"resolve_cid": str(resolve_cid).lower()}
        url = f"/api/ledger/chains/{chain_name}/blocks/{index_or_hash}"
        return self._request("GET", url, params=params)

    def get_node_status(self) -> NodeStatus:
        response = self._request("GET", "/api/admin/status")
        return NodeStatus(
            status=response.get("status", "unknown"),
            version=response.get("version", "unknown"),
            chains_active=response.get("chains_active", 0),
            license_active=response.get("license_active", False),
            uptime=response.get("uptime", "unknown"),
        )

    def get_chain_stats(self, chain_name: str) -> ChainStats:
        response = self._request("GET", f"/api/ledger/chains/{chain_name}/stats")
        return ChainStats(
            chain_name=response.get("chain_name", chain_name),
            total_blocks=response.get("total_blocks", 0),
            total_events=response.get("total_events", 0),
            unique_entities=response.get("unique_entities", 0),
            proof_count=response.get("proof_count"),
            registered_sub_chains=response.get("registered_sub_chains")
        )

    def submit_proof(self, chain_name: str) -> dict[str, Any]:
        return self._request("POST", f"/api/ledger/chains/{chain_name}/submit-proof")

    def trace_entity(
        self,
        entity_id: str,
        chain_name: str | None = None,
        resolve_cid: bool = False
    ) -> EntityTrace:
        params = {"resolve_cid": str(resolve_cid).lower()}
        if chain_name:
            params["chain_name"] = chain_name
        url = f"/api/ledger/entities/{entity_id}/trace"
        response = self._request("GET", url, params=params)
        return EntityTrace(
            entity_id=response.get("entity_id", entity_id),
            chains=response.get("chains", []),
            events=response.get("events", [])
        )

    def health_check(self) -> bool:
        try:
            response = self._request("GET", "/health")
            return response.get("status") == "healthy"
        except (HieraChainAPIError, CircuitOpenError):
            return False

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> "HieraChainClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
