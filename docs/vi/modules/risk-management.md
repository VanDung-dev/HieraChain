---
title: "Risk Management Module"
description: "Ghi nhật ký kiểm toán và báo cáo tính toàn vẹn cho các sự kiện vận hành."
icon: material/alert-circle
---

# Risk Management Module (`hierachain/risk_management/*`)

## Tổng quan

Package **Risk Management** hiện cung cấp ghi nhật ký kiểm toán và báo cáo tính toàn vẹn cho các sự kiện vận hành.

---

## Thành phần chính

<div class="grid cards" markdown>

*   :material-file-lock:{ .lg .middle } __Audit Logger__

    ---

    __File__: `audit_logger.py`

    * Ghi vết toàn bộ vòng đời rủi ro theo chuẩn **JSONL**.
    * Đảm bảo tính toàn vẹn dữ liệu bằng hàm băm **SHA-256**.
    * Hỗ trợ truy vấn và tạo báo cáo phục vụ kiểm toán tuân thủ (Compliance).

</div>

---

## Nhật ký Kiểm toán và Tính toàn vẹn

Mọi sự kiện trong module đều được lưu trữ với cấu trúc định danh duy nhất (Correlation ID) và được bảo vệ chống thay đổi:

*   **Hashing**: Mỗi bản ghi audit chứa hash SHA-256 của nội dung, cho phép phát hiện hành vi can thiệp vào log.
*   **Rotation**: Tự động xoay vòng log (100MB) và nén dữ liệu cũ để tối ưu lưu trữ.
*   **Retention**: Mặc định lưu trữ nhật ký trong 90 ngày (có thể cấu hình).

---

## Liên quan

*   [Giám sát hiệu năng (Monitoring)](./monitoring.md)
*   [Bảo mật và Danh tính (Security)](./security.md)
*   [Xử lý lỗi hệ thống (Error Mitigation)](./error-mitigation.md)
