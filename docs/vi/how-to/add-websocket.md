---
title: "Sử dụng WebSocket"
description: "Hướng dẫn kết nối thời gian thực với HieraChain qua giao thức WebSocket: đăng ký sự kiện, nhận thông báo block mới và các ví dụ mã nguồn client."
icon: material/connection
---

# Sử dụng WebSocket

## Mục đích

Kết nối tới HieraChain qua WebSocket để nhận thông báo event và block mới.

## Kết nối WebSocket

### Địa chỉ Endpoint

```
ws://localhost:2661/ws?chain_name=supply_chain
```

Truyền `chain_name` qua query để chọn chuỗi khi kết nối; bỏ tham số này để kết nối tới tất cả chuỗi:

```
ws://localhost:2661/ws
```

### Định dạng Tin nhắn

Tất cả các tin nhắn trao đổi đều ở định dạng JSON.

**Client → Server:**

```json
// Đăng ký nhận tất cả sự kiện/block từ một chuỗi cụ thể
{"type": "subscribe", "chain_name": "supply_chain"}

// Đăng ký nhận một loại sự kiện cụ thể
{"type": "subscribe", "chain_name": "supply_chain", "event_types": ["production_complete"]}

// Hủy đăng ký nhận tin
{"type": "unsubscribe"}

// Gửi ping để duy trì kết nối (keep-alive)
{"type": "ping", "timestamp": 1234567890}
```

**Server → Client:**

```json
// Block đã được commit
{"type": "block_added", "chain_name": "supply_chain", "data": {"hash": "...", "index": 10}}

// Thông báo sự kiện
{"type": "event", "chain_name": "supply_chain", "data": {"entity_id": "...", "event": "production_complete"}}

// Phản hồi Pong từ server
{"type": "pong", "timestamp": 1234567890}

// Lỗi
{"type": "error", "message": "Invalid subscription"}
```

## Ví dụ: JavaScript Client

```javascript
// Khởi tạo kết nối WebSocket
const ws = new WebSocket('ws://localhost:2661/ws?chain_name=supply_chain');

// Xử lý khi kết nối thành công
ws.onopen = () => {
  console.log('✅ Đã kết nối với HieraChain WebSocket');
  
  // Đăng ký nhận tin từ 'supply_chain'
  ws.send(JSON.stringify({
    type: 'subscribe',
    chain_name: 'supply_chain'
  }));
  
  // Hoặc đăng ký theo loại sự kiện cụ thể
  ws.send(JSON.stringify({
    type: 'subscribe',
    chain_name: 'supply_chain',
    event_types: ['production_complete']
  }));
};

// Nhận tin nhắn từ server
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'block_added':
      console.log('🆕 Block mới:', data.data.hash);
      break;
    case 'event':
      console.log('📝 Sự kiện mới:', data.data.event);
      break;
    case 'pong':
      console.log('💚 Nhận được Pong');
      break;
    case 'error':
      console.error('❌ Lỗi:', data.message);
      break;
  }
};

// Xử lý lỗi
ws.onerror = (error) => {
  console.error('Lỗi WebSocket:', error);
};

// Xử lý khi đóng kết nối
ws.onclose = () => {
  console.log('🔌 Đã ngắt kết nối');
};

// Giữ kết nối: gửi ping định kỳ mỗi 30 giây
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
        # Đăng ký nhận tin từ chuỗi
        await ws.send(json.dumps({
            "type": "subscribe",
            "event_types": ["production_complete"],
            "chain_name": "supply_chain"
        }))
        
        # Lắng nghe các tin nhắn
        async for message in ws:
            data = json.loads(message)
            
            if data["type"] == "block_added":
                print(f"🆕 Block mới: {data['data']['hash']}")
            elif data["type"] == "event":
                print(f"📝 Sự kiện mới: {data['data']['event']}")
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

    // Đăng ký nhận tin từ chuỗi
    let msg = serde_json::json!({
        "type": "subscribe",
        "event_types": ["production_complete"],
        "chain_name": "supply_chain"
    });
    write.send(Message::Text(msg.to_string())).await?;

    // Lắng nghe tin nhắn
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
  "total_connections": 5,
  "max_connections": 1000,
  "chains": {
    "supply_chain": 3,
    "orders": 2
  },
  "event_types_count": 1
}
```

## Xử lý Lỗi Thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|------|-------------|------------|
| Connection refused | Server chưa chạy | Chạy lệnh `python -m hierachain.api.server` |
| Không nhận được dữ liệu của chuỗi mong muốn | Chưa chọn `chain_name` hoặc chưa đăng ký chuỗi | Gửi `type=subscribe` kèm `chain_name` và `event_types` khi cần lọc |
| Không nhận được tin nhắn | Chưa đăng ký chuỗi | Cần gửi tin nhắn subscribe trước tiên |
| Ngắt kết nối đột ngột | Server khởi động lại | Tự động kết nối lại ở phía client |

## Liên quan

* API Module: [API](../modules/api.md)
* Tài liệu API Ledger: [API Ledger](../reference/api-ledger.md)
* Mã nguồn WebSocket: `hierachain/api/websocket/manager.py`, `hierachain/api/websocket/endpoints.py`
