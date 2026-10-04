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

*   Đặt `HRC_AUDIT_MANIFEST_WRITE_URL` thành URL PostgreSQL dùng để ghi digest. Trong production, `AuditLogger` từ chối khởi tạo nếu thiếu URL này hoặc callback `integrity_digest_writer(event_id, digest)` được truyền rõ ràng. Để bật xác minh khi đọc bằng cấu hình tích hợp sẵn, đặt riêng `HRC_AUDIT_MANIFEST_READ_URL` thành URL có thể đọc manifest; URL ghi không được tự dùng làm thông tin xác thực để đọc.
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

*   `query_events()` và `generate_report()` trả dữ liệu archive mà không kèm trạng thái manifest đáng tin cậy. Không coi các kết quả này là đã xác minh. Gọi `query_events_with_integrity(filter_criteria, limit)` để nhận `AuditReadResult` tường minh: chỉ trả trạng thái `verified` sau khi kiểm tra toàn bộ archive với manifest; trả `unverified` khi chưa cấu hình bộ đọc digest; và trả `failed` cùng danh sách event rỗng nếu không đọc được manifest hoặc có bản ghi thiếu, thừa, trùng lặp hay bị thay đổi.
*   API tường minh có thể dùng `HRC_AUDIT_MANIFEST_READ_URL` hoặc callback `integrity_digest_reader()`. URL chỉ có quyền ghi không được dùng để đọc digest. Với API mức thấp, truyền `manifest.load_hashes()` cùng toàn bộ tập event trong archive vào `verify_integrity(events, expected_hashes)`.
*   `verify_integrity(events, expected_hashes)` trả về `False` nếu thiếu manifest hoặc ID sự kiện hay digest không khớp. Truyền toàn bộ tập sự kiện tương ứng với manifest; bản ghi thiếu, thừa, trùng ID hoặc bị thay đổi đều làm kiểm tra thất bại.
*   Nếu lưu archive hoặc ghi digest lỗi, exception được trả về caller và không phát thống kê hay cảnh báo thành công. Lỗi sau khi lưu archive có thể để lại event thiếu mục manifest; xác minh sẽ từ chối.
*   File audit Arrow tự xoay vòng ở 100 MB. `get_event_count()` dùng số dòng trong metadata Parquet khi không lọc; khi có filter, hàm chỉ quét các cột cần thiết theo batch có giới hạn. SQLite và Arrow cùng áp dụng filter theo loại event, mức độ, nguồn, user và khoảng thời gian bao gồm hai đầu mút.
*   Retention của Arrow phải gọi rõ ràng: `ArrowAuditStorage.cleanup_old_events(max_age_seconds)` chỉ xóa archive Parquet khi mọi event trong file đều cũ hơn cutoff và trả về số event đã xóa. File trộn event cũ/mới và file legacy `.arrow`, `.log`, `.jsonl` được giữ lại; không có cleanup tự động. Cần phối hợp xóa archive với manifest digest lưu độc lập trước khi xác minh tính toàn vẹn trên toàn manifest.
*   `FileAuditStorage` ghi file JSONL theo ngày.
*   Truy xuất và đếm audit phát sinh `RuntimeError` khi không đọc được database, archive hoặc bản ghi đã giải mã. Chúng không chuyển một lượt tìm kiếm thất bại thành `[]`, `0` hoặc kết quả một phần. Parquet hỏng không được thử lại như frame Arrow cũ; frame cũ bị cắt và bản ghi JSONL sai định dạng cũng phát sinh lỗi. Tìm kiếm rỗng hợp lệ vẫn trả `[]` hoặc `0`. Consumer phải xử lý lỗi trước khi trình bày báo cáo. Query có giới hạn chỉ kiểm tra các bản ghi được đọc, còn đếm Parquet không có bộ lọc dùng metadata; cả hai không thay thế kiểm tra tính toàn vẹn toàn bộ archive.

---

## Liên quan

*   [Giám sát hiệu năng (Monitoring)](./monitoring.md)
*   [Bảo mật và Danh tính (Security)](./security.md)
*   [Xử lý lỗi hệ thống (Error Mitigation)](./error-mitigation.md)

## Xuất báo cáo CSV

`AuditLogger.generate_report(..., output_format="csv")` dùng quy tắc quote CSV cho dấu phẩy, dấu nháy và xuống dòng trong mọi ô. Ô văn bản có ký tự đầu tiên sau khoảng trắng là `=`, `+`, `-` hoặc `@` được thêm dấu nháy đơn phía trước để ngăn spreadsheet diễn giải công thức. Chính sách này thay đổi các ô văn bản tương ứng trong CSV; event đã lưu và bản xuất JSON giữ giá trị gốc. Xuất CSV không đồng nghĩa đã kiểm tra trusted manifest.
