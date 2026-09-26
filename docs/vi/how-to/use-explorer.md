---
title: Sử dụng Blockchain Explorer
description: Hướng dẫn công cụ giám sát hiệu suất và phân tích Block của Blockchain Explorer UI.
icon: material/monitor-dashboard
---

# Sử dụng Blockchain Explorer

## Trình Khám phá Chuỗi

`BlockchainExplorer` trong `hierachain/api/blockchain_explorer.py` trả dữ liệu dashboard dưới dạng JSON. Web view có thể dùng dữ liệu này để hiển thị hoạt động của chain và kết quả xác minh.

### 1. Thành phần của Explorer

Dữ liệu render có thể gồm bốn thành phần sau:

* **Chain Overview Component (`chain_overview`)**: Hiển thị độ cao block, số event trên Main-Chain và Sub-Chains, cùng hoạt động gần đây.
* **Entity Tracer Component (`entity_tracer`)**: Tìm theo entity ID và hiển thị các block, event liên quan.
* **Event Analytics Component (`event_analytics`)**: Hiển thị số event theo loại, timeline theo giờ trong 24 giờ gần nhất dựa trên block của Main-Chain, và tổng số event trên từng chain.
* **Proof Visualizer Component (`proof_visualizer`)**: Hiển thị proof gần đây, tóm tắt trạng thái xác minh và cấu trúc block của Main-Chain, Sub-Chains.

### Tính năng IPFS trong Explorer

Explorer hỗ trợ trực quan hóa dữ liệu được lưu trữ ngoài chuỗi (Off-chain):

* **Nhận diện dữ liệu**: Hiển thị huy hiệu cho các event lưu trên IPFS.

    * 📦 **Màu vàng**: Dữ liệu CID chưa tải (Unresolved).
    * ✓ **Màu xanh**: Dữ liệu đã được tải và giải mã (Resolved).

* **Tải dữ liệu**: Nút **"Load Details"** tải dữ liệu từ IPFS qua API Server mà không cần tải lại trang.
* **Giải mã**: Server giải mã dữ liệu trước khi hiển thị trên giao diện.

### 2. Render Dashboard qua API

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

Dữ liệu JSON trả về cho phép lập trình viên front-end (React/Vue/HTML5) tạo các card hiển thị chỉ số và block liên quan.
