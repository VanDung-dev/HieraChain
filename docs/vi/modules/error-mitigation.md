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

* `Validator`: Xác thực cấu trúc block và sự kiện theo các quy tắc sổ cái.
* `DataValidator`: Kiểm tra tính nhất quán của payload sự kiện, sự tương thích với schema Arrow và các ràng buộc đầu vào.

### 2.2 Nhật ký bền vững (`journal.py`)

* Triển khai `TransactionJournal` sử dụng Apache Parquet và Arrow để ghi nhật ký sự kiện lưu trữ trên đĩa.
* Áp dụng lưu trữ chỉ ghi tiếp trước khi sự kiện được commit vào trạng thái blockchain.
* Cung cấp các generator phát lại để tái tạo các sự kiện chưa commit sau các lần tắt máy đột ngột.

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
