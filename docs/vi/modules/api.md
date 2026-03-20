---
title: "API module"
description: "Module REST API v1/v2/v3: server, router, schemas và ví dụ curl — bám sát hierachain/api/*."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Mục đích

Cung cấp giao diện HTTP để tương tác với hệ thống HieraChain: quản lý chuỗi, ghi sự kiện, gửi proof, truy vết thực thể, lấy thống kê/khối.

## Kiến trúc & khái niệm

* Server: `hierachain/api/server.py` (khởi tạo FastAPI, wiring router, middleware).
* Router v1: `hierachain/api/v1/endpoints.py` + schemas Pydantic `api/v1/schemas.py`.
* Router v2 (nếu dùng): `hierachain/api/v2/*` (mở rộng nâng cao/ordering).
* Router v3: `hierachain/api/v3/*` (System & Admin: status, identity).
* Explorer: `hierachain/api/blockchain_explorer.py` (API khám phá chuỗi, nếu áp dụng).
* Dependency Injection: lazy singleton `HierarchyManager` / `EntityTracer` (xem `get_hierarchy_manager`, `get_entity_tracer`).
* Bảo vệ tài nguyên: có thể thêm `ResourceGuardMiddleware` từ `security/resource_guard.py` khi chạy server.

## API công khai (v1)

Định nghĩa trong `hierachain/api/v1/endpoints.py` (prefix `/api/v1`).

* GET `/health` → tình trạng service.
* GET `/chains` → danh sách chuỗi (main + sub), block_count, latest_block_hash.
* POST `/chains/{chain_name}/events` → thêm sự kiện vào sub-chain.
* POST `/chains/{chain_name}/submit-proof` → gửi proof từ sub-chain lên main chain.
* GET `/entities/{entity_id}/trace` → truy vết thực thể (toàn bộ hoặc trong một chain qua query `chain_name`).
* GET `/chains/{chain_name}/stats` → thống kê chuỗi.
* POST `/chains/{chain_name}/create` → tạo sub-chain mới.
* GET `/chains/{chain_name}/blocks` → lấy các block (có phân trang `limit`, `offset`).

Các schema phản hồi/yêu cầu chính nằm ở `hierachain/api/v1/schemas.py`:

* `EventRequest`, `EventResponse`
* `ChainInfoResponse`, `ProofSubmissionResponse`
* `EntityTraceResponse`, `ChainStatsResponse`
* `CreateChainRequest`, `CreateChainResponse`

## API công khai (v2) — Enterprise Features

Định nghĩa trong `hierachain/api/v2/endpoints.py` (prefix `/api/v2`), cung cấp các tính năng enterprise:

### Channels & Private Data

* `POST /channels` → tạo channel để giao tiếp an toàn giữa các tổ chức.
* `GET /channels/{channel_id}` → lấy thông tin channel.
* `POST /channels/{channel_id}/private-collections` → tạo private data collection.
* `POST /private-data` → thêm dữ liệu riêng tư vào collection.

### Domain Contracts

* `POST /contracts` → tạo domain contract mới với versioning.
* `POST /contracts/execute` → thực thi contract với event.

### Organization Management

* `POST /organizations` → đăng ký tổ chức với MSP.
* `GET /organizations/{org_id}` → lấy thông tin tổ chức.

Schemas chính (`api/v2/schemas.py`):

* `ChannelCreateRequest`, `PrivateCollectionCreateRequest`
* `ContractCreateRequest`, `ContractExecuteRequest`
* `OrganizationRequest`

## API công khai (v3)

Định nghĩa trong `hierachain/api/v3/endpoints.py` (prefix `/api/v3`), dành cho System Admin.

* POST `/verify-identity` → xác minh danh tính node (ký challenge).
* GET `/status` → báo cáo trạng thái node, uptime, số chain active.

Các schema chính nằm ở `hierachain/api/v3/schemas.py`:

* `VerifyIdentityRequest`, `VerifyIdentityResponse`
* `NodeStatusResponse`

## WebSocket API — Real-time Events

Định nghĩa trong `hierachain/api/websocket/`, cung cấp kết nối real-time qua WebSocket.

### Kết nối

* **Endpoint**: `ws://localhost:2661/ws`
* **Protocol**: JSON messages
* **Authentication**: Optional — thêm query param `?token=<api_key>` nếu bật AUTH

### Message Format

```json
// Client → Server (subscribe)
{"action": "subscribe", "chain_name": "supply_chain", "event_type": null}

// Client → Server (unsubscribe)
{"action": "unsubscribe", "chain_name": "supply_chain"}

// Client → Server (ping)
{"action": "ping"}

// Server → Client (block event)
{"type": "new_block", "chain_name": "supply_chain", "data": {...}}

// Server → Client (event)
{"type": "new_event", "chain_name": "supply_chain", "data": {...}}

// Server → Client (pong)
{"type": "pong", "timestamp": 1234567890}
```

