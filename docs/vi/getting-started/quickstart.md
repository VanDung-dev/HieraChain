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
pip install HieraChain
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
from hierachain.hierarchical import hierarchy_manager

# Khởi tạo manager
manager = hierarchy_manager.HierarchyManager()

# Tạo một sub-chain theo domain (yêu cầu tên và loại domain)
manager.create_sub_chain("supply_chain", "generic")

# Ghi nhận một Event domain (sử dụng start_operation hoặc lấy sub_chain direct)
success = manager.start_operation("supply_chain", "PROD-001", "production_complete", {
    "quantity": 100
})

# Gửi Proof lên Main Chain (sử dụng đúng tên hàm submit_proof_to_main_chain)
proof_success = manager.submit_proof_to_main_chain("supply_chain")
print("success=", success)
print("proof_success=", proof_success)
```

## Dùng CLI (tuỳ chọn)

```bash
hrc --help
```

## Bước tiếp theo

* Tìm hiểu chi tiết kiến trúc: [Tổng quan](../architecture/overview.md)
* Xem mô-đun cốt lõi: [Core](../modules/core.md)
* Xem thêm ví dụ kiểm thử trong [Kiểm thử](../dev/testing.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * API server khởi chạy bằng `python -m hierachain.api.server` (mặc định cổng 2661).
    * CLI `hrc` được đăng ký trong `pyproject.toml`.

    **DECISION**

    * Quickstart chỉ trình bày luồng tối thiểu, chi tiết API/Schema sẽ để trong mục Reference.

    **ASSUMPTION**

    * Hệ thống đã cài dependencies cần thiết theo hướng dẫn cài đặt.

    **INVARIANT**

    * Ví dụ phải sát với chữ ký/lớp hiện có trong `hierachain/*`.

    **EDGE CASES**
    
    * Người dùng không bật venv dẫn đến dùng sai phiên bản Python hoặc PATH.
