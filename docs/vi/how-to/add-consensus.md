---
title: "Thêm/Tùy biến Consensus"
description: "Hướng dẫn cấu hình PoA/PoF hoặc bổ sung cơ chế đồng thuận mới; tham chiếu core/consensus/* và hierarchical/consensus/bft_consensus.py."
icon: material/cog-sync
---

# Thêm/Tùy biến Consensus

Trang này hướng dẫn hai con đường: (A) chỉ cấu hình để chọn PoA/PoF/BFT hiện có; (B) mở rộng bằng cách thêm cơ chế đồng thuận mới dựa trên `BaseConsensus`.

## Chỉ cấu hình (không cần viết mã)

1. Đặt biến môi trường (ví dụ dùng `.env` hoặc shell):

    ```dotenv
    # .env (ví dụ)
    HRC_CONSENSUS_TYPE=proof_of_authority   # hoặc proof_of_federation
    HRC_ZK_REQUIRED_MAINCHAIN=false         # nếu dùng ZK, đặt true
    ```

2. Bật/tắt BFT (nếu áp dụng luồng sắp xếp/Byzantine):

    ```dotenv
    # .env
    # BFT trong thiết kế phân cấp thường gắn với Ordering/BFT layer ở hierarchical/consensus
    # Bật/tắt theo nhu cầu mô phỏng
    HRC_BFT_ENABLED=true
    ```

3. Khởi động API server và xác minh luồng cơ bản hoạt động:

    ```bash
    python -m hierachain.api.server
    ```

4. Kiểm thử nhanh bằng API v1:

    ```bash
    curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/create
    curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/events \
      -H 'Content-Type: application/json' \
      -d '{"entity_id":"PROD-001","event_type":"production_complete","details":{"quantity":100}}'
    curl -s -X POST http://localhost:2661/api/v1/chains/supply_chain/submit-proof
    ```

## Thêm cơ chế đồng thuận mới (viết mã)

1. Xem chuẩn giao diện và triển khai hiện có:

    * Base: `hierachain/consensus/base_consensus.py`
    * PoA: `hierachain/consensus/proof_of_authority.py`
    * PoF: `hierachain/consensus/proof_of_federation.py`
    * BFT (phân cấp): `hierachain/consensus/bft/`

2. Tạo lớp mới kế thừa `BaseConsensus` (ví dụ):

    ```python
    # hierachain/core/consensus/my_consensus.py (ví dụ mô tả)
    class MyConsensus(BaseConsensus):
      def validate_block(self, block, previous_block):
        # xác thực chữ ký/merkle/tính nhất quán
        ...
        return True
    
      def finalize_block(self, block):
        # đóng block/áp dụng chữ ký/metadata đồng thuận
        ...
        return block
    
      def can_create_block(self, authority_id=None):
        # kiểm tra quyền tạo block
        ...
        return True
    ```

3. Wiring điểm khởi tạo (factory/điểm tích hợp):

    * Tại nơi khởi tạo chuỗi (Sub‑Chain/DomainChain) hoặc dịch vụ Ordering, tham chiếu cơ chế mới khi `HRC_CONSENSUS_TYPE=my_consensus`.
    * Nếu có factory, bổ sung case ánh xạ `my_consensus` → `MyConsensus`.

4. Kiểm thử với API v1 như phần A (thêm event → finalize → submit proof). Theo dõi log để xác nhận phương thức `propose/validate/commit` mới được gọi.

## Liên quan

* Kiến trúc/Đồng thuận: [Consensus & Ordering](../architecture/consensus.md)
* Mô‑đun Hierarchical: [Hierarchical](../modules/hierarchical.md)
* Tham chiếu Config: [Config](../reference/config.md)
* API v1: [API v1](../reference/api-v1.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các tệp liên quan: `core/consensus/{base_consensus.py, proof_of_authority.py, proof_of_federation.py}`, `hierarchical/consensus/bft_consensus.py`.
    * Cấu hình đồng thuận đọc từ `hierachain/config/settings.py` (`CONSENSUS_TYPE`, `BFT_ENABLED`, …).

    **DECISION**

    * Ưu tiên cấu hình để chọn cơ chế sẵn có trước khi mở rộng bằng mã mới.
    * Nếu thêm cơ chế mới, tuân thủ giao diện `BaseConsensus` và quy ước hashing/Merkle.

    **ASSUMPTION**

    * Mạng/đồng hồ ổn định; có log để kiểm chứng quá trình đề xuất/commit block.
    * Môi trường dev có thể thay đổi biến môi trường và restart dịch vụ nhanh chóng.

    **INVARIANT**

    * Hash/Merkle phải xác định; block hợp lệ không bị thay đổi sau commit.
    * Luồng Sub‑Chain → Main Chain luôn gửi được proof hợp lệ (hoặc phát hiện lỗi rõ ràng).

    **EDGE CASES**

    * Sai cấu hình `HRC_CONSENSUS_TYPE` → fallback hoặc lỗi rõ ràng khi khởi tạo.
    * Giao diện mới không tương thích `BaseConsensus` → lỗi runtime; cần test unit tối thiểu.
    * Ordering BFT bị trễ/out‑of‑order → cần chiến lược retry và idempotency khi submit proof.
