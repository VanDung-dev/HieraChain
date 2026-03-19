---
title: Kiến trúc Triển khai (Deployment Architecture)
description: Mô hình triển khai HieraChain, cấu hình mạng ZMQ, và hướng dẫn vận hành Kubernetes để đảm bảo High Availability.
icon: material/server-network
---

# Kiến trúc Triển khai (Deployment Architecture)

Tài liệu này mô tả chi tiết các mô hình triển khai của HieraChain, cách cấu hình mạng, và hướng dẫn vận hành hệ thống trên môi trường Kubernetes để đảm bảo tính sẵn sàng cao (High Availability) cũng như khả năng mở rộng ở cấp độ doanh nghiệp (Enterprise-ready).

---

## 1. Mô hình triển khai Multi-Node (BFT Topology)

HieraChain hỗ trợ giao thức đồng thuận BFT (Byzantine Fault Tolerance) nhằm đảm bảo hệ thống vẫn hoạt động chính xác ngay cả khi có một số node bị lỗi hoặc có hành vi gian lận.

### Cấu hình BFT Tiêu chuẩn (Ví dụ: 4 Nodes)

Mô hình triển khai tối thiểu để BFT có thể chống chịu được 1 node lỗi (***f=1***) yêu cầu ít nhất ***3f + 1 = 4*** nodes.

Cấu trúc Topology cho một Sub-Chain:

- **Node 0 (Leader ban đầu)**: Nhận transaction, đóng block và khởi tạo các bước đồng thuận (Pre-prepare).
- **Node 1, Node 2, Node 3 (Validators)**: Tham gia vào các vòng Prepare và Commit để xác thực block.

Trong quá trình triển khai, cần thiết lập danh sách các peer (thông qua biến môi trường `PEERS`) trên mỗi node để chúng tạo thành một mạng liên kết ngang hàng (P2P Mesh Network).

---

## 2. Cấu hình Mạng (Network Configuration)

Để các node trong mạng có thể giao tiếp, hệ thống sử dụng **ZeroMQ TCP transport** và giao thức **HTTP REST API** qua `FastAPI` (hoặc cấu hình thủ công cổng riêng biệt cho API).

- **Cổng (Ports) tiêu chuẩn mặc định**:
  - **API Port** (`2661`): Dùng cho GraphQL API, REST API, và cho các external client (SDK/CLI) gửi sự kiện vào chuỗi. (Tham chiếu `api_port: int = 2661`).
  - **Node Port** (`5001` - `50xx`): Cổng ZeroMQ (ZMQ) nội bộ dành cho việc đồng thuận (Consensus P2P), trao đổi tin nhắn chữ ký và block giữa các validator. (Tham chiếu `node_port: int = 5001`).

- **Quy tắc Ingress / Egress (Firewall Rules)**:
  - **Ingress**: Chỉ mở port `2661` ra Internet hoặc Load Balancer nếu cần public API. Cổng `5001` chỉ nên được cấu hình chặn nội bộ lưới mạng đám mây (VPC/Subnet).
  - **Egress**: Cần cho phép các node gọi ra HTTP(s) (port `443/80`) nếu có tích hợp ERP, và gọi port ZeroMQ nội bộ (`5001` - `50xx`) của các Node khác.

---

## 3. Triển khai qua Kubernetes (K8s Orchestration)

Với HieraChain, môi trường Kubernetes là lựa chọn hàng đầu cho quản lý Sub-chain. Hệ thống tích hợp sẵn component **`K8sNamespaceManager`** nhằm cung cấp:

- **Nguyên lý Cách ly (Isolation)**: Mỗi Sub-chain được cấp phát một **Namespace** riêng biệt. Sự cố rò rỉ bộ nhớ, quá tải tài nguyên ở một Sub-chain sẽ không lây lan sang Sub-chain khác.
- **Microservice Lifecycle**: Sử dụng K8s Deployment để quản lý Pods.

### Quản lý Namespace & Resource Limits

Khi tạo mới một Sub-chain thông qua `HierarchyManager`, hệ thống sẽ tự động gửi yêu cầu đến `K8sNamespaceManager` để cấp phát Deployment với cấu hình giới hạn (Quota) như sau:

- **Tài nguyên Yêu cầu (Requests):**
  - **CPU:** `250m` (Đảm bảo số lượng core tối thiểu cần thiết để Arrow xử lý event).
  - **Memory:** `256Mi`.
- **Tài nguyên Giới hạn (Limits):**
  - **CPU:** `1000m` (1 vCPU). Tận dụng module `parallel_engine.py` cho đa luồng.
  - **Memory:** `1Gi` (Tránh Out-of-Memory do In-memory Storage tràn ngập).

### Lifecycle Management

Thông qua API hoặc SDK, người quản trị có thể:

1. **Provisioning**: Gọi `K8sNamespaceManager.provision_sub_chain_deployment(deploy_config)` truyền vào số lượng `replicas`.
2. **Monitoring**: Giám sát lượng Pod đang `ACTIVE`, lấy `resource_quotas` thông qua hàm `get_namespace_resources`.
3. **Termination**: Khi một Sub-chain ngừng hoạt động, `delete_namespace` sẽ được gọi để dọn sạch toàn bộ Pods, Volume (nếu có) mà không ảnh hưởng Main-chain.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/*` (Python >= 3.10 theo `pyproject.toml`).
    * Script CLI: `hrc` (định nghĩa tại `[project.scripts]` trong `pyproject.toml`).
    * API server: `hierachain/api/server.py` (có thể chạy bằng `python -m hierachain.api.server`).

    **DECISION**

    * Dùng Markdown, tách rõ các khối FACT / DECISION / ASSUMPTION / INVARIANT / EDGE CASES.
    * Tổ chức nội dung theo khung chuẩn thống nhất.

    **ASSUMPTION**

    * Người đọc đã cài Python 3.10+ và có quyền truy cập internet để cài dependencies.
    * Môi trường phát triển sử dụng `venv` hoặc công cụ tương đương.

    **INVARIANT**

    * FACT phải bám sát mã nguồn hiện tại (tên file, chữ ký API, đường dẫn).
    * Không pha trộn nội dung tiếp thị trong tài liệu kỹ thuật.

    **EDGE CASES**

    * Khác biệt shell giữa Windows (PowerShell) và Linux/macOS (bash) khi kích hoạt venv.
    * Mạng nội bộ hạn chế có thể ảnh hưởng quá trình cài gói.
