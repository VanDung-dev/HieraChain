---
title: Python SDK Reference
description: Reference and guide for developers integrating the HieraChain SDK library (Sync & Async).
icon: material/language-python
---

# Python SDK Reference

The HieraChain Python SDK provides synchronous and asynchronous clients for submitting events and reading data. Source: `hierachain/sdk/client.py`.

### 1. Client Initialization

The SDK provides 2 methods depending on needs: **Sync** and **Async**.
Both accept the `HieraChainClientConfig` object as a profile.

```python
from hierachain.sdk.client import HieraChainClientConfig, HieraChainClient

# Client Configuration
config = HieraChainClientConfig(
    base_url="http://localhost:2661",
    timeout=10.0,
    api_key="your-api-key-here"
)
```

### Main Methods

#### `submit_event(chain_name: str, event_data: dict[str, Any]) -> EventResult`

Submit a new event to a specific sub-chain.

*   **Example**: `client.submit_event("supply_chain", {"entity_id": "P001", "event_type": "check"})`

#### `get_block(chain_name: str, index_or_hash: str | int, resolve_cid: bool = False) -> dict`

Get detailed information about a block.

*   **resolve_cid**: If `True`, the SDK asks the API to resolve `details_cid`. The API must have IPFS enabled; otherwise the CID remains unresolved.

#### `get_node_status() -> NodeStatus`

Get system status from API Admin. Returns an object containing `version`, `uptime`, `chains_active`, etc.

#### `trace_entity(entity_id: str, chain_name: str | None = None, resolve_cid: bool = False) -> EntityTrace`

Trace the history of an entity across chains.

Entity IDs are percent-encoded as one URL path segment. `health_check()` uses the API route `/api/ledger/health`. If `api_key` is configured, the sync and async clients do not follow redirects for read requests; a 3xx response raises `HieraChainAPIError` and the `X-API-Key` is not sent to another origin.

---

### Example: Off-chain Storage (IPFS)

When submitting events with large or sensitive data, HieraChain recommends using IPFS. The SDK supports transparent querying:

```python
# 1. Submit event with CID from IPFS (uploaded beforehand)
client.submit_event("supply_chain", {
    "entity_id": "LARGE-DOC-001",
    "event_type": "document_notarization",
    "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
    "details_nonce": "00112233445566778899aabb"
})

# 2. Query and auto-decrypt data
block = client.get_block("supply_chain", 100, resolve_cid=True)
# The 'details' field in the event will contain data loaded from IPFS
```

### Error Handling

The SDK defines specialized exceptions so applications can handle business logic:

```python
from hierachain.sdk.exceptions import (
    CircuitOpenError,     # When Circuit Breaker is activated
    HieraChainAPIError,   # HTTP errors, with status_code
    LockdownError,        # When system is in security lockdown mode
    ServiceUnavailableError # When the server returns HTTP 503
)

try:
    client.submit_event(...)
except LockdownError:
    # Logic to handle when system is temporarily halted for maintenance/security
    pass
```

For synchronous code, open the client with a context manager:

```python
with HieraChainClient(config) as client:
    health = client.health_check()
    print("Healthy:", health)
```

For a web server or FastAPI application, use the async client:
```python
from hierachain.sdk.client import HieraChainAsyncClient

async def read_node_status(config: HieraChainClientConfig) -> None:
    async with HieraChainAsyncClient(config) as async_client:
        status = await async_client.get_node_status()
        print("Network:", status.chains_active)
```

### 2. Core Network Resilience Features

The SDK retries network failures and uses a circuit breaker to limit requests when the API is unavailable:

#### a. Auto-retry (Exponential Backoff)
Read requests (`GET`) retry transport failures and HTTP 5xx with `initial_delay * (backoff_multiplier ^ attempt)`, up to `max_retries = 5` times by default. A non-2xx response returned to the client raises `HieraChainAPIError` with its `status_code`; returned 3xx and 4xx responses are not retried. Sync and async clients follow redirects for unauthenticated `GET`, `HEAD`, and `OPTIONS` requests. They disable redirects for those methods when `X-API-Key` is configured, and for `POST` requests. Submission requests are sent once, including after a timeout or 503, because the server has no idempotency contract.

#### b. Circuit Breaker
Fail-fast operation (prioritizes early error reporting):
- **CLOSED**: Network state stable, all requests pass through to API.
- **OPEN**: If 5 consecutive transport or HTTP 5xx failures are detected (`circuit_failure_threshold`), the relay trips, immediately raising `CircuitOpenError` until the 30s timeout (`circuit_recovery_timeout`) elapses.
- **HALF_OPEN**: After the cooldown period, only one request is admitted as a probe. It is not retried; failure re-opens the circuit, and success closes it.

#### c. Lockdown & 503 Handling
If the Node server returns the `X-Lockdown-Mode: true` header or HTTP `503 Service Unavailable`, the SDK raises `LockdownError` or `ServiceUnavailableError`. Read requests may retry first; POST requests do not.

### 3. Data Interaction

```python
# Submit Event for transaction
result = client.submit_event("supply_chain", {
    "entity_id": "user_sysadmin",
    "event_type": "update_config"
})
print("Event accepted, event_id:", result.event_id)

# Get Block by hash
block = client.get_block("supply_chain", "8f2a9d...")
```

### JSON transport

Both SDK clients encode request bodies and decode response JSON through standard-library `json` helpers, using UTF-8 and a default `Content-Type: application/json` while honoring configured headers. Non-finite numbers are rejected before sending; responses containing `NaN`, `Infinity` or overflowing float values are rejected. Python integers larger than 64 bits are preserved without conversion to floats, within Python's integer conversion limit. Invalid response JSON follows the existing failure and retry handling. Mutating requests are still not retried automatically.
