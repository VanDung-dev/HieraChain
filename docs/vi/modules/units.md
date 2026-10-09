---
title: "Module quản lý phiên bản"
description: "Quản lý phiên bản hệ thống: Tuân thủ PEP 440, tuple phiên bản ngữ nghĩa và định dạng chuỗi phiên bản trong hierachain/config/version.py."
icon: material/numeric
---

# Module quản lý phiên bản (`hierachain/config/version.py`)

## 1. Tổng quan

Module quản lý phiên bản xác định phiên bản phát hành cho HieraChain. Hệ thống định dạng tuple phiên bản có cấu trúc thành chuỗi chuẩn theo đặc tả PEP 440, đảm bảo các thành phần Core, API, SDK và CLI đồng bộ thông tin phiên bản phát hành.

## 2. Cấu trúc tuple phiên bản

HieraChain định nghĩa phiên bản hệ thống dưới dạng tuple 5 phần tử trong `hierachain/config/version.py`:

```python
VERSION: tuple[int, int, int, str, int] = (0, 2, 0, "final", 0)
```

Ý nghĩa các phần tử:

* Major: Tăng khi có thay đổi kiến trúc hoặc API không tương thích ngược.
* Minor: Tăng khi bổ sung tính năng mới tương thích ngược.
* Micro: Tăng khi phát hành các bản vá lỗi.
* Release level: Trạng thái phát triển (`dev`, `alpha`, `beta`, `rc` hoặc `final`).
* Serial: Số thứ tự bản phát hành thử nghiệm.

## 3. Hàm định dạng phiên bản

Module cung cấp hàm chuyển đổi tuple thành chuỗi phiên bản tiêu chuẩn:

* Bản phát hành `final` bỏ hậu tố, cho chuỗi version như `0.2.0`.
* Các cấp thử nghiệm thêm hậu tố chuẩn PEP 440 như `-alpha1` hoặc `-beta2`.
* Mức `dev` dùng `.devN` khi serial dương, hoặc `.dev` khi serial bằng 0.

## 4. Sử dụng trong mã nguồn

```python
from hierachain.config.version import get_version, VERSION, __version__

# Current version string
print(f"HieraChain Version: {__version__}")

# Explicit tuple formatting
custom_version = (0, 2, 0, "beta", 1)
print(f"Formatted Version: {get_version(custom_version)}")
```

## Liên quan

* [Cấu hình hệ thống](./config.md)
* [API Quản trị](./api.md)
* [Công cụ CLI](./cli.md)
