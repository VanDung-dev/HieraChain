---
title: "Units & Versioning Module"
description: "Quản lý phiên bản hệ thống: Tuân thủ PEP 440, Semantic Versioning, và Trạng thái phát triển Project."
icon: material/numeric
---

# Units Module (`hierachain/units/*`)

## Tổng quan

Module **Units** chịu trách nhiệm quản lý hệ thống phiên bản (Versioning) của HieraChain. Nó đảm bảo toàn bộ hệ thống (từ Core, API đến CLI) luôn đồng bộ về mặt phiên bản và tuân thủ các tiêu chuẩn đóng gói phần mềm hiện đại như **PEP 440**.

---

## Cấu trúc Phiên bản (Version Tuple)

HieraChain sử dụng một Tuple 5 thành phần để định nghĩa phiên bản một cách chi tiết:
`VERSION = (major, minor, micro, releaselevel, serial)`

*   **Major**: Phiên bản lớn, thay đổi khi có các cập nhật kiến trúc quan trọng.
*   **Minor**: Phiên bản nhỏ, thay đổi khi thêm tính năng mới.
*   **Micro**: Phiên bản sửa lỗi (Bug fix).
*   **Release Level**: Trạng thái phát triển (`dev`, `alpha`, `beta`, `rc`, `final`).
*   **Serial**: Số thứ tự của bản release trong cùng một level.

---

## Các tính năng chính

<div class="grid cards" markdown>

*   :material-check-decagram:{ .lg .middle } __PEP 440 Compliance__

    ---

    Tự động chuyển đổi Tuple phiên bản sang chuỗi ký tự tiêu chuẩn Python (ví dụ: `0.0.2-beta1` hoặc `0.0.2` cho bản final).

*   :material-compare-remove:{ .lg .middle } __So sánh Phiên bản__

    ---

    Cung cấp hàm `compare_versions` hỗ trợ so sánh cả chuỗi và tuple, giúp hệ thống kiểm tra tính tương thích giữa các thành phần.

*   :material-book-information-variant:{ .lg .middle } __Trạng thái Tài liệu__

    ---

    Xác định trạng thái của dự án (Stable, Under Development, Release Candidate) dựa trên level phiên bản hiện tại.

</div>

---

## Ví dụ sử dụng

### 1. Lấy thông tin phiên bản hiện tại
```python
from hierachain.units.version import get_version, VERSION

# Trả về chuỗi PEP 440 (ví dụ: "0.0.2")
print(f"HieraChain Version: {get_version()}")

# Lấy phiên bản rút gọn (Major.Minor)
from hierachain.units.version import get_major_version
print(f"Base Version: {get_major_version()}")
```

### 2. So sánh tính tương thích
```python
from hierachain.units.version import compare_versions

required = "0.0.1"
current = get_version()

if compare_versions(current, required) >= 0:
    print("Hệ thống tương thích.")
else:
    print("Yêu cầu nâng cấp phiên bản!")
```

---

## Phân cấp Release Level

Khi so sánh phiên bản, HieraChain tuân theo thứ tự ưu tiên sau (từ thấp đến cao):
1.  `dev` (Development)
2.  `alpha` (Alpha testing)
3.  `beta` (Beta testing)
4.  `rc` (Release Candidate)
5.  `final` (Stable Release)

---

## Liên quan

*   [Cấu hình hệ thống (Config)](./config.md)
*   [API Status v3 (Sử dụng versioning)](./api.md)
*   [CLI (Hiển thị version)](./cli.md)
