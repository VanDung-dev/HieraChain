---
title: "API Module"
description: "Hệ thống API đa giao thức: REST ledger/business/admin, GraphQL và WebSocket. Tích hợp bảo mật đa lớp và quản lý dữ liệu IPFS."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Tổng quan

Module API xử lý giao tiếp giữa client bên ngoài và lõi HieraChain. Nó chạy trên FastAPI và hỗ trợ REST, GraphQL và WebSocket. Mục tiêu chính là hiệu năng, nên cùng một service có thể phục vụ cả ba giao thức mà không cần triển khai riêng.

### Thành phần cốt lõi

* FastAPI server (`server.py`) là điểm khởi chạy. Nó thiết lập middleware, xác thực và router.
* REST API có ba nhóm (ledger, business, admin) cho thao tác lõi, tính năng nghiệp vụ và quản trị hệ thống.
* GraphQL endpoint cho phép chọn field linh hoạt với giới hạn depth và complexity.
* WebSocket gateway truyền block và event tới subscriber theo mô hình publish/subscribe.
* Tích hợp IPFS xử lý dữ liệu off-chain với mã hóa AES-256-GCM. Payload lớn nằm ngoài chain, chỉ CID được lưu trên chain.

---

## Kiến trúc và bảo mật

API dùng middleware theo lớp. Mỗi request đi qua cùng một chuỗi kiểm tra trước khi tới handler.

### Bảo mật HTTP

* Header bảo mật được thêm vào mọi response, gồm CSP, HSTS, X-Frame-Options đặt là DENY và X-Content-Type-Options đặt là nosniff.
* Giới hạn payload chặn body request ở mức 5 MB mặc định. Mức này giúp tránh DoS bằng payload lớn.
* CORS kiểm soát origin nào được gọi API. Môi trường production yêu cầu danh sách cho phép cụ thể.

### Rate limiting

Rate limiting đếm request theo key và hỗ trợ hai backend:

* In-memory cho triển khai đơn node.
* Redis cho cụm cần đồng bộ bộ đếm.

Mặc định là 100 request mỗi phút, được cấu hình qua `HRC_RATE_LIMIT_RPM`.

### Xác thực

`APIKeyVerifier` kiểm tra header `X-API-Key`. Bật hoặc tắt qua `HRC_AUTH_ENABLED`.

---

## REST API reference

### ledger: core ledger

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

### business: enterprise features

Các endpoint này hỗ trợ quy trình nghiệp vụ:

* Channel tạo kênh giao tiếp riêng giữa các tổ chức (`POST /api/business/channels`).
* Private data collection lưu dữ liệu không chia sẻ trên sổ cái chung.
* Domain contract triển khai và chạy hợp đồng thông minh theo nghiệp vụ riêng.
* Organization đăng ký và quản lý danh tính qua MSP.

### admin: system và admin

Các endpoint này dành cho vận hành node và hệ thống:

* `POST /api/admin/verify-identity` cho phép node ký challenge để chứng minh danh tính.
* `GET /api/admin/status` trả về uptime, số lượng chain, phiên bản và trạng thái bản quyền.
* `POST /api/admin/chains/{chain_name}/secure-events` gửi sự kiện mức tin cậy cao yêu cầu xác thực chữ ký đồng bộ.

---

## GraphQL API

Endpoint: `/graphql`

Dùng GraphQL khi client cần chọn field cụ thể hoặc giảm kích thước payload.

### Giới hạn bảo mật

* Depth của query giới hạn ở 10 cấp.
* Complexity giới hạn ở 1000 điểm mỗi query, tính theo số field và phép toán.
* Introspection (`__schema`) bị tắt ở production.

### Ví dụ query (lazy-loading IPFS)

Bạn có thể chọn có fetch và giải mã dữ liệu IPFS hay không qua `resolveCid`.

```graphql
query {
  events(chainName: "supply_chain", entityId: "PROD-001", resolveCid: true) {
    eventType
    details  # Sẽ được tự động fetch từ IPFS và giải mã nếu cần
    timestamp
    isOffchain
  }
}
```

---

## WebSocket (real-time streaming)

Kết nối tới `/ws`. Để chọn chuỗi ngay khi kết nối, truyền `chain_name`, ví dụ `/ws?chain_name=supply_chain`.

Server đẩy dữ liệu ngay khi block được commit hoặc có event mới.

### Các loại message chính

* Client tới server
    * `subscribe` đăng ký nhận tin từ một chain cụ thể hoặc theo loại event.
    * `ping` giữ kết nối.
* Server tới client
    * `block_added` báo có block mới kèm dữ liệu rút gọn.
    * `event` đẩy chi tiết event tới subscriber.
    * `subscribed` xác nhận đăng ký thành công.

---

## Blockchain explorer

Tích hợp sẵn tại `blockchain_explorer.py`, explorer cung cấp dashboard cho người vận hành:

* Monitor hiển thị tốc độ tạo block và luồng event theo thời gian thực.
* Visualizer vẽ cây quan hệ giữa Main Chain và Sub-Chain.
* IPFS decoder cho phép admin có quyền giải mã CID trực tiếp trên trình duyệt.

---

## Quan sát (observability)

* `X-Request-ID` gắn UUID cho mỗi request để truy vết log.
* `/metrics` cung cấp metric dạng Prometheus, gồm:
    * Số request thành công và thất bại.
    * Độ trễ trung bình.
    * Trạng thái bộ nhớ và CPU của API server.

---

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

---

## Liên quan

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/encryption-keys.md)
