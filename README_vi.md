# HieraChain Framework

![Phiên bản Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![Giấy phép](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![Giấy phép](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
![Phiên bản](https://img.shields.io/badge/version-0.0.1.dev2-orange)
![Tests](https://img.shields.io/badge/tests-371%20passed-green)

[English](README.md) | **Tiếng Việt**

## Tổng Quan

HieraChain là một framework blockchain doanh nghiệp tiên tiến được thiết kế đặc biệt cho các ứng dụng kinh doanh mà không có bất kỳ khái niệm tiền điện tử nào. Khác với các nền tảng blockchain truyền thống tập trung vào tiền kỹ thuật số, HieraChain tập trung vào việc cung cấp một cấu trúc phân cấp an toàn để quản lý các hoạt động và quy trình kinh doanh.

Framework triển khai kiến trúc đa tầng trong đó Main Chain giám sát các Sub-Chain, cho phép quản lý quy trình kinh doanh có khả năng mở rộng và an toàn. Tất cả các hoạt động trong framework được gọi là "sự kiện" (events) thay vì "giao dịch" (transactions), nhấn mạnh sự tập trung vào các ứng dụng kinh doanh.

## Hệ Sinh Thái Dự Án

HieraChain là một phần của hệ sinh thái các công cụ blockchain lớn hơn:

| Dự án | Ngôn ngữ | Mô tả |
|-------|----------|-------|
| **[HieraChain](https://github.com/VanDung-dev/HieraChain)** | Python | Framework blockchain phân cấp chính (repository này) |
| [HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus) | Rust | **Official Core Consensus** - triển khai tối ưu hóa với Python/C bindings |
| [HieraChain-Engine](https://github.com/VanDung-dev/HieraChain-Engine) | Go | Blockchain engine hiệu suất cao với mạng P2P |

> **Lưu ý**: Trong khi repository này bao gồm triển khai đồng thuận bằng Python thuần, thư viện [HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus) được khuyến nghị cho các triển khai production yêu cầu hiệu suất cao.

## Kiến Trúc Cốt Lõi

### Cấu Trúc Phân Cấp

Framework tuân theo kiến trúc phân cấp bao gồm:

1. **Main Chain (Giám sát viên)**
   - Hoạt động như cơ quan gốc trong hệ thống
   - Chỉ lưu trữ các bằng chứng mật mã từ Sub-Chain, không lưu dữ liệu domain chi tiết
   - Duy trì tính toàn vẹn của toàn bộ hệ thống phân cấp
   - Cung cấp xác minh bằng chứng và điều phối chuỗi

2. **Sub-Chains (Chuyên gia Domain)**
   - Xử lý các hoạt động kinh doanh theo domain cụ thể
   - Lưu trữ các sự kiện và dữ liệu domain chi tiết
   - Gửi bằng chứng mật mã đến Main Chain
   - Hoạt động độc lập nhưng được giám sát bởi Main Chain

```
Main Chain (Giám sát viên)
├── Sub-Chain 1 (Domain A)
├── Sub-Chain 2 (Domain B)
└── Sub-Chain 3 (Domain C)
```

### Nguyên Tắc Thiết Kế Chính

- **Mô hình Sự kiện**: Các hoạt động kinh doanh được biểu diễn dưới dạng "sự kiện" thay vì giao dịch tiền điện tử
- **Gửi Bằng chứng**: Sub-Chain gửi bằng chứng mật mã đến Main Chain để xác minh
- **Phân tách Dữ liệu**: Dữ liệu domain chi tiết ở lại Sub-Chain; chỉ bằng chứng đến Main Chain
- **Nhận dạng Thực thể**: Thực thể được nhận dạng thông qua các trường metadata
- **Khả năng Mở rộng**: Cấu trúc phân cấp cho phép mở rộng theo chiều ngang qua nhiều domain

## Cấu Trúc Module

### Core (`hierachain/core/`)

Nền tảng của HieraChain:

| Thành phần | Mô tả |
|------------|-------|
| `block.py` | Cấu trúc Block với lưu trữ Apache Arrow |
| `blockchain.py` | Triển khai blockchain cơ bản |
| `caching.py` | Hệ thống cache L1/L2 (chính sách LRU, LFU, TTL) |
| `parallel_engine.py` | Công cụ xử lý song song |
| `domain_contract.py` | Logic domain giống smart contract |
| `consensus/` | Proof of Authority & Proof of Federation |

### Hierarchical (`hierachain/hierarchical/`)

Quản lý đa chuỗi:

| Thành phần | Mô tả |
|------------|-------|
| `main_chain.py` | Cơ quan gốc lưu trữ bằng chứng |
| `sub_chain.py` | Chuỗi theo domain cụ thể |
| `hierarchy_manager.py` | Điều phối giữa các chuỗi |
| `channel.py` | Kênh riêng tư cho tổ chức |
| `multi_org.py` | Hỗ trợ đa tổ chức |
| `private_data.py` | Bộ sưu tập dữ liệu riêng tư |
| `consensus/bft_consensus.py` | Đồng thuận chống lỗi Byzantine |

### Security (`hierachain/security/`)

Bảo mật cấp doanh nghiệp:

| Thành phần | Mô tả |
|------------|-------|
| `msp.py` | Nhà cung cấp dịch vụ thành viên (MSP) |
| `certificate.py` | Quản lý chứng chỉ X.509 |
| `key_manager.py` | Quản lý khóa Ed25519 |
| `key_provider.py` | Lưu trữ khóa an toàn (FileVault) |
| `key_backup_manager.py` | Sao lưu & phục hồi khóa |
| `policy_engine.py` | Chính sách kiểm soát truy cập |
| `verify_api_key.py` | Xác thực API key |
| `identity.py` | Quản lý danh tính |

### Consensus (`hierachain/consensus/`)

Sắp xếp và đồng thuận:

| Thành phần | Mô tả |
|------------|-------|
| `ordering_service.py` | Sắp xếp sự kiện với hybrid cache |

### API (`hierachain/api/`)

Giao diện RESTful:

| Phiên bản | Mô tả |
|-----------|-------|
| `v1/` | Endpoint cốt lõi cho quản lý chuỗi |
| `v2/` | Endpoint nâng cao với ordering service |
| `blockchain_explorer.py` | API khám phá chuỗi |

### Error Mitigation (`hierachain/error_mitigation/`)

Chịu lỗi:

| Thành phần | Mô tả |
|------------|-------|
| `recovery_engine.py` | Phục hồi mạng, đồng thuận, sao lưu |
| `rollback_manager.py` | Khả năng hoàn tác trạng thái |
| `journal.py` | Nhật ký giao dịch (ghi log bền vững) |
| `validator.py` | Quy tắc xác thực dữ liệu |
| `error_classifier.py` | Phân loại & độ ưu tiên lỗi |

### Risk Management (`hierachain/risk_management/`)

| Thành phần | Mô tả |
|------------|-------|
| `risk_analyzer.py` | Phát hiện & chấm điểm rủi ro |
| `mitigation_strategies.py` | Giảm thiểu tự động |
| `audit_logger.py` | Ghi nhật ký kiểm toán toàn diện |

### Monitoring (`hierachain/monitoring/`)

| Thành phần | Mô tả |
|------------|-------|
| `performance_monitor.py` | Metrics hệ thống & blockchain |

### Storage (`hierachain/storage/`)

| Thành phần | Mô tả |
|------------|-------|
| `sql_backend.py` | Lưu trữ SQLite/PostgreSQL |
| `memory_storage.py` | Lưu trữ trong bộ nhớ |
| `world_state.py` | Quản lý world state |

### Integration (`hierachain/integration/`)

| Thành phần | Mô tả |
|------------|-------|
| `erp_framework.py` | Tích hợp hệ thống ERP |
| `enterprise.py` | Kết nối doanh nghiệp |

### Adapters (`hierachain/adapters/`)

| Thành phần | Mô tả |
|------------|-------|
| `storage/file_storage.py` | Adapter lưu trữ file |
| `storage/redis_storage.py` | Adapter lưu trữ Redis |

### Config (`hierachain/config/`)

| Thành phần | Mô tả |
|------------|-------|
| `settings.py` | Cấu hình dựa trên Python |

## Tính Năng Chính

### Cơ Chế Đồng Thuận

- **Proof of Authority (PoA)**: Đồng thuận dựa trên validator tĩnh cho triển khai tập trung
- **Proof of Federation (PoF)**: Đồng thuận dựa trên consortium động
- **BFT Consensus**: Đồng thuận chống lỗi Byzantine với hỗ trợ view change

### Bảo Mật

- **Chữ ký Ed25519**: Mật mã đường cong elliptic hiện đại
- **Mã hóa AES-256-GCM**: Cho dữ liệu riêng tư và sao lưu
- **MSP (Membership Service Provider)**: Xác thực dựa trên chứng chỉ
- **Xác thực API Key**: Với hỗ trợ thu hồi

### Hiệu Suất

- **Apache Arrow**: Lưu trữ dạng cột cho block
- **Hybrid Cache**: Cache bộ nhớ L1 + cache bền vững L2
- **Xử lý Song song**: Xử lý sự kiện đa luồng
- **Bounded History**: Lịch sử block hiệu quả bộ nhớ với fallback DB

### Độ Tin Cậy

- **Transaction Journal**: Ghi log sự kiện bền vững
- **Rollback Manager**: Khả năng khôi phục trạng thái
- **Recovery Engines**: Phục hồi lỗi tự động
- **371 Test Cases**: Bao phủ test toàn diện bao gồm fuzzing

## Bắt Đầu Nhanh

### Cài Đặt

> **Lưu ý**: HieraChain hiện đang trong giai đoạn phát triển. Dự kiến phát hành trên PyPI vào Quý 1 năm 2026.

#### Cài Đặt Local

```bash
# Clone repository
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain

# Tạo môi trường ảo (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# hoặc
venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Cài đặt dependencies cho phát triển
pip install -r requirements_dev.txt

# Cài đặt ở chế độ development
pip install -e .
```

### Sử Dụng Cơ Bản

```python
from hierachain.hierarchical import HierarchyManager

# Tạo hierarchy manager
manager = HierarchyManager()

# Tạo một sub-chain
manager.create_sub_chain("supply_chain")

# Thêm một sự kiện
event_id = manager.add_event("supply_chain", {
    "entity_id": "PROD-001",
    "event": "production_complete",
    "timestamp": 1703088000.0,
    "details": {"quantity": 100}
})

# Gửi bằng chứng đến main chain
proof = manager.submit_proof("supply_chain")
```

### Chạy API Server

```bash
python -m hierachain.api.server
```

API có sẵn tại `http://localhost:2661/docs`

## Trường Hợp Sử Dụng

HieraChain lý tưởng cho các ứng dụng doanh nghiệp yêu cầu:

- Quản lý chuỗi cung ứng
- Theo dõi tuân thủ quy định
- Duy trì dấu vết kiểm toán
- Điều phối quy trình làm việc đa phòng ban
- Chia sẻ dữ liệu an toàn giữa các tổ chức
- Quy trình đảm bảo chất lượng
- Theo dõi và quản lý tài sản

## Thông Số Kỹ Thuật

| Thông số | Giá trị |
|----------|---------|
| File mã nguồn | 96 file Python |
| Dòng code | ~30,000 |
| Test Cases | 371 |
| Hỗ trợ Python | 3.10, 3.11, 3.12, 3.13 |
| Loại đồng thuận | PoA, PoF, BFT |
| Thuật toán ký | Ed25519 |
| Mã hóa | AES-256-GCM |

## Cấu Hình

Cấu hình được quản lý thông qua `hierachain/config/settings.py`:

```python
from hierachain.config import settings

# Truy cập cài đặt
print(settings.API_PORT)  # 2661
print(settings.CONSENSUS_TYPE)  # proof_of_authority
print(settings.BFT_ENABLED)  # True
```

Biến môi trường:

- `HRC_ENV`: Môi trường (dev/test/product)
- `HRC_CONSENSUS_TYPE`: Loại đồng thuận
- `HRC_AUTH_ENABLED`: Bật xác thực API
- `LOG_LEVEL`: Cấp độ logging

## Giấy Phép

Dự án này được cấp phép kép theo [Giấy phép Apache-2.0](LICENSE-APACHE) hoặc [Giấy phép MIT](LICENSE-MIT). Bạn có thể chọn một trong hai giấy phép.

---
