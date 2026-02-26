---
title: "Cluster module"
description: "Cụm và đồng bộ liên tầng: cluster_manager, cross_level_sync, lockdown_protocol, state_sync_manager — bám sát hierachain/cluster/*."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Mục đích

Quản lý cụm (cluster) và cơ chế đồng bộ trạng thái giữa các tầng/phân cấp để đảm bảo tính nhất quán hệ thống trong môi trường phân tán.

## Kiến trúc & khái niệm

* Cluster Manager: `hierachain/cluster/cluster_manager.py` — điều phối node/role trong cụm.
* Cross‑Level Sync: `hierachain/cluster/cross_level_sync.py` — đồng bộ trạng thái giữa các tầng (cross‑level).
* Lockdown Protocol: `hierachain/cluster/lockdown_protocol.py` — cơ chế hạn chế/tạm dừng an toàn khi có sự cố nghiêm trọng.
* State Sync Manager: `hierachain/cluster/state_sync_manager.py` — quản lý đồng bộ trạng thái.

## API công khai (mang tính mô tả)

```python
class ClusterManager:
  add_node(node) -> bool
  remove_node(node) -> bool
  elect_leader() -> str | None

class StateSyncManager:
  sync_from(source) -> bool
  checkpoint() -> str
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
