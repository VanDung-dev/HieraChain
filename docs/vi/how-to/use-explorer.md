---
title: Sử dụng Blockchain Explorer
description: Hướng dẫn công cụ giám sát hiệu suất và phân tích Block của Blockchain Explorer UI.
icon: material/monitor-dashboard
---

# Sử dụng Blockchain Explorer

## Trình Khám phá Chuỗi

Khác với các ứng dụng Web ngoài lề, HieraChain cung cấp lõi API Dashboard trực quan chuyên sâu ngay trong core (`hierachain/api/blockchain_explorer.py`). Qua cấu trúc JSON trả về với mô đun `render`, bất kỳ web-view nào cũng có thể hiện thực hóa thành Dashboard kiểm toán theo thời gian thực (Real-time).

### 1. Thành phần của Explorer

Giao diện (hoặc Render format từ API) sẽ bao gồm 4 khối chủ lực (Components):

* **Chain Overview Component (`chain_overview`)**: Hiển thị bảng tóm tắt cấu trúc. Số liệu tổng quan độ cao Block, lượng Event trên cả Main-chain và dải Sub-chains cũng như các hoạt động mới nhất.
* **Entity Tracer Component (`entity_tracer`)**: Thanh công cụ dò vết. Nhập thông tin ID hoặc bất kì đặc tả nào của Entity để tìm toàn cục xem Block và Event nào đang giao quyền kiểm soát cho đối tượng đó, hỗ trợ tracing mọi mắt xích tài sản.
* **Event Analytics Component (`event_analytics`)**: Đổ ra Timeline lịch sử hoạt động lượng event rải trên Block (ví dụ tính mốc bucket 24 tiếng gần nhất) hoặc vẽ biểu đồ sự kiện (Chart Distribution). Đóng vai trò giám sát hoạt động tải cao (High-load monitoring).
* **Proof Visualizer Component (`proof_visualizer`)**: Bản vẽ cây sơ đồ đệ quy (Hierarchy view). Thể hiện tỷ lệ thành công của Proof ZK, chỉ ra những chuỗi đang vướng mắc cơ chế Mock hay Production Mode xác minh.

### Tính năng IPFS trong Explorer

Explorer hỗ trợ trực quan hóa dữ liệu được lưu trữ ngoài chuỗi (Off-chain):

* **Nhận diện dữ liệu**: Tự động hiển thị Huy hiệu (Badge) cho các sự kiện lưu trên IPFS.

    * 📦 **Màu vàng**: Dữ liệu CID chưa tải (Unresolved).
    * ✓ **Màu xanh**: Dữ liệu đã được tải và giải mã (Resolved).

* **Tải dữ liệu tức thời**: Cung cấp nút **"Load Details"** để fetch dữ liệu từ IPFS qua API Server mà không cần load lại trang.
* **Bảo mật**: Dữ liệu được giải mã an toàn tại Server trước khi hiển thị trên giao diện người dùng.

### 2. Cách triệu hồi Dashboard qua API

Lập trình viên tích hợp Dashboard ngay trên Server-side Rendering của họ:

```python
from hierachain.api.blockchain_explorer import BlockchainExplorer

# Gắn module với cấu trúc Core hiện hữu
explorer = BlockchainExplorer(chain=my_hierarchy_manager_instance)

# Render Full trang chủ chứa Chain Overview, Entity Tracer, Event Analytics
dashboard_data = explorer.render()

# Hoặc Render riêng mục "Truy vết Entity"
tracer_form_ui = explorer.render(component_id="entity_tracer")
```

Với cấu trúc JSON cực kì logic, nhà lập trình Front-end (React/Vue/HTML5) dễ dàng "xào nấu" render ra các ô card hiển thị số dư, block tương ứng mà không phải tốn sức ghép truy vấn tay.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/api/blockchain_explorer.py` (Python >= 3.10 theo `pyproject.toml`).

    **DECISION**

    * Tổ chức nội dung tập trung vào hướng dẫn giải đáp chức năng Component render ra UI từ core backend.

    **ASSUMPTION**

    * Developer có kiến thức về cách ánh xạ JSON Response sang Component DOM phía trình duyệt.

    **INVARIANT**

    * Phải load tham số `total_events` trực tiếp nếu muốn `O(1)` performance (khuyến cáo trong hàm `render_summary`).

    **EDGE CASES**

    * Khối lượng truy vết entity có thể mất tài nguyên nếu gọi liên tục vào tệp `sub-chain` khi node chạy hàng tỷ events.
