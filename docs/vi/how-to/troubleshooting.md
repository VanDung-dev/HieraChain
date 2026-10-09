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
    python -m hierachain
    ```

* Mặc định lắng nghe `http://localhost:2661`. Mở `http://localhost:2661/docs` để xác minh.
* Nếu cổng đổi khác: xem `hierachain/config/settings.py` (biến môi trường `HRC_API_PORT`).

## 401/403 khi gọi API

* Production yêu cầu `settings.AUTH_ENABLED=True`. Route được bảo vệ cần API key có scope phù hợp; route health/status có thể được miễn. Kiểm tra một route được bảo vệ:

    ```bash
    curl -H "X-API-Key: <your-key>" http://localhost:2661/api/ledger/chains
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

* REST `details` là đối tượng JSON và giữ nguyên kiểu dữ liệu được hỗ trợ trong payload sự kiện canonical. Cột metadata `details` của Arrow là bản biểu diễn chuỗi; nó không thay thế payload gốc.
* Request model của API không có trường timestamp và event builder lấy thời gian từ server. Timestamp do client gửi không được sử dụng.

## Không tạo được Sub-Chain

* Endpoint tạo chuỗi:

    ```bash
    curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    ```

* Tên chain phải khớp regex `[a-zA-Z0-9_\-]+` (xem xác minh trong `hierachain/api/ledger/chains.py`).

## Sự kiện không xuất hiện trong block trả về

* Dùng API lấy block:

    ```bash
    curl "http://localhost:2661/api/ledger/chains/supply_chain/blocks?limit=5&offset=0"
    ```

* Kết quả gửi sự kiện xác nhận ordering đã tiếp nhận. Đợi batch đạt kích thước/timeout và consumer xử lý commit rồi đọc block lại. Nếu sự kiện vẫn thiếu, kiểm tra trạng thái orderer và lỗi lưu trữ/hoàn tất block. Gửi bằng chứng lên MainChain là thao tác riêng; nó không buộc batch đang chờ của Sub-Chain phải commit.

## Hiệu năng kém/503 Service Unavailable

* Kiểm tra payload/rate limit của API, lỗi Redis, giới hạn event pool/RAM trong ordering và log lỗi storage. Không có `ResourceGuardMiddleware` CPU/RAM ở API.
* Kiểm tra giới hạn tốc độ API và CORS trong `settings.py`; cấu hình HSTS tại proxy HTTPS.
* Giảm kích thước lô sự kiện; chỉ điều chỉnh instance cache hiện có sau khi đo việc sử dụng chúng.

## Redis/SQLite không kết nối

* Kiểm tra biến môi trường:

  * `DATABASE_URL` (SQLite/PostgreSQL)
  * `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

* Chỉ đặt `HRC_STORAGE_BACKEND=memory` cho test biệt lập; backend này không giữ dữ liệu ledger sau khi process kết thúc. Dùng `sqlite` hoặc `postgres` để lưu bền block có chữ ký.

## business endpoints trả lỗi

* Xác minh API business đã được nạp (xem `hierachain/api/server.py` và `hierachain/api/business/router.py`).
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
