---
title: "Error Mitigation Module"
description: "Xác thực runtime, ghi nhật ký bền vững và phân loại lỗi."
icon: material/bug
---

# Error Mitigation Module (`hierachain/error_mitigation/*`)

## 1. Tổng quan

Module `error_mitigation` cung cấp các primitive runtime để xác thực trạng thái, ghi nhật ký bền vững và phân loại lỗi. View change của đồng thuận và khôi phục vận hành thuộc về các tầng runtime hoặc deployment tương ứng.

## 2. Các thành phần lõi

Các thành phần nằm trong thư mục `hierachain/error_mitigation/`.

### 2.1 Lớp xác thực (`validator.py`, `data_validator.py`)

* `validate_certificate()`: Từ chối chứng chỉ đã hết hạn.
* `DataValidator`: Kiểm tra tính nhất quán của payload sự kiện, sự tương thích với schema Arrow và các ràng buộc đầu vào.

Custom field validator trả về `(is_valid, message)`. Nếu callback ném exception hoặc trả kết quả sai hợp đồng, `DataValidator` ghi lỗi và trả `ValidationResult.is_valid=False`, kể cả khi xác thực batch. Mức validation và tính năng tự sửa không ghi đè thất bại này.

### 2.2 Nhật ký bền vững (`journal.py`)

* Triển khai `TransactionJournal` sử dụng Apache Parquet và Arrow để ghi nhật ký sự kiện lưu trữ trên đĩa.
* Áp dụng lưu trữ chỉ ghi tiếp trước khi sự kiện được commit vào trạng thái blockchain.
* Cung cấp các generator phát lại để tái tạo các sự kiện chưa commit sau các lần tắt máy đột ngột.

`read_since(cursor=None)` flush writer đang hoạt động và chỉ fsync khi trạng thái tệp chưa xác định hoặc đã thay đổi. Append thành công đã fsync trước khi `log_event()` trả về. Phương thức đọc frame bền vững và trả `(records, (inode, byte_offset))`. Lần đầu quét lịch sử, gồm cả Parquet cũ; các lần sau đọc frame Arrow mới và theo file rotation. File đang hoạt động bị mất, file cursor bị mất hoặc bị cắt ngắn, frame hỏng hoặc lỗi fsync khi cần đồng bộ khiến read-back thất bại. Mỗi lần gọi vẫn liệt kê tên archive, nên chi phí phụ thuộc số archive cùng với số record mới.

Mỗi lần ghi lưu offset bắt đầu. Nếu ghi hoặc fsync frame thất bại, journal cắt file về offset đó và fsync phần cắt trước khi cho phép lần ghi tiếp theo. Nếu thao tác cắt hoặc fsync phần cắt thất bại, writer bị vô hiệu hóa và từ chối ghi cho đến khi được đóng rồi mở lại thành instance mới; khi khởi động, journal sửa phần cuối chưa hoàn chỉnh của file đang hoạt động.

### 2.3 Mã hóa có thể khôi phục (`encryption_validator.py`)

`EncryptionValidator(config, key_resolver)` dùng AES-256-GCM. Mã hóa yêu cầu `config["key_id"]` và `key_resolver(key_id)` do caller cung cấp, trả đúng 32 byte cho khóa đã được cho phép và giữ lại. ID thiếu, khóa không khả dụng hoặc dữ liệu khóa không hợp lệ gây `SecurityError`; validator không tạo khóa mã hóa dùng xong rồi bỏ.

`encrypt_data(text)` trả `ciphertext`, `tag` và `iv` dạng bytes, cùng `algorithm`, `key_id` và `timestamp`. GCM tag xác thực ciphertext, thuật toán, ID khóa và timestamp. `decrypt_data(envelope)` tìm khóa theo ID trong envelope, nên dữ liệu cũ vẫn đọc được sau khi đổi ID khóa đang dùng để mã hóa, miễn là khóa gốc được giữ lại. Envelope thiếu trường hoặc bị sửa gây `SecurityError`.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hierachain.error_mitigation import EncryptionValidator

