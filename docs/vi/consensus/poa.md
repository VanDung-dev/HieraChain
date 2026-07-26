---
title: "Proof of Authority (PoA)"
description: "Giao thức đồng thuận dựa trên thẩm quyền: Hiệu năng tối đa, Định danh nút và Luân phiên Round-Robin."
icon: material/account-check-outline
---

# Proof of Authority (`hierachain/consensus/proof_of_authority.py`)

## Tổng quan

**Proof of Authority (PoA)** là giao thức đồng thuận dựa trên định danh, được tối ưu hóa cho **nội bộ một Doanh nghiệp / Tổ chức** (1 MainChain quản lý các Sub-Chains thuộc các phân khu/tên miền nội bộ). Trong kiến trúc đồng thuận 2 tầng của HieraChain, các đối tượng `SubChain` **mặc định luôn sử dụng PoA** để xử lý các sự kiện nghiệp vụ nội bộ với tốc độ cực nhanh (~0ms latency) mà không cần chờ đợi đồng thuận liên tổ chức.

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

*   :material-lightning-bolt:{ .lg .middle } __Hiệu năng Đột phá__

    ---

    Khối được tạo ngay lập tức theo chu kỳ cấu hình (`block_interval`), phù hợp cho các ứng dụng yêu cầu phản hồi thời gian thực.

*   :material-account-multiple-check:{ .lg .middle } __Quản trị Danh tính__

    ---

    Hỗ trợ thêm/xóa Authority linh hoạt thông qua API, cho phép thay đổi cấu hình mạng mà không cần dừng hệ thống.

*   :material-shield-sync:{ .lg .middle } __Tính Toàn vẹn Tuyệt đối__

    ---

    Mọi khối đều mang chữ ký số của một tổ chức được xác thực, loại bỏ hoàn toàn rủi ro từ các nút vô danh hoặc giả mạo.

</div>

---

## Tham số cấu hình quan trọng

| Tham số | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `block_interval` | Khoảng thời gian tối thiểu giữa hai khối. | `10.0` giây |
| `max_authorities` | Số lượng nút Authority tối đa trong mạng. | `100` |
| `require_signature` | Bắt buộc phải có chữ ký hợp lệ để chấp nhận khối. | `True` |

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