### Subscriptions

* **Per-chain**: Nhận tất cả events/blocks từ một chain cụ thể
  ```json
  {"action": "subscribe", "chain_name": "supply_chain"}
  ```
* **Per-event-type**: Nhận events theo loại (ví dụ: `production_complete`)
  ```json
  {"action": "subscribe", "chain_name": "supply_chain", "event_type": "production_complete"}
  ```
* **Unsubscribe**: Huỷ subscription
  ```json
  {"action": "unsubscribe", "chain_name": "supply_chain"}
  ```

### Ví dụ JavaScript

```javascript
const ws = new WebSocket('ws://localhost:2661/ws');

ws.onopen = () => {
  console.log('Connected to HieraChain WebSocket');
  // Subscribe to chain events
  ws.send(JSON.stringify({
    action: 'subscribe',
    chain_name: 'supply_chain'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data.type, data);
};

// Keep alive with ping every 30 seconds
setInterval(() => {
  ws.send(JSON.stringify({ action: 'ping' }));
}, 30000);
```

### Kiến trúc

* `websocket_manager.py`: Quản lý connection lifecycle, subscriptions, broadcasting
  * `WebSocketManager`: Singleton quản lý tất cả connections
  * `connect()` / `disconnect()`: Thêm/xoá connection
  * `subscribe()` / `unsubscribe()`: Quản lý subscriptions
  * `broadcast_to_chain()`: Gửi message tới subscribers của một chain
* `websocket_endpoints.py`: FastAPI WebSocket endpoints
  * `/ws`: Main WebSocket endpoint
  * `/ws/status`: Connection stats

### Cấu hình

Các biến liên quan (xem `hierachain/config/settings.py`):

* Không có cấu hình riêng — WebSocket sử dụng cùng host/port với HTTP API

## GraphQL API — Query & Mutation

Định nghĩa trong `hierachain/api/graphql/schema.py`, cung cấp giao diện GraphQL để truy vấn và thao tác dữ liệu.

### Kết nối

* **Endpoint**: `http://localhost:2661/graphql` (nếu được bật trong server)
* **Library**: Sử dụng `graphene` (Python)

### GraphQL Types

* `EventType`: entity_id, event_type, details (JSON string), timestamp, signature
* `BlockType`: index, hash, previous_hash, timestamp, nonce, events, metadata
* `BlockMetadataType`: chain_name, events_count, validator_signatures
* `ChainStatusType`: chain_name, block_count, latest_block_index, latest_block_hash, status

### GraphQL Queries

```graphql
# Lấy một block cụ thể
query {
  block(chainName: "supply_chain", blockIndex: 0) {
    index
    hash
    timestamp
    events {
      entityId
      eventType
      timestamp
    }
  }
}

# Lấy nhiều blocks với phân trang
query {
  blocks(chainName: "supply_chain", fromIndex: 0, toIndex: 10, limit: 5) {
    index
    hash
    timestamp
  }
}

# Lấy events với bộ lọc
query {
  events(chainName: "supply_chain", entityId: "PROD-001", eventType: "created", fromTimestamp: 1700000000, toTimestamp: 1800000000, limit: 10) {
    entityId
    eventType
    details
    timestamp
  }
}

# Lấy trạng thái chain
query {
  chainStatus(chainName: "supply_chain") {
    chainName
    blockCount
    latestBlockIndex
    latestBlockHash
    status
  }
}

# Lấy tất cả chains
query {
  allChains {
    chainName
    blockCount
    status
  }
}
```

### GraphQL Mutations

```graphql
# Thêm event vào chain
mutation {
  addEvent(event: {
    chainName: "supply_chain"
    entityId: "PROD-001"
    eventType: "created"
    details: "{\"key\": \"value\"}"
  }) {
    success
    blockIndex
    error
  }
}
```

### Helper Functions

* `_filter_event()`: Hàm nội bộ lọc events theo các tiêu chí (entity_id, event_type, from_timestamp, to_timestamp). Sử dụng `all()` với generator expression để giảm cyclomatic complexity.
* `_to_event_type()`, `_to_block_type()`, `_to_chain_status()`: Chuyển đổi từ objects nội bộ sang GraphQL types.

### Kiến trúc

* `schema.py`: Định nghĩa types, queries, mutations và schema GraphQL
* Sử dụng `graphene` library cho Python
* Tích hợp với `HierarchyManager` qua `get_hierarchy_manager()`

## Ví dụ curl

