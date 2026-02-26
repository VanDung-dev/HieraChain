---
title: Cài đặt HieraChain
description: Hướng dẫn cài đặt HieraChain từ mã nguồn cho môi trường phát triển.
icon: material/download
---

# Cài đặt

Tài liệu này hướng dẫn cài đặt HieraChain từ mã nguồn phục vụ phát triển và thử nghiệm.

## Yêu cầu hệ thống

* Python >= 3.10 (được khai báo trong `pyproject.toml`)
* pip, venv (hoặc công cụ quản lý môi trường ảo tương đương)
* Quyền truy cập Internet để cài dependencies từ PyPI

Tùy chọn (không bắt buộc để bắt đầu):

* Redis (nếu muốn dùng adapter Redis)
* SQLite/PostgreSQL (mặc định dự án có SQLite qua `sqlalchemy`)

## Cài đặt từ mã nguồn (khuyến nghị cho dev)

1. Clone repository và tạo môi trường ảo

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
```

Tạo & kích hoạt venv

=== "Linux/macOS"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

=== "Windows (PowerShell)"

    ```powershell
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    ```

2. Cài dependencies và cài đặt chế độ phát triển

```bash
# Dependencies tối thiểu
pip install -r requirements.txt

# Dependencies cho phát triển (tùy chọn)
pip install -r requirements_dev.txt

# Cài đặt ở chế độ editable
pip install -e .
```

1. Xác minh cài đặt

```bash
# Kiểm tra phiên bản qua importlib.metadata
python -c "import importlib.metadata as m; print(m.version('HieraChain'))"

# Kiểm tra CLI đã có trong PATH
hrc --help

# Khởi động API server (tuỳ chọn)
python -m hierachain.api.server
```

Nếu server khởi chạy thành công, bạn có thể mở tài liệu tương tác tại: `http://localhost:2661/docs`.

## Chạy Server

Để khởi chạy API server của HieraChain:

```bash
python -m hierachain.api.server
```

## Sử dụng thư viện (Usage)

Sau khi cài đặt, bạn có thể import các thành phần từ gói trong mã nguồn Python của mình:

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
```

## Chạy Demo

Các file demo nằm trong thư mục `demo/`. Trước khi chạy, đảm bảo bạn đã cài đặt gói và dependencies.

* **Demo Chính (Main Ledger - Minh họa các tính năng cốt lõi: chuỗi phân cấp, MSP, channels, dữ liệu riêng tư:

    ```bash
    python demo/demo.py
    ```

* **Demo Sao lưu & Khôi phục Khóa** - Minh họa chức năng backup/recovery khóa:

    ```bash
    python demo/demo_key_backup.py
    ```

* **Demo Đồng thuận ZeroMQ BFT** - Minh họa đồng thuận Byzantine Fault Tolerance qua ZeroMQ:

    ```bash
    python demo/demo_zmq_consensus.py
    ```

!!! note "Lưu ý"

    Để dọn dẹp dữ liệu cũ trước khi chạy lại demo:

    === "Linux/macOS"

        ```bash
        rm -rf demo/data demo/hierachain.db 2>/dev/null
        ```

    === "Windows (PowerShell)"

        ```powershell
        Remove-Item -Recurse -Force demo/data, demo/hierachain.db -ErrorAction SilentlyContinue
        ```

## Tài liệu (Documentation)

Dự án sử dụng [Zensical](https://zensical.org/) để build tài liệu.

### Yêu cầu

Đảm bảo đã cài Zensical:

```bash
pip install zensical
```

### Chạy Server Tài liệu (Local)

Để xem tài liệu với chế độ live-reload:

```bash
zensical serve
```

Truy cập `http://127.0.0.1:8000`.

### Build Static Site

Để build ra HTML tĩnh (thư mục `site/`):

```bash
zensical build
```

## Gỡ cài đặt / Làm sạch môi trường

```bash
pip uninstall -y HieraChain
deactivate  # thoát môi trường ảo (nếu đang bật)
```

## Sự cố thường gặp (Troubleshooting)

* Không chạy được `hrc`: kiểm tra đã kích hoạt venv và `pip install -e .` thành công.
* Lỗi biên dịch gói phụ thuộc: đảm bảo có build tools phù hợp (ví dụ: trên Windows cài Build Tools for Visual Studio nếu cần).
* Cổng API 2661 bận: điều chỉnh cấu hình trong `hierachain/config/settings.py` hoặc tắt tiến trình chiếm cổng.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * `requires-python = ">=3.10"` (xem `pyproject.toml`).
    * Script CLI `hrc` cấu hình tại `[project.scripts]` trong `pyproject.toml`.
    * API server có thể chạy bằng `python -m hierachain.api.server` (mặc định phục vụ tại `http://localhost:2661`).

    **DECISION**

    * Khuyến nghị dùng môi trường ảo `venv` để cô lập gói.
    * Cài đặt ở chế độ editable (`pip install -e .`) cho vòng lặp dev nhanh.

    **ASSUMPTION**

    * Máy phát triển có quyền truy cập PyPI; tường lửa không chặn.
    * Người dùng có quyền cài đặt gói hệ thống phụ thuộc (nếu cần).

    **INVARIANT**

    * Hướng dẫn cài đặt luôn bám thông tin từ `pyproject.toml` và `README_vi.md` của repository hiện tại.

    **EDGE CASES**

    * Khác biệt lệnh kích hoạt venv giữa bash và PowerShell.
    * Môi trường doanh nghiệp có proxy: cần cấu hình `pip` với biến môi trường `HTTP_PROXY`/`HTTPS_PROXY`.
