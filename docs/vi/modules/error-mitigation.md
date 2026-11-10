---
title: "Error Mitigation Module"
description: "Ghi nhật ký giao dịch bền vững cho ledger phân cấp."
icon: material/bug
---

# Error Mitigation Module (`hierachain/error_mitigation/*`)

## 1. Tổng quan

Module `error_mitigation` cung cấp ghi nhật ký giao dịch bền vững. Khôi phục vận hành thuộc về tầng deployment.

## 2. Nhật ký giao dịch (`journal.py`)

`TransactionJournal` cung cấp khả năng lưu trữ ghi trước:

1. Ghi bền vững: Ghi tiếp record Arrow có frame và fsync xuống đĩa trước khi block hoàn tất; Parquet cũ vẫn đọc được.
2. Thực thi schema: Đảm bảo mọi bản ghi nhật ký khớp với schema sự kiện bắt buộc.
3. Khả năng phát lại: Phát lại các sự kiện đã ghi từ đĩa vào hàng đợi sắp xếp khi nút khởi động lại.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

`read_since(cursor=None)` flush writer đang hoạt động và chỉ fsync khi trạng thái tệp chưa xác định hoặc đã thay đổi. Append thành công đã fsync trước khi `log_event()` trả về. Phương thức đọc frame bền vững và trả `(records, (inode, byte_offset))`. Lần đầu quét lịch sử, gồm cả Parquet cũ; các lần sau đọc frame Arrow mới và theo file rotation. File đang hoạt động bị mất, file cursor bị mất hoặc bị cắt ngắn, frame hỏng hoặc lỗi fsync khi cần đồng bộ khiến read-back thất bại. Mỗi lần gọi vẫn liệt kê tên archive, nên chi phí phụ thuộc số archive cùng với số record mới.

Mỗi lần ghi lưu offset bắt đầu. Nếu ghi hoặc fsync frame thất bại, journal cắt file về offset đó và fsync phần cắt trước khi cho phép lần ghi tiếp theo. Nếu thao tác cắt hoặc fsync phần cắt thất bại, writer bị vô hiệu hóa và từ chối ghi cho đến khi được mở lại qua `_open_journal()` hoặc journal được clear. Mở lại cùng instance sẽ reset cờ poison; khi khởi động, journal cũng sửa phần cuối chưa hoàn chỉnh của file đang hoạt động. Replay liệt kê archive legacy trước các file xoay vòng có timestamp và sắp xếp các file xoay vòng theo timestamp tăng dần.

Journal fsync các entry thư mục sau khi tạo và xoay tệp. Frame mới giữ kiểu của `details` và tập field gốc trong binary envelope để registration domain và retry theo ID ổn định được khôi phục đúng. Reader mới đọc được envelope cũ và archive Parquet legacy; reader cũ không hiểu envelope mở rộng nên cần nâng cấp reader trước khi ghi định dạng mới. Metadata không được lưu trong registration lịch sử không thể tái tạo. Mỗi đường dẫn journal cần một process sở hữu; xem [quyền sở hữu journal cục bộ](../consensus/ordering.md#local-journal-ownership).

Journal duyệt thư mục và mở tệp qua descriptor với cờ no-follow để từ chối symlink.

## Tài liệu liên quan

* [Module Adapters](./adapters.md)
* [Module Core](./core.md)
* [Ordering](../consensus/ordering.md)
