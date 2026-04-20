---
title: Bắt đầu nhanh
description: Thiết lập nhanh môi trường và chạy thử HieraChain trong vài phút.
icon: material/lightning-bolt
---

# Bắt đầu nhanh

Tài liệu này tóm tắt các bước tối thiểu để bạn chạy thử HieraChain.

## Cài đặt nhanh

Để bắt đầu nhanh nhất, bạn chỉ cần cài đặt gói qua PIP:

```bash
# Cách 1: Cài đặt qua PIP truyền thống
pip install .

# Cách 2: Sử dụng uv (Khuyên dùng)
uv sync
```

Nếu bạn muốn phát triển mã nguồn, vui lòng xem hướng dẫn [Cài đặt chi tiết](install.md).

## Khởi động API server

Sau khi cài đặt, bạn có thể khởi chạy server bằng lệnh:

```bash
python -m hierachain.api.server
```

Hoặc sử dụng CLI (nếu đã cài đặt qua pip):

```bash
hrc server start
```

Mặc định server phục vụ tại `http://localhost:2661`. Mở `http://localhost:2661/docs` để xem tài liệu OpenAPI và thử endpoint.

## Sử dụng nhanh trong Python

Ví dụ tối thiểu bên dưới minh họa cách tạo một `Sub-Chain`, ghi nhận sự kiện, và gửi bằng chứng lên `Main Chain`.

```python
from hierachain.hierarchical.hierarchy_manager import HierarchyManager

# 1. Khởi tạo Hierarchy Manager (Quản lý các chuỗi)
manager = HierarchyManager()

# 2. Tạo một sub-chain cho domain cụ thể (ví dụ: chuỗi cung ứng)
# Tham số: tên chuỗi, loại domain (generic, v.v.)
manager.create_sub_chain("supply_chain", "generic")

# 3. Ghi nhận một hoạt động nghiệp vụ (Event) vào Sub-Chain
# Tham số: tên chuỗi, ID thực thể, loại sự kiện, dữ liệu chi tiết
success = manager.start_operation(
    "supply_chain", 
    "PROD-100", 
    "production_start", 
    {"location": "Factory-A", "operator": "user_01"}
)

# 4. Neo bằng chứng (Proof) từ Sub-Chain lên Main Chain
# Điều này giúp bảo chứng tính toàn vẹn của Sub-Chain trên Main Chain
proof_success = manager.submit_proof_to_main_chain("supply_chain")

print(f"Ghi sự kiện: {'Thành công' if success else 'Thất bại'}")
print(f"Neo Proof: {'Thành công' if proof_success else 'Thất bại'}")
```

## Dùng CLI (tuỳ chọn)

```bash
hrc --help
```

## Bước tiếp theo

* Tìm hiểu chi tiết kiến trúc: [Tổng quan](../architecture/overview.md)
* Xem mô-đun cốt lõi: [Core](../modules/core.md)
* Xem thêm ví dụ kiểm thử trong [Kiểm thử](../dev/testing.md)
