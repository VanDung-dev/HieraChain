---
title: "Ghi nhật ký an toàn"
description: "Log JSON có cấu trúc, sanitization và che trường nhạy cảm."
icon: material/lock-alert
---

# Ghi nhật ký an toàn

`SecureLogger` trong `hierachain/security/secure_logging.py` ghi log JSON có cấu trúc cho thao tác nhạy cảm về bảo mật. Nó làm sạch chuỗi và che trường nhạy cảm theo tên, kể cả dữ liệu lồng nhau. Các instance logger riêng cho phép ứng dụng cấu hình handler và level theo module.

Cấu trúc JSON không tự phát hiện việc sửa hay xóa bản ghi. `SecureLogger` không có chuỗi hash, chữ ký hay manifest đáng tin cậy. Log tập trung và chính sách lưu giữ thuộc hệ thống log của môi trường triển khai.

Để xác minh kiểm toán, dùng `AuditLogger` riêng và workflow manifest đáng tin cậy được mô tả trong [Quản lý rủi ro](../modules/risk-management.md). Lưu manifest độc lập với log cần xác minh.

## Liên quan

* [Sanitization đầu vào](./risk-analyzer.md)
* [Module bảo mật](../modules/security.md)
