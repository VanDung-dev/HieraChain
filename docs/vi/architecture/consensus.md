---
title: "Consensus & Ordering"
description: "Tổng quan PoA/PoF/BFT và Ordering Service trong HieraChain; cấu hình, luồng và bất biến."
icon: material/sync
---

# Consensus & Ordering (Đồng thuận & Sắp xếp)

## Mục đích

Mô tả các cơ chế Consensus và Ordering Service được HieraChain sử dụng để đảm bảo tính toàn vẹn, thứ tự và khả năng xác minh của Block/Event.

## Kiến trúc & khái niệm

* Base Consensus: `hierachain/consensus/base_consensus.py` — Giao diện/khung cơ bản cho các thuật toán đồng thuận.
* Proof of Authority (PoA): `hierachain/consensus/proof_of_authority.py` — Môi trường tập trung/validator tĩnh; tốc độ cao, cấu hình đơn giản.
* Proof of Federation (PoF): `hierachain/consensus/proof_of_federation.py` — Liên minh tổ chức động; phù hợp consortium.
* BFT Consensus: `hierachain/consensus/bft/` — Chống lỗi Byzantine ở lớp phân cấp.
* Ordering Service: `hierachain/consensus/ordering/` — Sắp xếp Event trước khi đóng Block; kiến trúc đa thành phần (Processor, Certifier, BlockBuilder).

### Luồng điển hình

```mermaid
sequenceDiagram
    participant SC as Sub-Chain
    participant OS as Ordering Service
    participant C as Consensus (PoA/PoF)
    participant MC as Main Chain

    SC->>OS: 1. Submit Event
    OS->>OS: Queue & Batch
    OS->>C: 2. Propose Batch
    C->>C: Validate & Sign
    C-->>SC: 3. Approved Block
    SC->>SC: Finalize & Store
    SC->>MC: 4. Submit Proof (Root Hash)
    MC-->>SC: Acknowledge
```

1. Sub‑Chain nhận Event → đẩy vào hàng đợi của Ordering Service.
2. Ordering Service tạo batch theo chính sách (kích thước/ngưỡng thời gian) → gửi cho cơ chế Consensus đã chọn.
3. Cơ chế Consensus (PoA/PoF hoặc BFT) xác nhận batch/Block → Sub‑Chain đóng Block.
4. Nếu bật neo lên Main Chain: Sub‑Chain gửi Proof (Merkle root/hash) để Main Chain ghi nhận.

## Cấu hình

Các biến trong `hierachain/config/settings.py`:

* `CONSENSUS_TYPE`: `proof_of_authority` (mặc định) hoặc `proof_of_federation`.
* `BFT_ENABLED`: Bật/tắt lớp BFT cho kịch bản cần chống Byzantine.
* `VALIDATOR_TIMEOUT`: Thời gian timeout giữa các validator.
* `CONSENSUS_FEDERATION_CONFIG`: tham số liên minh (ví dụ `min_validators`, `block_interval`).

Ví dụ môi trường:

```dotenv
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_ZK_REQUIRED_MAINCHAIN=false
```

## Tính năng & hạn chế

* PoA: triển khai đơn giản, độ trễ thấp; phụ thuộc niềm tin vào validator tập trung.
* PoF: cân bằng giữa tin cậy và phân tán; cần quản trị thành viên liên minh.
* BFT: chịu lỗi Byzantine tốt; đổi lại phức tạp/chi phí thông điệp cao hơn.
* Ordering: đảm bảo thứ tự/nhóm sự kiện ổn định trước khi đóng block.

## Liên quan

* Kiến trúc tổng quan: [Tổng quan](overview.md)
* Hierarchical module: [Hierarchical](../modules/hierarchical.md)
* Data Models: [Data Models](../reference/data-models.md)
* Config: [Config](../reference/config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Tệp PoA: `hierachain/consensus/proof_of_authority.py`; PoF: `hierachain/consensus/proof_of_federation.py`; Base: `hierachain/consensus/base_consensus.py`.
    * BFT: `hierachain/hierarchical/consensus/bft_consensus.py`.
    * Ordering Service: `hierachain/consensus/ordering_service.py`.
    * Cấu hình đồng thuận đọc từ `hierachain/config/settings.py` (ví dụ `CONSENSUS_TYPE`, `VALIDATOR_TIMEOUT`, `BFT_ENABLED`).

    **DECISION**

    * Ưu tiên dùng PoA cho môi trường dev và PoF/BFT cho môi trường consortium/production.
    * Mọi Sub‑Chain phải qua Ordering trước khi đóng block để đảm bảo tính xác định thứ tự.

    **ASSUMPTION**

    * Đồng hồ hệ thống các node đủ đồng bộ để timestamp không gây sai lệch kiểm toán.
    * Mạng ổn định hoặc có cơ chế retry/idempotency ở tầng giao tiếp.

    **INVARIANT**

    * Block hợp lệ phải có thứ tự sự kiện xác định và hash/Merkle nhất quán.
    * Khi `BFT_ENABLED=true`, commit phải tuân thủ điều kiện an toàn của thuật toán BFT tương ứng.

    **EDGE CASES**

    * Mất đồng thuận/timeout kéo dài → cần cơ chế view‑change/leader‑election (nếu có) hoặc chuyển chế độ an toàn.
    * Sự kiện đến trễ/out‑of‑order → Ordering phải xếp đúng thứ tự trước khi đóng Block.
    * Thay đổi cấu hình `CONSENSUS_TYPE` khi hệ thống đang chạy → cần quy trình nâng cấp/di trú an toàn.
