---
title: "Cluster Module"
description: "Đồng bộ liên tầng và các kiểu dữ liệu thông điệp của cluster."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Tổng quan

Module **Cluster** chứa runtime đồng bộ liên tầng và các kiểu dữ liệu dùng cho thông điệp cluster.

---

## Kiến trúc & Các thành phần chính

Package hiện cung cấp hai khối chức năng nhỏ:

<div class="grid cards" markdown>

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Đồng bộ bằng chứng (proofs) giữa Main Chain và Sub-Chains.
    * Đảm bảo tính toàn vẹn của cây phân cấp doanh nghiệp.

*   :material-shield-lock:{ .lg .middle } __Kiểu dữ liệu thông điệp Lockdown__

    ---

    __File__: `lockdown_types.py`

    * Định nghĩa thông điệp lockdown và quarantine có thể serialize.
    * Cung cấp helper ký và xác thực HMAC.

</div>

---

## Sử dụng

`HierarchyManager` sở hữu instance `CrossLevelSyncManager` tùy chọn và dùng nó
để đồng bộ metadata proof giữa main chain và sub-chain. Các kiểu dữ liệu trong
`lockdown_types.py` chỉ là helper cho dữ liệu và chữ ký; chúng không triển khai
bộ điều phối bỏ phiếu hoặc phong tỏa toàn cluster.

---

## Liên quan

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
