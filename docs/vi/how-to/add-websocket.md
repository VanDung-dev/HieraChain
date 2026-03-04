---
title: "Sử dụng WebSocket"
description: "Hướng dẫn kết nối real-time với HieraChain qua WebSocket: subscribe events, nhận thông báo block mới, và ví dụ client."
---

# How-to: Sử dụng WebSocket

## Mục đích

Hướng dẫn kết nối real-time với HieraChain qua WebSocket protocol để nhận thông báo sự kiện (events) và khối (blocks) mới ngay khi chúng được ghi vào chuỗi.

## Kết nối WebSocket

### Endpoint

```
ws://localhost:2661/ws
```

Với authentication (nếu bật):
```
ws://localhost:2661/ws?token=<your-api-key>
```

### Message Format

Tất cả messages là JSON.

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

## Ví dụ: JavaScript Client

```javascript
// Kết nối WebSocket
const ws = new WebSocket('ws://localhost:2661/ws');

// Xử lý khi kết nối
ws.onopen = () => {
  console.log('✅ Connected to HieraChain WebSocket');
  
  // Subscribe vào chain 'supply_chain'
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain'
  }));
  
  // Hoặc subscribe theo event type
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain',
    event_type: 'production_complete'
  }));
};

// Nhận message
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

// Xử lý lỗi
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Xử lý đóng kết nối
ws.onclose = () => {
  console.log('🔌 Disconnected');
};

// Keep-alive: gửi ping mỗi 30 giây
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'ping' }));
  }
}, 30000);
```

## Ví dụ: Python Client

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

## Ví dụ: Rust Client (tokio-tungstenite)

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

## Playground

HieraChain cung cấp giao diện test WebSocket tại:

```
http://localhost:2661/ws/playground
```

Sử dụng playground để:

* Gửi subscribe/unsubscribe messages
* Xem real-time events
* Test connection health

## Connection Health

Kiểm tra số lượng kết nối:

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

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|------|-------------|------------|
| Connection refused | Server không chạy | Chạy `python -m hierachain.api.server` |
| 401 Unauthorized | Thiếu token | Thêm `?token=<api_key>` vào URL |
| No messages received | Chưa subscribe | Gửi message subscribe trước |
| Sudden disconnect | Server restart | Reconnect tự động trong client |

## Liên quan

* API Module: [API](../modules/api.md)
* Reference API v1: [API v1](../reference/api-v1.md)
* WebSocket Source: `hierachain/api/websocket_manager.py`, `hierachain/api/websocket_endpoints.py`

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * WebSocket endpoint tại `hierachain/api/websocket_endpoints.py`.
    * WebSocketManager tại `hierachain/api/websocket_manager.py`.
    * Server chạy cùng port 2661 với HTTP API.

    **DECISION**

    * Sử dụng JSON cho messages để dễ tích hợp đa ngôn ngữ.
    * Hỗ trợ per-chain và per-event-type subscriptions.
    * Ping/pong cho connection health.

    **ASSUMPTION**

    * Client tự xử lý reconnection khi mất kết nối.
    * Server WebSocket dùng same authentication với REST API.

    **INVARIANT**

    * Messages luôn là JSON hợp lệ.
    * Subscriptions được quản lý per-connection.

    **EDGE CASES**

    * Large number of connections → kiểm tra `ws_manager._connections` memory usage.
    * Slow clients → server có thể drop connection nếu buffer full.
