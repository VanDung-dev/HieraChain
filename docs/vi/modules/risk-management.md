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

    * Lưu sự kiện audit vào backend đã cấu hình; mặc định là Arrow Parquet, còn `FileAuditStorage` ghi JSONL.
    * Tính digest **SHA-256** trên mọi trường của `AuditEvent`.
    * Hỗ trợ truy vấn và tạo báo cáo phục vụ kiểm toán tuân thủ (Compliance).

</div>

---

## Nhật ký Kiểm toán và Tính toàn vẹn

Tính toàn vẹn của sự kiện audit dùng manifest digest đáng tin cậy riêng:

*   Đặt `HRC_AUDIT_MANIFEST_WRITE_URL` thành URL của PostgreSQL dành riêng cho manifest để `PostgresAuditManifest` được nối tự động. Trong production, `AuditLogger` từ chối khởi tạo nếu thiếu URL này hoặc callback `integrity_digest_writer(event_id, digest)` được truyền rõ ràng.
*   Đặt database manifest ngoài host hoặc volume có thể sửa archive và dùng quyền truy cập tách biệt. Role của ứng dụng chỉ có quyền `INSERT` trên bảng; role xác minh riêng chỉ có quyền `SELECT`; cả hai cần quyền `USAGE` trên schema. Sidecar có thể bị sửa cùng archive không cung cấp bằng chứng chống can thiệp.
*   Tạo hai role và bảng manifest trong database đó trước khi khởi động logger:

    ```sql
    CREATE TABLE public.audit_event_digests (
        event_id TEXT PRIMARY KEY,
        digest TEXT NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    REVOKE ALL ON public.audit_event_digests FROM PUBLIC;
    GRANT USAGE ON SCHEMA public TO audit_manifest_writer, audit_manifest_reader;
    GRANT INSERT ON public.audit_event_digests TO audit_manifest_writer;
    GRANT SELECT ON public.audit_event_digests TO audit_manifest_reader;
    ```

*   Khi xác minh, kết nối `PostgresAuditManifest` bằng role xác minh rồi truyền `manifest.load_hashes()` và toàn bộ event trong archive vào `verify_integrity(events, expected_hashes)`.
*   `verify_integrity(events, expected_hashes)` trả về `False` nếu thiếu manifest hoặc ID sự kiện hay digest không khớp. Truyền toàn bộ tập sự kiện tương ứng với manifest; bản ghi thiếu, thừa, trùng ID hoặc bị thay đổi đều làm kiểm tra thất bại.
*   Nếu lưu archive hoặc ghi digest lỗi, exception được trả về caller và không phát thống kê hay cảnh báo thành công. Lỗi sau khi lưu archive có thể để lại event thiếu mục manifest; xác minh sẽ từ chối.
*   File audit Arrow tự xoay vòng ở 100 MB. `FileAuditStorage` ghi file JSONL theo ngày.

---

## Liên quan

*   [Giám sát hiệu năng (Monitoring)](./monitoring.md)
*   [Bảo mật và Danh tính (Security)](./security.md)
*   [Xử lý lỗi hệ thống (Error Mitigation)](./error-mitigation.md)
