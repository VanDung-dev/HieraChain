---
title: Base Consensus
description: Giao diện chuẩn (Abstract Base Class) cho tất cả các cơ chế đồng thuận trong hệ thống HieraChain.
icon: material/puzzle-outline
---

# Base Consensus (`hierachain/core/consensus/base_consensus.py`)

## Mục đích

`BaseConsensus` cung cấp một lớp trừu tượng định nghĩa các API tiêu chuẩn mà mọi cơ chế đồng thuận (như PoA, PoF) đều phải tuân theo. Điều này đảm bảo tính nhất quán của mô hình hướng sự kiện (event-based) và hỗ trợ kiến trúc phân cấp của HieraChain (Main Chain / Sub-Chain).

## Kiến trúc & khái niệm

* Lớp `BaseConsensus` (nằm tại `hierachain/core/consensus/base_consensus.py`) định nghĩa các abstract methods cơ bản.
* Nó hoạt động như một lớp lọc, kiểm tra sự kiện để loại bỏ các thuật ngữ tiền điện tử không phù hợp với ngữ cảnh doanh nghiệp (như `mining`, `coin`, `wallet`).
* Tích hợp chuẩn giao tiếp mật mã Zero-Knowledge (ZK Proof) để xác thực tính hợp lệ của block mà không làm lộ dữ liệu nội bộ gốc.

## API công khai (Public API)

* `validate_block(block: Block, previous_block: Block) -> bool`: (Abstract) Xác thực khối theo quy tắc đồng thuận.
* `finalize_block(block: Block) -> Block`: (Abstract) Chốt khối bằng cách đính kèm chữ ký/nonce/bằng chứng phù hợp.
* `can_create_block(authority_id: str | None = None) -> bool`: (Abstract) Kiểm tra quyền tạo khối.
* `validate_event_for_consensus(event: dict[str, Any]) -> bool`: Xác minh cấu trúc sự kiện và lọc thuật ngữ cấm.
* `get_consensus_info() -> dict[str, Any]`: Trả về thông tin cấu hình và trạng thái của consensus.
* `update_config(config: dict[str, Any]) -> None`: Cập nhật linh hoạt cấu hình ngay tại runtime.

Ví dụ sử dụng (tích hợp trong custom consensus):

```python
from hierachain.core.consensus.base_consensus import BaseConsensus

class MyCustomConsensus(BaseConsensus):
    def validate_block(self, block, previous_block):
        return super().validate_event_for_consensus(block.to_event_list()[0])
```

## Cấu hình

* Config nội bộ của consensus (lưu trong `self.config`), có thể cập nhật trong thời gian chạy.
* Hỗ trợ ZK tuân theo `settings.ENABLE_ZK_PROOFS` từ `hierachain/config/settings.py`.

## Tính năng & hạn chế

* **Hỗ trợ Zero-Knowledge**: Phương thức `_verify_block_zk_proof` mặc định cho phép các triển khai đồng thuận xác minh tính đúng đắn của giao dịch bị che giấu.
* **Doanh nghiệp hóa**: Tính năng lọc từ khóa cấm loại bỏ các rủi ro việc dùng HieraChain như một phương tiện tiền điện tử rác.

## Bảo mật & quyền truy cập (nếu áp dụng)

* BaseConsensus loại trừ (`EXCLUDED_CONTENT_FIELDS`) những trường như chữ ký (`signature`), băm (`hash`), ROOT (`merkle_root`), hay ZK proof (`zk_proof`) ra khỏi vòng lọc từ, để đảm bảo tính sinh ngẫu nhiên của các chuỗi ký tự mật mã.

## Xử lý lỗi & khắc phục

* Nếu block chứa từ khóa tiền điện tử trong `details`, hệ thống lập tức báo lỗi cấu trúc (cụ thể trả về `False` khi validate).

## Hiệu năng

* Quá trình kiểm tra ZK Proof tiêu tốn lượng tính toán nhất định nếu được kích hoạt; nhưng tối ưu nhất quán và dễ mở rộng.

## FAQ

* **Tại sao cần loại trừ từ vựng?** Để nhất quán với mục tiêu Blockchain Doanh Nghiệp (Enterprise Blockchain).

## Liên quan

* [PoA Consensus](poa.md)
* [PoF Consensus](pof.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**
    
    * Mã nguồn hiện diện tại: `hierachain/core/consensus/base_consensus.py`.
    * Tự động gọi hàm `_is_event_structure_valid` để rà soát sự kiện block.
    
    **DECISION**
    
    * Mọi cơ chế đồng thuận trong HieraChain bắt buộc kế thừa `BaseConsensus`.
    * Bất kì Blockchain nào thuộc HieraChain (Main chain/Sub-chain) đều áp dụng bộ quy tắc kiểm tra từ khóa này.
    
    **ASSUMPTION**
    
    * Giả định hệ thống quản lý Block có cấu trúc Event-based (`block.to_event_list()`).
    
    **INVARIANT**
    
    * Nếu ZK Proof đang bật ở mức settings, mọi proof gửi lên phải hợp lệ với state cũ (`previous_state`) và state mới (`current_state`) của sự kiện chốt đồng thuận (`consensus_finalization`).
    
    **EDGE CASES**
    
    * Mất `zk_proof` nhưng `settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN` = `True`, hệ thống sẽ ghi log cảnh báo và trả về `False` (block không hợp lệ).
