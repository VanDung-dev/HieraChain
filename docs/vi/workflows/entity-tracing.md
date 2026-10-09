---
title: "Truy vết entity"
description: "Truy vấn lịch sử entity đã finalize trên các Sub-Chain đã đăng ký, tổng hợp dòng thời gian và hiểu chi phí truy vấn."
icon: material/map-marker-path
---

# Truy vết entity

## Đường truy vấn

`HierarchyManager.trace_entity_across_chains(entity_id)` chuyển tới `_trace_entity_history()` trong `hierachain/hierarchical/hierarchy_manager/organization.py`. Hàm duyệt Sub-Chain đã đăng ký tuần tự và trả dictionary gồm chain có lịch sử không rỗng. Nó không tự gộp hoặc sắp xếp timeline toàn cục.

`SubChain.get_entity_history()` lấy event hoàn tất và sắp xếp kết quả của chain đó theo timestamp. `Blockchain` gốc giữ entry index entity chứa vị trí block/row và payload event đã cache. Index tránh quét toàn bộ block, nhưng copy m event khớp tốn O(m), sắp xếp trong chain tốn O(m log m). Truy vấn liên chain còn phải duyệt từng chain đã đăng ký. Index được dựng lại khi phục hồi.

## Ví dụ

Sau [Bắt đầu nhanh](../getting-started/quickstart.md), ứng dụng có thể gộp kết quả:

```python
# manager is the configured HierarchyManager from the quickstart.
history_by_chain = manager.trace_entity_across_chains("PROD-001")
timeline = sorted(
    (
        {"chain": name, **event}
        for name, events in history_by_chain.items()
        for event in events
    ),
    key=lambda event: event.get("timestamp", 0),
)
```

## Lỗi và giao diện HTTP

Entity không tồn tại trả dictionary rỗng. Manager bỏ qua chain thiếu API lịch sử (`AttributeError`); không bắt mọi lỗi storage/truy vấn để bảo đảm trả thành công một phần.

`EntityTracer` trong `hierachain/domains/utils/entity_tracer.py` cung cấp truy vết và gộp timeline chi tiết hơn. REST dùng `GET /api/ledger/entities/{entity_id}/trace`, có thể thêm `chain_name` và `resolve_cid`. Event Sub-Chain đang chờ không thuộc lịch sử hoàn tất. Xem [API Ledger](../reference/api-ledger.md).

## Liên quan

* [Xác minh toàn vẹn](integrity-validation.md)
* [Tích hợp ERP](erp-integration.md)
