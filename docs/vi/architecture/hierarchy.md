---
title: "Hierarchical Architecture (Detailed)"
description: "Main Chain/Sub-Chain/HierarchyManager relationships, channels/multi-org, private data, cross-chain transactions, proof anchoring, and rebalancing."
icon: material/sitemap
---

# Hierarchical Architecture (Detailed)

## Mục đích

Phần này giải thích cách HieraChain tổ chức phân cấp. Nó bao gồm cách Sub-Chain tương tác với Main Chain qua `HierarchyManager`, cách channel và mô hình multi-org vận hành, cách xử lý private data, cách giao dịch liên chuỗi dùng 2PC, cách neo proof và cách cân bằng lại Sub-Chain.

## Thành phần và khái niệm

* Main Chain: `hierachain/hierarchical/main_chain/base.py` lưu proof từ Sub-Chain và tổng hợp báo cáo toàn vẹn.
* Sub-Chain (Domain Chain): `hierachain/hierarchical/sub_chain/base.py` xử lý event theo domain, sắp xếp và đóng block, tạo proof.
* Hierarchy Manager: `hierachain/hierarchical/hierarchy_manager/base.py` điều phối hệ thống chuỗi, quản lý vòng đời Sub-Chain, giao dịch liên chuỗi và thống kê hệ thống.
* Channel: `hierachain/hierarchical/channel/channel.py` cung cấp không gian giao tiếp riêng cho nhóm organization và giữ policy tạo channel.
* Multi-Org: `hierachain/hierarchical/multi_org.py` xử lý khởi tạo organization, mạng multi-org và quan hệ giữa channel với organization.
* Private Data: `hierachain/hierarchical/private_data.py` giữ collection dữ liệu riêng ở tầng Sub-Chain.
* Cross-Chain Transaction Manager: `hierachain/hierarchical/transaction_manager.py` điều phối giao dịch 2PC giữa các Sub-Chain.

### Luồng tiêu biểu

```mermaid
graph TD
    User[Client/User] -->|Submit Event| SubChain
    SubChain -->|1. Ordering| Orderer[Ordering Service]
    Orderer -->|2. Batch| Consensus[Consensus Layer]
    Consensus -->|3. Validate| SubChain
    SubChain -->|4. Finalize Block| SubChain
    SubChain -->|5. Submit Proof| MainChain[Main Chain]
    MainChain -->|6. Store Root Hash| Storage[World State]
```

1. Tạo Sub-Chain bằng `HierarchyManager.create_sub_chain(name, domain_type, metadata)`. Lệnh này khởi tạo DomainChain và nối vào Main Chain.
2. Ghi event và đóng block bằng `SubChain.add_event()`, đi qua ordering và consensus rồi tới `finalize_block()`.
3. Neo proof lên Main Chain bằng `SubChain.submit_proof_to_main(main_chain, ...)` hoặc `HierarchyManager.submit_proof_to_main_chain(name)`.
4. Chạy giao dịch liên chuỗi (2PC) bằng `HierarchyManager.transaction_manager.initiate_transaction(src, dst, payload)`, xử lý prepare, commit và rollback.
5. Channel và private data: tạo channel giữa các organization. Collection private được lưu ở Sub-Chain theo policy của channel.

## Cấu hình liên quan (settings.py, thực tế `HRC_*`)

* Consensus/Ordering: xem [Consensus & Ordering](consensus.md) và `HRC_CONSENSUS_TYPE`/`HRC_MAINCHAIN_CONSENSUS`, `VALIDATOR_TIMEOUT`, `HRC_BLOCK_INTERVAL`.

## Tính năng và hạn chế

* Tính năng: tách dữ liệu theo domain, neo proof tập trung trên Main Chain, hỗ trợ 2PC, channel và multi-org và private data.
* Hạn chế: vận hành channel và multi-org cần policy rõ ràng và 2PC cần đồng bộ tốt.

## Liên quan

* Tổng quan: [Tổng quan](overview.md)
* Consensus & Ordering: [Consensus & Ordering](consensus.md)
* Mô-đun Hierarchical: [Hierarchical](../modules/hierarchical.md)
* Config: [Config](../reference/config.md)
