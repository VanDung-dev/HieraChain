---
title: Python SDK Reference
description: Reference and guide for developers integrating the HieraChain SDK library (Sync & Async).
icon: material/language-python
---

# Python SDK Reference

The HieraChain Python SDK library is designed as a powerful module to help Developers push transactions and read data quickly and efficiently in Python environments. Source code located at: `hierachain/sdk/client.py`.

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

*   **Example**: `client.submit_event("supply_chain", {"entity_id": "P001", "event": "check"})`

#### `get_block(chain_name: str, index_or_hash: str | int, resolve_cid: bool = False) -> dict`

Get detailed information about a block.

*   **resolve_cid**: If `True`, the SDK will automatically load data from IPFS for events that have `details_cid`.

#### `get_node_status() -> NodeStatus`

Get system status from API Admin. Returns an object containing `version`, `uptime`, `chains_active`, etc.

#### `trace_entity(entity_id: str, chain_name: str = None, resolve_cid: bool = False) -> EntityTrace`

Trace the history of an entity across chains.

---

### Example: Off-chain Storage (IPFS)

When submitting events with large or sensitive data, HieraChain recommends using IPFS. The SDK supports transparent querying:

```python
# 1. Submit event with CID from IPFS (uploaded beforehand)
client.submit_event("supply_chain", {
    "entity_id": "LARGE-DOC-001",
    "event": "document_notarization",
    "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
    "details_nonce": "12345"
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
    LockdownError,        # When system is in security lockdown mode
    ServiceUnavailableError # When connection error or server overload
)

try:
    client.submit_event(...)
except LockdownError:
    # Logic to handle when system is temporarily halted for maintenance/security
    pass
```

# Run as context manager
with HieraChainClient(config) as client:
    health = client.health_check()
    print("Healthy:", health)
```

**Using Async (Suitable for Web Server/FastAPI):**
```python
from hierachain.sdk.client import HieraChainAsyncClient

async with HieraChainAsyncClient(config) as async_client:
    status = await async_client.get_chain_status()
    print("Network:", status.block_height)
```

### 2. Core Network Resilience Features

The SDK is equipped with recovery and throughput assurance mechanisms to prevent spam / Node server overload:

#### a. Auto-retry (Exponential Backoff)
If a network drop occurs, the SDK automatically calculates a pause interval `initial_delay * (backoff_multiplier ^ attempt)`. Instead of crashing the whole system, queries are continuously retried (default `max_retries = 5`).

#### b. Circuit Breaker
Fail-fast operation (prioritizes early error reporting):
- **CLOSED**: Network state stable, all requests pass through to API.
- **OPEN**: If 5 consecutive transport failures are detected (`circuit_failure_threshold`), the relay trips, immediately raising `CircuitOpenError` until the 30s timeout (`circuit_recovery_timeout`) elapses.
- **HALF_OPEN**: After the cooldown period, it self-tests one packet. If it fails, it re-opens; if successful, it recovers to Closed.

#### c. Lockdown & 503 Handling
If the Node server returns a `X-Lockdown-Mode: true` header (System under DDoS attack / manual maintenance) or an HTTP `503 Service Unavailable`, the SDK will not spam retries (causing overload). Errors are exposed via dedicated Exception classes `LockdownError` and `ServiceUnavailableError`. 

### 3. Data Interaction

```python
# Submit Event for transaction
result = client.submit_event("main_chain", {
    "entity_id": "user_sysadmin",
    "event": "update_config"
})
print("Successfully pushed to block, Message ID:", result.event_id)

# Get Block by hash
block = client.get_block(block_id="8f2a9d...")
```
