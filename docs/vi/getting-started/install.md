---
title: Cài đặt HieraChain
description: Hướng dẫn cài đặt HieraChain từ mã nguồn cho môi trường phát triển.
icon: material/download
---

# Cài đặt HieraChain

Tài liệu này hướng dẫn các cách để cài đặt và thiết lập HieraChain.

## Cài đặt qua PIP (Khuyên dùng)

Đây là cách nhanh nhất và đơn giản nhất để bắt đầu sử dụng HieraChain như một thư viện hoặc chạy server.

```bash
# Lưu ý: Hiện tại dự án đang trong giai đoạn phát triển, khuyên dùng cài đặt từ mã nguồn.
pip install .
```

Sau khi cài đặt, bạn có thể kiểm tra bằng lệnh:

```bash
hrc --help
```

### Sử dụng `uv` (Khuyên dùng cho hiệu năng cao)

`uv` là công cụ quản lý package Python hiện đại viết bằng Rust, nhanh hơn pip từ 10-100 lần.

**Cài đặt uv:**
=== "Linux/macOS"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
=== "Windows (PowerShell)"
    ```powershell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

**Thiết lập dự án với uv:**
```bash
# Tạo môi trường ảo và đồng bộ dependencies cơ bản
uv sync

# Cài đặt kèm theo các nhóm công cụ (extras) cụ thể:
uv sync --extra dev --extra doc

# Hoặc cài đặt TẤT CẢ extras có trong dự án:
uv sync --all-extras

# Nếu chỉ muốn cài đặt môi trường production (bỏ qua dev dependencies):
uv sync --no-dev

# Kích hoạt môi trường ảo
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows
```

## Cài đặt từ mã nguồn (Dành cho nhà phát triển)

Nếu bạn muốn đóng góp cho dự án hoặc tùy chỉnh mã nguồn, hãy làm theo các bước sau:

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

    === "Sử dụng UV (Khuyên dùng)"

        ```bash
        # Đồng bộ dependencies cùng với môi trường dev
        uv sync --extra dev
        
        # Hoặc nếu muốn cài thêm doc, test
        uv sync --all-extras
        ```
    
    === "Sử dụng pip"

        ```bash
        # Cài đặt tất cả dependencies (production + dev + test) trong chế độ editable
        pip install -e ".[dev]"
        ```

3. Xác minh cài đặt

    ```bash
    # Kiểm tra phiên bản qua importlib.metadata
    python -c "import importlib.metadata as m; print(m.version('HieraChain'))"
    
    # Kiểm tra CLI đã có trong PATH
    hrc --help
    
    # Khởi động API server (tuỳ chọn)
    python -m hierachain.api.server
    ```

Nếu server khởi chạy thành công, bạn có thể mở tài liệu tương tác tại: `http://localhost:2661/docs`.

## Chạy Kiểm thử (Testing)

!!! warning "Cảnh báo"

    Không nên chạy tất cả các test cùng lúc để tránh xung đột tài nguyên. Khuyên dùng chạy theo từng file hoặc từng thư mục unit/integration.

```bash
# Chạy unit tests
python -m pytest tests/unit -v

# Chạy integration tests
python -m pytest tests/integration -v

# Chạy scenarios tests
python -m pytest tests/scenarios -v
```

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

Đảm bảo đã cài Zensical (dependencies cho docs):

=== "Sử dụng UV"

    ```bash
    uv sync --extra doc
    ```

=== "Sử dụng pip"

    ```bash
    pip install -e ".[doc]"
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
