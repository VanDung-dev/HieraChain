---
title: API Ledger
description: "Tài liệu REST API Ledger của HieraChain: endpoint, schema, ví dụ request/response, và các trường hợp lỗi."
icon: material/numeric-1-circle
---

# API Ledger

## Mục đích

Mô tả các endpoint REST trong phiên bản API Ledger dùng để tương tác với HieraChain: quản lý chuỗi, ghi sự kiện, gửi bằng chứng (proof), truy vết thực thể, thống kê và truy xuất block.

#### Phụ lục: Ví dụ Gửi Sự kiện kèm IPFS

Khi doanh nghiệp cần lưu trữ các tệp tin lớn (hợp đồng PDF, ảnh sản phẩm) mà không muốn làm phình to blockchain:

1. **Bước 1**: Upload tệp lên IPFS và nhận `CID`.
2. **Bước 2**: Gửi sự kiện vào HieraChain với `details_cid`.

```bash
curl -X POST "http://localhost:2661/api/ledger/chains/supply_chain/events" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{
       "entity_id": "CONTRACT-2024-001",
       "event_type": "contract_signed",
       "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
       "details_nonce": "a1b2c3d4e5f6789012345678"
     }'
```

Dữ liệu này sẽ được HieraChain bảo chứng tính toàn vẹn thông qua mã băm, trong khi nội dung thực tế được lưu trữ an toàn trên mạng lưới IPFS.

## Tổng quan endpoint

```mermaid
sequenceDiagram
    participant Client
    participant API as API Ledger
    participant Sub as Sub-Chain
    participant Main as Main Chain

    Client->>API: POST /api/ledger/chains/{chain_name}/create
    API->>Sub: Khởi tạo Sub-Chain
    API-->>Client: 201 Created

    Client->>API: POST /api/ledger/chains/{chain_name}/events
    API->>Sub: add_event(event)
    Sub->>Sub: OrderingService.receive_event()
    Sub->>Sub: Ghi Journal và đưa sự kiện vào hàng đợi
    API-->>Client: 200 OK (event_id; đã tiếp nhận, chưa phải block finality)

    Note over Sub: Xử lý nền sau phản hồi API
    Sub->>Sub: Gom batch và tạo block
    Sub->>Sub: Finalize bằng consensus PoA hoặc PoF đã cấu hình
    Sub->>Sub: Lưu block đã finalize

    Client->>API: POST /api/ledger/chains/{chain_name}/submit-proof
    API->>Sub: Lấy Proof
    Sub->>Main: Gửi Proof (Neo dữ liệu)
    Main-->>Sub: Xác nhận
    API-->>Client: 200 OK (Proof ID)
```

* GET `/api/ledger/health`: Kiểm tra tình trạng.
* GET `/api/ledger/chains`: Liệt kê Main Chain và tất cả Sub-Chain.
* POST `/api/ledger/chains/{chain_name}/create`: Tạo Sub-Chain mới (nếu chưa có Main Chain sẽ tự tạo).
* POST `/api/ledger/chains/{chain_name}/events`: Thêm sự kiện vào Sub-Chain.
* POST `/api/ledger/channels/{channel_id}/organizations/{org_id}/events`: Thêm sự kiện vào channel bằng user của API key đã xác thực và role ghi đã đăng ký trong organization.
* POST `/api/ledger/chains/{chain_name}/submit-proof`: Gửi proof từ Sub-Chain lên Main Chain.
* GET `/api/ledger/chains/{chain_name}/stats`: Lấy thống kê chuỗi.
* GET `/api/ledger/chains/{chain_name}/blocks?limit=10&offset=0&resolve_cid=false`: Lấy danh sách block (có phân trang). Nếu `resolve_cid=true`, tự động tải dữ liệu chi tiết từ IPFS.
* GET `/api/ledger/chains/{chain_name}/blocks/{index_or_hash}`: Lấy chi tiết một block cụ thể.
* GET `/api/ledger/entities/{entity_id}/trace[?chain_name=...&resolve_cid=false]`: Truy vết sự kiện. Nếu `resolve_cid=true`, giải mã chi tiết sự kiện từ IPFS.

## Gửi Sự kiện vào Channel

Gửi sự kiện vào channel và organization đã được provision trong `HierarchyManager` đang hoạt động. API key cần có quyền `events`. Server dùng `user_id` đã xác thực từ API key làm người gửi và kiểm tra role đã đăng ký của user trong organization theo write policy của channel; trường `sender` do caller gửi không quyết định membership hoặc role.

```bash
curl -X POST "http://localhost:2661/api/ledger/channels/supply_chain/organizations/acme/events" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{
       "entity_id": "PRODUCT-2024-001",
       "event_type": "production_start",
       "details": {"batch": "BATCH-001"}
     }'
```

Channel không tồn tại trả về `404`; thiếu user đã xác thực hoặc user không có write role phù hợp trong organization trả về `403`. Phải bật xác thực API key và key cần có quyền `events`. `HierarchyManager` đang hoạt động phải khôi phục channel cùng member registry từ storage bền vững đã cấu hình, hoặc các registry phải được provision trong bộ nhớ trước request. Ledger event của channel vẫn ở trong bộ nhớ khi manager restart.

## Schema chính (trích từ `hierachain/api/ledger/schemas.py`)

