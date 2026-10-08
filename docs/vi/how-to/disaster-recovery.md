---
title: "Độ bền dữ liệu và phục hồi sau sự cố"
description: "Cách HieraChain bảo vệ sự kiện đang chờ và tiếp tục đồng thuận sau gián đoạn."
icon: material/backup-restore
---

# Độ bền dữ liệu và phục hồi sau sự cố

Repository cung cấp journaling sự kiện và view change của đồng thuận. Backup
database, snapshot filesystem, khôi phục khóa và mở rộng hạ tầng thuộc về
deployment.

## 1. Ghi nhật ký sự kiện

`TransactionJournal` ghi các sự kiện đang chờ trước khi chúng đi vào ordering
service. Cơ chế này bảo vệ sự kiện khi ứng dụng crash hoặc hệ điều hành tắt đột
ngột.

Mỗi event được ghi nối tiếp và fsync đồng bộ trước khi đưa vào hàng đợi. Fsync
luôn được bật và không thể tắt qua cấu hình. Khi khởi động, recovery replay các
entry journal và ghi event đã khôi phục vào block storage trước khi Ordering
Service hoạt động. Frame cuối chưa hoàn chỉnh trong journal đang hoạt động sẽ
bị cắt bỏ trước khi ghi entry mới. Frame hoàn chỉnh nhưng chứa Arrow data lỗi
khiến recovery thất bại; lỗi replay, chứng thực hoặc xử lý block giữ Ordering
Service ở `MAINTENANCE` cho đến khi recovery thành công.

Trong lúc khởi động, kiểm tra `GET /api/ledger/ready`. Endpoint trả HTTP 200 khi
Ordering Service của mọi Sub-Chain đã đăng ký ở trạng thái `ACTIVE`, và HTTP
503 khi còn service đang recovery hoặc ở trạng thái maintenance.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

## 2. Hành vi của đồng thuận sau restart

`BFTConsensus` sử dụng `BFTViewChangeManager` khi leader hiện tại hỏng hoặc
timeout view change hết hạn. Manager điều phối quorum và cài đặt view mới để
đồng thuận tiếp tục mà không cần recovery engine riêng.

## 3. Trách nhiệm phục hồi của deployment

Deployment phải cung cấp và xác minh:

- backup database và filesystem;
- quy trình backup và khôi phục khóa;
- chính sách snapshot retention và rollback;
- thay thế node và mở rộng hạ tầng.

Các thao tác này cố ý không được expose thành các class tự động trong
`hierachain.error_mitigation`.

## Tài liệu liên quan

- [Xử lý lỗi và phục hồi](../workflows/error-recovery.md)
- [Module Error Mitigation](../modules/error-mitigation.md)
- [Nạp lại trạng thái chuỗi](../workflows/chain-rehydration.md)
