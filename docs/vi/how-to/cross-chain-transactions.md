---
title: Thao tác Liên chuỗi (Cross-Chain Operations)
description: Cách khởi tạo và phục hồi giao dịch Two-Phase Commit (2PC) bền vững.
icon: material/swap-horizontal
---

# Thao tác Liên chuỗi (2PC)

## Mục đích

`CrossChainTransactionManager` điều phối giao dịch giữa hai participant `DomainChain`. Journal thuộc coordinator lưu metadata giao dịch và quyết định commit bền vững, tách biệt với ordering event journal của từng chain.

## Trạng thái giao dịch

- **`PENDING`**: Coordinator đã tạo giao dịch.
- **`PREPARED`**: Cả hai participant đã chấp nhận yêu cầu prepare; chưa có quyết định commit.
- **`IN_DOUBT`**: Coordinator chưa thể xác nhận giao dịch đã hoàn tất. Trước quyết định COMMIT bền vững, coordinator retry abort; sau quyết định đó, coordinator retry commit.
- **`COMMITTED`**: Cả hai participant xác nhận operation event đã được fsync vào ordering journal. Block có thể vẫn đang được hoàn thiện bất đồng bộ.
- **`ROLLED_BACK`**: Cả hai participant xác nhận abort trước khi có quyết định COMMIT bền vững.
- **`FAILED`**: Giao dịch không thể bắt đầu, ví dụ chain được chỉ định không tồn tại hoặc không hỗ trợ 2PC.

## Luồng giao dịch

1. Coordinator fsync bản ghi `begin` trước khi prepare participant nào.
2. Coordinator prepare source và destination, sau đó fsync bản ghi `prepared`.
3. Coordinator fsync quyết định COMMIT trước khi gọi `commit_transaction()` ở participant nào.
4. Mỗi participant chỉ xác nhận sau khi event bắt đầu và hoàn tất có gắn mã giao dịch đã được ordering journal chấp nhận.
5. Sau khi có cả hai xác nhận, coordinator fsync `committed` và đặt trạng thái `COMMITTED`.

Nếu prepare lỗi, coordinator thử abort cả hai participant. Chỉ đặt trạng thái `ROLLED_BACK` khi cả hai trả về `True`; nếu không, giao dịch ở `IN_DOUBT` và sẽ retry abort. Sau quyết định COMMIT bền vững, coordinator không gọi rollback. Commit lỗi giữ trạng thái `IN_DOUBT` và được retry theo hướng commit.

## Khởi tạo thao tác

Dùng coordinator của `HierarchyManager` để journal bền vững và trạng thái phục hồi được chia sẻ:

```python
tx_id = hierarchy_manager.initiate_cross_chain_transaction(
    source_chain_name="sub_chain_finance",
    dest_chain_name="sub_chain_logistics",
    payload={
        "entity_id": "PKG-099238",
        "operation_type": "transfer",
        "details": {"quantity": 500},
    },
)

transaction = hierarchy_manager.transaction_manager.get_transaction(tx_id)
```

Entity phải được đăng ký trên cả hai chain và payload thao tác phải vượt qua bước xác thực của cả hai participant.

## Phục hồi giao dịch chưa hoàn tất

Coordinator retry quyết định bền vững khi khởi động lại và khi participant được đăng ký. Để retry sau lỗi trong lúc chạy:

```python
hierarchy_manager.transaction_manager.retry_pending()
```

Các chain đã lưu có tên trong bản ghi 2PC chưa hoàn tất được khôi phục thành participant `DomainChain`. Các chain đã lưu khác vẫn là `SubChain` chung. Nếu cần nâng cấp tường minh placeholder chung, gọi `create_sub_chain()` với tên và domain type hiện có; chain mới kết nối trước khi placeholder được dừng.

Sau COMMIT bền vững, bản ghi `prepared` của coordinator xác nhận cả hai participant đã xác thực payload trước quyết định. Quá trình phục hồi khôi phục dữ liệu participant từ payload và bỏ qua operation event đã có marker trong ordering journal, nên không phụ thuộc vào entity registry chỉ lưu trong bộ nhớ.