keys = {"data-v1": AESGCM.generate_key(bit_length=256)}
validator = EncryptionValidator(
    {"algorithm": "AES-256-GCM", "key_id": "data-v1"},
    key_resolver=keys.__getitem__,
)
envelope = validator.encrypt_data("business event")
reader = EncryptionValidator({"algorithm": "AES-256-GCM"}, key_resolver=keys.__getitem__)
assert reader.decrypt_data(envelope) == "business event"
```

Ví dụ này giữ khóa trong bộ nhớ. Caller production phải giữ khóa trong kho khóa an toàn sẵn có và khôi phục resolver khi khởi động lại; khóa không được nhúng vào envelope. Khi lưu JSON, mã hóa các trường bytes thành Base64 và đổi lại thành bytes trước khi giải mã. Thông báo xoay khóa của module không tự cấp phát hoặc giữ lại khóa. Ciphertext cũ có khóa ngẫu nhiên đã bị triển khai trước bỏ đi không thể được khôi phục bằng thay đổi này.

### 2.4 Khuyến nghị về tài nguyên và xoay khóa

`ConsensusValidator.validate_node_count()` vẫn từ chối số node dưới `3f+1`. Phương thức legacy `monitor_and_scale()` chỉ trả các node khỏe và ghi khuyến nghị bổ sung tài nguyên khi tỷ lệ này dưới `auto_scale_threshold`; nó không thay đổi thành viên hay khôi phục quorum. Runtime BFT gọi validator số node nhưng không tự gọi bộ kiểm tra sức khỏe này.

`ResourceValidator.validate_resources()` báo các vi phạm ngưỡng CPU, memory và disk. Cờ legacy `auto_scale=True` ghi thêm khuyến nghị tài nguyên CPU/memory; vi phạm disk chỉ tạo cảnh báo. Caller phải tự gọi các kiểm tra này và thực hiện cấp phát qua hạ tầng của host.

Ngưỡng mặc định là CPU 70%, memory 80% và disk 85%, cấu hình qua `cpu_threshold`, `memory_threshold` và `disk_threshold`. Kiểm tra theo thứ tự CPU, memory, disk; chỉ mức sử dụng cao hơn ngưỡng mới là vi phạm, nên bằng ngưỡng vẫn được chấp nhận.

`EncryptionValidator.validate_config()` cảnh báo khi `key_rotation_interval` dưới `min_key_rotation_interval` hiện có (2.592.000 giây). Đây là so sánh cấu hình để tham khảo, không đánh giá tuổi khóa hay áp dụng chính sách hết hạn. Nó không tạo lịch, deadline hoặc khóa thay thế. Ứng dụng host quản lý việc xoay khóa và giữ khóa cũ.

Bên đọc log cần cập nhật bộ lọc sự kiện: `auto_scaling_triggered` và wrapper `consensus_scaling` đổi thành `consensus_capacity_recommendation`; `resource_scaling_triggered` đổi thành `resource_capacity_recommendation`. Các đường dẫn Parquet legacy `log/error_mitigation/consensus_scaling.parquet` và `log/error_mitigation/resource_scaling.parquet`, field payload (gồm `auto_scale_enabled`) và record hiện có vẫn tương thích. Log gây hiểu nhầm `key_rotation_scheduled` và field `next_rotation` được bỏ; cảnh báo về interval vẫn còn.

## 3. Chiến lược phân loại lỗi

`classify_error()` trả về `ErrorInfo` gồm category, `PriorityLevel` và mitigation strategy. Priority được tính từ impact và likelihood. `PriorityLevel` có các giá trị `CRITICAL`, `HIGH`, `MEDIUM` và `LOW`.

## 4. Nhật ký sự kiện

`TransactionJournal` cung cấp khả năng lưu trữ ghi trước:

1. Ghi bền vững: Ghi tiếp record Arrow có frame và fsync xuống đĩa trước khi block hoàn tất; Parquet cũ vẫn đọc được.
2. Thực thi schema: Đảm bảo mọi bản ghi nhật ký khớp với schema sự kiện bắt buộc.
3. Khả năng phát lại: Phát lại các sự kiện đã ghi từ đĩa vào hàng đợi sắp xếp khi nút khởi động lại.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

## Tài liệu liên quan

* [Module Adapters](./adapters.md)
* [Module Core](./core.md)
* [Khóa cụm khẩn cấp](./cluster.md)

`ErrorClassifier` gọi callback lockdown được cung cấp cho lỗi security mức HIGH hoặc CRITICAL và lỗi performance mức CRITICAL. `DataValidator.validate_table()` kiểm tra kiểu Arrow bắt buộc ở mọi mức; strict kiểm tra thêm null. Kiểm tra consistency so sánh từng hàng theo thứ tự, gồm details JSON đã giải mã. Journal duyệt thư mục và mở tệp qua descriptor với cờ no-follow để từ chối symlink.

Journal fsync các entry thư mục sau khi tạo và xoay tệp. Frame mới giữ kiểu của `details` và tập field gốc trong binary envelope để registration domain và retry theo ID ổn định được khôi phục đúng. Reader mới đọc được envelope cũ và archive Parquet legacy; reader cũ không hiểu envelope mở rộng nên cần nâng cấp reader trước khi ghi định dạng mới. Metadata không được lưu trong registration lịch sử không thể tái tạo. Mỗi đường dẫn journal cần một process sở hữu; xem [quyền sở hữu journal cục bộ](../consensus/ordering.md#local-journal-ownership).
