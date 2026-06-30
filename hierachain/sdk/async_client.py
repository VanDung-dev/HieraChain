"""
HieraChain SDK — Asynchronous HTTP client.

Provides a resilient async client with automatic retry, exponential
backoff, circuit breaker pattern, and aiohttp transport.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any
from http import HTTPStatus

import aiohttp

from hierachain.sdk.types import (
    HieraChainClientConfig,
    CircuitBreaker,
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

logger = logging.getLogger(__name__)


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
        self.config = config or HieraChainClientConfig()
        self._circuit = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
        )
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            headers = dict(self.config.headers)
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        assert self._session is not None
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

    async def _handle_response(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
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
        self._circuit.record_failure()
        if attempt >= self.config.max_retries:
            if isinstance(
                e, (ServiceUnavailableError, LockdownError, HieraChainAPIError)
            ):
                raise e
            raise HieraChainAPIError(str(e)) from e
        delay = self._calculate_delay(attempt)
        logger.warning(
            "Request failed (%s: %s), retry %d/%d in %.1fs",
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
        url = f"/api/ledger/chains/{chain_name}/events"
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
        params = {"resolve_cid": str(resolve_cid).lower()}
        url = f"/api/ledger/chains/{chain_name}/blocks/{index_or_hash}"
        return await self._request("GET", url, params=params)

    async def get_node_status(self) -> NodeStatus:
        response = await self._request("GET", "/api/admin/status")
        return NodeStatus(
            status=response.get("status", "unknown"),
            version=response.get("version", "unknown"),
            chains_active=response.get("chains_active", 0),
            license_active=response.get("license_active", False),
            uptime=response.get("uptime", "unknown"),
        )

    async def get_chain_stats(self, chain_name: str) -> ChainStats:
        response = await self._request("GET", f"/api/ledger/chains/{chain_name}/stats")
        return ChainStats(
            chain_name=response.get("chain_name", chain_name),
            total_blocks=response.get("total_blocks", 0),
            total_events=response.get("total_events", 0),
            unique_entities=response.get("unique_entities", 0),
            proof_count=response.get("proof_count"),
            registered_sub_chains=response.get("registered_sub_chains")
        )

    async def submit_proof(self, chain_name: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/ledger/chains/{chain_name}/submit-proof")

    async def trace_entity(
        self,
        entity_id: str,
        chain_name: str | None = None,
        resolve_cid: bool = False
    ) -> EntityTrace:
        params = {"resolve_cid": str(resolve_cid).lower()}
        if chain_name:
            params["chain_name"] = chain_name
        url = f"/api/ledger/entities/{entity_id}/trace"
        response = await self._request("GET", url, params=params)
        return EntityTrace(
            entity_id=response.get("entity_id", entity_id),
            chains=response.get("chains", []),
            events=response.get("events", [])
        )

    async def health_check(self) -> bool:
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "healthy"
        except (HieraChainAPIError, CircuitOpenError):
            return False

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "HieraChainAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
