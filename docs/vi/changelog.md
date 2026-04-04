---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

## v0.0.2 (2026-04-04)

Phiên bản này tập trung vào tăng cường bảo mật, khả năng quan sát hệ thống và các cải thiện quan trọng về ổn định cho core package `hierachain/`, giải quyết các vấn đề thực tế phát hiện trong quá trình kiểm thử và đánh giá.

??? note "Improvements (5)"

    * **Quản lý Secret & Thông tin xác thực**:

        * Giới thiệu `SecretManager` thống nhất trong `config` để quản lý thông tin xác thực an toàn với hỗ trợ nhiều backend.
        * Ngăn chặn vô tình làm lộ bí mật trong logs bằng cách che tên secret và định danh backend.
        * Ngăn chặn tự động sinh master key trong môi trường production để yêu cầu cấp phát key rõ ràng.

    * **Bảo mật & Chính sách**:

        * Thêm lưu trữ persistent cho brute force lockouts và chủ động từ chối các mẫu input nguy hiểm trong policy engine.
        * Tăng cường kiểm tra tạo thư mục để ngăn chặn tấn công path traversal trong đường dẫn cơ sở dữ liệu SQLite của SubChain.
        * Thêm module bảo mật chuyên dụng cho endpoint GraphQL với xác thực input và kiểm soát truy cập.

    * **Khả năng Quan sát & Giám sát**:

        * Tích hợp thu thập metrics Prometheus để giám sát thời gian thực độ trễ API, thông lượng khối và sức khỏe consensus.
        * Thêm hỗ trợ logging JSON để tích hợp tốt hơn với các hệ thống tổng hợp logs như ELK và Loki.
        * Thêm phương thức alert đơn giản và instance manager toàn cục để thông báo sự kiện chủ động.
        * Tăng cường rate limiting API với backend Redis cho các deployment phân tán.

    * **Cải thiện Core & Hierarchical Chain**:

        * Triển khai phát hiện deadlock với timeout và cơ chế phục hồi trong quản lý lock.
        * Leo thang mức độ nghiêm trọng của ZK proof bị thiếu lên mức critical và tích hợp trigger alert tự động.
        * Cải thiện độ mạnh mẽ của việc submit proof và xử lý shutdown trong hierarchical chains.
        * Thêm xác thực input cho `ChannelLedger.add_event` để ngăn chặn events bị malformed.

    * **Công cụ Nhà phát triển & CLI**:

        * Thêm lệnh CLI chuyên dụng cho sinh, backup và phục hồi key (`python -m hierachain key ...`).
        * Thêm endpoint để fetch khối cụ thể theo index hoặc hash cho audit mục tiêu.
        * Cập nhật SDK client để hỗ trợ đầy đủ multi-chain API v3.
        * Đồng bộ block schema với event schema để có cấu trúc dữ liệu nhất quán.

??? warning "Fix (3)"

    * **Ổn định Consensus & Ordering**:

        * Giải quyết race condition quan trọng trong commit khối và xử lý sự kiện chờ trong `OrderingService`.
        * Đảm bảo các hoạt động lockdown và resume là atomic để ngăn chặn trạng thái không nhất quán trong quá trình bảo trì.
        * Ngăn chặn mất dữ liệu im lặng trong quá trình phục hồi transaction journal với xác thực đúng đắn.
        * Cải thiện logic phục hồi state với xác thực config và modularized recovery từ transaction journal.

    * **Core & Hierarchical Chain**:

        * Sửa race condition trong quản lý hierarchical chain và thêm thủ tục shutdown graceful.

    * **Build & Packaging**:

        * Nhúng template cấu hình vào module Python để sửa lỗi thiếu file `.env.HRC.example` khi cài đặt qua pip.

---

## v0.0.1 (2026-03-22)

Phiên bản này đánh dấu việc hoàn thiện định hướng kiến trúc ban đầu của HieraChain, tập trung vào việc hợp nhất các thành phần cốt lõi thành một khung nguyên mẫu thống nhất.

??? note "Improvements (4)"

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

??? warning "Fix (1)"

    * **Ổn định & QA**: 

        * Sửa lỗi Chain Rehydration giúp khôi phục trạng thái chính xác sau khi restart.
        * Cải thiện độ tin cậy của CI/CD với matrix testing và xử lý flaky tests.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Ngày tháng theo UTC; ghi nhận các thay đổi quan trọng của HieraChain.
    * Mỗi phiên bản được chia thành 2 phần: **Improvements** (cải tiến, tính năng mới) và **Fix** (sửa lỗi, khắc phục sự cố).

    **DECISION**

    * Phân loại thay đổi theo nhóm **Improvements** và **Fix** để dễ theo dõi.
    * Sử dụng collapsible blocks (`???`) để ẩn/hiện nội dung, giúp tài liệu gọn gàng.
    * Trước khi có bản release chính thức, changelog tập trung vào development milestones.

    **ASSUMPTION**

    * Các PR tương ứng đã được merge vào nhánh chính.

    **INVARIANT**

    * Khi có bản release chính thức (v0.0.1+), sẽ sử dụng semantic versioning.

    **EDGE CASES**

    * Mô tả có thể rút gọn khi thay đổi nhỏ; chi tiết xem lịch sử Git/PR.
