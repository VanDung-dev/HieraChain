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

---

## Chữ ký báo cáo Quarantine

`QuarantineReport.compute_signature(secret_key)` tính HMAC-SHA256 trên mọi trường do `to_dict()` trả về, trừ `signature`: `msg_type`, `lockdown_type`, `node_id`, `timestamp`, `pending_event_ids`, `last_block_index`, `last_block_hash` và `total_pending`. Payload là JSON UTF-8 dạng gọn, sắp xếp khóa object, giữ nguyên Unicode và chỉ chấp nhận số hữu hạn. Thứ tự danh sách event được giữ nguyên và bảo vệ. Digest vẫn lấy 32 ký tự hex đầu tiên.

Byte canonical dùng `orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)`. Thành phần ký bên ngoài phải dùng cùng cách mã hóa. Định dạng float có thể khác thư viện JSON chuẩn của Python; báo cáo có cách mã hóa khác cần được ký lại từ dữ liệu tin cậy.

Caller gán kết quả vào `report.signature`; `verify_signature(secret_key)` kiểm tra bằng phép so sánh thời gian hằng. Thay đổi bất kỳ trường báo cáo nào đều làm chữ ký sai. Round-trip JSON hoặc đổi thứ tự khóa object vẫn xác minh được. Chữ ký thiếu/sai định dạng và giá trị payload không được hỗ trợ trả `False`; ký timestamp không hữu hạn gây `ValueError`. `from_dict()` từ chối giá trị `msg_type` hoặc `lockdown_type` được cung cấp nhưng không mô tả báo cáo quarantine.

Chữ ký tạo bằng payload cũ chỉ có ba trường bị từ chối. Cần tạo lại báo cáo từ dữ liệu tin cậy và ký payload đầy đủ; không fallback sang định dạng chữ ký cũ. Caller cung cấp và bảo vệ khóa bí mật dùng chung. Các helper không cấp khóa, kiểm tra độ mới của báo cáo hoặc tự xác thực báo cáo trong bộ điều phối runtime.

---

## Liên quan

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
