---
title: "Thêm/Tùy biến Consensus"
description: "Hướng dẫn cấu hình PoA/PoF hoặc bổ sung cơ chế đồng thuận mới; tham chiếu core/consensus/* và hierarchical/consensus/bft_consensus.py."
icon: material/cog-sync
---

# Thêm/Tùy biến Consensus

Hướng dẫn này trình bày cách cấu hình PoA hoặc PoF cho MainChain và SubChain, đồng thời chỉ cách tích hợp cơ chế đồng thuận khác qua `BaseConsensus`.

## Chỉ cấu hình (không cần viết mã)

1. Chọn PoA hoặc PoF cho MainChain. Ví dụ dưới đây dùng `HRC_CONSENSUS_TYPE`; `HRC_MAINCHAIN_CONSENSUS` cũng được hỗ trợ:

    ```dotenv
    # .env (ví dụ)
    HRC_CONSENSUS_TYPE=proof_of_authority   # hoặc proof_of_federation
    HRC_ZK_REQUIRED_MAINCHAIN=false         # nếu dùng ZK, đặt true
    ```

Trong luồng runtime hiện tại, MainChain và SubChain dùng PoA hoặc PoF. BFT có triển khai riêng trong `hierachain/consensus/bft/`; API Ledger không chọn cơ chế này và không có biến môi trường `HRC_BFT_ENABLED`. SubChain mặc định dùng PoA; truyền `consensus_type="proof_of_federation"` khi khởi tạo để dùng PoF.

2. Khởi động API server và xác minh luồng cơ bản hoạt động:

    ```bash
    python -m hierachain.api.server
    ```

3. Gửi request thử qua API Ledger:

    ```bash
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/events \
      -H 'Content-Type: application/json' \
      -d '{"entity_id":"PROD-001","event_type":"production_complete","details":{"quantity":100}}'
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
    ```

## Thêm cơ chế đồng thuận mới (viết mã)

1. Xem chuẩn giao diện và triển khai hiện có:

    * Base: `hierachain/consensus/base_consensus.py`
    * PoA: `hierachain/consensus/proof_of_authority.py`
    * PoF: `hierachain/consensus/proof_of_federation.py`
    * BFT (triển khai riêng, không được chọn bởi cấu hình MainChain/SubChain hiện tại): `hierachain/consensus/bft/`

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

    * Tích hợp cơ chế mới bằng cách sửa điểm khởi tạo hoặc factory để tham chiếu lớp mới. `HRC_CONSENSUS_TYPE` hiện chỉ chấp nhận PoA/PoF; không đặt biến này thành tên consensus mới nếu chưa bổ sung hỗ trợ cấu hình.
    * Nếu có factory, bổ sung case ánh xạ `my_consensus` → `MyConsensus`.

4. Kiểm thử với API Ledger như phần A (thêm event → finalize → submit proof). Theo dõi log để xác nhận phương thức `propose/validate/commit` mới được gọi.

## Liên quan

* Kiến trúc/Đồng thuận: [Consensus & Ordering](../architecture/consensus.md)
* Mô‑đun Hierarchical: [Hierarchical](../modules/hierarchical.md)
* Tham chiếu Config: [Config](../reference/config.md)
* API Ledger: [API Ledger](../reference/api-ledger.md)
