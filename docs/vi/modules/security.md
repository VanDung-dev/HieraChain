---
title: "Security Module"
description: "Tổng quan về hệ thống bảo mật đa tầng: MSP, Policy Engine, Key Management và ZK Proofs."
icon: material/shield-lock
---

# Security Module (`hierachain/security/*`)

## Tổng quan

Module security cung cấp lớp bảo vệ chính cho HieraChain. Nó không dựa vào một lớp duy nhất. Module kết hợp danh tính, kiểm soát truy cập, bảo vệ tài nguyên và tính toàn vẹn ledger có chữ ký. Các interface ZK tùy chọn hiện chỉ có mock phát triển; ZK production chưa được triển khai.

---

## Sáu nhóm bảo mật

Thiết kế gom các biện pháp bảo vệ thành sáu nhóm phối hợp với nhau:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Authorization và access__

    ---

    Quản lý danh tính (MSP), xác thực API key và kiểm soát truy cập theo thuộc tính (ABAC).
    [:octicons-arrow-right-24: Chi tiết](../security/authorization-access-control.md)

*   :material-lock-alert:{ .lg .middle } __Ghi nhật ký an toàn__

    ---

    Ghi log chống giả mạo cho các thao tác nhạy cảm về bảo mật.
    [:octicons-arrow-right-24: Chi tiết](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Integrity và guard__

    ---

    Bảo vệ tài nguyên trước DoS và kiểm tra tính toàn vẹn của code và cấu hình khi khởi động.
    [:octicons-arrow-right-24: Chi tiết](../security/fault-tolerance-integrity.md)

*   :material-security-network:{ .lg .middle } __Làm sạch input__

    ---

    Xác thực và làm sạch input để chặn injection.
    [:octicons-arrow-right-24: Chi tiết](../security/risk-analyzer.md)

*   :material-key-chain:{ .lg .middle } __Encryption và keys__

    ---

    Quản lý vòng đời khóa (Ed25519, AES-GCM) và chứng chỉ X.509.
    [:octicons-arrow-right-24: Chi tiết](../security/encryption-keys.md)

*   :material-brain:{ .lg .middle } __Zero-knowledge proofs__

    ---

    Mock phát triển để kiểm thử luồng proof ZK; tạo và xác minh production chưa được triển khai.
    [:octicons-arrow-right-24: Chi tiết](../security/decentralized-zkp.md)

</div>

---

## Cách các lớp kết nối

Mọi phần của HieraChain đều dùng chung các lớp này:

* API server dùng `ResourceGuard` và `APIKeyVerifier` làm middleware. Chúng chạy đầu tiên trên mỗi request.
* Consensus ký mọi message đồng thuận và kiểm tra tính toàn vẹn trước khi chấp nhận.
* Storage mã hóa dữ liệu nhạy cảm trước khi ghi và làm sạch input khi truy vấn.

---

## Cấu hình bảo mật

Các thiết lập chính nằm ở `hierachain/config/settings.py`:

* `AUTH_ENABLED` bật hoặc tắt xác thực API.
* `HRC_ENABLE_ZK_PROOFS` bật luồng xác thực ZK; nó không cung cấp backend production. Xem [phạm vi ZK](../security/decentralized-zkp.md).

---

## Liên quan

*   [Kiến trúc bảo mật (Architecture)](../architecture/security.md)
*   [Mạng lưới P2P (Network Security)](./network.md)
*   [Giám sát và Cảnh báo (Monitoring)](./monitoring.md)

## Che bí mật theo field trong structured log

`sanitize_for_log()`, mọi mức của `SecureLogger`, context security event, details audit và `log_user_action()` che toàn bộ giá trị có tên field nhạy cảm trước khi duyệt dictionary và list. Các tên được hỗ trợ gồm API key, password, private key, credentials, token, session ID, authorization và field secret có tiền tố, dưới dạng snake_case, kebab-case hoặc camelCase. Container dưới field nhạy cảm trở thành `***`; public key thông thường vẫn hiển thị. Cơ chế chống log injection và che mẫu bí mật trong chuỗi vẫn áp dụng. Ứng dụng nên truyền bí mật trong field có tên; chuỗi không có tên bất kỳ không thể được nhận diện nhạy cảm một cách tin cậy.
