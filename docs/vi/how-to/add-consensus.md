---
title: "Thêm/Tùy biến Consensus"
description: "Hướng dẫn cấu hình PoA/PoF hoặc bổ sung cơ chế đồng thuận mới; tham chiếu hierachain/consensus/base_consensus.py và hierachain/consensus/bft/."
icon: material/cog-sync
---

# Thêm/Tùy biến Consensus

Hướng dẫn này trình bày cách cấu hình PoA hoặc PoF cho MainChain và SubChain, đồng thời chỉ cách tích hợp cơ chế đồng thuận khác qua `BaseConsensus`.

## Cấu hình PoA hoặc PoF

1. Chọn PoA hoặc PoF cho MainChain. Ví dụ dưới đây dùng `HRC_CONSENSUS_TYPE`; `HRC_MAINCHAIN_CONSENSUS` cũng được hỗ trợ:

    ```dotenv
    # .env (example)
    HRC_CONSENSUS_TYPE=proof_of_authority   # or proof_of_federation
    HRC_ZK_REQUIRED_MAINCHAIN=false         # if using ZK, set true
    ```

Trong luồng runtime hiện tại, MainChain và SubChain dùng PoA hoặc PoF. BFT có triển khai riêng trong `hierachain/consensus/bft/`; API Ledger không chọn cơ chế này và không có biến môi trường `HRC_BFT_ENABLED`. SubChain mặc định dùng PoA; truyền `config={"consensus_type": "proof_of_federation"}` khi khởi tạo để dùng PoF.

2. Khởi động API server và xác minh luồng cơ bản hoạt động:

    ```bash
    python -m hierachain
    ```

3. Cấp danh tính ký, khóa tin cậy và API key cần thiết theo [Khởi động nhanh](../getting-started/quickstart.md). Ví dụ dưới đây giả định đã tắt xác thực trong dev/test. Gửi sự kiện, rồi đọc khối để xác nhận đã ghi trước khi gửi bằng chứng:

    ```bash
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/events \
      -H 'Content-Type: application/json' \
      -d '{"entity_id":"PROD-001","event_type":"production_complete","details":{"quantity":100}}'
    curl -s http://localhost:2661/api/ledger/chains/supply_chain/blocks
    ```

Sau khi sự kiện xuất hiện trong khối đã lưu, gửi bằng chứng:

```bash
curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
```

## Thêm triển khai đồng thuận

1. Xem chuẩn giao diện và triển khai hiện có:

    * Base: `hierachain/consensus/base_consensus.py`
    * PoA: `hierachain/consensus/proof_of_authority.py`
    * PoF: `hierachain/consensus/proof_of_federation.py`
    * BFT (triển khai riêng, không được chọn bởi cấu hình MainChain/SubChain hiện tại): `hierachain/consensus/bft/`

2. Tạo lớp mới kế thừa `BaseConsensus` (ví dụ):

    ```python
    from hierachain.consensus.base_consensus import BaseConsensus
    from hierachain.core.block import Block

    class MyConsensus(BaseConsensus):
        def validate_block(self, block: Block, previous_block: Block) -> bool:
            raise NotImplementedError("Implement trusted validation")

        def finalize_block(self, block: Block, authority_id: str | None = None) -> Block:
            raise NotImplementedError("Implement signed finalization")

        def can_create_block(self, authority_id: str | None = None) -> bool:
            raise NotImplementedError("Implement proposer authorization")
    ```

3. Wiring điểm khởi tạo (factory/điểm tích hợp):

    * Sửa điểm khởi tạo chuỗi hoặc điểm tích hợp để tạo lớp mới. `HRC_CONSENSUS_TYPE` hiện hỗ trợ PoA/PoF; tên mới cũng cần được bổ sung vào kiểm tra cấu hình và bộ chọn.
    * Nếu có factory, bổ sung case ánh xạ `my_consensus` → `MyConsensus`.

4. Kiểm thử các phương thức đã triển khai `can_create_block()`, `finalize_block()` và `validate_block()`, bao gồm chữ ký sai và bên đề xuất không có quyền. Sau đó kiểm tra tích hợp API: gửi sự kiện, chờ khối Sub-Chain được lưu, rồi gửi bằng chứng. Giao diện cơ sở không có phương thức `propose` hay `commit`.

Các phương thức trừu tượng trong ví dụ trên cố ý chưa được triển khai và không thể hoàn tất khối hợp lệ. Chỉ định nghĩa lớp không cài nó vào MainChain, SubChain hay API.

## Liên quan

* Kiến trúc/Đồng thuận: [Consensus & Ordering](../architecture/consensus.md)
* Mô‑đun Hierarchical: [Hierarchical](../modules/hierarchical.md)
* Tham chiếu Config: [Config](../reference/config.md)
* API Ledger: [API Ledger](../reference/api-ledger.md)
