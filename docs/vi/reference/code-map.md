---
title: "Codebase Map"
description: "Bản đồ ánh xạ Concepts sang Source Code giúp AI và Developer định vị nhanh file mã nguồn."
icon: material/map
---

# Codebase Map

Tài liệu này ánh xạ các khái niệm (Concepts) trong tài liệu kỹ thuật sang các file mã nguồn (Source Code) cụ thể. Mục đích giúp AI và Developer nhanh chóng định vị code dựa trên ngữ cảnh.

## Kiến trúc lõi

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **Blockchain (Base)** | `hierachain/core/blockchain.py` | Lớp cơ sở quản lý chuỗi, thêm block, kiểm tra tính toàn vẹn. |
| **Block Structure** | `hierachain/core/block.py` | Định nghĩa cấu trúc Block (Index, Hash, Data, Proof). |
| **Main Chain** | `hierachain/hierarchical/main_chain.py` | Chuỗi chính (Layer 1), chỉ lưu Proof và quản lý Sub-chain. |
| **Sub Chain** | `hierachain/hierarchical/sub_chain.py` | Chuỗi con (Layer 2), xử lý dữ liệu Domain và tạo Proof. |
| **Hierarchy Manager** | `hierachain/hierarchical/hierarchy_manager.py` | Điều phối viên quản lý vòng đời Main/Sub-chain. |

## Consensus & Ordering

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **Ordering Service** | `hierachain/consensus/ordering/service.py` | Tiếp nhận Event, sắp xếp thứ tự trước khi đóng Block. |
| **Block Builder** | `hierachain/consensus/ordering/block_builder.py` | Xây dựng block từ các transaction đã được sắp xếp. |
| **Block Manager** | `hierachain/consensus/ordering/block_manager.py` | Quản lý lifecycle của block trong hệ thống ordering. |
| **Proof of Authority** | `hierachain/consensus/proof_of_authority.py` | Cơ chế đồng thuận PoA (dùng cho Dev/Testnet). |
| **Proof of Federation** | `hierachain/consensus/proof_of_federation.py` | Cơ chế đồng thuận PoF (đa tổ chức). |
| **BFT Consensus** | `hierachain/hierarchical/consensus/bft_consensus.py` | Đồng thuận chịu lỗi Byzantine (cho môi trường Production). |

## API & Interfaces

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **API Server** | `hierachain/api/server.py` | Điểm khởi chạy FastAPI server. |
| **Endpoints V1** | `hierachain/api/v1/endpoints.py` | Các API cơ bản (Blocks, Chain info). |
| **CLI Entry** | `hierachain/__main__.py` | Điểm vào của dòng lệnh `python -m hierachain`. |
| **SDK Client** | `hierachain/sdk/client.py` | Thư viện Python để ứng dụng bên ngoài tương tác với Chain. |

## Security & Identity

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **MSP (Membership)** | `hierachain/security/msp.py` | Quản lý định danh (Identity) và chứng chỉ thành viên. |
| **ZK Prover** | `hierachain/security/zk_prover.py` | Tạo bằng chứng Zero-Knowledge (bảo mật dữ liệu). |
| **Policy Engine** | `hierachain/security/policy_engine.py` | Thực thi các quy tắc truy cập (Access Control). |
| **Key Manager** | `hierachain/security/key_manager.py` | Quản lý khóa Cryptographic. |

## Storage & Persistence

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **SQLite Adapter** | `hierachain/adapters/database/sqlite_adapter.py` | Lưu trữ dữ liệu vào SQLite (SQLAlchemy). |
| **Redis Storage** | `hierachain/adapters/storage/redis_storage.py` | Lưu trữ tạm thời/Cache hiệu năng cao. |
| **SQL Backend** | `hierachain/storage/sql_backend.py` | Lớp trừu tượng hóa tương tác SQL. |

## Network & Cluster

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **Network Client** | `hierachain/network/network_client.py` | Client giao tiếp mạng lưới (P2P). |
| **Secure Connection** | `hierachain/network/secure_connection.py` | Thiết lập kết nối bảo mật giữa các node. |
| **Cluster Manager** | `hierachain/cluster/cluster_manager.py` | Quản lý trạng thái và thành viên trong cụm. |
| **State Sync** | `hierachain/cluster/state_sync_manager.py` | Đồng bộ trạng thái giữa các node trong cụm. |
| **Lockdown Protocol** | `hierachain/cluster/lockdown_protocol.py` | Giao thức khóa cụm khi phát hiện sự cố nghiêm trọng. |

## Giám sát & Quản lý rủi ro

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **Alert System** | `hierachain/monitoring/alert_system.py` | Hệ thống cảnh báo thời gian thực. |
| **Performance Monitor**| `hierachain/monitoring/performance_monitor.py` | Giám sát hiệu năng hệ thống (CPU, RAM, TPS). |
| **Risk Analyzer** | `hierachain/risk_management/risk_analyzer.py` | Phân tích rủi ro dựa trên hành vi hệ thống. |
| **Audit Logger** | `hierachain/risk_management/audit_logger.py` | Ghi nhật ký kiểm toán phục vụ truy vết. |

## CLI  & Cấu hình

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **CLI Commands** | `hierachain/cli/` | Các lệnh quản trị: `chain`, `node`, `event`, `verify`. |
| **Configuration** | `hierachain/config/settings.py` | Quản lý biến môi trường và cấu hình hệ thống. |
| **Logging Config** | `hierachain/config/logging.py` | Cấu hình hệ thống ghi log tập trung. |

## Mô-đun nâng cao

| Concept | File Path | Vai trò chính |
|---------|-----------|---------------|
| **Cross-Chain** | `hierachain/cluster/cross_level_sync.py` | Đồng bộ dữ liệu giữa các cấp (Main <-> Sub). |
| **Error Mitigation** | `hierachain/error_mitigation/` | Cơ chế tự phục hồi (Rollback, Journal). |
| **Integration (ERP)** | `hierachain/integration/enterprise.py` | Kết nối với hệ thống doanh nghiệp bên ngoài. |

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**
    
    * Tài liệu này đóng vai trò "Index" giúp AI định vị context khi đọc code.
    * Cấu trúc thư mục phản ánh kiến trúc Modular Monolith.

    **DECISION**
    
    * Gom nhóm module theo chức năng nghiệp vụ (Business Capability) thay vì lớp kỹ thuật.
    * Duy trì sự tách biệt rõ ràng giữa `core` (dùng chung) và `hierarchical` (logic phân cấp).

    **ASSUMPTION**
    
    * Các file path được liệt kê là tương đối so với root project.
    * AI Agent phải tra cứu bảng này trước khi thực hiện các thay đổi kiến trúc.

    **INVARIANT**
    
    * **Immutability**: Block đã commit là bất biến, không được sửa đổi (`add_block`).
    * **Hierarchy**: Sub-chain **phải** gửi Proof lên Main-chain; Main-chain **không** lưu dữ liệu thô.
    * **Ordering**: Mọi Event phải đi qua `OrderingService` để lấy `sequence_number`.
    * **Error Handling**: Mọi lỗi Logic phải raise `HieraChainError` (hoặc subclass).
