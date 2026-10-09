---
title: "Thực hành bảo mật"
description: "Khuyến nghị bảo mật: MSP/Identity, quản lý khóa, API key, sanitization, logging an toàn, CORS/HSTS, rate limit."
icon: material/shield-star
---

# Thực hành bảo mật

## Triển khai

Production yêu cầu xác thực API key và bản đồ khóa đã được cấp sẵn. Chỉ cấp cho client các scope mà route của nó cần. Kết thúc HTTPS tại reverse proxy doanh nghiệp, cấu hình `Strict-Transport-Security` ở đó và giới hạn CORS cho các frontend được phép. Cấu hình HSTS của HieraChain không thêm header này.

Dùng giới hạn payload/tốc độ của API và giới hạn event pool/RAM của ordering để bảo vệ tài nguyên ứng dụng. Cấu hình thêm giới hạn tại proxy. Package không có `ResourceGuardMiddleware` hay `security/resource_guard.py`.

## Khóa và log

Lưu đầy đủ node identity, bản đồ khóa block đáng tin cậy và khóa mã hóa IPFS trong kho có kiểm soát truy cập và khả năng khôi phục. Khi xoay khóa, cập nhật các bản đồ khóa công khai được verifier phê duyệt. Xem [Sao lưu khóa](../workflows/key-backup.md) để phân biệt node identity với file cặp khóa của CLI.

Dùng trường có tên trong dữ liệu có cấu trúc để `SecureLogger` che bí mật. Nó không phát hiện việc xóa hay sửa log. Xác minh kiểm toán dùng `AuditLogger` với manifest đáng tin cậy được lưu riêng. Áp dụng chính sách lưu giữ và kiểm soát truy cập tại hệ thống log của môi trường triển khai.

## Lưu trạng thái khóa xác thực

* Dùng backend brute-force SQLite hoặc Redis khi xác thực API chạy trên nhiều worker. Cả hai backend đều đếm lần thất bại nguyên tử giữa các worker.
* Backend memory và file giữ bộ đếm lần thử trong một process; dùng một worker với các backend này. Instance dùng file nạp lại trạng thái khóa, nên lần kiểm tra tiếp theo thấy được khóa do instance khác ghi.
* Lỗi backend dùng chung làm dừng xác thực. Khôi phục backend trước khi tiếp tục phục vụ request cần xác thực.

## Tham chiếu triển khai

| Phạm vi | Mã nguồn |
|:-----|:-------|
| Identity và khóa | `hierachain/security/identity.py`, `msp.py`, `key_manager.py`, `key_provider.py`, `identity_loader.py` |
| ABAC do caller quản lý | `hierachain/security/policy_engine.py` |
| Xác thực API | `hierachain/security/verify/api_key_verifier.py` |
| Log có cấu trúc | `hierachain/security/secure_logging.py`, `sanitization.py` |
| Giới hạn API | `hierachain/api/middleware.py` |

## Cấu hình

Dùng `HRC_AUTH_ENABLED`, `HRC_API_KEYS_FILE`, `HRC_API_KEY_LOCATION` và `HRC_API_KEY_NAME` để cấu hình xác thực API. CORS dùng `HRC_CORS_ALLOW_ALL` và `HRC_CORS_ORIGINS`. Giới hạn tốc độ dùng `HRC_RATE_LIMIT`, `HRC_RATE_LIMIT_RPM` và `HRC_RATE_LIMIT_BACKEND`.

Xem [Triển khai an toàn](../how-to/secure-deployment.md) để biết lệnh cấp khóa và [Cấu hình](../reference/config.md) để biết giá trị mặc định. Tích hợp OAuth, LDAP, HSM và SIEM thuộc ứng dụng chủ hoặc gateway doanh nghiệp.