* `EventRequest`

    * `entity_id: str`
    * `event_type: str`
    * `details: dict[str, Any] | None` (On-chain data)
    * `details_cid: str | None` (Off-chain CID reference)
    * `details_nonce: str | None` (Encryption nonce)
    * `details_metadata: dict[str, Any] | None`

* `EventResponse`

    * `success: bool`
    * `message: str`
    * `event_id: str | None`

* `ChainInfoResponse`

    * `name: str`
    * `type: str` ("main" | "sub")
    * `block_count: int`
    * `latest_block_hash: str | None`

* `ProofSubmissionResponse`

    * `success: bool`
    * `message: str`
    * `proof_id: str | None`

* `EntityTraceResponse`

    * `entity_id: str`
    * `chains: list[str]`
    * `events: list[dict[str, Any]]`

* `ChainStatsResponse`

    * `chain_name: str`
    * `total_blocks: int`
    * `total_events: int`
    * `proof_count: int | None`
    * `registered_sub_chains: int | None`

## Ví dụ sử dụng

Giả định server đang chạy tại `http://localhost:2661`:

### 1. Health check

```bash
curl -s http://localhost:2661/api/ledger/health
```

### 2. Tạo Sub-Chain

```bash
curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
```

Phản hồi (201):

```json
{
  "success": true,
  "message": "Sub-chain 'supply_chain' created successfully",
  "chain_name": "supply_chain"
}
```

### 3. Thêm sự kiện vào Sub-Chain

```bash
curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/events \
  -H "Content-Type: application/json" \
  -d '{
        "entity_id": "PROD-001",
        "event_type": "production_complete",
        "details": {"quantity": 100}
      }'
```

Phản hồi:

```json
{
  "success": true,
  "message": "Event added to chain 'supply_chain'",
  "event_id": "supply_chain_1_1"
}
```

Phản hồi xác nhận sự kiện đã được ghi journal và đưa vào hàng đợi Ordering; tạo block và lưu block diễn ra bất đồng bộ sau đó.

### 4. Gửi proof lên Main Chain

```bash
curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
```

Phản hồi:

```json
{
  "success": true,
  "message": "Proof submitted from 'supply_chain' to main chain",
  "proof_id": "supply_chain_1"
}
```

### 5. Lấy thông tin khối (Chi tiết)

**Endpoint**: `GET /api/ledger/chains/{chain_name}/blocks/{index_or_hash}`

Lấy dữ liệu chi tiết của một khối cụ thể bằng Index (số) hoặc Hash (chuỗi).

**Tham số Query**:

* `resolve_cid` (boolean): Nếu `True`, server sẽ giải mã các `details_cid` từ IPFS và trả về dữ liệu gốc trong trường `details`.

**Ví dụ**:
```bash
curl -X GET "http://localhost:2661/api/ledger/chains/supply_chain/blocks/10?resolve_cid=true" \
     -H "X-API-Key: your_api_key"
```

### 6. Truy vết entity trên tất cả chuỗi

```bash
curl -s "http://localhost:2661/api/ledger/entities/PROD-001/trace"
```

Hoặc giới hạn trong một chuỗi:

```bash
curl -s "http://localhost:2661/api/ledger/entities/PROD-001/trace?chain_name=supply_chain"
```

### 6. Lấy thống kê chuỗi

```bash
curl -s http://localhost:2661/api/ledger/chains/supply_chain/stats
```

### 7. Lấy block theo trang

```bash
curl -s "http://localhost:2661/api/ledger/chains/supply_chain/blocks?limit=5&offset=0"
```

## Mã trạng thái & lỗi phổ biến

* 200 OK: Thành công cho GET/POST đa số trường hợp.
* 201 Created: Tạo Sub-Chain thành công.
* 400 Bad Request: `chain_name` không hợp lệ khi tạo (chỉ cho phép `[a-zA-Z0-9_\-]`).
* 404 Not Found: Không tìm thấy chuỗi hoặc sub-chain.
* 500 Internal Server Error: Lỗi xử lý nội bộ (ví dụ lỗi khi liệt kê chuỗi, khi thêm sự kiện, gửi proof, thống kê, truy xuất blocks).

## Ghi chú triển khai (rút gọn từ `endpoints.py`)

* DI lười (lazy DI): dùng các singleton nhẹ `get_hierarchy_manager()` và `get_entity_tracer()` cho request lifecycle.
* `POST /chains/{chain_name}/events`: server sẽ đặt `timestamp = time.time()`; `details` vắng mặt sẽ thành `{}`.
* `POST /api/ledger/chains/{chain_name}/submit-proof`: gọi `HierarchyManager.submit_proof_to_main_chain()`; thành công nghĩa là block proof MainChain đã ký được hoàn tất và kiểm tra lại sau khi đọc từ SQL bền vững. Thiếu storage hoặc backend chưa hỗ trợ sẽ trả lỗi.
* `GET /chains/{chain_name}/blocks`: khi `Block` không có `to_event_list`, có fallback chuyển đổi từ Arrow Table (`to_pylist`) để an toàn.

## Liên quan

* Kiến trúc tổng quan: [Tổng quan](../architecture/overview.md)
* Hierarchical module: [Hierarchical](../modules/hierarchical.md)
* Core module: [Core](../modules/core.md)

Danh sách block nhận `limit` từ 1 đến 100 (mặc định 10) và `offset >= 0`; giá trị không hợp lệ trả HTTP 422. Giới hạn này áp dụng cho số block, không phải tổng byte của các sự kiện. Xung đột đăng ký sub-chain đồng thời trả HTTP 409.
