---
title: Proof of Authority - PoA
description: Đồng thuận hiệu năng cao dành cho các tổ chức được nhận dạng (Authorized Entities).
icon: material/account-check-outline
---

# Proof of Authority - PoA (`hierachain/consensus/proof_of_authority.py`)

## Mục đích

PoA trong HieraChain Ledger là cơ chế sinh khối cho mạng chính (`Main Chain`) hoặc chuỗi phụ (`Sub-Chains`) dựa trên thẩm quyền. Không giải nén các tính toán tìm kiếm (mining) nặng nề, PoA dành cho các node có danh tính nhằm mang lại hiệu suất tạo khối tuyệt đối cao và an toàn cho doanh nghiệp (ví dụ mạng nội bộ hoặc hệ sinh thái một tập đoàn).

## Kiến trúc & khái niệm

* Lớp `ProofOfAuthority` kế thừa `BaseConsensus` (`hierachain/consensus/proof_of_authority.py`).
* Xác định Authorities thông qua định danh `authority_id` và Public Key (sở hữu mã xác minh chữ ký).
* Phân bổ tạo khối theo lịch quy ước (`Round-Robin`) giữa các node để tối ưu công bằng tính toán.
* Áp dụng Zero-Knowledge (ZK Proof) để đảm bảo thông tin nội bộ của khối thuộc Enterprise được bảo mật hoàn toàn.

## API công khai (Public API)

* `add_authority(authority_id: str, metadata: dict[str, Any] | None = None) -> bool`: Chấp thuận danh tính mới sinh khối.
* `remove_authority(authority_id: str) -> bool`: Loại bỏ Authority khỏi tập hợp đồng thuận.
* `is_authority(authority_id: str) -> bool`: Kiểm tra Node có thuộc tập hợp tạo khối hay không.
* `can_create_block(authority_id: str | None = None) -> bool`: Trả về `True` nếu thuộc Authority.
* `validate_block(block: Block, previous_block: Block) -> bool`: Tiến trình xác nhận thời gian sinh khối, sự kiện cấu trúc và chữ ký hợp lệ.
* `get_next_authority(current_block_index: int) -> str | None`: Cho ra thuật toán luân phiên Round-Robin.

Ví dụ thêm Node sinh khối mới:

```python
from hierachain.consensus import ProofOfAuthority

poa = ProofOfAuthority()
poa.add_authority("node_1", metadata={"public_key": "Bằng chứng..."})
print(poa.is_authority("node_1"))  # True
```

## Cấu hình

* Config cơ bản nội bộ của thuật toán nằm trong `self.config` với chu kỳ tối thiểu `block_interval: 10.0` giây, cấm `mining`, `coin_transfer`, v.v...
* Ràng buộc cấu hình `require_authority_signature` chỉ cho phép lưu trạng thái khi AuthNode ký khối thành công. Khả năng giám sát giới hạn lên đến `max_authorities: 100` node.

## Tính năng & hạn chế

* **Tính năng**: Tiết kiệm tài nguyên; khối được xác nhận ngay lập tức theo `block_interval`; an toàn trên môi trường định danh thực (KYC/Enterprise).
* **Hạn chế**: Không phù hợp để vận hành Permissionless (các Blockchain mở như Bitcoin, mà bất kỳ ai cũng có thể vào giải mã/bỏ phiếu).

## Bảo mật & quyền truy cập (nếu áp dụng)

* Toàn bộ khối đều được bảo vệ và xác nhận thông qua chữ ký của node tạo lập `_create_authority_signature`.
* Chữ ký băm cùng các đối tượng (Hash khối, Authority ID, Timestamp). Quá trình xác thực ngược lại bởi hàm `verify_signature` của module Security hệ thống.

## Xử lý lỗi & khắc phục

* Ký khối thất bại khi thiếu Public Key, hoặc Signature sai, hệ thống lập tức từ chối và ghi log trả về `False`.
* Nếu khối bị sinh ra nhanh hơn thời gian quy định (thấp hơn `block_interval / 2`), tiến trình validate báo lỗi chống DDos nội bộ.

## Hiệu năng

* Khả năng xử lý lượng giao dịch (TPS) vô cùng cao và ổn định vì được xử lý qua nhóm các Authority có cấu hình máy chủ mạnh.

## FAQ

* **Liệu có thể loại bỏ hay thay đổi luân phiên Authority không?** Có, bằng API `add_authority` và `remove_authority` trong lúc blockchain đang chạy. Nhưng quá trình này sẽ không ảnh hưởng luồng (vẫn chạy bình thường trên số node còn lại).

## Liên quan

* [Base Consensus](base_consensus.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**
    
    * File `hierachain/consensus/proof_of_authority.py` triển khai Round-Robin cho thuật toán Proof-of-Authority bằng phương thức `get_next_authority`.
    * Cấm các event type phục vụ tiền điện tử (`mining`, `transaction`).
    
    **DECISION**
    
    * PoA được mặc định sử dụng cho HieraChain khi khối doanh nghiệp được quản lý ở mạng đơn tổ chức (Single-Orgs) hoặc mạng tập đoàn nơi các Node được chỉ định sẵn sinh block.
    * Chấp nhận không kiểm tra chữ ký cho các máy Client nếu `metadata` bỏ trống Public Key (phù hợp cho Unit Test). Tuy nhiên, trên Production, `metadata` Public Key luôn bắt buộc.
    
    **ASSUMPTION**
    
    * Giả định rủi ro mạng (phân mảnh nội bộ) và node ác ý thấp vì đã được chỉ định bằng danh tính.
    
    **INVARIANT**
    
    * Nếu quá trình ký `consensus_finalization` thiếu vắng ID hoặc sai Public Key, kết quả xác nhận khối vĩnh viễn không vượt qua.
    * Difficulty cho PoA luôn trả về 1.0.
    
    **EDGE CASES**
    
    * Khi `authorities` rỗng (Chưa node nào cấu hình định danh), quá trình gọi API lấy người kế tiếp sẽ trả về `None` – blockchain không sinh khối đồng thuận.
