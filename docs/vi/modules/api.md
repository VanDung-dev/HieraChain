---
title: "Module API"
description: "Hệ thống API đa giao thức: REST ledger/business/admin, GraphQL và WebSocket. Tích hợp bảo mật đa lớp và quản lý dữ liệu IPFS."
icon: material/api
---

# Module API (`hierachain/api/*`)

## Tổng quan

Module API xử lý giao tiếp giữa client bên ngoài và lõi HieraChain. Nó chạy trên FastAPI và hỗ trợ REST, GraphQL và WebSocket. Mục tiêu chính là hiệu năng, nên cùng một service có thể phục vụ cả ba giao thức mà không cần triển khai riêng.

### Thành phần cốt lõi

Import helper của API client, như `hierachain.api.storage.ipfs_client`, không tạo ứng dụng server. Các export `app` và `create_app` nạp server khi được yêu cầu; yêu cầu xác thực production vẫn được kiểm tra. Khi lifespan API kết thúc, hierarchy manager được đóng và provider manager/tracer được reset, kể cả khi startup P2P thất bại.

* FastAPI server (`server.py`) là điểm khởi chạy. Nó thiết lập middleware, xác thực và router.
* REST API có ba nhóm (ledger, business, admin) cho thao tác lõi, tính năng nghiệp vụ và quản trị hệ thống.
* GraphQL endpoint cho phép chọn field linh hoạt với giới hạn depth và complexity.
* Gateway WebSocket quản lý subscription và helper broadcast; ứng dụng phải nối sự kiện ledger vào các helper này.
* Tích hợp IPFS xử lý dữ liệu off-chain với mã hóa AES-256-GCM. Payload lớn nằm ngoài chain, chỉ CID được lưu trên chain.

## Kiến trúc và bảo mật

API dùng middleware theo lớp. Mỗi request đi qua cùng một chuỗi kiểm tra trước khi tới handler.

### Bảo mật HTTP

* HTTP middleware thêm CSP, X-Frame-Options có giá trị DENY và X-Content-Type-Options có giá trị nosniff. Nó không thêm HSTS; hãy cấu hình header này tại reverse proxy HTTPS.
* Middleware payload giới hạn body POST/PUT/PATCH ở 1 MiB. Nó kiểm tra Content-Length nếu được gửi và đọc stream khi thiếu header này.
* CORS kiểm soát origin nào được gọi API. Môi trường production yêu cầu danh sách cho phép cụ thể.

### Rate limiting

Rate limiting đếm request theo key và hỗ trợ hai backend:

* In-memory cho triển khai đơn node.
* Redis cho cụm cần đồng bộ bộ đếm.

Mặc định là 100 request mỗi phút, được cấu hình qua `HRC_RATE_LIMIT_RPM`.

### Xác thực

`APIKeyVerifier` kiểm tra header `X-API-Key` cho HTTP và WebSocket. Production bắt buộc `HRC_AUTH_ENABLED=true` và file key `HRC_API_KEYS_FILE` đã được cấp; dev/test có thể tắt xác thực. Khi bật xác thực, GraphQL kiểm tra scope cho từng operation: query chain và block cần `chains`, query event và `addEvent` cần `events`, còn query block chọn event lồng bên trong cần cả hai scope. WebSocket truyền cả message block và event, nên kết nối và đăng ký cần `chains` và `events` (hoặc `all`). Trong production, GraphQL và WebSocket từ chối yêu cầu nếu app không có verifier đang bật hoặc verifier không trả auth context.

## Tham chiếu REST API

### ledger: sổ cái cốt lõi

Các endpoint này tương tác trực tiếp với trạng thái sổ cái:

* `GET /api/ledger/health` kiểm tra sức khỏe node.
* `GET /api/ledger/network/ping/{target_id}` gửi ping trực tiếp đến nút mạng mục tiêu.
* `GET /api/ledger/chains` liệt kê Main Chain và Sub-Chain.
* `POST /api/ledger/chains/{chain_name}/create` khởi tạo một sub-chain mới.
* `GET /api/ledger/chains/{chain_name}/stats` lấy số lượng block, event và proof.
* `POST /api/ledger/chains/{chain_name}/events` gửi event, chuyển tải dữ liệu quá cỡ sang IPFS.
* `POST /api/ledger/chains/{chain_name}/submit-proof` gửi bằng chứng mật mã từ sub-chain lên main chain.
* `GET /api/ledger/chains/{chain_name}/blocks` liệt kê block có phân trang và tùy chọn giải mã CID.
* `GET /api/ledger/chains/{chain_name}/blocks/{index_or_hash}` lấy thông tin chi tiết một block theo chỉ số hoặc mã băm.
* `GET /api/ledger/entities/{id}/trace` truy vết entity xuyên suốt hệ thống phân cấp chuỗi.

### business: tính năng doanh nghiệp

Các endpoint này hỗ trợ quy trình nghiệp vụ:

