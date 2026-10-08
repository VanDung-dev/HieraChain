---
title: "Thực hành bảo mật"
description: "Khuyến nghị bảo mật: MSP/Identity, quản lý khóa, API key, sanitization, logging an toàn, CORS/HSTS, rate limit."
icon: material/shield-star
---

# Thực hành bảo mật

## Mục đích

Đề xuất các thực hành chuẩn để triển khai HieraChain an toàn ở môi trường production.

## Khuyến nghị cốt lõi

* Bật AUTH và dùng API key (hoặc nâng cấp OAuth/mTLS theo nhu cầu).
* Quản lý khóa (Ed25519) tập trung; luân chuyển/thu hồi khóa định kỳ; sao lưu an toàn.
* Sanitization log và payload để tránh rò rỉ dữ liệu nhạy cảm.
* Bật HSTS/CORS/Rate limit phù hợp với môi trường và front‑end hợp lệ.
* Bật guard tài nguyên để giảm tải khi hệ thống quá tải.

## Lưu trạng thái khóa xác thực

* Dùng backend brute-force SQLite hoặc Redis khi xác thực API chạy trên nhiều worker. Cả hai backend đều đếm lần thất bại nguyên tử giữa các worker.
* Backend memory và file giữ bộ đếm lần thử trong một tiến trình; chỉ chạy một worker với các backend này. Các instance dùng file sẽ tải lại trạng thái khóa để nhận biết lệnh khóa do instance khác trong cùng triển khai ghi ở lần kiểm tra tiếp theo.
* Lỗi backend dùng chung sẽ dừng yêu cầu xác thực. Hãy khôi phục backend đã cấu hình trước khi tiếp tục phục vụ yêu cầu cần xác thực.

## Thành phần liên quan

* Identity/MSP/Key: `hierachain/security/{identity.py, msp.py, key_manager.py, key_provider.py, key_backup_manager.py, certificate.py}`
* Policy/Guard: `hierachain/security/{policy_engine.py, resource_guard.py}`
* Log/Sanitize: `hierachain/security/{secure_logging.py, sanitization.py}`
* API Key: `hierachain/security/verify/api_key_verifier.py`

## Cấu hình

* `AUTH_ENABLED`, `API_KEY_LOCATION`, `API_KEY_NAME`
* `CORS_ALLOW_ALL`, `CORS_ORIGINS`
* `HSTS_ENABLED`, `HSTS_MAX_AGE`
* `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_MINUTE`

## Danh sách kiểm tra nhanh

* [ ] Secrets qua secret manager (không hard‑code).
* [ ] CORS chỉ cho phép origin hợp lệ (không dùng `*` ở production).
* [ ] Bật HSTS với `max-age` phù hợp; đảm bảo HTTPS.
* [ ] Rate limit tại API gateway/ngay trên app (khi cần).
* [ ] Nhật ký không chứa dữ liệu nhạy cảm; bật sanitize.
* [ ] Cơ chế thu hồi API key khi bị lộ; audit đầy đủ.
