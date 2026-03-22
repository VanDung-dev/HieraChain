# HieraChain - Sổ cái doanh nghiệp dựa trên công nghệ blockchain phân cấp

![Phiên bản Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![Giấy phép](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![Giấy phép](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
[![Phiên bản PyPI](https://img.shields.io/pypi/v/HieraChain.svg)](https://pypi.org/project/HieraChain/)

[English](README.md) | **Tiếng Việt**

## Tổng Quan

HieraChain là một sổ cái doanh nghiệp được xây dựng trên công nghệ blockchain phân cấp, được thiết kế đặc biệt cho các ứng dụng kinh doanh mà không có bất kỳ khái niệm tiền điện tử nào. Thay vì là một nền tảng blockchain mục đích chung tập trung vào tiền kỹ thuật số, HieraChain cung cấp một cấu trúc sổ cái phân cấp, an toàn để quản lý các hoạt động và quy trình kinh doanh.

Sổ cái này triển khai kiến trúc đa tầng phân cấp trong đó Main Chain giám sát các Sub-Chain, cho phép quản lý quy trình kinh doanh có khả năng mở rộng và an toàn. Tất cả các hoạt động trong hệ thống được gọi là "Event" thay vì "Giao dịch", nhấn mạnh sự tập trung vào các ứng dụng kinh doanh.

## Hệ Sinh Thái Dự Án

HieraChain là một phần của hệ sinh thái các công cụ blockchain lớn hơn:

| Dự án | Ngôn ngữ | Mô tả |
|-------|----------|-------|
| **[HieraChain](https://github.com/VanDung-dev/HieraChain)** | Python | Sổ cái blockchain phân cấp chính (repository này) |
| [HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus) | Rust | **Official Core Consensus** - triển khai tối ưu hóa với Python/C bindings |

> **Lưu ý**: Trong khi repository này bao gồm triển khai đồng thuận bằng Python thuần, thư viện [HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus) được khuyến nghị cho các triển khai production yêu cầu hiệu suất cao.

## Tính Năng Nổi Bật

- **Cấu Trúc Phân Cấp**: Kiến trúc đa tầng với Main Chain (Giám sát viên) và Sub-Chain (Chuyên gia Domain).
- **Cơ Chế Đồng Thuận**: Hỗ trợ Proof of Authority (PoA), Proof of Federation (PoF), và BFT.
- **Bảo Mật Cấp Doanh Nghiệp**: Chữ ký Ed25519, mã hóa AES-256-GCM, Quản lý chứng chỉ MSP và xác thực API Key mạnh mẽ.
- **Hiệu Suất Cao**: Lưu trữ dạng cột bằng Apache Arrow, hybrid cache và xử lý sự kiện đa luồng.
- **Độ Tin Cậy & Phục Hồi**: Ghi log sự kiện bền vững, tự động phục hồi lỗi, và khả năng khôi phục trạng thái linh hoạt.

## Tài Liệu (Documentation)

Kho tài liệu chi tiết có sẵn tại trang web chính thức **[docs.hierachain.org](https://docs.hierachain.org/)**:

- [Bắt đầu nhanh (Getting Started)](https://docs.hierachain.org/getting-started/install/) - Cài đặt và thiết lập cơ bản
- [Kiến trúc (Architecture)](https://docs.hierachain.org/architecture/overview/) - Thiết kế hệ thống và mô hình phân cấp
- [Thành phần hệ thống (Modules)](https://docs.hierachain.org/modules/core/) - Chi tiết về các module của hệ thống
- [Hướng dẫn (How-to Guides)](https://docs.hierachain.org/how-to/integrate-web2/) - Các bước hướng dẫn triển khai
- [Tài liệu tham khảo (Reference)](https://docs.hierachain.org/reference/code-map/) - API REST và cấu hình chi tiết

## Bắt Đầu Nhanh

### Cài Đặt

**Qua PIP (khuyên dùng)**

```bash
pip install HieraChain
```

**Từ mã nguồn (dành cho phát triển)**

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
python -m venv venv
source venv/bin/activate  # Linux/macOS (hoặc venv\Scripts\activate trên Windows)

# Cài đặt dependencies và dự án ở chế độ dev
pip install -r requirements.txt
pip install -e .
```

### Sử Dụng Cơ Bản

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
manager.create_sub_chain("supply_chain")

# Thêm một sự kiện
manager.add_event("supply_chain", {
    "entity_id": "PROD-001",
    "event": "production_complete",
    "timestamp": 1703088000.0,
    "details": {"quantity": 100}
})

# Gửi bằng chứng đến main chain
manager.submit_proof("supply_chain")
```

Chạy API Server:

```bash
python -m hierachain
```

API có sẵn tại `http://localhost:2661/docs`

## Thông Số Kỹ Thuật

| Thông số | Giá trị |
|----------|---------|
| Test Cases | >600 |
| Hỗ trợ Python | 3.10, 3.11, 3.12, 3.13 |
| Loại đồng thuận | PoA, PoF, BFT |
| Thuật toán ký | Ed25519 |
| Mã hóa | AES-256-GCM |

## Giấy Phép

Dự án này được cấp phép kép theo [Giấy phép Apache-2.0](LICENSE-APACHE) hoặc [Giấy phép MIT](LICENSE-MIT). Bạn có thể chọn một trong hai giấy phép.
