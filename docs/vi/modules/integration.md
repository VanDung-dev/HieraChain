---
title: "Integration Module"
description: "Công cụ ánh xạ và lập lịch ERP cùng các bộ dữ liệu mô phỏng được bật rõ ràng."
icon: material/puzzle
---

# Integration Module (`hierachain/integration/*`)

## 1. Tổng quan

Module `integration` cung cấp công cụ ánh xạ trường, phát hiện thay đổi và lập lịch cho ứng dụng tự kết nối adapter ERP với nơi nhận sự kiện HieraChain. Module không có bộ truyền tải SAP, Oracle hay Microsoft Dynamics thực tế, và máy chủ API không tự khởi chạy đồng bộ ERP. Ứng dụng gọi thư viện phải đăng ký adapter và nơi nhận chuỗi.

## 2. Các thành phần cốt lõi

### 2.1 ERP Integration Ledger (`erp_ledger.py`, `erp/base.py`)

* Điều phối adapter do ứng dụng cung cấp và chuyển đổi bản ghi theo hồ sơ ánh xạ.
* Truyền `config` của hồ sơ vào hàm khởi tạo adapter đã đăng ký.
* Yêu cầu có nơi nhận chuỗi khi lập lịch gửi dữ liệu; dùng `translate_erp_to_blockchain()` cho trường hợp chỉ cần chuyển đổi.
* Hỗ trợ metadata tùy chọn `detect_changes` và `key_fields`. Trường khóa chấp nhận đường dẫn có dấu chấm như `material.document_number`.

Adapter đăng ký bằng `register_adapter()` phải có phương thức `get_changes_since_last_sync()`. Phương thức `add_event()` của nơi nhận phải trả về `True` hoặc mã sự kiện không rỗng thì sự kiện mới được tính là đã chấp nhận.

### 2.2 Bộ dữ liệu mô phỏng được xuất (`enterprise.py`)

`SAPIntegration`, `OracleIntegration` và `DynamicsIntegration` trả về các bản ghi tổng hợp. Mặc định, `EnterpriseIntegration.connect_to_erp()` từ chối khởi tạo chúng. Truyền `{"simulation_mode": True}` để bật trong kiểm thử hoặc minh họa. Các lớp này không gửi yêu cầu mạng và không xác thực với hệ thống của nhà cung cấp.

### 2.3 Bộ phát hiện thay đổi (`erp/change_detector.py`)

* So sánh các trường nghiệp vụ với ảnh chụp trạng thái trong bộ nhớ, được phân vùng theo hồ sơ và khóa thực thể.
* Loại metadata `changes` và `change_detected` do chính nó tạo ra khỏi ảnh chụp kế tiếp, nhờ đó bản ghi không đổi vẫn được xem là không đổi.

## 3. Công cụ ánh xạ dữ liệu

Công cụ ánh xạ chuyển đổi trường nguồn thành trường sự kiện và tạo đối tượng lồng nhau từ đích có dấu chấm như `details.quantity`.

| Transformer | Chức năng | Ví dụ chuyển đổi |
| :--- | :--- | :--- |
| `date` | Chuẩn hóa định dạng thời gian | `12/04/2024` -> `ISO-8601` |
| `amount` | Chuẩn hóa giá trị số | `5000` -> `5000.0` |
| `status` | Ánh xạ mã trạng thái nghiệp vụ | `REQ` -> `REQUESTED` |
| `id` | Thêm tiền tố định danh | `123` -> `ERP_123` |
| `boolean` | Chuẩn hóa giá trị logic | `1/Yes/On` -> `True` |

Quy tắc ánh xạ, cấu hình adapter và trường khóa được sao chép khi tạo và đọc hồ sơ. Việc thay đổi đối tượng đầu vào phía ứng dụng không làm thay đổi hồ sơ đã đăng ký.

## 4. Đồng bộ và thử lại

