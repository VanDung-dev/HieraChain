---
title: "Khắc phục sự cố"
description: "Checklist chẩn đoán nhanh các lỗi thường gặp: cổng/API, phụ thuộc, schema mismatch, API key, Redis/SQLite, hiệu năng."
icon: material/wrench
---

# Khắc phục sự cố

Trang này cung cấp checklist và các bước chẩn đoán nhanh cho các lỗi thường gặp khi triển khai và vận hành HieraChain.

## API không lên hoặc 404

* Kiểm tra tiến trình server:

    ```bash
    python -m hierachain.api.server
    ```

* Mặc định lắng nghe `http://localhost:2661`. Mở `http://localhost:2661/docs` để xác minh.
* Nếu cổng đổi khác: xem `hierachain/config/settings.py` (biến môi trường `HRC_API_PORT`).

## 401/403 khi gọi API

* Production có thể bật AUTH: `settings.AUTH_ENABLED`. Khi đó cần gửi API key:

    ```bash
    curl -H "X-API-Key: <your-key>" http://localhost:2661/api/v1/health
    ```

* Tên header tuỳ `settings.API_KEY_NAME` (mặc định `X-API-Key`).

## Lỗi khi thêm sự kiện (schema mismatch)

* Đảm bảo payload có các trường bắt buộc:

    ```json
    {
      "entity_id": "...",
      "event_type": "...",
      "details": {"k": "v"}
    }
    ```

* `details` là map<string,string>. Giá trị không phải chuỗi sẽ bị chuyển sang chuỗi.
* Timestamp do server sinh; không cần gửi từ client.

## Không tạo được Sub-Chain

* Endpoint tạo chuỗi:

    ```bash
    curl -X POST http://localhost:2661/api/v1/chains/supply_chain/create
    ```

* Tên chuỗi phải khớp regex `[a-zA-Z0-9_\-]+` (xem kiểm tra trong `api/v1/endpoints.py`).

## Sự kiện không xuất hiện trong block trả về

* Dùng API lấy block:

    ```bash
    curl "http://localhost:2661/api/v1/chains/supply_chain/blocks?limit=5&offset=0"
    ```

* Một số chuỗi cần gọi finalize/submit proof để thấy block mới. Thử submit proof:

    ```bash
    curl -X POST http://localhost:2661/api/v1/chains/supply_chain/submit-proof
    ```

## Hiệu năng kém/503 Service Unavailable

* Nếu tích hợp `ResourceGuardMiddleware`, 503 có thể do CPU/RAM vượt ngưỡng.
* Kiểm tra cấu hình rate limit/HSTS/CORS trong `settings.py`.
* Giảm kích thước lô sự kiện, bật cache nâng cao nếu phù hợp (`ADVANCED_CACHING_ENABLED`).

## Redis/SQLite không kết nối

* Kiểm tra biến môi trường:

  * `DATABASE_URL` (SQLite/PostgreSQL)
  * `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

* Đổi `DEFAULT_STORAGE_BACKEND` về `memory` để cô lập sự cố lưu trữ.

## V2 endpoints trả lỗi

* Xác minh API v2 đã được nạp (xem `hierachain/api/server.py` và `hierachain/api/v2/endpoints.py`).
* Thử health v2:

    ```bash
    curl -s http://localhost:2661/api/v2/health
    ```

## Chữ ký/khóa

* Kiểm tra public key 64‑hex (Ed25519) khi đăng ký người dùng (`security/identity.py`).
* Dùng `security/security_utils.py` để sinh cặp khóa test.

## Nhật ký và kiểm toán

* Bật mức log phù hợp, xem `settings.LOG_LEVEL`.
* Dùng `risk_management/audit_logger.py` cho vết kiểm toán.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Port/API mặc định trong `hierachain/config/settings.py` (API_PORT=2661).
    * Regex tên Sub-Chain và endpoints ở `hierachain/api/v1/endpoints.py`.
    * Middleware `ResourceGuardMiddleware` trong `hierachain/security/resource_guard.py`.

    **DECISION**

    * Ưu tiên chẩn đoán theo lớp: Config → API → Storage → Security → Performance.
    * Sử dụng curl/CLI đơn giản để tái hiện và cô lập vấn đề.

    **ASSUMPTION**

    * Môi trường đã cài đủ dependencies, network local ổn định.

    **INVARIANT**

    * FACT phải bám sát đường dẫn mã nguồn thực tế.
    * Không tắt bảo mật ở production chỉ để vượt qua lỗi tạm thời.

    **EDGE CASES**

    * Port bị chiếm bởi tiến trình khác → đổi `HRC_API_PORT`.
    * Dữ liệu `details` dạng phức tạp gây lỗi serialize → chuẩn hoá về chuỗi.
