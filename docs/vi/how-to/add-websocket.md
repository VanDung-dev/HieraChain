---
title: "Sử dụng WebSocket"
description: "Hướng dẫn kết nối thời gian thực với HieraChain qua giao thức WebSocket: đăng ký sự kiện, nhận thông báo block mới và các ví dụ mã nguồn client."
icon: material/connection
---

# Sử dụng WebSocket

## Mục đích

Hướng dẫn kết nối thời gian thực với HieraChain thông qua giao thức WebSocket để nhận các thông báo về sự kiện và block ngay khi chúng được ghi nhận trên chuỗi.

## Kết nối WebSocket

### Địa chỉ Endpoint

```
ws://localhost:2661/ws
```

Nếu có bật tính năng xác thực (authentication):
```
ws://localhost:2661/ws?token=<api-key-cua-ban>
```

### Định dạng Tin nhắn

Tất cả các tin nhắn trao đổi đều ở định dạng JSON.

**Client → Server:**

```json
// Đăng ký nhận tất cả sự kiện/block từ một chuỗi cụ thể
{"action": "subscribe", "chain_name": "supply_chain"}

// Đăng ký nhận một loại sự kiện cụ thể
{"action": "subscribe", "chain_name": "supply_chain", "event_type": "production_complete"}

// Hủy đăng ký nhận tin
{"action": "unsubscribe", "chain_name": "supply_chain"}

// Gửi ping để duy trì kết nối (keep-alive)
{"action": "ping"}
```

**Server → Client:**

```json
// Có block mới được tạo
{"type": "new_block", "chain_name": "supply_chain", "data": {"block_hash": "...", "height": 10}}

// Có sự kiện mới được thêm vào
{"type": "new_event", "chain_name": "supply_chain", "data": {"entity_id": "...", "event_type": "..."}}

// Phản hồi Pong từ server
{"type": "pong", "timestamp": 1234567890}

// Lỗi
{"type": "error", "message": "Invalid subscription"}
```

## Ví dụ: JavaScript Client

```javascript
// Khởi tạo kết nối WebSocket
const ws = new WebSocket('ws://localhost:2661/ws');

// Xử lý khi kết nối thành công
ws.onopen = () => {
  console.log('✅ Đã kết nối với HieraChain WebSocket');
  
  // Đăng ký nhận tin từ 'supply_chain'
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain'
  }));
  
  // Hoặc đăng ký theo loại sự kiện cụ thể
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain',
    event_type: 'production_complete'
  }));
};

// Nhận tin nhắn từ server
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'new_block':
      console.log('🆕 Block mới:', data.data.block_hash);
      break;
    case 'new_event':
      console.log('📝 Sự kiện mới:', data.data.event_type);
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
        # Đăng ký nhận tin từ chuỗi
        await ws.send(json.dumps({
            "action": "subscribe",
            "chain_name": "supply_chain"
        }))
        
        # Lắng nghe các tin nhắn
        async for message in ws:
            data = json.loads(message)
            
            if data["type"] == "new_block":
                print(f"🆕 Block mới: {data['data']['block_hash']}")
            elif data["type"] == "new_event":
                print(f"📝 Sự kiện mới: {data['data']['event_type']}")
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

    // Đăng ký nhận tin từ chuỗi
    let msg = serde_json::json!({
        "action": "subscribe",
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
  "chains": {
    "supply_chain": 3,
    "orders": 2
  }
}
```

## Xử lý Lỗi Thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|------|-------------|------------|
| Connection refused | Server chưa chạy | Chạy lệnh `python -m hierachain.api.server` |
| 401 Unauthorized | Thiếu token xác thực | Thêm tham số `?token=<api_key>` vào URL |
| Không nhận được tin nhắn | Chưa đăng ký chuỗi | Cần gửi tin nhắn subscribe trước tiên |
| Ngắt kết nối đột ngột | Server khởi động lại | Tự động kết nối lại ở phía client |

## Liên quan

* API Module: [API](../modules/api.md)
* Tài liệu API Ledger: [API Ledger](../reference/api-ledger.md)
* Mã nguồn WebSocket: `hierachain/api/websocket/manager.py`, `hierachain/api/websocket/endpoints.py`
```
