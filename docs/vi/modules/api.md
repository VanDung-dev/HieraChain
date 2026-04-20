---
title: "API Module"
description: "Hệ thống API đa giao thức: REST v1/v2/v3, GraphQL và WebSocket. Tích hợp bảo mật đa lớp và quản lý dữ liệu IPFS."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Tổng quan

Module **API** là cổng giao tiếp chính giữa thế giới bên ngoài và nhân blockchain HieraChain. Hệ thống được xây dựng trên nền tảng **FastAPI**, cung cấp hiệu năng cực cao và hỗ trợ đồng thời nhiều phương thức tương tác: RESTful, GraphQL và WebSocket.

### Các thành phần cốt lõi

* **FastAPI Server (`server.py`)**: Điểm khởi chạy, cấu hình Middleware, Authentication và tích hợp Router.
* **Versioned REST API**: Chia làm 3 phiên bản (v1, v2, v3) phục vụ các mục đích khác nhau từ cốt lõi đến quản trị hệ thống.
* **GraphQL Endpoint**: Cung cấp khả năng truy vấn linh hoạt với cơ chế bảo mật (Depth/Complexity limit).
* **WebSocket Gateway**: Truyền tải sự kiện (events/blocks) thời gian thực theo mô hình Publish/Subscribe.
* **IPFS Integration**: Xử lý minh bạch dữ liệu on-chain và off-chain (IPFS + AES-256-GCM).

---

## Kiến trúc & Bảo mật (Middleware Layer)

HieraChain API triển khai một lớp Middleware bảo mật đa tầng để đảm bảo an toàn cho dữ liệu doanh nghiệp:

### Bảo mật HTTP

* **Security Headers**: Tự động thêm các header bảo mật như CSP (Content Security Policy), HSTS, X-Frame-Options (DENY), và X-Content-Type-Options (nosniff).
* **Payload Limit**: Giới hạn kích thước body request (mặc định 5MB) để ngăn chặn tấn công DoS.
* **CORS Management**: Kiểm soát truy cập từ các origin không xác định, đặc biệt nghiêm ngặt trong môi trường Production.

### Kiểm soát lưu lượng (Rate Limiting)

Hỗ trợ hai backend lưu trữ cho bộ đếm Rate Limit:

* **In-memory**: Phù hợp cho node đơn lẻ.
* **Redis**: Phù hợp cho cụm node (cluster) cần đồng bộ trạng thái giới hạn.

*Mặc định*: 60 requests/phút (có thể cấu hình qua `HRC_RATE_LIMIT_REQUESTS_PER_MINUTE`).

### Xác thực (Authentication)

Sử dụng `APIKeyVerifier` để kiểm tra quyền truy cập dựa trên API Key. Cơ chế này có thể bật/tắt qua biến môi trường `HRC_AUTH_ENABLED`.

---

## REST API Reference

### v1: Core Ledger (Cốt lõi)

Tập trung vào các hoạt động blockchain cơ bản:

* `GET /api/v1/health`: Kiểm tra tình trạng node.
* `GET /api/v1/chains`: Liệt kê tất cả Main Chain và Sub-Chains.
* `POST /api/v1/chains/{name}/events`: Thêm sự kiện (tự động xử lý IPFS nếu dữ liệu lớn).
* `GET /api/v1/entities/{id}/trace`: Truy vết thực thể xuyên suốt các chain trong hệ thống phân cấp.
* `GET /api/v1/chains/{name}/blocks`: Lấy danh sách block (hỗ trợ phân trang và giải mã CID IPFS).

### v2: Enterprise Features (Tính năng doanh nghiệp)

Cung cấp các công cụ nâng cao cho quy trình kinh doanh phức tạp:

* **Channels**: Tạo kênh giao tiếp riêng tư giữa các tổ chức (`POST /api/v2/channels`).
* **Private Data**: Quản lý bộ sưu tập dữ liệu riêng tư (`Private Data Collections`) không công khai trên sổ cái chung.
* **Domain Contracts**: Triển khai và thực thi hợp đồng thông minh theo nghiệp vụ đặc thù.
* **Organizations**: Đăng ký và quản lý danh tính tổ chức qua MSP.

### v3: System & Admin (Quản trị)

Dành riêng cho việc quản lý node và vận hành hệ thống:

* `POST /api/v3/verify-identity`: Node ký một challenge để chứng minh danh tính với hệ thống quản lý.
* `GET /api/v3/status`: Báo cáo chi tiết uptime, số lượng chain active, phiên bản và tình trạng bản quyền.

---

## GraphQL API

Endpoint: `/graphql`

GraphQL được khuyến khích sử dụng khi client cần truy vấn dữ liệu phức tạp hoặc cần tối ưu hóa băng thông (chọn lọc field).

### Cơ chế bảo mật đặc thù

* **Query Depth Limit**: Tối đa 10 cấp độ lồng nhau.
* **Complexity Analysis**: Giới hạn 1000 điểm cho mỗi truy vấn (tính dựa trên số lượng field và phép toán).
* **Introspection Control**: Tự động tắt tính năng khám phá schema (`__schema`) trong môi trường Production.

### Ví dụ truy vấn (Lazy-loading IPFS)

Khi truy vấn event, bạn có thể quyết định có giải mã dữ liệu từ IPFS hay không thông qua tham số `resolveCid`.

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

## WebSocket (Real-time Streaming)

Endpoint: `/ws`

HieraChain sử dụng WebSocket để đẩy dữ liệu mới đến client ngay khi block được cam kết hoặc có event mới phát sinh.

### Các loại message chính

* **Client -> Server**
    * `subscribe`: Đăng ký nhận tin từ một chain cụ thể hoặc theo loại event.
    * `ping`: Duy trì kết nối.
* **Server -> Client**
    * `block_added`: Thông báo có block mới kèm theo data rút gọn.
    * `event`: Đẩy thông tin event chi tiết đến subscribers.
    * `subscribed`: Xác nhận đăng ký thành công.

---

## Blockchain Explorer

Tích hợp sẵn tại `blockchain_explorer.py`, explorer cung cấp giao diện dashboard cho các nhà vận hành:

* **Monitor**: Theo dõi tốc độ sinh block và event theo thời gian thực.
* **Visualizer**: Trực quan hóa cấu hình cây phân cấp giữa Main Chain và các Sub-Chains.
* **IPFS Decoder**: Cho phép người quản trị có quyền truy cập giải mã nhanh các CID trực tiếp trên trình duyệt.

---

## Quan sát & Giám sát (Observability)

* **X-Request-ID**: Mỗi request được gán một UUID duy nhất trong header để truy vết log.
* **Metrics**: Tích hợp sẵn endpoint `/metrics` (Prometheus format) để theo dõi các chỉ số:

    * Số lượng request thành công/thất bại.
    * Thời gian phản hồi (Latency) trung bình.
    * Tình trạng bộ nhớ và CPU của API server.

---

## Hướng dẫn sử dụng nhanh (curl)

### Ghi sự kiện vào chuỗi

```bash
curl -X POST http://localhost:2661/api/v1/chains/my_chain/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_key" \
  -d '{
    "entity_id": "ITEM-123",
    "event_type": "quality_check",
    "details": {"status": "passed", "inspector": "AI-Agent"}
  }'
```

### Truy vết thực thể (Trace)

```bash
curl "http://localhost:2661/api/v1/entities/ITEM-123/trace?resolve_cid=true"
```

---

## Liên quan

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/keys-certs.md)
