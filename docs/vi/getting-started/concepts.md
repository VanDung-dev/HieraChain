---
title: "Khái niệm cơ bản"
description: "Các khái niệm cốt lõi của HieraChain: Chain, Block, Event, Proof, Main/Sub-Chain và cách chúng liên hệ."
icon: material/lightbulb
---

# Khái niệm cơ bản

Trang này tóm tắt các khái niệm nền tảng để đọc và sử dụng HieraChain hiệu quả. Khi gặp thuật ngữ mới, xem thêm trang [Thuật ngữ](../glossary.md).

## Các khái niệm chính

* Chain: Tập hợp các Block được liên kết bằng `previous_hash`. HieraChain có hai lớp chuỗi: `Main Chain` và các `Sub-Chain` theo domain.
* Block: Nhóm nhiều Event và siêu dữ liệu (header). Xem `hierachain/core/block.py`.
* Event: Hoạt động nghiệp vụ (không phải giao dịch tiền mã hóa). Được lưu dưới dạng bảng Arrow theo schema trong `hierachain/core/schemas.py`.
* Proof: Dấu vết mật mã (ví dụ Merkle root/hash) đại diện cho trạng thái Sub-Chain, được neo lên Main Chain.
* Hierarchy: Kiến trúc Main Chain giám sát nhiều Sub-Chain. Quản lý bởi `HierarchyManager`.

```mermaid
graph TD
    Main[Main Chain]
    subgraph Domains
        A[Sub-Chain A]
        B[Sub-Chain B]
        C[Sub-Chain C]
    end
    Main --> A
    Main --> B
    Main --> C
    
    note[Main Chain lưu Proof <br/> Sub-Chain lưu Event chi tiết]
    Main -.- note
```

### Cấu trúc dữ liệu

```mermaid
classDiagram
    direction LR
    class HierarchyManager {
        +MainChain main_chain
        +dict sub_chains
        +create_sub_chain()
        +start_operation()
    }
    class Blockchain {
        +list chain
        +add_block()
        +get_latest_block()
    }
    class Block {
        +int index
        +hash hash
        +hash previous_hash
        +list events
        +hash merkle_root
    }
    class Event {
        +string entity_id
        +string event
        +float timestamp
        +dict details
    }
    
    HierarchyManager "1" *-- "1" Blockchain : main_chain
    HierarchyManager "1" *-- "many" Blockchain : sub_chains
    Blockchain "1" *-- "many" Block
    Block "1" *-- "many" Event
```

## Dòng chảy cơ bản

1. Ghi Event ở Sub-Chain → gom thành Block theo điều kiện (kích thước/thời gian).
2. Sinh Proof từ Block (ví dụ: Merkle root) → gửi lên Main Chain để neo.
3. Truy vết/thống kê: API cho phép theo dõi thực thể, xem Block/Chain, và tổng hợp thông tin hệ thống.

## Tệp mã nguồn liên quan

* Core: `hierachain/core/{block.py, blockchain.py, schemas.py}`
* Phân cấp: `hierachain/hierarchical/{main_chain.py, sub_chain.py, hierarchy_manager.py}`
* API: `hierachain/api/v1/{endpoints.py, schemas.py}`
* Bảo mật: `hierachain/security/*`
* Cấu hình: `hierachain/config/settings.py`

## Liên quan

* Bắt đầu nhanh: [Bắt đầu nhanh](quickstart.md)
* Kiến trúc tổng quan: [Tổng quan](../architecture/overview.md)
* Thuật ngữ: [Thuật ngữ](../glossary.md)