`SyncScheduler` gọi adapter do ứng dụng cung cấp, chuyển đổi từng bản ghi trả về rồi gửi đến nơi nhận chuỗi. Bản ghi chỉ được tính là đã xử lý sau khi nơi nhận xác nhận. Nếu thiếu nơi nhận, thao tác thất bại trước khi truy vấn adapter. Lỗi chuyển đổi hoặc gửi của từng bản ghi khiến lượt chạy có trạng thái `failed`; `get_sync_status()` cung cấp số sự kiện được chấp nhận và danh sách lỗi.

Lượt chạy thành công dùng khoảng thời gian đã cấu hình. Lượt chạy lỗi được thử lại sau 30, 60, rồi 120 giây theo mặc định; thời gian chờ tối đa là 300 giây. Sau ba lần thử lại ngoài lần chạy đầu, tác vụ báo `retry_exhausted` và ngừng lập lịch. Trạng thái scheduler chỉ ở trong bộ nhớ và mất khi tiến trình khởi động lại. Khi thử lại một lô, cơ chế gửi có thể chuyển phát ít nhất một lần: các bản ghi được chấp nhận ở lượt một phần trước đó có thể được gửi lại. Hãy dùng mã sự kiện ổn định, con trỏ chuyển phát của adapter, khử trùng lặp tại nơi nhận hoặc đối soát thủ công; module này không bảo đảm chuyển phát đúng một lần.

Thay thế hoặc dừng hồ sơ sẽ hủy bộ hẹn giờ đang chờ và ngăn thế hệ cũ bắt đầu lượt mới. Thao tác này không thể hủy lời gọi adapter đang chạy; lời gọi đó vẫn có thể gửi bản ghi trước khi kết thúc, còn kết quả cũ sẽ bị scheduler bỏ qua.

## 5. Ví dụ sử dụng

Đăng ký adapter do ứng dụng triển khai và cung cấp nơi nhận:

```python
from hierachain.integration.erp_ledger import ERPIntegrationLedger

ledger = ERPIntegrationLedger()
ledger.register_adapter("sap", MyConfiguredSapAdapter)  # application-provided
ledger.create_mapping_profile(
    "SAP_Logistics",
    "sap",
    {
        "entity_id": "material.document_number",
        "event": "material.event_type",
        "details.quantity": "material.qty",
    },
    config={"tenant": "example"},
    detect_changes=True,
    key_fields=["material.document_number"],
)
ledger.start_scheduled_sync(
    profile_name="SAP_Logistics",
    interval_seconds=60,
    chain=sub_chain_instance,
)
```

`MyConfiguredSapAdapter` và `sub_chain_instance` do ứng dụng gọi thư viện cung cấp. Các lớp fixture của nhà cung cấp là ví dụ mô phỏng riêng.

## 6. Phạm vi lúc chạy

Integration Ledger là thành phần thư viện, chưa được nối vào vòng đời máy chủ REST. Ứng dụng phải đăng ký adapter, chọn nơi nhận chuỗi, quản lý thông tin xác thực trong adapter của mình và theo dõi trạng thái đồng bộ trả về.

## Liên quan

* [Hệ thống Phân cấp (Hierarchical)](./hierarchical.md)
* [Cấu trúc Sổ cái Cốt lõi (Core)](./core.md)
* [Xử lý lỗi và Giảm thiểu rủi ro](./error-mitigation.md)

## Định danh trong change detection

`key_fields` đã cấu hình phải là danh sách không rỗng gồm các đường dẫn field không rỗng. Giá trị định danh thiếu, null hoặc chuỗi rỗng gây `ValueError` trước khi detector thay snapshot hoặc record. Số `0` vẫn hợp lệ. Đường dẫn SAP lồng nhau như `material.document_number` phân biệt các record; định danh thiếu không được gộp vào khóa `unknown`. Đồng bộ theo lịch ghi nhận record này là lỗi dịch dữ liệu thay vì giao thành công.
