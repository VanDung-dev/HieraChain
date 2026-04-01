---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

## v0.0.1 (2026-03-22)

Phiên bản này đánh dấu việc hoàn thiện định hướng kiến trúc ban đầu của HieraChain, tập trung vào việc hợp nhất các thành phần cốt lõi thành một khung nguyên mẫu thống nhất.

* **Tích hợp Lưu trữ IPFS**: Hỗ trợ lưu trữ dữ liệu off-chain với mã hóa AES-256-GCM và định danh CID trên toàn bộ các giao diện API (REST, GraphQL, WebSocket).
* **Tối ưu Hiệu suất & Khả năng mở rộng**:

    * Xử lý khối song song trong `OrderingService`.
    * Caching cho xác thực chứng chỉ và quyền hạn.
    * Tối ưu hóa worker pool (75% CPU) và hỗ trợ đa luồng cho SQLite.

* **Công cụ cho Nhà phát triển**: Ra mắt `BlockchainExplorer` dashboard và hệ thống tài liệu kỹ thuật chi tiết.
* **Bảo mật & Toàn vẹn**: 

    * Hỗ trợ Merkle Root trong block header và lưu trữ.
    * Đảm bảo tính nhất quán của hash và thread-safe cho các thành phần core.
    * Chuẩn hóa logging bảo mật với `SecureLogger`.

* **Ổn định & QA**: 

    * Sửa lỗi Chain Rehydration giúp khôi phục trạng thái chính xác sau khi restart.
    * Cải thiện độ tin cậy của CI/CD với matrix testing và xử lý flaky tests.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Ngày tháng theo UTC; ghi nhận các thay đổi quan trọng của HieraChain.

    **DECISION**

    * Gộp thay đổi theo nhóm tính năng/module để dễ tra cứu.
    * Trước khi có bản release chính thức, changelog tập trung vào development milestones.

    **ASSUMPTION**

    * Các PR tương ứng đã được merge vào nhánh chính.

    **INVARIANT**

    * Khi có bản release chính thức (v0.0.1+), sẽ sử dụng semantic versioning.

    **EDGE CASES**

    * Mô tả có thể rút gọn khi thay đổi nhỏ; chi tiết xem lịch sử Git/PR.