* Channel tạo kênh giao tiếp riêng giữa các tổ chức (`POST /api/business/channels`).
* Có thể quản lý metadata của private collection, nhưng `POST /api/business/private-data` hiện trả HTTP 501 vì API chưa có kho lưu private data. Endpoint này không nhận giá trị inline hoặc tham chiếu IPFS như dữ liệu đã lưu.
* Domain contract đăng ký metadata; `POST /api/business/contracts/execute` trả HTTP 501 vì engine thực thi chưa được triển khai.
* Organization đăng ký và quản lý danh tính qua MSP.

### admin: hệ thống và quản trị

Các endpoint này dành cho vận hành node và hệ thống:

* `POST /api/admin/verify-identity` cho phép node ký challenge để chứng minh danh tính.
* `GET /api/admin/status` được miễn xác thực API key và trả uptime, số chain, version cùng cờ license được gán cố định.
* `POST /api/admin/chains/{chain_name}/secure-events` kiểm tra chữ ký đồng bộ rồi gửi qua ordering bất đồng bộ; response không xác nhận block đã commit.

## GraphQL API

Endpoint: `/graphql`

Dùng GraphQL khi client cần chọn field cụ thể hoặc giảm kích thước payload.

### Giới hạn bảo mật

* Depth của query giới hạn ở 10 cấp.
* Complexity giới hạn ở 1000 điểm mỗi query, tính theo số field và phép toán.
* Introspection (`__schema`) bị tắt ở production.

### Ví dụ query

Query event cần quyền `events`. Query block và chain cần `chains`; chọn event lồng trong block cần cả hai quyền.

```graphql
query {
  events(chainName: "supply_chain", entityId: "PROD-001", limit: 20) {
    eventType
    details
    timestamp
  }
}
```

## WebSocket (truyền dữ liệu thời gian thực)

Kết nối tới `/ws`. Để chọn chuỗi ngay khi kết nối, truyền `chain_name`, ví dụ `/ws?chain_name=supply_chain`.

Khi bật xác thực, gửi header `X-API-Key` trong WebSocket handshake. Kết nối và từng subscription cần cả quyền `chains` lẫn `events` vì stream hiện gửi cả hai loại thông điệp cho subscriber của chain. Luồng ledger không tự gọi helper broadcast. Subscription chỉ nhận thông điệp ledger khi ứng dụng đã tích hợp việc phát thông điệp.

### Các loại message chính

* Client tới server
    * `subscribe` đăng ký nhận tin từ một chain cụ thể hoặc theo loại event.
    * `ping` giữ kết nối.
* Server tới client
    * `block_added` báo có block mới kèm dữ liệu rút gọn.
    * `event` đẩy chi tiết event tới subscriber.
    * `subscribed` xác nhận đăng ký thành công.

## Blockchain explorer

Tích hợp sẵn tại `blockchain_explorer.py`, explorer cung cấp dashboard cho người vận hành:

* Monitor hiển thị tốc độ tạo block và luồng event theo thời gian thực.
* Visualizer vẽ cây quan hệ giữa Main Chain và Sub-Chain.
* IPFS decoder cho phép admin có quyền giải mã CID trực tiếp trên trình duyệt.

## Quan sát (observability)

* `X-Request-ID` gắn UUID cho mỗi request để truy vết log.
* Khi `HRC_METRICS_ENABLED=true`, `/metrics` xuất registry mặc định của `prometheus_client`. Các collector process/runtime mặc định phụ thuộc nền tảng. API không đăng ký bộ đếm request thành công/thất bại, histogram latency hay collector throughput ledger; ứng dụng phải bổ sung instrumentation. `PerformanceMonitor` là thành phần riêng và không tự được xuất qua endpoint này.

## Hướng dẫn nhanh (curl)

### Ghi event vào chain

```bash
curl -X POST http://localhost:2661/api/ledger/chains/my_chain/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_key" \
  -d '{
    "entity_id": "ITEM-123",
    "event_type": "quality_check",
    "details": {"status": "passed", "inspector": "AI-Agent"}
  }'
```

### Truy vết entity

```bash
curl "http://localhost:2661/api/ledger/entities/ITEM-123/trace?resolve_cid=true"
```

## Liên quan

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/encryption-keys.md)

GraphQL đọc sự kiện Arrow theo hàng và chờ resolver bất đồng bộ, gồm trường details. Đọc sự kiện bên trong block cần cả quyền `chains` và `events`. Tên chain không tồn tại trả kết quả truy vấn rỗng và từ chối mutation; không tự chuyển sang main chain.

### Mã hóa JSON

Response JSON được tạo trực tiếp và các handler lỗi HTTP dùng `JSONResponse` của FastAPI/Starlette. Response mặc định và response model tiếp tục dùng validation, serialization và schema OpenAPI của FastAPI/Pydantic. Lỗi validation request giữ status `422` và danh sách `detail`. Thông điệp WebSocket dùng JSON chuẩn, mã hóa thành text frame UTF-8.
