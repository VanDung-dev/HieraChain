---
title: "Cluster module"
description: "Cụm và đồng bộ liên tầng: cluster_manager, cross_level_sync, lockdown_protocol, state_sync_manager — bám sát hierachain/cluster/*."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Mục đích

Quản lý cụm (cluster) và cơ chế đồng bộ trạng thái giữa các tầng/phân cấp để đảm bảo tính nhất quán hệ thống trong môi trường phân tán.

## Kiến trúc & khái niệm

<div class="grid cards" markdown>

* :material-server-network:{ .lg .middle } __Cluster Manager__

    ---

    __File__: `hierachain/cluster/cluster_manager.py`

    * Điều phối node/role trong cụm.
    * Quản lý vòng đời node, election leader.

* :material-connection:{ .lg .middle } __Cross‑Level Sync__

    ---

    __File__: `hierachain/cluster/cross_level_sync.py`

    * Đồng bộ trạng thái giữa các tầng (cross‑level).
    * Đảm bảo tính nhất quán liên tầng.

* :material-shield-lock:{ .lg .middle } __Lockdown Protocol__

    ---

    __File__: `hierachain/cluster/lockdown_protocol.py`

    * Cơ chế hạn chế/tạm dừng an toàn khi có sự cố nghiêm trọng.
    * Bảo vệ tính toàn vẹn hệ thống trong trạng thái khẩn cấp.

* :material-database-sync:{ .lg .middle } __State Sync Manager__

    ---

    __File__: `hierachain/cluster/state_sync_manager.py`

    * Quản lý đồng bộ trạng thái giữa các node.
    * Checkpoint và khôi phục trạng thái.

</div>

## API công khai (mang tính mô tả)

```python
class ClusterManager:
  register_node(node_id, address)
  unregister_node(node_id)
  vote_lockdown(node_id, reason) -> bool
  vote_recovery(node_id) -> bool

class StateSyncManager:
  sync_from(source) -> bool
  checkpoint() -> str

#### Cross-Level Sync

**File**: `hierachain/cluster/cross_level_sync.py`

Cơ chế đồng bộ trạng thái giữa Main Chain và Sub-Chains:

```python
from hierachain.cluster.cross_level_sync import CrossLevelSync

sync = CrossLevelSync(hierarchy_manager)

# Đồng bộ proof từ Sub-chain lên Main-chain
sync.sync_subchain_to_main("supply_chain")

# Kiểm tra tính nhất quán liên tầng
is_consistent = sync.verify_cross_level_integrity("supply_chain")
```

## Cấu hình

* Tham chiếu `hierachain/config/settings.py` (CROSS_LEVEL_SYNC_*, LOG_LEVEL, v.v.).

## Tính năng & hạn chế

* Tính năng: đồng bộ liên tầng, chế độ lockdown an toàn khi rủi ro.
* Hạn chế: đòi hỏi hạ tầng ổn định và chính sách leader rõ ràng.

## Liên quan

* Architecture/Hierarchy: [Phân cấp (chi tiết)](../architecture/hierarchy.md)
* Monitoring: [Monitoring](monitoring.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Thư mục: `hierachain/cluster/{cluster_manager.py, cross_level_sync.py, lockdown_protocol.py, state_sync_manager.py}`.

    **DECISION**

    * Khi phát hiện bất thường, kích hoạt Lockdown Protocol để bảo vệ tính toàn vẹn.

    **ASSUMPTION**

    * Có sẵn kênh truyền thông tin cậy giữa các node trong cụm.

    **INVARIANT**

    * Đồng bộ trạng thái phải idempotent, checkpoint có thể khôi phục.

    **EDGE CASES**

    * Mất leader hoặc split‑brain → cần cơ chế bầu lại/hoà giải.
