---
title: "Using WebSocket"
description: "Guide to real-time connection with HieraChain via WebSocket: subscribe to events, receive new block notifications, and client examples."
icon: material/connection
---

# Using WebSocket

## Purpose

Connect to HieraChain over WebSocket to register subscriptions and receive messages sent through its broadcast helpers. The ledger commit/event paths do not invoke those helpers automatically; the application must supply that integration. See [WebSocket workflow](../workflows/websocket-streaming.md).

## WebSocket connection

### Endpoint

Connect to `/ws`; optionally pass `chain_name` as a query parameter to select a chain when connecting:

```
ws://localhost:2661/ws?chain_name=supply_chain
```

Without a `chain_name` query parameter, the connection uses the `all` subscription. It receives messages sent explicitly with `broadcast_to_all()`; per-chain block and event helpers require a named chain subscription:

```
ws://localhost:2661/ws
```

When API-key authentication is enabled, include the configured API-key header (default `X-API-Key`) in the WebSocket handshake. The key needs both `chains` and `events` permissions because the stream delivers both blocks and events. The browser example below applies to dev/test setups with authentication disabled; browser-native `WebSocket` does not support setting custom handshake headers.

The HTTP `GET /ws/status` endpoint requires `chains` permission when authenticated, because its statistics include chain names and subscriber counts.

### Message format

All messages are JSON.

Client → Server:

```json
// Subscribe to all events/blocks from a chain
{"type": "subscribe", "chain_name": "supply_chain"}

// Subscribe to specific event type
{"type": "subscribe", "chain_name": "supply_chain", "event_types": ["production_complete"]}

// Unsubscribe
{"type": "unsubscribe"}

// Keep-alive ping
{"type": "ping", "timestamp": 1234567890}
```

Server → Client:

```json
// Block added notification (example payload)
{"type": "block_added", "chain_name": "supply_chain", "data": {"hash": "...", "index": 10}, "optimized": true, "timestamp": "2026-10-09T12:00:00"}

// Event notification
{"type": "event", "chain_name": "supply_chain", "data": {"entity_id": "...", "event": "production_complete"}, "optimized": true, "timestamp": "2026-10-09T12:00:00"}

// Pong response
{"type": "pong", "timestamp": 1234567890}

// Error
{"type": "error", "message": "Invalid subscription"}
```

## Example: JavaScript Client

```javascript
// Connect WebSocket
const ws = new WebSocket('ws://localhost:2661/ws?chain_name=supply_chain');

// Handle connection
ws.onopen = () => {
  console.log('✅ Connected to HieraChain WebSocket');

  // Subscribe to 'supply_chain'
  ws.send(JSON.stringify({
    type: 'subscribe',
    chain_name: 'supply_chain'
  }));

  // Or subscribe by event type
  ws.send(JSON.stringify({
    type: 'subscribe',
    chain_name: 'supply_chain',
    event_types: ['production_complete']
  }));
};

// Receive messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'block_added':
      console.log('🆕 New block:', data.data.hash);
      break;
    case 'event':
      console.log('📝 New event:', data.data.event);
      break;
    case 'pong':
      console.log('💚 Pong received');
      break;
    case 'error':
      console.error('❌ Error:', data.message);
      break;
  }
};

// Handle errors
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Handle close
ws.onclose = () => {
  console.log('🔌 Disconnected');
};

// Keep-alive: send ping every 30 seconds
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
  }
}, 30000);
```

## Example: Python Client

```python
import asyncio
import websockets
import json

async def listen():
    uri = "ws://localhost:2661/ws?chain_name=supply_chain"

    async with websockets.connect(uri) as ws:
        # Subscribe to chain
        await ws.send(json.dumps({
            "type": "subscribe",
            "event_types": ["production_complete"],
            "chain_name": "supply_chain"
        }))

        # Listen for messages
        async for message in ws:
            data = json.loads(message)

            if data["type"] == "block_added":
                print(f"🆕 New block: {data['data']['hash']}")
            elif data["type"] == "event":
                print(f"📝 New event: {data['data']['event']}")
            elif data["type"] == "pong":
                print("💚 Pong")

asyncio.run(listen())
```

## Example: Rust Client (tokio-tungstenite)

```rust
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{StreamExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "ws://localhost:2661/ws?chain_name=supply_chain";
    let (ws_stream, _) = connect_async(url).await?;
    let (mut write, mut read) = ws_stream.split();

    // Subscribe to chain
    let msg = serde_json::json!({
        "type": "subscribe",
        "event_types": ["production_complete"],
        "chain_name": "supply_chain"
    });
    write.send(Message::Text(msg.to_string())).await?;

    // Listen
    while let Some(msg) = read.next().await {
        if let Message::Text(text) = msg? {
            let data: serde_json::Value = serde_json::from_str(&text)?;
            println!("Received: {:?}", data);
        }
    }

    Ok(())
}
```

## Connection health

Check connection count:

```bash
curl http://localhost:2661/ws/status
```

Response:

```json
{
  "status": "running",
  "stats": {
    "total_connections": 5,
    "max_connections": 1000,
    "chains": {
      "supply_chain": 3,
      "orders": 2
    },
    "event_types_count": 1
  }
}
```

## Common error handling

| Error | Cause | Solution |
|------|-------------|------------|
| Connection refused | Server not running | Run `python -m hierachain` |
| No ledger messages received | Missing subscription or broadcast integration | Confirm subscription and ensure the application calls the broadcast helpers |
| Sudden disconnect | Server restart | Auto-reconnect in client |

## Related

* API Module: [API](../modules/api.md)
* API Ledger Reference: [API Ledger](../reference/api-ledger.md)
* WebSocket Source: `hierachain/api/websocket/manager.py`, `hierachain/api/websocket/endpoints.py`
