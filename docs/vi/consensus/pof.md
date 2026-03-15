---
title: Proof of Federation (PoF)
description: Giao thức xoay vòng lãnh đạo dành riêng cho mạng liên minh (Consortium).
icon: material/account-group-outline
---

# Proof of Federation - PoF (`hierachain/consensus/proof_of_federation.py`)

## Mục đích

PoF trong hệ thống HieraChain (nằm tại `hierachain/consensus/proof_of_federation.py`) là biến thể nâng cấp trên mô hình Authority, tập trung vào mô hình đa đối tác (Bệnh viện, Trường học, Ngân hàng) tham gia chia sẻ sổ cái mà không có tổ chức lãnh đạo đơn bộ nào (phi tập trung một phần).

## Kiến trúc & khái niệm

* Lớp `ProofOfFederation` chịu trách nhiệm quay vòng tính minh bạch thông qua công thức Toán Học Lịch Trình (Deterministic Schedule): `Leader = Validator[BlockIndex % ValidatorCount]`.
* Giám sát luân phiên, thay thế liên kết tĩnh của PoA, khắc phục điểm lõi đơn lẻ `Single point of Failure`.

## API công khai (Public API)

* `add_validator(validator_id: str, metadata: dict[str, Any] | None = None) -> bool`: Hàm định danh và thêm node mới vào Liên Minh (giữ danh sách được Sắp Xếp / Sort).
* `remove_validator(validator_id: str) -> bool`: Xóa Node tổ chức tham gia Liên minh.
* `get_current_leader(block_index: int) -> str | None`: Công thức Toán chỉ định Người Lãnh Đạo tiếp theo của BlockIndex truyền vào.
* `validate_block_proposer(block_index: int, proposer_id: str) -> bool`: Xác nhận cẩn thận Leader hiện tại (Proposer ID) có đúng với thiết kế lịch trình toán (BlockIndex) hay không.
* `verify_quorum_signatures(message: bytes, signatures: list[dict[str, str]], required_count: int | None = None) -> bool`: Cơ chế xác nhận theo Quorum (Số lượng biểu quyết lớn hơn). Bác bỏ giả mạo.

Ví dụ xác nhận Leader:

```python
from hierachain.consensus import ProofOfFederation

pof = ProofOfFederation()
pof.add_validator("Hospital_A")
pof.add_validator("Hospital_B")
print(pof.get_current_leader(0))  # Hospital_A
print(pof.get_current_leader(1))  # Hospital_B
```

## Cấu hình

* Vòng lặp thiết lập khối của PoF (thuộc tính nội bộ `config`) được tinh chỉnh: tạo nhanh chóng `block_interval: 5.0` (giây).
* Điều kiện Liên minh tối thiểu (`min_validators: 3`) phải duy trì.
* Cho phép xoay vòng `enforce_rotation: True` luôn được bật.

## Tính năng & hạn chế

* **Hoạt động Quorum**: Tính pháp lý được công nhận qua quy tắc xác nhận `(TotalValidators * 2) // 3 + 1` Node có chữ ký số (Mở rộng cho môi trường không tin cậy toàn bộ BFT-style).
* **Hạn chế**: Số lượng liên minh cần giới hạn (thường < 50-100 Validator) để giữ tính phản chiếu (Sync) vì mọi biểu quyết Quorum làm chậm thời gian finality của hệ thống hơn là PoA đơn điệu.

## Bảo mật & quyền truy cập (nếu áp dụng)

* Mật mã chữ ký Quỹ Đạo xác nhận qua hàm xử lý băm SHA-256 đối với tham số: (Mã băm khối, Validator ID, Vị trí khối, và Thời gian thực).
* Được kết hợp với Zero-knowledge Proof (tương đồng logic PoA) để ẩn dữ liệu Liên Minh cho các Node.

## Xử lý lỗi & khắc phục

* Nếu số lượng Liên minh (Validator) rớt thấp hơn ngưỡng `min_validators`, hệ thống từ chối mọi quyền sinh khối (`can_create_block = False`), dừng tạm thời chờ cấu hình từ mạng để phục hồi.
* Nếu Block được tạo trễ/chậm nhịp (Chấp nhận trễ 80% thời gian tạo khối lý thuyết - Lỗi trễ thời gian hệ thống), hệ thống vẫn duy trì xác thực.

## Hiệu năng

* Với chỉ số interval = 5.0 (so với 10 của PoA), cơ chế xoay vòng PoF đem lại sự mượt mà và khả năng chia sẻ tác vụ ra đồng đều cho Liên Minh nhanh gấp đôi trên mỗi nút rẽ nhánh.

## FAQ

* **Chuyện gì xảy ra khi Leader bị ngắt mạng (Drop)?** Sẽ dẫn đến quá trình Timeout / View-Change do layer mạng xử lý, rồi tiếp tục bỏ qua vòng hiện tại và bầu Node kế tiếp. Hệ thống luân phiên (Modulo Rotation) không có Leader nào giữ vai trò vĩnh viễn.

## Liên quan

* [PoA Consensus](poa.md)
* [BFT Consensus](bft_consensus.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Tồn tại logic bắt Quorum số lượng trong `_get_required_quorum_count`.
    * ID Array `validators` được hệ thống bảo đảm luôn trong trạng thái sắp xếp `sort()` ngay khi nạp.
    
    **DECISION**

    * Quyết định chuẩn xác minh Quorum của Federation Blockchain tuân thủ mô hình 2/3 (Byzantine-style Quorum Requirement) để tạo nền tảng an toàn đa tác nhân.
    
    **ASSUMPTION**
    
    * Giả định rằng mạng chỉ chứa đựng lượng nhỏ các Node không trực tiếp phản hồi ác ý, mà có thể bị trì trệ thời gian hoặc đứt gãy kết nối mạng nội bộ; nên không cần dùng đến 1 thuật toán Consensus hoàn toàn phi tập trung (PoW).
    
    **INVARIANT**
    
    * Nếu người sinh (signer) cố ý chốt block khi chưa đến lượt mình (sai BlockIndex trong Modulo ValidatorCount), Block sẽ bị vứt bỏ hoàn toàn trong bước `validate_block`.
    
    **EDGE CASES**
    
    * Nếu mảng chữ ký (`signatures`) thu thập từ mạng vượt yêu cầu số lượng, `verify_quorum_signatures` sớm ngắt lệnh kiểm tra ngay khi đủ Quorum để tối ưu thời gian. Dư thừa chữ ký được xử lý ổn thoả.