```bash
# 1. Health
curl -s http://localhost:2661/api/v1/health

# 2. Tạo sub-chain (nếu chưa có)
curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/create

# 3. Ghi sự kiện
curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/events \
  -H 'Content-Type: application/json' \
  -d '{
        "entity_id": "PROD-001",
        "event_type": "production_complete",
        "details": {"quantity": 100}
      }'

# 4. Gửi proof
curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/submit-proof

# 5. Truy vết thực thể trên tất cả chuỗi
curl -s "http://localhost:2661/api/v1/entities/PROD-001/trace"

# 6. Lấy block của sub-chain (phân trang)
curl -s "http://localhost:2661/api/v1/chains/supply_chain/blocks?limit=5&offset=0"
```

Nếu bật xác thực API key (production), thêm header theo `settings.API_KEY_NAME` (mặc định `X-API-Key`):

```bash
  -H 'X-API-Key: <your-key>'
```

## Cấu hình

Các biến cấu hình liên quan (xem `hierachain/config/settings.py`):

* `API_HOST` (mặc định `localhost`), `API_PORT` (mặc định `2661`).
* `AUTH_ENABLED` (bật xác thực API key ở production).
* `API_KEY_LOCATION` (`header`|`query`), `API_KEY_NAME` (mặc định `X-API-Key`).
* CORS/HSTS/RateLimit: `HRC_CORS_*`, `HRC_HSTS_*`, `HRC_RATE_LIMIT*`.

## Tính năng & hạn chế

* Tính năng:

  * Các endpoint cốt lõi để thao tác chuỗi và quan sát dữ liệu.
  * Truy vết thực thể (`EntityTracer`) trên nhiều chain.
  * Fallback an toàn khi serialize events từ Arrow Table.

* Hạn chế:

  * Một số endpoint dùng mô phỏng (ví dụ submit proof ở chế độ không có ZK thực) — cần cấu hình/triển khai bổ sung nếu bật ZK.

## Bảo mật & quyền truy cập

* Xác thực API key (tuỳ môi trường): `security/verify/api_key_verifier.py`.
* Bảo vệ tài nguyên: `ResourceGuardMiddleware` có thể từ chối request khi CPU/RAM vượt ngưỡng.
* Chính sách/role: tích hợp qua `security/identity.py`, `policy_engine.py` (tài liệu ở trang Security).

## Xử lý lỗi & khắc phục

* Trả về HTTP status và thông điệp rõ ràng (400, 404, 500) qua `HTTPException`.
* Khuyến nghị bật rate limit và audit log ở production.

## Hiệu năng

* Đường đi ngắn nhất từ endpoint → HierarchyManager/Sub-Chain/Main-Chain.
* Sử dụng PyArrow trong core cho lưu trữ sự kiện; endpoint có fallback `to_pylist()` để tránh crash khi thiếu `to_event_list()`.

## FAQ

!!! question "Tại sao event body không có timestamp?"
    Server sinh timestamp (epoch) tại thời điểm ghi.

!!! question "Có cần tạo Main Chain trước?"
    `HierarchyManager` sẽ tự đảm bảo tạo/khởi tạo khi cần.

## Liên quan

* Reference API v1: [API v1](../reference/api-v1.md)
* Reference API v3: [API v3](../reference/api-v3.md)
* Config: [Config](../reference/config.md)
* Hierarchical module: [Hierarchical](hierarchical.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các endpoint và schema nằm tại `hierachain/api/v1/{endpoints.py, schemas.py}`.
    * Endpoint chính: `/health`, `/chains`, `/chains/{name}/events`, `/chains/{name}/submit-proof`, `/entities/{id}/trace`, `/chains/{name}/stats`, `/chains/{name}/create`, `/chains/{name}/blocks`.

    **DECISION**

    * Sử dụng DI kiểu lazy singleton cho `HierarchyManager`/`EntityTracer` để tránh chi phí khởi tạo lặp.
    * Tài liệu minh hoạ bằng curl tối thiểu, không phụ thuộc công cụ ngoài.

    **ASSUMPTION**

    * Cổng mặc định 2661; người dùng chưa bật AUTH ở môi trường phát triển.
    * Nếu bật AUTH, client sẽ đính kèm API key đúng header/tên.

    **INVARIANT**

    * Yêu cầu thay đổi trạng thái phải trải qua xác thực (khi `AUTH_ENABLED=true`).
    * Dữ liệu trả về từ endpoint phải serialize an toàn, không crash nếu không có `to_event_list()`.

    **EDGE CASES**

    * Tên chain chứa ký tự không hợp lệ → endpoint trả 400 (regex kiểm tra tên).
    * Sub-chain chưa tồn tại → 404.
    * Quá tải tài nguyên (CPU/RAM) → 503 khi dùng `ResourceGuardMiddleware`.
