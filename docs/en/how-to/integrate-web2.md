---
title: "Web2 & Existing System Integration"
description: "Guide to integrating Web2 applications, Legacy systems, and ERP with HieraChain via REST API and SDK."
icon: material/web
---

# Web2 & Existing System Integration

## Purpose

Guide to patterns for connecting traditional Web2 applications (Node.js, Java, PHP, etc.) or legacy ERP systems with the HieraChain network.

## Integration Patterns

There are 3 main integration models:

1. **REST API (Loose Coupling)**: Most common, used for Web/Mobile Apps.
2. **Integration SDK (High Performance)**: Used for Python backend services needing high performance.
3. **ERP Adapter (Enterprise)**: Used for ERP systems (SAP, Oracle) requiring periodic data synchronization.

```mermaid
graph TD
    Web2[Web2 App / Frontend] -->|REST HTTP| API[HieraChain API]
    Legacy[Legacy System] -->|Adapter| SDK[Integration SDK]
    ERP[ERP System] -->|Pull/Push| Adapter

    API --> Core[HieraChain Core]
    SDK --> Core
```

## Method 1: Using REST API (Recommended)

This is the simplest method, using standard HTTP protocol.

### Scenario

You have an E-commerce Website (Node.js/React) and want to record product traceability on the Blockchain when an order is completed.

```mermaid
sequenceDiagram
    participant Web as Web2 App (Node/React)
    participant API as HieraChain API
    participant Sub as Sub-Chain (Orders)

    Web->>API: POST /chains/orders/events
    Note right of Web: Payload: {order_id, items...}
    API->>API: Validate API Key
    API->>Sub: Record Event (Add Event)
    Sub-->>API: Return Event ID
    API-->>Web: 200 OK (Event ID)
```

### Implementation Example (Python/Requests)

```python
import requests
import json

API_URL = "http://localhost:2661/api/ledger"
API_KEY = "your-api-key-here"  # If AUTH is enabled

def log_order_to_chain(order_id, items):
    # 1. Create Sub-Chain for orders (or use shared 'orders' chain)
    # Assuming using shared 'orders' chain

    # 2. Submit event
    payload = {
        "entity_id": order_id,
        "event_type": "order_completed",
        "details": {
            "items_count": len(items),
            "total_value": sum(i['price'] for i in items)
        }
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    try:
        response = requests.post(
            f"{API_URL}/chains/orders/events",
            json=payload,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        print(f"Success: {response.json()}")
        return response.json().get("event_id")
    except requests.exceptions.RequestException as e:
        print(f"Error logging to blockchain: {e}")
        return None
```

### Implementation Example (JavaScript/Fetch)

```javascript
const API_URL = "http://localhost:2661/api/ledger";

async function logOrder(orderId, items) {
  try {
    const response = await fetch(`${API_URL}/chains/orders/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // "X-API-Key": "your-key"
      },
      body: JSON.stringify({
        entity_id: orderId,
        event_type: "order_completed",
        details: { count: items.length }
      })
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const result = await response.json();
    console.log("Logged event:", result.event_id);
    return result.event_id;

  } catch (error) {
    console.error("Blockchain integration error:", error);
  }
}
```

Configure a signing identity and SQL storage using [Quickstart](../getting-started/quickstart.md) before using `HierarchyManager`. The HTTP SDK in `hierachain/sdk/` is distinct from the direct library call below.

## Method 2: Direct in-process library integration (Python Backend)

This example imports and calls `HierarchyManager` directly in the service process. Use `HieraChainClient` when your service should call the API through the HTTP SDK.

```mermaid
sequenceDiagram
    participant Service as Python Service
    participant Manager as HierarchyManager
    participant Sub as Sub-Chain
    participant Main as Main Chain

    Service->>Manager: start_operation(sub_chain, data)
    Manager->>Sub: Journal and queue event
    Service->>Manager: submit_proof_to_main_chain()
    Manager->>Sub: Get Proof
    Manager->>Main: Submit Proof (Anchor Data)
    Main-->>Manager: Acknowledge (Ack)
```

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
try:
    assert manager.create_sub_chain("supply_chain", "supply_chain")
    chain = manager.get_sub_chain("supply_chain")
    assert chain.register_entity("PROD-001", {"product": "sample"})
    assert manager.start_operation(
        "supply_chain", "PROD-001", "production_start", {"quantity": 100}
    )
    chain.flush_pending_and_finalize(timeout=10.0)
    assert any(
        event["event"] == "operation_start"
        for event in chain.get_events_by_entity("PROD-001")
    )
    assert manager.submit_proof_to_main_chain("supply_chain")
finally:
    manager.close()
```

## Method 3: ERP Adapter

Use the mapping/scheduler library with an application-provided ERP adapter. Built-in vendor connectors are simulation-only.

See details at: [Integration Module](../modules/integration.md).

## Important Notes

1. **Security**: Always use HTTPS and API Key (or OAuth if custom deployment) when connecting over public networks.
2. **Asynchronous**: Blockchain writes can be slower than regular DB writes. Use a queue (e.g., RabbitMQ, Kafka) on the Web2 app side to send requests to HieraChain workers, avoiding blocking the user UI.
3. **Error Handling**: Design Retry mechanisms if HieraChain API temporarily becomes unresponsive (503, timeout).

## Related

* API Ledger Reference: [API Ledger](../reference/api-ledger.md)
* Integration Module: [Integration](../modules/integration.md)
