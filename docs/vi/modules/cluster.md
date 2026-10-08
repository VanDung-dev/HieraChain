---
title: "Cluster Module"
description: "Đồng bộ liên tầng và các kiểu dữ liệu thông điệp của cluster."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Tổng quan

Module **Cluster** chứa runtime đồng bộ liên tầng và các kiểu dữ liệu dùng cho thông điệp cluster.

---

## Kiến trúc & Các thành phần chính

Package hiện cung cấp hai khối chức năng nhỏ:

<div class="grid cards" markdown>

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Đồng bộ bằng chứng (proofs) giữa Main Chain và Sub-Chains.
    * Đảm bảo tính toàn vẹn của cây phân cấp doanh nghiệp.

*   :material-shield-lock:{ .lg .middle } __Kiểu dữ liệu thông điệp Lockdown__

    ---

    __File__: `lockdown_types.py`

    * Định nghĩa thông điệp lockdown và quarantine có thể serialize.
    * Cung cấp helper ký và xác thực HMAC.

</div>

---

## Sử dụng

`HierarchyManager` sở hữu instance `CrossLevelSyncManager` tùy chọn và dùng nó
để đồng bộ metadata proof giữa main chain và sub-chain. Các kiểu dữ liệu trong
`lockdown_types.py` chỉ là helper cho dữ liệu và chữ ký; chúng không triển khai
bộ điều phối bỏ phiếu hoặc phong tỏa toàn cluster.

Việc gửi proof của một Sub-Chain được tuần tự hóa trên chain đó trong lúc lấy
tip hiện tại, kiểm tra anchor có sẵn, ghi event MainChain và xác minh đọc lại
từ storage bền vững. Vì vậy các request đồng thời cho cùng tip sẽ dùng lại một
proof anchor thay vì thêm bản trùng. Khóa này chỉ áp dụng trong một object
Sub-Chain, không phải khóa phân tán giữa các tiến trình.

---

## Chữ ký báo cáo Quarantine

`QuarantineReport.compute_signature(secret_key)` tính HMAC-SHA256 trên mọi trường do `to_dict()` trả về, trừ `signature`: `msg_type`, `lockdown_type`, `node_id`, `timestamp`, `pending_event_ids`, `last_block_index`, `last_block_hash` và `total_pending`. Payload là JSON UTF-8 dạng gọn, sắp xếp khóa object, giữ nguyên Unicode và chỉ chấp nhận số hữu hạn. Thứ tự danh sách event được giữ nguyên và bảo vệ. Digest vẫn lấy 32 ký tự hex đầu tiên.

Byte canonical dùng `hierachain.serialization.dumps_canonical_json(payload)`, tương đương `json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")` của thư viện chuẩn. Thành phần ký bên ngoài phải dùng cùng cách mã hóa. Chữ ký đã phát hành với cách biểu diễn float khác cần được ký lại từ dữ liệu tin cậy.

Caller gán kết quả vào `report.signature`; `verify_signature(secret_key)` kiểm tra bằng phép so sánh thời gian hằng. Thay đổi bất kỳ trường báo cáo nào đều làm chữ ký sai. Round-trip JSON hoặc đổi thứ tự khóa object vẫn xác minh được. Chữ ký thiếu/sai định dạng và giá trị payload không được hỗ trợ trả `False`; ký timestamp không hữu hạn gây `ValueError`. `from_dict()` từ chối giá trị `msg_type` hoặc `lockdown_type` được cung cấp nhưng không mô tả báo cáo quarantine.

Chữ ký tạo bằng payload cũ chỉ có ba trường bị từ chối. Cần tạo lại báo cáo từ dữ liệu tin cậy và ký payload đầy đủ; không fallback sang định dạng chữ ký cũ. Caller cung cấp và bảo vệ khóa bí mật dùng chung. Các helper không cấp khóa, kiểm tra độ mới của báo cáo hoặc tự xác thực báo cáo trong bộ điều phối runtime.

---

## Liên quan

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)

## Trạng thái đồng bộ song song và tiếp nhận lockdown

`CrossLevelSyncManager.get_status()` giữ trạng thái đang chạy khi còn bất kỳ sync hoặc xử lý conflict nào trong nhóm tác vụ chồng lấn. Khi nhóm hoàn tất, trạng thái là `failed` nếu có tác vụ thất bại, ngược lại là `complete`. Tác vụ độc lập tiếp theo mở nhóm mới. `get_stats()` có `active_operations`; `reset()` gây `RuntimeError` khi còn công việc. Lỗi callback hoàn tất được ghi log và không đảo ngược proof đã commit.

`LockdownMessage.verify_signature()` chỉ xác thực chữ ký. Trước khi xử lý thông điệp, dispatcher của ứng dụng phải gọi `LockdownMessageGuard.accept(message, secret_key)` và chỉ xử lý khi nhận `True`. Giữ một guard xuyên suốt các request. Guard kiểm tra chữ ký và timestamp hữu hạn, mặc định cho phép thông điệp cũ tối đa 60 giây hoặc đi trước 5 giây, đồng thời từ chối nguyên tử payload đã tiếp nhận, kể cả khi đổi giữa chữ ký đầy đủ và rút gọn. Có thể cấu hình `max_age`, `future_skew`, `max_entries`. Khi kho replay đầy, guard từ chối thông điệp mới đến lúc entries hết hạn; không đẩy entries còn hiệu lực ra ngoài. Chữ ký sai không chiếm dung lượng.

Repo chưa có dispatcher lockdown. Guard chỉ giữ trạng thái trong một process; không lưu qua restart hoặc chia sẻ giữa worker. Ứng dụng cần các bảo đảm này phải giữ trạng thái replay trong storage của dispatcher. Guard không kiểm tra tiếp nhận `QuarantineReport`.
