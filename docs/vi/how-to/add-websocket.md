---
title: "Sử dụng WebSocket"
description: "Hướng dẫn kết nối thời gian thực với HieraChain qua giao thức WebSocket: đăng ký sự kiện, nhận thông báo block mới và các ví dụ mã nguồn client."
icon: material/connection
---

# Sử dụng WebSocket

## Mục đích

Kết nối WebSocket tới HieraChain để đăng ký subscription và nhận thông điệp từ các helper broadcast. Luồng commit/sự kiện của ledger không tự gọi các helper này; ứng dụng phải tích hợp chúng. Xem [Workflow WebSocket](../workflows/websocket-streaming.md).

## Kết nối WebSocket

### Endpoint

Kết nối tới `/ws`; có thể truyền `chain_name` qua query parameter để chọn chain khi kết nối:

```
ws://localhost:2661/ws?chain_name=supply_chain
```

Khi không có query parameter `chain_name`, kết nối dùng subscription `all`. Subscription này nhận các thông điệp được gửi tường minh bằng `broadcast_to_all()`; helper block và event theo chain yêu cầu subscription có tên chain cụ thể:

```
ws://localhost:2661/ws
```

Khi bật xác thực API key, gửi header API key đã cấu hình (mặc định `X-API-Key`) trong WebSocket handshake. Khóa cần cả quyền `chains` và `events` vì stream gửi cả block và sự kiện. Ví dụ trình duyệt dưới đây dùng cho dev/test đã tắt xác thực; `WebSocket` gốc của trình duyệt không hỗ trợ header handshake tùy chỉnh.

Endpoint HTTP `GET /ws/status` cần quyền `chains` khi bật xác thực vì thống kê chứa tên chain và số subscriber.

### Định dạng Tin nhắn

Tất cả các tin nhắn trao đổi đều ở định dạng JSON.

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

## Ví dụ: JavaScript Client

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

## Ví dụ: Python Client

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

## Ví dụ: Rust Client (tokio-tungstenite)

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

## Trạng thái Kết nối

Kiểm tra số lượng kết nối đang hoạt động:

```bash
curl http://localhost:2661/ws/status
```

Phản hồi mẫu:

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

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|------|-------------|------------|
| Kết nối bị từ chối | Server chưa chạy | Chạy `python -m hierachain` |
| Không nhận thông điệp ledger | Thiếu subscription hoặc tích hợp broadcast | Kiểm tra subscription và bảo đảm ứng dụng gọi các helper broadcast |
| Mất kết nối đột ngột | Server khởi động lại | Cho client tự kết nối lại |

## Liên quan

* API Module: [API](../modules/api.md)
* Tài liệu API Ledger: [API Ledger](../reference/api-ledger.md)
* Mã nguồn WebSocket: `hierachain/api/websocket/manager.py`, `hierachain/api/websocket/endpoints.py`
