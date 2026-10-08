---
title: "Ghi nhật ký an toàn"
description: "Hệ thống ghi nhật ký an toàn có khả năng phát hiện giả mạo."
icon: material/lock-alert
---

# Ghi nhật ký an toàn

Lớp bảo mật này cung cấp log có cấu trúc và khả năng phát hiện giả mạo cho các thao tác nhạy cảm.

## Ghi nhật ký an toàn

**File**: `hierachain/security/secure_logging.py`

Hệ thống ghi nhật ký được thiết kế chuyên biệt cho an ninh:

*   **Tamper-evident**: Mỗi bản ghi log có cấu trúc chặt chẽ, hỗ trợ phát hiện các hành vi xóa hoặc sửa đổi nhật ký.
*   **Structured Logs**: Log được ghi dưới dạng JSON để dễ dàng tích hợp với các hệ thống giám sát tập trung (SIEM).
*   **Phân quyền Log**: Các module nhạy cảm (như `security`, `consensus`) sử dụng `SecureLogger` riêng biệt với mức độ bảo vệ cao hơn.

## Liên quan

*   [Làm sạch input](./risk-analyzer.md)
*   [Security module](../modules/security.md)
