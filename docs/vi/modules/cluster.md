---
title: "Cluster Module"
description: "Đồng bộ chéo cấp giữa main chain và các sub-chain."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Tổng quan

Module **Cluster** chứa runtime đồng bộ chéo cấp dùng để neo proof của Sub-Chain lên MainChain.

---

## Kiến trúc và thành phần chính

<div class="grid cards" markdown>

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Đồng bộ proof giữa Main Chain và các Sub-Chain.
    * Bảo đảm tính toàn vẹn của cây phân cấp doanh nghiệp.

</div>

---

## Cách sử dụng

`HierarchyManager` sở hữu instance `CrossLevelSyncManager` tùy chọn và dùng nó
để đồng bộ metadata proof giữa main chain và các sub-chain.

Việc gửi proof cho một Sub-Chain được tuần tự hóa trên chain đó trong lúc chụp
tip hiện tại, kiểm tra anchor đã tồn tại, ghi event MainChain và xác minh
read-back bền vững. Các request đồng thời cho cùng một tip Sub-Chain vì vậy
dùng lại một proof anchor thay vì thêm bản trùng. Khóa này cục bộ trong một
object Sub-Chain, không phải khóa phân tán giữa các process.

---

## Liên quan

*   [Network](./network.md)
*   [Bảo mật (Security)](./security.md)
*   [Kiến trúc phân cấp](../architecture/hierarchy.md)

## Trạng thái đồng bộ song song

`CrossLevelSyncManager.get_status()` giữ trạng thái đang chạy khi còn bất kỳ sync hoặc xử lý conflict nào trong nhóm tác vụ chồng lấn. Khi nhóm hoàn tất, trạng thái là `failed` nếu có tác vụ thất bại, ngược lại là `complete`. Tác vụ độc lập tiếp theo mở nhóm mới. `get_stats()` có `active_operations`; `reset()` gây `RuntimeError` khi còn công việc. Lỗi callback hoàn tất được ghi log và không đảo ngược proof đã commit.
