---
title: "Cluster Module"
description: "Quản lý cụm node, cơ chế đồng bộ trạng thái phân tán và giao thức phong tỏa (lockdown) an toàn."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Tổng quan

Module **Cluster** là bộ não điều phối sự phối hợp giữa các node trong mạng lưới HieraChain. Nó đảm bảo hệ thống hoạt động như một thực thể thống nhất, duy trì tính nhất quán dữ liệu xuyên suốt các tầng phân cấp và cung cấp các cơ chế bảo vệ khẩn cấp khi phát hiện dấu hiệu bất thường.

---

## Kiến trúc & Các thành phần chính

Hệ thống được thiết kế theo mô hình phi tập trung với các thành phần chuyên biệt:

<div class="grid cards" markdown>

*   :material-server-network:{ .lg .middle } __Cluster Manager__

    ---

    __File__: `cluster_manager.py`

    * Theo dõi sức khỏe (Health tracking) của toàn bộ node.
    * Cơ chế Heartbeat để phát hiện node ngoại tuyến.
    * Quản lý bỏ phiếu Quorum (2/3 majority).

*   :material-shield-lock:{ .lg .middle } __Lockdown Protocol__

    ---

    __File__: `lockdown_protocol.py`

    * Giao thức truyền tin Gossip qua P2P (ZMQ).
    * Bảo mật bằng chữ ký HMAC-SHA256 (`HRC_CLUSTER_SECRET`).
    * Cơ chế "Quarantine Report" (Báo cáo cách ly).

*   :material-database-sync:{ .lg .middle } __State Sync (Resurrection)__

    ---

    __File__: `state_sync_manager.py`

    * Khôi phục trạng thái sau sự cố hoặc phong tỏa.
    * Cơ chế "Gap-fill" (Lấp đầy khoảng trống) block.
    * Xác thực block nhận được từ đồng đẳng (peers).

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Đồng bộ bằng chứng (proofs) giữa Main Chain và Sub-Chains.
    * Đảm bảo tính toàn vẹn của cây phân cấp doanh nghiệp.

</div>

---

## Giao thức Phong tỏa & Khôi phục (Lockdown & Recovery)

Đây là cơ chế an ninh tối thượng của HieraChain để bảo vệ sổ cái khi có tấn công hoặc lỗi hệ thống nghiêm trọng.

### 1. Bỏ phiếu Quorum (Quorum Voting)
Hệ thống yêu cầu đa số tuyệt đối (**2/3 số node**) đồng thuận để thay đổi trạng thái cụm:
*   **Lockdown**: Tạm dừng mọi hoạt động ghi mới để bảo vệ dữ liệu hiện có.
*   **Recovery**: Tái khởi động hệ thống sau khi đã xử lý xong sự cố.

### 2. Báo cáo "Hơi thở cuối" (Quarantine Report)
Trước khi một node thực hiện phong tỏa và xóa bộ nhớ đệm (event pool), nó sẽ phát đi một `QuarantineReport` chứa dấu vân tay (fingerprints) của các sự kiện chưa được ghi. Điều này giúp các node khác đối chiếu và phát hiện lỗ hổng dữ liệu sau khi khôi phục.

### 3. Bảo mật thông điệp
Mọi thông điệp trong cụm (Lockdown, Vote, Sync) đều phải được ký bằng **HMAC-SHA256** sử dụng khóa bí mật dùng chung `HRC_CLUSTER_SECRET`. Các thông điệp không hợp lệ hoặc hết hạn (>300s) sẽ bị loại bỏ ngay lập tức.

---

## Cơ chế Đồng bộ Trạng thái (State Synchronization)

Khi một node mới gia nhập hoặc một node vừa khôi phục từ trạng thái phong tỏa, nó sẽ thực hiện quy trình **Resurrection**:

1.  **Xác định khoảng trống (Gap Identification)**: Đối chiếu chỉ số (index) block cuối cùng với các peers.
2.  **Yêu cầu dữ liệu (Sync Request)**: Gửi yêu cầu lấp đầy khoảng trống cho các node lành mạnh.
3.  **Xác thực đa tầng (Verification)**: Mỗi block nhận về đều được kiểm tra hash chaining và chữ ký bởi `BlockVerifier`.
4.  **Hợp nhất (Merging)**: Chỉ các dữ liệu hợp lệ mới được ghi vào database địa phương.

---

## Ví dụ cấu hình & Sử dụng

### Cấu hình biến môi trường
```bash
HRC_CLUSTER_SECRET="your-super-secret-hmac-key"
HRC_QUORUM_THRESHOLD=0.66  # Tương đương 2/3
```

### Sử dụng ClusterManager trong mã nguồn
```python
from hierachain.cluster.cluster_manager import ClusterManager

manager = ClusterManager(node_id="node-01")

# Đăng ký node đồng đẳng
manager.register_node("node-02", "192.168.1.10:5000", auth_token="...")

# Bỏ phiếu phong tỏa khi phát hiện rủi ro
if manager.vote_lockdown("node-01", reason="Phát hiện giả mạo hash"):
    print("Quorum reached - Hệ thống đang chuyển sang trạng thái LOCKDOWN")
```

---

## Quan sát sức khỏe cụm (Health Metrics)

`ClusterManager` cung cấp đối tượng `ClusterHealthMetrics` cho phép theo dõi:

*   `total_nodes`: Tổng số node trong cấu hình.
*   `healthy_nodes`: Số node đang hoạt động và gửi heartbeat đều đặn.
*   `is_in_lockdown`: Trạng thái phong tỏa hiện tại của toàn cụm.
*   `lockdown_votes`: Số phiếu bầu phong tỏa hiện tại.

---

## Liên quan

*   [P2P Networking](../network/p2p.md)
*   [Security Identity](../security/identity.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
