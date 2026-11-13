---
title: "Module API"
description: "Hệ thống API đa giao thức: REST ledger/business/admin và WebSocket. Tích hợp bảo mật đa lớp và quản lý dữ liệu IPFS."
icon: material/api
---

# Module API (`hierachain/api/*`)

## Tổng quan

Module API xử lý giao tiếp giữa client bên ngoài và lõi HieraChain. Nó chạy trên FastAPI và hỗ trợ REST và WebSocket. Mục tiêu chính là hiệu năng, nên cùng một service có thể phục vụ cả hai giao thức mà không cần triển khai riêng.

### Thành phần cốt lõi

Import helper của API client, như `hierachain.api.storage.ipfs_client`, không tạo ứng dụng server. Các export `app` và `create_app` nạp server khi được yêu cầu; yêu cầu xác thực production vẫn được kiểm tra. Khi lifespan API kết thúc, hierarchy manager được đóng và provider manager/tracer được reset, kể cả khi startup P2P thất bại.

* FastAPI server (`server.py`) là điểm khởi chạy. Nó thiết lập middleware, xác thực và router.
* REST API có ba nhóm (ledger, business, admin) cho thao tác lõi, tính năng nghiệp vụ và quản trị hệ thống.
* Gateway WebSocket quản lý subscription và helper broadcast; luồng gửi event Sub-Chain và channel tự gọi `broadcast_event()`, còn thông báo commit block yêu cầu ứng dụng gọi `broadcast_new_block()`.
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

`APIKeyVerifier` kiểm tra header `X-API-Key` cho HTTP và WebSocket. Production bắt buộc `HRC_AUTH_ENABLED=true` và file key `HRC_API_KEYS_FILE` đã được cấp; dev/test có thể tắt xác thực. WebSocket truyền cả message block và event, nên kết nối và đăng ký cần `chains` và `events` (hoặc `all`). Trong production và WebSocket từ chối yêu cầu nếu app không có verifier đang bật hoặc verifier không trả auth context.

## Tham chiếu REST API

### ledger: sổ cái cốt lõi

Các endpoint này tương tác trực tiếp với trạng thái sổ cái:

* `GET /api/ledger/health` kiểm tra sức khỏe node.
* `GET /api/ledger/network/ping/{target_id}` gửi ping trực tiếp đến nút mạng mục tiêu.
* `GET /api/ledger/chains` liệt kê Main Chain và Sub-Chain.
* `POST /api/ledger/chains/{chain_name}/create` khởi tạo một sub-chain mới và yêu cầu user đã xác thực có quyền `chains:manage`.
* `GET /api/ledger/chains/{chain_name}/stats` lấy số lượng block, event và proof.
* `POST /api/ledger/chains/{chain_name}/events` gửi event, chuyển tải dữ liệu quá cỡ sang IPFS. Khi cung cấp `details_cid`, bắt buộc có `details_nonce` khác rỗng gồm 24 ký tự hex; bỏ qua hoặc null trả HTTP 422. Khi có chữ ký, API xác minh trên payload canonical của request, giữ `signature_content` và bảo toàn danh tính ký ở `sender`; `submitted_by` là user của API key đã xác thực. Production từ chối event không ký bằng HTTP 422. Chữ ký kiểu cũ bao phủ `details.payload` khi giá trị này là chuỗi; phản hồi tiếp nhận đến trước certification.
* `POST /api/ledger/chains/{chain_name}/submit-proof` gửi bằng chứng mật mã từ sub-chain lên main chain.
* `GET /api/ledger/chains/{chain_name}/blocks` liệt kê block có phân trang và tùy chọn giải mã CID.
* `GET /api/ledger/chains/{chain_name}/blocks/{index_or_hash}` lấy thông tin chi tiết một block theo chỉ số hoặc mã băm.
* `GET /api/ledger/entities/{id}/trace` truy vết entity xuyên suốt hệ thống phân cấp chuỗi.

### business: tính năng doanh nghiệp

Các endpoint này hỗ trợ quy trình nghiệp vụ:

* Channel tạo đường giao tiếp riêng giữa các tổ chức (`POST /api/business/channels`). Private collection được quản lý theo channel (`POST /api/business/channels/{channel_id}/private-collections`), yêu cầu `channels:manage` và ủy quyền cho `Channel.create_private_collection(...)`.
* Tổ chức và thành viên đăng ký qua dịch vụ tổ chức phân cấp (`POST /api/business/organizations`, `POST /api/business/organizations/{org_id}/members`).

### admin: hệ thống và quản trị

Các endpoint này dành cho vận hành node và hệ thống:

* `POST /api/admin/verify-identity` cho phép node ký challenge hex 1–256 ký tự để chứng minh danh tính; mỗi tiến trình API giới hạn 10 lần thử mỗi phút cho mỗi IP client.
* `GET /api/admin/status` được miễn xác thực API key và trả uptime, số chain, version cùng cờ license được gán cố định.
* `POST /api/admin/chains/{chain_name}/secure-events` kiểm tra chữ ký canonical đồng bộ rồi ghi journal và đưa event vào hàng đợi. HTTP 200 trả `status="queued"`, ID event từ ordering trong `event_hash` và thời gian phản hồi trong `timestamp`; client đang chờ `committed` cần cập nhật. Response này không xác nhận block đã commit. Ordering và replay journal xác minh lại `signature_content` gốc cùng ràng buộc với các trường được đưa vào block. Khi hàng đợi quá tải, API trả HTTP 503 với `event_id` và `journaled` trong `detail`.

## WebSocket (truyền dữ liệu thời gian thực)

Kết nối tới `/ws`. Để chọn chuỗi ngay khi kết nối, truyền `chain_name`, ví dụ `/ws?chain_name=supply_chain`.

Khi bật xác thực, gửi header `X-API-Key` trong WebSocket handshake. Kết nối và từng subscription cần cả quyền `chains` lẫn `events` vì stream hiện gửi cả hai loại thông điệp cho subscriber của chain. Luồng gửi event Sub-Chain và channel tự gọi `broadcast_event()`. Luồng commit block không gọi `broadcast_new_block()`; ứng dụng phải tự cung cấp tích hợp thông báo block.

### Các loại message chính

* Client tới server
    * `subscribe` đăng ký nhận tin từ một chain cụ thể hoặc theo loại event.
    * `ping` giữ kết nối.
* Server tới client
    * `block_added` báo có block mới kèm dữ liệu rút gọn.
    * `event` đẩy chi tiết event tới subscriber.
    * `subscribed` xác nhận đăng ký thành công.

## Quan sát (observability)

* `X-Request-ID` gắn UUID cho mỗi request để truy vết log.
* Khi `HRC_METRICS_ENABLED=true`, `/metrics` xuất registry mặc định của `prometheus_client`. Các collector process/runtime mặc định phụ thuộc nền tảng. API không đăng ký bộ đếm request thành công/thất bại, histogram latency hay collector throughput ledger; ứng dụng phải bổ sung instrumentation.

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


### Mã hóa JSON

Response JSON được tạo trực tiếp và các handler lỗi HTTP dùng `JSONResponse` của FastAPI/Starlette. Response mặc định và response model tiếp tục dùng validation, serialization và schema OpenAPI của FastAPI/Pydantic. Lỗi validation request giữ status `422` và danh sách `detail`. Thông điệp WebSocket dùng JSON chuẩn, mã hóa thành text frame UTF-8.
