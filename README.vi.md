# HieraChain - Ledger doanh nghiệp phân cấp

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
[![PyPI version](https://img.shields.io/pypi/v/HieraChain.svg)](https://pypi.org/project/HieraChain/)

[English](README.md) | **Tiếng Việt**

## Tổng quan

HieraChain là ledger Python dành cho event nghiệp vụ. Sub-Chain theo domain ghi event vào block có chữ ký và liên kết hash; MainChain neo proof của các block đó. `HierarchyManager` điều phối vòng đời chain, phục hồi và gửi proof.

## Các khả năng đã triển khai

* Bảng event Apache Arrow, truy vấn entity/event qua index và gom batch ordering bất đồng bộ.
* Chữ ký Ed25519 với bản đồ khóa tin cậy do operator cấp, storage SQLite/PostgreSQL bền vững và journal ordering.
* PoA mặc định; có thể cấu hình PoF với luân phiên validator. Thành phần BFT tách biệt với runtime MainChain/Sub-Chain.
* REST, GraphQL, WebSocket, client Python đồng bộ/bất đồng bộ và công cụ CLI.
* Xác thực API key khi được bật, policy organization/channel, audit log và payload IPFS mã hóa AES-256-GCM tùy chọn.

## Giới hạn hiện tại

* Tạo/xác minh ZK chỉ hỗ trợ mock phát triển; backend production chưa triển khai.
* Đăng ký contract giữ implementation hoặc tham chiếu CID và metadata trong bộ nhớ tiến trình API. Thực thi contract và ghi private data trả HTTP 501 cho tài nguyên đã đăng ký, hoặc HTTP 404 nếu contract/collection không tồn tại, sau khi kiểm tra request và quyền truy cập.
* Connector SAP/Oracle/Dynamics có sẵn yêu cầu `simulation_mode=True` và cung cấp fixture mô phỏng. Ứng dụng phải cung cấp adapter ERP thật.
* Redis hỗ trợ adapter phụ trợ nhưng chưa làm backend block bền vững cho hierarchy.
* Xác thực block PoF thông thường kiểm tra chữ ký leader; đường này chưa tự thu thập quorum nhiều bên hoặc cung cấp failover.
* Subscription WebSocket nhận thông báo qua các hàm broadcast; ứng dụng phải nối các hàm này với event ledger và quá trình commit block.
* Route REST cho event và contract nhận dữ liệu inline hoặc tham chiếu CID IPFS đã có. Ứng dụng phải chủ động upload payload off-chain; các route này chưa tự chuyển payload lớn lên IPFS.

Xem [phạm vi tính năng](docs/vi/modules/hierarchical.md) và [phạm vi đồng thuận](docs/vi/workflows/consensus_mechanisms.md).

## Bắt đầu nhanh

### Cài từ mã nguồn

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev
source .venv/bin/activate
```

Nếu không dùng uv, tạo và kích hoạt `.venv`, rồi cài:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Với package đã phát hành, dùng `python -m pip install HieraChain`. Bản phát hành có thể khác checkout mã nguồn hiện tại. Dependency cơ bản và extra `dev`/`doc` được khai báo trong `pyproject.toml`.

### Cấu hình và sử dụng ledger

Trước tiên hoàn thành [thiết lập identity ký và SQLite cục bộ](docs/vi/getting-started/quickstart.md). Hướng dẫn tạo identity cố định, bản đồ khóa tin cậy và biến môi trường. Chạy phần thiết lập và ví dụ trong cùng một thư mục làm việc trống; đường dẫn SQLite và journal ordering được tính theo thư mục đó:

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
try:
    assert manager.create_sub_chain("supply_chain", "supply_chain")
    chain = manager.get_sub_chain("supply_chain")
    assert chain.register_entity("PROD-001", {"product": "sample"})
    assert manager.start_operation(
        "supply_chain", "PROD-001", "production_start", {"quantity": 100}
    )
    chain.flush_pending_and_finalize(timeout=10.0)
    assert any(
        event["event"] == "operation_start"
        for event in chain.get_events_by_entity("PROD-001")
    )
    assert manager.submit_proof_to_main_chain("supply_chain")
finally:
    manager.close()
```

Xác nhận nhận event là xác nhận ordering, chưa phải block finality. Ví dụ này chủ động xử lý ordering và kiểm tra event entity đã hoàn tất trước khi gửi proof bền vững.

PoA mặc định `HRC_BLOCK_INTERVAL=0`; batching vẫn ảnh hưởng latency. PoF giữ interval riêng là 5 giây. Đo throughput event đã commit và latency p95/p99 theo [hướng dẫn hiệu năng](docs/vi/guides/performance.md).

### Khởi động API

Dùng môi trường đã cấu hình theo hướng dẫn bắt đầu nhanh:

```bash
python -m hierachain
```

Mở `http://localhost:2661/docs`. Kiểm tra `/api/ledger/ready` để xác nhận phục hồi hierarchy. Quickstart cục bộ tắt xác thực API key bằng `HRC_AUTH_ENABLED=false`; production yêu cầu bật xác thực, cấp API key và identity ký. Xem [cấu hình](docs/vi/reference/config.md).

## Tài liệu

* [Tài liệu tiếng Anh](https://docs.hierachain.org/) · [Tài liệu tiếng Việt](https://docs.hierachain.org/vi/)
* [Cài đặt](docs/vi/getting-started/install.md) · [Kiến trúc](docs/vi/architecture/overview.md)
* [REST Ledger API](docs/vi/reference/api-ledger.md) · [Python SDK](docs/vi/reference/sdk-reference.md)
* [Kiểm thử](docs/vi/dev/testing.md) · [Build tài liệu](docs/README.md)

## Phạm vi kỹ thuật

| Thành phần | Triển khai hiện tại |
|------------|---------------------|
| Python | 3.10, 3.11, 3.12, 3.13, 3.14 |
| Đồng thuận phân cấp | PoA / PoF; thành phần BFT riêng |
| Chữ ký block | Ed25519, kể cả genesis |
| Storage hierarchy | SQLite / PostgreSQL |
| Mã hóa off-chain | IPFS AES-256-GCM tùy chọn |

## Giấy phép

Cấp phép kép theo [Apache-2.0](LICENSE-APACHE) hoặc [MIT](LICENSE-MIT). Bạn có thể chọn một trong hai.
