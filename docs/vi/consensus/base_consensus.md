---
title: "Base Consensus Interface"
description: "Giao diện chuẩn (Abstract Base Class) định nghĩa quy tắc đồng thuận và kiểm soát nội dung doanh nghiệp."
icon: material/puzzle-outline
---

# Base Consensus (`hierachain/consensus/base_consensus.py`)

## Tổng quan

`BaseConsensus` là lớp cơ sở trừu tượng (Abstract Base Class) định nghĩa bộ khung tiêu chuẩn cho mọi thuật toán đồng thuận trong hệ thống HieraChain. Nó đảm bảo tính nhất quán giữa các giao thức khác nhau (PoA, PoF, BFT) và thực thi các quy tắc nghiệp vụ cốt lõi của một nền tảng blockchain doanh nghiệp.

---

## Các nhiệm vụ cốt lõi

<div class="grid cards" markdown>

*   :material-gavel:{ .lg .middle } __Định nghĩa Giao thức__

    ---

    Thiết lập các phương thức bắt buộc như `validate_block`, `finalize_block` và `can_create_block` để các module tầng trên (như Ordering Service) có thể tương tác đồng nhất.

*   :material-filter-check:{ .lg .middle } __Kiểm soát Nội dung (Enterprise Filtering)__

    ---

    Tự động quét và loại bỏ các sự kiện chứa thuật ngữ tiền điện tử cấm (`mining`, `coin`, `token`, `wallet`). Đây là lớp bảo vệ quan trọng để duy trì mục đích sử dụng doanh nghiệp của HieraChain.

*   :material-shield-link-variant:{ .lg .middle } __Xác thực Toàn vẹn__

    ---

    Tích hợp các cơ chế xác thực mã băm (Hash), chữ ký số và hỗ trợ Zero-Knowledge (ZK) Proof để đảm bảo dữ liệu khối không bị thay đổi.

</div>

---

## API trừu tượng (Abstract Methods)

Mọi thuật toán đồng thuận kế thừa từ `BaseConsensus` phải triển khai các phương thức sau:

| Phương thức | Ý nghĩa |
| :--- | :--- |
| `validate_block(block, prev_block)` | Xác thực tính hợp lệ của khối mới so với khối trước đó. |
| `finalize_block(block)` | Thực hiện các bước cuối cùng (ký số, gán nonce) trước khi lưu khối. |
| `can_create_block(node_id)` | Kiểm tra xem nút hiện tại có quyền tạo khối hay không. |
| `get_consensus_info()` | Trả về thông tin trạng thái và cấu hình hiện tại của giao thức. |

---

## Quy tắc Lọc sự kiện (Event Validation)

Hệ thống thực thi việc lọc từ khóa cấm một cách nghiêm ngặt:
*   **Dữ liệu bị kiểm tra**: Tất cả các trường trong `details` và nội dung sự kiện.
*   **Trường loại trừ**: Các trường mật mã như `signature`, `hash`, `merkle_root` và `zk_proof` được bỏ qua để tránh nhận diện nhầm các chuỗi ký tự ngẫu nhiên.
*   **Hành động**: Nếu phát hiện từ khóa vi phạm, phương thức `validate_event_for_consensus` sẽ trả về `False`, dẫn đến việc khối bị từ chối.

---

## Tích hợp Zero-Knowledge (ZK)

`BaseConsensus` cung cấp các hàm hỗ trợ xác thực bằng chứng ZK (`_verify_block_zk_proof`). Khi `settings.ENABLE_ZK_PROOFS` được bật, mọi khối đồng thuận phải mang theo bằng chứng hợp lệ để chứng minh tính đúng đắn của các thay đổi trạng thái mà không cần tiết lộ dữ liệu thô.

---

## Liên quan

*   [Đồng thuận PoA](./poa.md)
*   [Đồng thuận PoF](./pof.md)
*   [Dịch vụ sắp xếp (Ordering)](./ordering.md)
