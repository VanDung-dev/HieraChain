---
title: "Luồng dữ liệu WebSocket"
description: "Giao thức đẩy thông tin và đăng ký thời gian thực khi có khối mới được cam kết hoặc sự kiện mới phát sinh trên sổ cái."
icon: material/connection
---

# Luồng dữ liệu WebSocket thời gian thực

## Tổng quan

HieraChain đẩy thông báo khối mới và sự kiện mới tới client đang kết nối qua WebSocket. Client có thể đăng ký theo chuỗi cụ thể hoặc theo loại sự kiện. Vòng lặp ping nền giám sát kết nối chết và tự giải phóng.

`WebSocketManager` là singleton (`ws_manager`) dùng chung cho mọi route API để quản lý đăng ký tập trung.

---

## Biểu đồ luồng: vòng đời kết nối và broadcast

```mermaid
sequenceDiagram
    autonumber
    participant Client as 🖥️ Trình duyệt / SDK Client
    participant WS as 🔌 WebSocket Endpoint
    participant WSM as 📡 WebSocketManager
    participant SC as 📦 SubChain

    Client->>WS: Nâng cấp WebSocket (GET /ws?chain_name={chain_name})
    WS->>WSM: connect(connection_id, websocket, chain_name)
    WSM->>WSM: Kiểm tra max_connections (mặc định 1000)
    WSM->>WSM: Registry.add(connection_id, conn)
    WSM->>WSM: SubscriptionManager.subscribe_to_chain(connection_id, chain_name)
    WS-->>Client: Kết nối thành công ✅

    opt Client lọc theo loại sự kiện cụ thể
        Client->>WS: { "type": "subscribe", "chain_name": "supply_chain", "event_types": ["quality_check", ...] }
        WS->>WSM: subscribe(connection_id, chain_name, event_types)
        WSM->>WSM: SubscriptionManager.subscribe_to_event_type(...)
    end

    Note over SC: Khối đã được hoàn tất (Gửi Sự kiện - bước 8)

    SC->>WSM: broadcast_new_block(chain_name, block_data)
    WSM->>WSM: get_chain_subscribers(chain_name)
    loop Với từng người đăng ký
        WSM->>Client: send_text(JSON { type: "block_added", chain_name: "supply_chain", data: block_data })
    end
```

---

## Biểu đồ luồng: vòng lặp ping và dọn dẹp

```mermaid
sequenceDiagram
    autonumber
    participant BG as 🔄 PingLoopRunner (chạy nền)
    participant WSM as 📡 WebSocketManager
    participant Client as 🖥️ Client

    Note over BG: Chạy định kỳ mỗi 30 giây

    loop Trên từng kết nối đang hoạt động
        BG->>Client: Gửi gói tin ping
        alt Nhận lại Pong trong vòng 10 giây
            Client-->>BG: pong ✅
        else Quá thời gian phản hồi (10 giây)
            BG->>WSM: disconnect(connection_id)
            WSM->>WSM: Registry.remove(connection_id)
            WSM->>WSM: SubscriptionManager.unsubscribe_all(connection_id)
        end
    end
```

---

## Định dạng thông điệp

```json
// Thông báo khi có khối mới
{
    "type": "block_added",
    "chain_name": "supply_chain",
    "data": {
        "index": 42,
        "hash": "a3f8b2c1...",
        "previous_hash": "9d1e4f...",
        "timestamp": 1714000000.0,
        "event_count": 5
    }
}

// Thông báo sự kiện (nếu đăng ký lọc theo event_types)
{
    "type": "event",
    "chain_name": "supply_chain",
    "data": {
        "entity_id": "product-SKU-001",
        "event": "quality_check",
        "details": { "result": "passed" }
    }
}
```

---

## Các bước chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Nâng cấp giao thức** | Kết nối `/ws` và truyền `chain_name` qua query string, ví dụ `/ws?chain_name=supply_chain`. |
| **2. Kiểm tra giới hạn** | Từ chối nếu `active_connections >= max_connections` (mặc định 1000). |
| **3. Đăng ký** | `ConnectionRegistry.add()` lưu kết nối theo `connection_id`. |
| **4. Đăng ký chuỗi** | `SubscriptionManager.subscribe_to_chain()` liên kết kết nối với chuỗi. |
| **5. Bộ lọc tùy chọn** | Client có thể gửi danh sách `event_types` để lọc. |
| **6. Broadcast** | Khi Gửi Sự kiện hoàn tất khối mới, `broadcast_new_block()` gửi tới mọi subscriber. |
| **7. Vòng lặp ping** | Luồng nền gửi ping mỗi 30 giây; ngắt client không phản hồi quá 10 giây. |

---

## Xử lý lỗi

| Tình huống | Hành vi |
|:-----------|:--------|
| Vượt giới hạn kết nối | Từ chối kèm mã `1008 Policy Violation` |
| Client ngắt đột ngột | `ConnectionRegistry.remove()` được gọi ở lần gửi lỗi tiếp theo |
| Gửi lỗi do kết nối hỏng | Bắt exception, gọi `disconnect()`, xóa khỏi Registry |
| Broadcast khi không có subscriber | Bỏ qua (No-op), không lỗi |

---

## Lớp và phương thức chính

| Bước | Lớp / Phương thức | Tệp |
|:-----|:--------------|:-----|
| Singleton | `ws_manager` | `api/websocket/manager.py` |
| Tạo kết nối | `WebSocketManager.connect()` | `api/websocket/manager.py` |
| Ngắt kết nối | `WebSocketManager.disconnect()` | `api/websocket/manager.py` |
| Đăng ký | `WebSocketManager.subscribe()` | `api/websocket/manager.py` |
| Phát khối mới | `WebSocketManager.broadcast_new_block()` | `api/websocket/manager.py` |
| Phát sự kiện mới | `WebSocketManager.broadcast_event()` | `api/websocket/manager.py` |
| Vòng lặp ping | `PingLoopRunner` | `api/websocket/handlers.py` |
| Xây dựng thông điệp | `build_block_added()` / `build_event_message()` | `api/websocket/builders.py` |
| Kho kết nối | `ConnectionRegistry` | `api/websocket/registry.py` |

---

## Liên quan

- [Gửi Sự kiện](./event-submission.md): kích hoạt `broadcast_new_block()` sau khi commit khối
- [Cảnh báo Rủi ro](./risk-alerts.md): cảnh báo cũng được đẩy qua kênh WebSocket này
