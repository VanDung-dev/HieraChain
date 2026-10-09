---
title: "Giao diện đồng thuận cơ sở"
description: "Giao diện trừu tượng PoA/PoF, kiểm tra nội dung sự kiện và xác minh ZK tùy chọn dùng chung."
icon: material/puzzle-outline
---

# Base Consensus (`hierachain/consensus/base_consensus.py`)

## Phạm vi

`BaseConsensus` định nghĩa giao diện được PoA và PoF triển khai. `BFTConsensus` là lớp riêng, không kế thừa giao diện này. Lớp cơ sở lưu `name` và `config`; các triển khai cụ thể cung cấp việc xác thực và hoàn tất khối.

## Phương thức trừu tượng

| Phương thức | Quy tắc |
|:------------|:--------|
| `validate_block(block, previous_block)` | Trả về khối có đáp ứng quy tắc của giao thức cụ thể hay không |
| `finalize_block(block)` | Trả về khối sau bước hoàn tất riêng của giao thức |
| `can_create_block(authority_id=None)` | Trả về việc tạo khối có được phép hay không |

PoA và PoF mở rộng `finalize_block()` bằng `authority_id` tùy chọn. Hàm finalizer đã cấu hình của orderer nối đồng thuận với việc tạo khối; block manager của ordering ký và lưu header đã hoàn tất riêng.

`get_validator_count()` là helper cụ thể trả về zero trong lớp cơ sở và được PoA/PoF ghi đè. Giao diện này không có phương thức `get_consensus_info()`.

## Xác thực nội dung sự kiện

`validate_event_for_consensus()` nhận dictionary có `event` và `timestamp`. Nó kiểm tra tên sự kiện và các giá trị nội dung được chọn theo `FORBIDDEN_TERMS`: `transaction`, `mining`, `coin`, `token`, `wallet` và `fee`. Việc so khớp không phân biệt chữ hoa/thường và dùng ranh giới từ.

`EXCLUDED_CONTENT_FIELDS` bỏ qua `authority_signature`, `signature`, `hash`, `proof_hash`, `zk_proof`, `merkle_root`, `previous_state`, `current_state`, `details`, `event` và `timestamp` trong lượt kiểm tra trường chung. Tên sự kiện và details được kiểm tra riêng. Details dạng dictionary dùng cùng tập loại trừ; details dạng chuỗi được kiểm tra trực tiếp. Đây không phải xác thực lược đồ đệ quy hay kiểm tra quyền. Đầu vào Arrow Table và RecordBatch trả về `True` mà không qua các kiểm tra nội dung này.

Kiểm tra thất bại trả về `False`. Bên gọi phải sử dụng kết quả đó; chỉ gọi helper không tự từ chối hay loại bỏ sự kiện trong hàng đợi.

## Helper ZK dùng chung

Hàm cấp module `_verify_block_zk_proof()` được PoA và PoF gọi khi xác thực khối. `HRC_ENABLE_ZK_PROOFS` bật kiểm tra; xử lý bằng chứng thiếu phụ thuộc vào `HRC_ZK_REQUIRED_MAINCHAIN`. Mock phát triển kiểm tra commitment của public input; tạo/xác minh production chưa được triển khai. Kiểm tra hash và chữ ký thuộc các giao thức cụ thể và bộ xác minh khối.

## Liên quan

* [PoA](./poa.md)
* [PoF](./pof.md)
* [Dịch vụ ordering](./ordering.md)
