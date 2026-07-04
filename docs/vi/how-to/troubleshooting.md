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
    curl -H "X-API-Key: <your-key>" http://localhost:2661/api/ledger/health
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
    curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    ```

* Tên chuỗi phải khớp regex `[a-zA-Z0-9_\-]+` (xem kiểm tra trong `api/ledger/endpoints.py`).

## Sự kiện không xuất hiện trong block trả về

* Dùng API lấy block:

    ```bash
    curl "http://localhost:2661/api/ledger/chains/supply_chain/blocks?limit=5&offset=0"
    ```

* Một số chuỗi cần gọi finalize/submit proof để thấy block mới. Thử submit proof:

    ```bash
    curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
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

## business endpoints trả lỗi

* Xác minh API business đã được nạp (xem `hierachain/api/server.py` và `hierachain/api/business/endpoints.py`).
* Thử health business:

    ```bash
    curl -s http://localhost:2661/api/business/health
    ```

## Chữ ký/khóa

* Kiểm tra public key 64‑hex (Ed25519) khi đăng ký người dùng (`security/identity.py`).
* Dùng `security/security_utils.py` để sinh cặp khóa test.

## Nhật ký và kiểm toán

* Bật mức log phù hợp, xem `settings.LOG_LEVEL`.
* Dùng `risk_management/audit_logger.py` cho vết kiểm toán.
