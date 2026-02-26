---
title: "Units module"
description: "Thông tin phiên bản/đơn vị: hierachain/units/version.py — hàm tiện ích truy xuất phiên bản Ledger."
icon: material/ruler
---

# Units

## Mục đích

Cung cấp các đơn vị/thông tin hệ thống ở mức khối nhỏ (ví dụ phiên bản Ledger) để các mô‑đun khác có thể tham chiếu.

## Thành phần

* Version: `hierachain/units/version.py` — định nghĩa phiên bản và hàm `get_version()`.

## API công khai (mang tính mô tả)

```python
from hierachain.units.version import VERSION, get_version
current = get_version(VERSION)
```

## Liên quan

* Config/Settings: [Config (Module)](config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * File: `hierachain/units/version.py` (truy xuất phiên bản Ledger).

    **DECISION**

    * Giữ thông tin phiên bản tập trung để tiện truy xuất trong log/config/API.

    **ASSUMPTION**

    * Phiên bản được quản lý bởi `setuptools_scm` (xem README/pyproject) và mapping trong `units/version.py`.

    **INVARIANT**

    * Hàm `get_version()` luôn trả về giá trị nhất quán để hiển thị/logging.

    **EDGE CASES**

    * Môi trường không có tag/git metadata → cần fallback hợp lý trong `get_version()`.
