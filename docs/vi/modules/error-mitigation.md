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

## 3. Chiến lược phân loại lỗi

`ErrorClassifier` trong `error_classifier.py` phân loại lỗi theo mức độ nghiêm trọng và đề xuất hành động xử lý:

| Mức độ nghiêm trọng | Ý nghĩa | Hành động xử lý |
| :--- | :--- | :--- |
| INFO / WARNING | Bất thường vận hành nhỏ | Ghi log và tiếp tục |
| ERROR | Lỗi xác thực sự kiện hoặc lỗi xử lý tạm thời | Thử lại kèm giãn cách hoặc từ chối |
| CRITICAL | Hỏng trạng thái hoặc không khớp Merkle root | Từ chối, ghi log và yêu cầu khôi phục vận hành |
| FATAL | Lỗi phần cứng hoặc lỗi đồng thuận không thể phục hồi | Khóa hệ thống khẩn cấp |

## 4. Nhật ký sự kiện

`TransactionJournal` cung cấp khả năng lưu trữ ghi trước:

1. Ghi bền vững: Ghi các bản ghi vào tệp Parquet trên đĩa trước khi các block hoàn tất.
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
