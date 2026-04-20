---
title: Viết Hợp đồng Miền (Domain Contracts)
description: Hướng dẫn chi tiết thiết kế phần mềm, quản lý vòng đời và xử lý sự kiện trong DomainContract.
icon: material/file-document-edit
---

# Viết Hợp đồng Miền (Domain Contracts)

## Hợp đồng Miền

HieraChain sử dụng hệ thống Hợp đồng Miền (Domain Contracts) linh hoạt, hỗ trợ xử lý logic nghiệp vụ một cách chuyên biệt cho từng loại dữ liệu hay sự kiện cụ thể. Hệ thống quản lý mã được định nghĩa trực tiếp trong `hierachain/core/domain_contract.py`.

### 1. Khởi tạo Domain Contract

Mỗi hợp đồng cung cấp một số thuộc tính cốt lõi bao gồm định danh, phiên bản, callback thực thi và siêu dữ liệu (metadata):

```python
from hierachain.core.domain_contract import DomainContract

contract = DomainContract(
    contract_id="logistics_tracker_v1",
    version="1.0.0",
    implementation=my_custom_logic_function,
    metadata={"department": "supply_chain"}
)
```

### 2. Quản lý Vòng đời (Lifecycle)

Các hợp đồng trên HieraChain không bao giờ khởi chạy trực tiếp ra ngay production mà đi qua một chu trình kiểm soát chất lượng (ContractStatus):

* `DEVELOPMENT`: Mặc định khi vừa khởi tạo. Dành cho dev/gỡ lỗi.
* `TESTING`: Giai đoạn QA, thử nghiệm với test data.
* `ACTIVE`: Hợp đồng chính thức live trên mạng, được phép kích hoạt xử lý giao dịch qua `activate()`.
* `DEPRECATED`: Đánh dấu là lỗi thời nhưng vẫn giữ để hỗ trợ khối block cũ thông qua `deprecate()`.
* `DISABLED`: Vô hiệu hóa khẩn cấp bằng `disable()`.
* `ARCHIVED`: Đã cất gọn hoàn toàn, không thể kích hoạt lại.

### 3. Nâng cấp Phiên bản (Versioning)

Thay vì ghi đè lên những hợp đồng cũ, gây sai lệch lịch sử chuỗi khối, người dùng dễ dàng nâng cấp một phiên bản hợp đồng logic mới mà hệ thống vẫn lưu trữ lại `previous_versions`. Cơ chế này cho phép các hoạt động bảo trì mạng không bao giờ bị **Downtime**.

```python
contract.upgrade_to_version(
    new_version="1.1.0",
    new_implementation=optimized_logic_function,
    metadata={"upgrade_reason": "Performance improvement"}
)
```

### 4. Đăng ký Bộ xử lý Sự kiện (Event Handlers)

Giao dịch hoặc Event khi cập bến DomainContract có thể được chẻ luồng ra và gọi nhiều hàm callback khác nhau tùy thuộc vào loại `event_type`.

```python
def quality_check_handler(event, context, storage):
    # Logic đối chiếu, thay đổi storage tuỳ ý...
    return {"status": "passed"}

# Đăng ký handler này riêng cho event "quality_inspection"
contract.register_event_handler(
    event_type="quality_inspection",
    handler=quality_check_handler
)
```

Điều này giúp tách biệt rõ ràng việc kiểm tra, đối soát và phê duyệt (approval) qua từng module riêng rẽ.
