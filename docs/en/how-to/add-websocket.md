---
title: "Using WebSocket"
description: "Guide to real-time connection with HieraChain via WebSocket: subscribe to events, receive new block notifications, and client examples."
icon: material/connection
---

# Using WebSocket

## Purpose

Guide to real-time connection with HieraChain via WebSocket protocol to receive event and block notifications as soon as they are recorded on the chain.

## WebSocket Connection

### Endpoint

```
ws://localhost:2661/ws
```

With authentication (if enabled):
```
ws://localhost:2661/ws?token=<your-api-key>
```

### Message Format

All messages are JSON.

**Client → Server:**

```json
// Subscribe to all events/blocks from a chain
{"action": "subscribe", "chain_name": "supply_chain"}

// Subscribe to specific event type
{"action": "subscribe", "chain_name": "supply_chain", "event_type": "production_complete"}

// Unsubscribe
{"action": "unsubscribe", "chain_name": "supply_chain"}

// Keep-alive ping
{"action": "ping"}
```

**Server → Client:**

```json
// New block created
{"type": "new_block", "chain_name": "supply_chain", "data": {"block_hash": "...", "height": 10}}

// New event added
{"type": "new_event", "chain_name": "supply_chain", "data": {"entity_id": "...", "event_type": "..."}}

// Pong response
{"type": "pong", "timestamp": 1234567890}

// Error
{"type": "error", "message": "Invalid subscription"}
```

## Example: JavaScript Client

```javascript
// Connect WebSocket
const ws = new WebSocket('ws://localhost:2661/ws');

// Handle connection
ws.onopen = () => {
  console.log('✅ Connected to HieraChain WebSocket');
  
  // Subscribe to 'supply_chain'
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain'
  }));
  
  // Or subscribe by event type
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain',
    event_type: 'production_complete'
  }));
};

// Receive messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'new_block':
      console.log('🆕 New block:', data.data.block_hash);
      break;
    case 'new_event':
      console.log('📝 New event:', data.data.event_type);
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
    ws.send(JSON.stringify({ action: 'ping' }));
  }
}, 30000);
```

## Example: Python Client

```python
import asyncio
import websockets
import json

async def listen():
    uri = "ws://localhost:2661/ws"
    
    async with websockets.connect(uri) as ws:
        # Subscribe to chain
        await ws.send(json.dumps({
            "action": "subscribe",
            "chain_name": "supply_chain"
        }))
        
        # Listen for messages
        async for message in ws:
            data = json.loads(message)
            
            if data["type"] == "new_block":
                print(f"🆕 New block: {data['data']['block_hash']}")
            elif data["type"] == "new_event":
                print(f"📝 New event: {data['data']['event_type']}")
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
    let url = "ws://localhost:2661/ws";
    let (ws_stream, _) = connect_async(url).await?;
    let (mut write, mut read) = ws_stream.split();

    // Subscribe to chain
    let msg = serde_json::json!({
        "action": "subscribe",
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

## Connection Health

Check connection count:

```bash
curl http://localhost:2661/ws/status
```

Response:

```json
{
  "total_connections": 5,
  "chains": {
    "supply_chain": 3,
    "orders": 2
  }
}
```

## Common Error Handling

| Error | Cause | Solution |
|------|-------------|------------|
| Connection refused | Server not running | Run `python -m hierachain.api.server` |
| 401 Unauthorized | Missing token | Add `?token=<api_key>` to URL |
| No messages received | Not subscribed | Send subscribe message first |
| Sudden disconnect | Server restart | Auto-reconnect in client |

## Related

* API Module: [API](../modules/api.md)
* API Ledger Reference: [API Ledger](../reference/api-ledger.md)
* WebSocket Source: `hierachain/api/websocket_manager.py`, `hierachain/api/websocket_endpoints.py`
