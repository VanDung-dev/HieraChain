---
title: "Proof of Authority (PoA)"
description: "Giao thức đồng thuận dựa trên Authority, với định danh nút, chữ ký block và luân phiên Round-Robin."
icon: material/account-check-outline
---

# Proof of Authority (`hierachain/consensus/proof_of_authority.py`)

## Tổng quan

**Proof of Authority (PoA)** là giao thức đồng thuận dựa trên định danh dành cho **mạng nội bộ doanh nghiệp hoặc tổ chức**, trong đó một MainChain quản lý các Sub-Chain nội bộ. Trong kiến trúc đồng thuận hai tầng của HieraChain, `SubChain` mặc định dùng PoA cho event nội bộ mà không cần đồng thuận giữa các tổ chức.

Đối với kịch bản liên kết đồng thuận giữa các MainChain của nhiều doanh nghiệp độc lập, xem [Proof of Federation (PoF)](./pof.md).

---

## Nguyên lý hoạt động

Giao thức hoạt động dựa trên sự tin tưởng vào danh tính của các nút tham gia:
1.  **Định danh nút**: Mỗi Authority được gán một `authority_id` và một cặp khóa ký số duy nhất.
2.  **Lịch trình luân phiên (Round-Robin)**: Hệ thống sử dụng thuật toán tuần tự để xác định nút nào có quyền tạo khối tiếp theo dựa trên chỉ số khối (`BlockIndex % TotalAuthorities`).
3.  **Xác thực chữ ký**: Mỗi khối mới phải được ký bởi Authority được chỉ định. Các nút khác sẽ xác thực chữ ký này trước khi chấp nhận khối vào sổ cái.

---

## Các tính năng chính

<div class="grid cards" markdown>

*   :material-lightning-bolt:{ .lg .middle } __Kiểm tra thời gian block__

    ---

    Mặc định, PoA không thêm thời gian chờ tối thiểu giữa các block. Timestamp của các block liên tiếp vẫn không được giảm. Khi `block_interval` dương, timestamp phải cách nhau ít nhất bằng một nửa giá trị đó.

*   :material-account-multiple-check:{ .lg .middle } __Quản trị Danh tính__

    ---

    Lớp `ProofOfAuthority` cung cấp các method `add_authority()` và `remove_authority()`.

*   :material-shield-sync:{ .lg .middle } __Chữ ký block__

    ---

    Authority được chỉ định ký từng block. Các nút khác xác minh chữ ký trước khi chấp nhận block.

</div>

---

## Tham số cấu hình quan trọng

| Tham số | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `block_interval` | Cấu hình khoảng cách tùy chọn; `0` không thêm thời gian chờ, còn giá trị dương giữ ngưỡng validator bằng một nửa giá trị này. | `0.0` giây |
| `max_authorities` | Số lượng nút Authority tối đa trong mạng. | `100` |
| `require_authority_signature` | Bắt buộc phải có chữ ký hợp lệ để chấp nhận khối. | `True` |

MainChain và SubChain dùng PoA đọc giá trị này từ `HRC_BLOCK_INTERVAL`, mặc định là `0.0`. Khởi tạo trực tiếp `ProofOfAuthority()` cũng mặc định là `0.0`. Giá trị âm hoặc không hữu hạn bị từ chối khi khởi tạo PoA.

Orderer của SubChain vẫn gom event theo `block_size` và `batch_timeout` (mặc định: 50 event và 1.0 giây). Bỏ thời gian chờ PoA không loại bỏ thời gian gom batch, xác thực chữ ký, đồng bộ journal hay công việc lưu trữ. PoF giữ cấu hình thời gian riêng.

Với triển khai hiện có, cấu hình tường minh `HRC_BLOCK_INTERVAL=10` giữ khoảng cách tối thiểu 5 giây như trước. Dùng `HRC_BLOCK_INTERVAL=0` để bỏ khoảng cách này và cấu hình nhất quán giữa bên tạo block và validator: validator giữ khoảng cách cũ sẽ từ chối các block nhanh hơn. Các block đã đáp ứng khoảng cách cũ vẫn hợp lệ với mặc định mới.

---

## Ví dụ triển khai

```python
from hierachain.consensus import ProofOfAuthority

# Khởi tạo giao thức PoA
poa = ProofOfAuthority()

# Cấp quyền cho các nút tham gia đồng thuận
poa.add_authority("node_hq", metadata={"org": "Headquarters", "pubkey": "..."})
poa.add_authority("node_branch_1", metadata={"org": "Branch 01", "pubkey": "..."})

# Kiểm tra quyền tạo khối của nút hiện tại
if poa.can_create_block("node_hq"):
    # Tiến hành đóng khối...
    pass
```

---

## Ưu điểm và Hạn chế

*   **Ưu điểm**: Tiết kiệm tài nguyên (không cần CPU mạnh để đào), thông lượng cao, quản trị minh bạch.
*   **Hạn chế**: Tính phi tập trung thấp hơn so với BFT, chỉ phù hợp cho mạng có sự tin tưởng nhất định giữa các thành viên.

---

## Liên quan

*   [Giao diện chuẩn (Base Consensus)](./base_consensus.md)
*   [Đồng thuận liên minh (PoF)](./pof.md)
*   [Kiến trúc phân cấp](../modules/hierarchical.md)
