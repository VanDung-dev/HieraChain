---
title: Giao dịch Liên chuỗi (Cross-Chain Transactions)
description: Hướng dẫn cơ chế Two-Phase Commit (2PC) và điều phối giao dịch phân tán.
icon: material/swap-horizontal
---

# Giao dịch Liên chuỗi (Cross-Chain Transactions)

## Mục đính

Mạng lưới phân cấp cấp cao của HieraChain bao gồm nhiều Sub-chain độc lập phục vụ các mảng khác nhau. Để đảm bảo tính toàn vẹn cũng như nguyên tử hạt nhân (Atomicity) khi điều phối luồng dữ liệu hoặc chuyển đổi tài sản ở hai (hay nhiều) hệ thống khác biệt nhau, HieraChain tích hợp một cơ chế điều phối gọi là **Two-Phase Commit (2PC)**.

Cơ chế này được quản lý chủ đạo bởi module `CrossChainTransactionManager` tại `hierachain/hierarchical/transaction_manager.py`.

### 1. Vòng đời Trạng thái Giao dịch (TransactionState)

Mỗi giao dịch liên chuỗi sẽ di chuyển tuần tự qua các biểu đồ trạng thái sau nhằm tránh thất thoát:

- **`PENDING`**: Giao dịch đã được khởi tạo, mạng lưới đang chờ chạy lệnh hoạt động chính.
- **`PREPARED`**: Cả chuỗi nguồn (Source chain) và chuỗi đích (Destination chain) đều đã cam kết có đủ điều kiện thực hiện giao dịch, thực tế đã khóa (lock) trước tài nguyên thành công.
- **`COMMITTED`**: Giao dịch hoàn tất trên tất cả các chuỗi mạng lưới một cách đồng thuận.
- **`ROLLED_BACK`**: Giao dịch bị hủy do một trong hai chốt thất bại. Tài nguyên đã "đặt trước" (locked) trên các chi nhánh sẽ được rollback về phiên bản cũ.
- **`FAILED`**: Giao dịch thất bại hoàn toàn (nhiều khả năng do không kết nối được TCP nội bộ hoặc lỗi logic nghiêm trọng).

### 2. Mô hình Two-Phase Commit (2PC)

Trong `CrossChainTransactionManager`, chức năng `_execute_2pc(transaction)` phân bổ rõ ràng quá trình chạy quy trình chính để xử lý giao dịch. Logic hoạt động cốt lõi gồm có hai pha:

#### Pha 1: Chuẩn bị (Prepare Phase)

- Người quản lý lấy ra đối tượng từ hàm cấp `get_sub_chain()` của HierarchyManager.
- Lần lượt gọi phương thức `prepare_transaction(tx_id, payload, is_source=True)` của chuỗi **Nguồn** để khóa các tài khoản nguồn lại.
- Tiếp tục gọi `prepare_transaction` lên chuỗi **Đích** để yêu cầu đánh dấu nhận giao dịch.
- Mục tiêu của Phase 1: Buộc mọi chuỗi tham gia giao dịch đưa ra lời cam kết có khả năng thực hiện thay đổi.
- Nếu chuỗi Nguồn hoặc Đích không thể Prepare thành công (ví dụ do lỗi số dư khóa), hệ thống đi ngay vào khâu `_rollback()`.

#### Pha 2: Chốt xác nhận (Commit Phase)

- Được thực hiện nếu và chỉ nếu Phase 1 trả về thành công ở tất cả các bên tham gia giao dịch.
- Module gọi tới API `commit_transaction(tx_id)` của chuỗi Nguồn.
- Đồng thời chạy tương tự tới cấu trúc của chuỗi Đích định danh là Commit hoàn tất.
- Ở bước này, block thực thụ sẽ được tạo trên hai Sub-chain để dứt điểm quá trình hoán đổi dữ liệu.
- Nếu lỗi trong quy trình Commit (mặc dù hãn hữu), trạng thái giao dịch sẽ bị gắn cờ `FAILED` để đợi công cụ sửa chữa thủ công (Recovery) kiểm tra qua ID đó.

### 3. Hướng dẫn Khởi tạo Lệnh

Khi cần phát sinh lệnh qua DApp hoặc Module ngoài, lập trình viên truy xuất API/Function sau:

```python
# Gọi instance từ HierarchyManager đã sẵn có
manager = CrossChainTransactionManager(hierarchy_manager=hierarchy_manager_instance)

# Thực hiện lệnh initiate giao dịch
tx_id = manager.initiate_transaction(
    source_chain_name="sub_chain_finance",
    dest_chain_name="sub_chain_logistics",
    payload={
        "event_name": "asset_transfer",
        "asset_id": "PKG-099238",
        "amount": 500
    }
)
```

Điều này sẽ kích hoạt `_execute_2pc` tự động và đồng bộ trực tiếp trong logic quản lý mà không cần thêm thao tác phụ từ phía client.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/*` (Python >= 3.10 theo `pyproject.toml`).
    * Script CLI: `hrc` (định nghĩa tại `[project.scripts]` trong `pyproject.toml`).
    * API server: `hierachain/api/server.py` (có thể chạy bằng `python -m hierachain.api.server`).

    **DECISION**

    * Dùng Markdown, tách rõ các khối FACT / DECISION / ASSUMPTION / INVARIANT / EDGE CASES.
    * Tổ chức nội dung theo khung chuẩn thống nhất.

    **ASSUMPTION**

    * Người đọc đã cài Python 3.10+ và có quyền truy cập internet để cài dependencies.
    * Môi trường phát triển sử dụng `venv` hoặc công cụ tương đương.

    **INVARIANT**

    * FACT phải bám sát mã nguồn hiện tại (tên file, chữ ký API, đường dẫn).
    * Không pha trộn nội dung tiếp thị trong tài liệu kỹ thuật.

    **EDGE CASES**

    * Khác biệt shell giữa Windows (PowerShell) và Linux/macOS (bash) khi kích hoạt venv.
    * Mạng nội bộ hạn chế có thể ảnh hưởng quá trình cài gói.
