---
title: "Cài đặt HieraChain"
description: "Hướng dẫn cài đặt HieraChain từ mã nguồn cho môi trường phát triển."
icon: material/download
---

# Cài đặt HieraChain

Package yêu cầu Python từ 3.10; workflow tương thích kiểm thử Python 3.10–3.14. Dùng checkout mã nguồn khi làm theo tài liệu của triển khai hiện tại.

## Cài mã nguồn với uv

Chạy từ thư mục gốc repository:

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev --extra doc
source .venv/bin/activate
hrc --help
```

`uv sync` cài package cơ bản. Extra `dev` cung cấp công cụ kiểm thử/phân tích; `doc` cung cấp Zensical. Trên Windows, kích hoạt môi trường bằng `.venv\Scripts\Activate.ps1`.

## Cài mã nguồn với pip

Sau khi clone và vào repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,doc]"
```

Để dùng thư viện từ bản đã phát hành, cài `python -m pip install HieraChain`. Bản phát hành có thể khác checkout này.

## Cấu hình trước khi khởi động

Khởi tạo chain, kể cả genesis, cần identity ký cố định và `HRC_BLOCK_TRUSTED_KEYS_FILE` tương ứng. Development mặc định dùng PostgreSQL; không tự chuyển sang SQLite khi PostgreSQL lỗi. Làm theo [Bắt đầu nhanh](quickstart.md) để thử SQLite biệt lập. Production còn cần file API key đã cấp và cấu hình database rõ ràng; xem [Cấu hình](../reference/config.md).

Sau khi thiết lập, khởi động bằng `python -m hierachain` hoặc `hrc node start`. API mặc định ở `http://localhost:2661`; `/docs` cung cấp OpenAPI và `/api/ledger/ready` kiểm tra readiness hierarchy.

## Kiểm thử

Chạy từng file để tránh xung đột tài nguyên dùng chung. Dùng storage và journal tạm; fixture có thể dọn thư mục `data/` cục bộ. Ví dụ:

```bash
python -m pytest tests/unit/core/test_block.py -v
```

Xem [Kiểm thử](../dev/testing.md) về contract PostgreSQL/Redis bắt buộc và workload Docker biệt lập.

## Demo

Xem [Hướng dẫn demo](../how-to/use-demos.md). Demo minh họa cách dùng; cài dependency không làm khả dụng lưu private data, thực thi contract, ZK production hoặc kết nối ERP vendor thật.

## Tài liệu

Preview một ngôn ngữ bằng `zensical serve -f zensical.toml` hoặc `zensical serve -f zensical.vi.toml`. Build tiếng Anh trước, rồi tiếng Việt:

```bash
zensical build -f zensical.toml
zensical build -f zensical.vi.toml
```

Đầu ra là `site/` và `site/vi/`. Xem [hướng dẫn build tài liệu](https://github.com/VanDung-dev/HieraChain/blob/main/docs/README.md).

## Khắc phục lỗi

* Thiếu `hrc`: kích hoạt `.venv` và kiểm tra cài đặt đã thành công.
* Thiếu/không tin cậy identity: kiểm tra đường dẫn identity, node ID và public key tin cậy tương ứng.
* Lỗi kết nối database: bật PostgreSQL hoặc chọn SQLite rõ ràng; không có fallback tự động.
* Port 2661 bị chiếm: đặt `HRC_API_PORT` trước khi import/khởi động ứng dụng.
