---
title: "Security Module"
description: "Tổng quan về hệ thống bảo mật đa tầng: MSP, Policy Engine, Key Management và ZK Proofs."
icon: material/shield-lock
---

# Security Module (`hierachain/security/*`)

## Tổng quan

Module **Security** cung cấp các năng lực bảo mật cấp doanh nghiệp cho HieraChain. Thay vì dựa vào một lớp bảo vệ duy nhất, HieraChain triển khai chiến lược **Phòng thủ đa tầng (Defense-in-Depth)**, bao trùm từ xác thực danh tính, kiểm soát truy cập, bảo vệ tài nguyên cho đến các công nghệ tiên tiến như Zero-Knowledge Proofs.

---

## 6 Trụ cột Bảo mật chính

Kiến trúc bảo mật được cấu thành từ 6 luồng chính phối hợp chặt chẽ:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Authorization & Access__

    ---

    Quản trị danh tính (MSP), xác thực API Key và kiểm soát truy cập dựa trên thuộc tính (ABAC).
    [:octicons-arrow-right-24: Chi tiết](../security/auth-access.md)

*   :material-lock-alert:{ .lg .middle } __Lockdown & Logging__

    ---

    Cơ chế phong tỏa khẩn cấp cụm (Cluster) và hệ thống ghi nhật ký an toàn chống giả mạo.
    [:octicons-arrow-right-24: Chi tiết](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Integrity & Guard__

    ---

    Bảo vệ tài nguyên chống DoS và kiểm tra tính toàn vẹn của mã nguồn/cấu hình khi khởi động.
    [:octicons-arrow-right-24: Chi tiết](../security/integrity-guard.md)

*   :material-security-network:{ .lg .middle } __Risk & Sanitization__

    ---

    Phân tích hành vi bất thường (Anomaly Detection) và làm sạch dữ liệu đầu vào chống Injection.
    [:octicons-arrow-right-24: Chi tiết](./security/risk-sanitization.md)

*   :material-key-chain:{ .lg .middle } __Encryption & Keys__

    ---

    Quản lý vòng đời khóa mã hóa (Ed25519, AES-GCM) và chứng chỉ số chuẩn doanh nghiệp (X.509).
    [:octicons-arrow-right-24: Chi tiết](./security/keys-certs.md)

*   :material-brain:{ .lg .middle } __Zero-Knowledge Proofs__

    ---

    Bảo mật dữ liệu riêng tư xuyên chuỗi bằng công nghệ chứng minh không tiết lộ thông tin (ZKP).
    [:octicons-arrow-right-24: Chi tiết](./security/zk-proofs.md)

</div>

---

## Tích hợp Hệ thống

Mọi thành phần của HieraChain đều được bảo vệ bởi các lớp an ninh này:

*   **API Server**: Sử dụng `ResourceGuard` và `APIKeyVerifier` làm middleware bảo vệ đầu tiên.
*   **Consensus**: Mọi thông điệp đồng thuận đều được ký số và kiểm tra tính toàn vẹn.
*   **Storage**: Dữ liệu nhạy cảm được mã hóa trước khi lưu và làm sạch khi truy vấn.

---

## Cấu hình Bảo mật

Các thiết lập quan trọng được quản lý tập trung tại `hierachain/config/settings.py`:

*   `AUTH_ENABLED`: Bật/tắt xác thực API.
*   `HRC_CLUSTER_SECRET`: Mã bí mật cho các lệnh điều khiển cụm.
*   `HRC_ENABLE_ZK_PROOFS`: Kích hoạt xác thực bằng chứng ZK.

---

## Liên quan

*   [Kiến trúc bảo mật (Architecture)](../architecture/security.md)
*   [Mạng lưới P2P (Network Security)](./network.md)
*   [Giám sát và Cảnh báo (Monitoring)](./monitoring.md)
