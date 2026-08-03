---
title: Thao tác Liên chuỗi (Cross-Chain Operations)
description: Hướng dẫn cơ chế Two-Phase Commit (2PC) và điều phối hoạt động phân tán.
icon: material/swap-horizontal
---

# Thao tác Liên chuỗi (Cross-Chain Operations)

## Mục đính

Mạng lưới phân cấp cấp cao của HieraChain bao gồm nhiều Sub-chain độc lập phục vụ các mảng khác nhau. Để đảm bảo tính toàn vẹn cũng như nguyên tử hạt nhân (Atomicity) khi điều phối luồng dữ liệu hoặc chuyển đổi trạng thái ở hai (hay nhiều) hệ thống khác biệt nhau, HieraChain tích hợp một cơ chế điều phối gọi là **Two-Phase Commit (2PC)**.

Cơ chế này được quản lý chủ đạo bởi module `CrossChainTransactionManager` tại `hierachain/hierarchical/transaction_manager.py`.

### 1. Vòng đời Trạng thái Thao tác (TransactionState)

Mỗi thao tác liên chuỗi sẽ di chuyển tuần tự qua các biểu đồ trạng thái sau nhằm tránh thất thoát:

* **`PENDING`**: Thao tác đã được khởi tạo, mạng lưới đang chờ chạy lệnh hoạt động chính.
* **`PREPARED`**: Cả chuỗi nguồn (Source chain) và chuỗi đích (Destination chain) đều đã cam kết có đủ điều kiện thực hiện thao tác, thực tế đã khóa (lock) trước tài nguyên thành công.
* **`COMMITTED`**: Thao tác hoàn tất trên tất cả các chuỗi mạng lưới một cách đồng thuận.
* **`ROLLED_BACK`**: Thao tác bị hủy do một trong hai chốt thất bại. Tài nguyên đã "đặt trước" (locked) trên các chi nhánh sẽ được rollback về phiên bản cũ.
* **`FAILED`**: Thao tác thất bại hoàn toàn (nhiều khả năng do không kết nối được TCP nội bộ hoặc lỗi logic nghiêm trọng).

### 2. Mô hình Two-Phase Commit (2PC)

Trong `CrossChainTransactionManager`, chức năng `_execute_2pc(transaction)` phân bổ rõ ràng quá trình chạy quy trình chính để xử lý thao tác liên chuỗi. Logic hoạt động cốt lõi gồm có hai pha:

#### Pha 1: Chuẩn bị (Prepare Phase)

* Người quản lý lấy ra đối tượng từ hàm cấp `get_sub_chain()` của HierarchyManager.
* Lần lượt gọi phương thức `prepare_transaction(tx_id, payload, is_source=True)` của chuỗi **Nguồn** để khóa các tài khoản nguồn lại.
* Tiếp tục gọi `prepare_transaction` lên chuỗi **Đích** để yêu cầu đánh dấu nhận giao dịch.
* Mục tiêu của Phase 1: Buộc mọi chuỗi tham gia giao dịch đưa ra lời cam kết có khả năng thực hiện thay đổi.
* Nếu chuỗi Nguồn hoặc Đích không thể Prepare thành công (ví dụ do lỗi số dư khóa), hệ thống đi ngay vào khâu `_rollback()`.

#### Pha 2: Chốt xác nhận (Commit Phase)

* Được thực hiện nếu và chỉ nếu Phase 1 trả về thành công ở tất cả các bên tham gia giao dịch.
* Module gọi tới API `commit_transaction(tx_id)` của chuỗi Nguồn.
* Đồng thời chạy tương tự tới cấu trúc của chuỗi Đích định danh là Commit hoàn tất.
* Ở bước này, block thực thụ sẽ được tạo trên hai Sub-chain để dứt điểm quá trình hoán đổi dữ liệu.
* Nếu lỗi trong quy trình Commit (mặc dù hãn hữu), trạng thái giao dịch sẽ bị gắn cờ `FAILED` để đợi công cụ sửa chữa thủ công (Recovery) kiểm tra qua ID đó.

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
        "quantity": 500
    }
)
```

Điều này sẽ kích hoạt `_execute_2pc` tự động và đồng bộ trực tiếp trong logic quản lý mà không cần thêm thao tác phụ từ phía client.
