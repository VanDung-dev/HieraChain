---
title: "Module bảo mật"
description: "Tổng quan về hệ thống bảo mật đa tầng: MSP, Policy Engine, Key Management và ZK Proofs."
icon: material/shield-lock
---

# Module bảo mật (`hierachain/security/*`)

## Tổng quan

Module bảo mật cung cấp helper identity, chính sách kiểm soát truy cập, sanitization và kiểm tra ledger có chữ ký. Kiểm tra scope HTTP, chính sách tổ chức và lời gọi Python trực tiếp có các luồng thực thi riêng. Giao diện ZK tùy chọn hiện cung cấp mock cho phát triển; ZK production chưa được triển khai.

## Sáu nhóm bảo mật

Thiết kế gom các biện pháp bảo vệ thành sáu nhóm phối hợp với nhau:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Phân quyền và truy cập__

    ---

    Quản lý danh tính (MSP), xác thực API key và kiểm soát truy cập theo thuộc tính (ABAC).
    [:octicons-arrow-right-24: Chi tiết](../security/authorization-access-control.md)

*   :material-lock-alert:{ .lg .middle } __Ghi nhật ký an toàn__

    ---

    Log JSON có cấu trúc, sanitization và che trường nhạy cảm. Xác minh kiểm toán dùng `AuditLogger` riêng cùng manifest đáng tin cậy.
    [:octicons-arrow-right-24: Chi tiết](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Toàn vẹn và bảo vệ tài nguyên__

    ---

    Giới hạn tài nguyên tại API và ordering, cùng xác minh block có chữ ký khi nạp và commit ledger.
    [:octicons-arrow-right-24: Chi tiết](../security/fault-tolerance-integrity.md)

*   :material-security-network:{ .lg .middle } __Làm sạch input__

    ---

    Xác thực và làm sạch input để chặn injection.
    [:octicons-arrow-right-24: Chi tiết](../security/risk-analyzer.md)

*   :material-key-chain:{ .lg .middle } __Mã hóa và khóa__

    ---

    Provider khóa Ed25519, mã hóa AES-GCM cho IPFS và chứng chỉ MSP nội bộ. MSP không triển khai X.509 hay mTLS.
    [:octicons-arrow-right-24: Chi tiết](../security/encryption-keys.md)

*   :material-brain:{ .lg .middle } __Zero-knowledge proofs__

    ---

    Mock phát triển để kiểm thử luồng proof ZK; tạo và xác minh production chưa được triển khai.
    [:octicons-arrow-right-24: Chi tiết](../security/decentralized-zkp.md)

</div>

## Cách các lớp kết nối

Runtime áp dụng các kiểm tra sau ở từng luồng tương ứng:

* Kiểm tra payload/rate limit của API, lỗi Redis, giới hạn event pool/RAM trong ordering và log lỗi storage. Không có `ResourceGuardMiddleware` CPU/RAM ở API.
* Block có chữ ký được kiểm tra bằng khóa creator do operator phê duyệt; kiểm tra thông điệp đồng thuận phụ thuộc vào thành phần được chọn.
* Upload IPFS mặc định mã hóa. Kho ledger SQL không tự mã hóa mọi chi tiết sự kiện được lưu; hãy cấu hình mã hóa lưu trữ và kiểm soát truy cập tại môi trường triển khai.

## Cấu hình bảo mật

Các thiết lập chính nằm ở `hierachain/config/settings.py`:

* `AUTH_ENABLED` bật hoặc tắt xác thực API.
* `HRC_ENABLE_ZK_PROOFS` bật luồng xác thực ZK; nó không cung cấp backend production. Xem [phạm vi ZK](../security/decentralized-zkp.md).

## Liên quan

*   [Kiến trúc bảo mật (Architecture)](../architecture/security.md)
*   [Mạng lưới P2P (Network Security)](./network.md)
*   [Giám sát và Cảnh báo (Monitoring)](./monitoring.md)

## Che bí mật theo field trong structured log

`sanitize_for_log()`, mọi mức của `SecureLogger`, context security event, details audit và `log_user_action()` che toàn bộ giá trị có tên field nhạy cảm trước khi duyệt dictionary và list. Các tên được hỗ trợ gồm API key, password, private key, credentials, token, session ID, authorization và field secret có tiền tố, dưới dạng snake_case, kebab-case hoặc camelCase. Container dưới field nhạy cảm trở thành `***`; public key thông thường vẫn hiển thị. Cơ chế chống log injection và che mẫu bí mật trong chuỗi vẫn áp dụng. Ứng dụng nên truyền bí mật trong field có tên; chuỗi không có tên bất kỳ không thể được nhận diện nhạy cảm một cách tin cậy.
