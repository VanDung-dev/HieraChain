---
title: "Bản đồ Mã nguồn"
description: "Bảng ánh xạ Khái niệm - Mã nguồn giúp AI và Nhà phát triển nhanh chóng định vị các file mã nguồn."
icon: material/map
---

# Bản đồ Mã nguồn (Codebase Map)

Tài liệu này ánh xạ các khái niệm trong tài liệu kỹ thuật sang các file mã nguồn cụ thể. Nó giúp AI và các Nhà phát triển nhanh chóng định vị vị trí code dựa trên ngữ cảnh.

## Kiến trúc Cốt lõi

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **Blockchain (Base)** | `hierachain/core/blockchain.py` | Lớp cơ sở quản lý chuỗi, thêm block, kiểm tra tính toàn vẹn. |
| **Block Structure** | `hierachain/core/block.py` | Định nghĩa cấu trúc Block (Index, Hash, Data, Proof). |
| **Main Chain** | `hierachain/hierarchical/main_chain/base.py` | Chuỗi chính (Layer 1), chỉ lưu Proof và quản lý Sub-chain. |
| **Sub Chain** | `hierachain/hierarchical/sub_chain/base.py` | Chuỗi con (Layer 2), xử lý dữ liệu Domain và tạo Proof. |
| **Hierarchy Manager** | `hierachain/hierarchical/hierarchy_manager/base.py` | Điều phối viên quản lý vòng đời Main/Sub-chain. |

## Đồng thuận & Sắp xếp (Consensus & Ordering)

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **Ordering Service** | `hierachain/consensus/ordering/service.py` | Tiếp nhận Event, sắp xếp thứ tự trước khi đóng Block. |
| **Block Builder** | `hierachain/consensus/ordering/block_builder.py` | Xây dựng block từ các transaction đã được sắp xếp. |
| **Block Manager** | `hierachain/consensus/ordering/block_manager.py` | Quản lý lifecycle của block trong hệ thống ordering. |
| **Proof of Authority** | `hierachain/consensus/proof_of_authority.py` | Cơ chế đồng thuận PoA (Nội bộ 1 Doanh nghiệp). |
| **Proof of Federation** | `hierachain/consensus/proof_of_federation.py` | Cơ chế đồng thuận PoF (Liên minh các MainChain đa tổ chức). |
| **BFT Consensus** | `hierachain/consensus/bft/consensus.py` | Đồng thuận chịu lỗi Byzantine (cho môi trường Production). |

## API & Giao diện

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **API Server** | `hierachain/api/server.py` | Điểm khởi chạy FastAPI server. |
| **API Ledger** | `hierachain/api/ledger/router.py` | Các API cơ bản (Blocks, Chain info). |
| **API Business** | `hierachain/api/business/router.py` | API nâng cao (Events, Domain). |
| **API Admin** | `hierachain/api/admin/` | API hệ thống (Admin, Health). |
| **WebSocket Manager** | `hierachain/api/websocket/manager.py` | Quản lý kết nối WebSocket thời gian thực. |
| **GraphQL Schema** | `hierachain/api/graphql/schema.py` | Schema GraphQL cho truy vấn linh hoạt. |
| **IPFS Client** | `hierachain/api/storage/ipfs_client.py` | Tích hợp lưu trữ Off-chain (AES-256-GCM). |
| **Blockchain Explorer** | `hierachain/api/blockchain_explorer.py` | Giao diện phân tích và hiển thị chuỗi. |
| **CLI Entry** | `hierachain/__main__.py` | Điểm vào của dòng lệnh `python -m hierachain`. |
| **SDK Client** | `hierachain/sdk/client.py` | Thư viện Python để ứng dụng bên ngoài tương tác với Chain. |

## Bảo mật & Định danh

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **MSP (Membership)** | `hierachain/security/msp.py` | Quản lý định danh và chứng chỉ thành viên. |
| **ZK Prover** | `hierachain/security/zk_prover.py` | Tạo bằng chứng Không tiết lộ kiến thức (Bảo mật dữ liệu). |
| **Policy Engine** | `hierachain/security/policy_engine.py` | Thực thi các quy tắc kiểm soát truy cập. |
| **Key Manager** | `hierachain/security/key_manager.py` | Quản lý các khóa mã hóa. |
| **Key Provider** | `hierachain/security/key_provider.py` | Cung cấp khóa cho Node. |
| **Block Verifier** | `hierachain/security/verify/block_verifier.py` | Xác thực tính toàn vẹn của Block. |
| **Signature Verifier** | `hierachain/security/verify/signature_verifier.py` | Xác thực chữ ký số. |

## Lưu trữ & Duy trì Dữ liệu

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **SQLite Adapter** | `hierachain/adapters/database/sqlite_adapter.py` | Bộ lưu trữ cơ sở dữ liệu SQLite nhẹ, hiệu năng cao. |
| **Redis Adapter** | `hierachain/adapters/database/redis_adapter.py` | Bộ lưu trữ Key-Value cho caching và trạng thái đồng thuận. |

## Mạng & Cụm (Network & Cluster)

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **Network Client** | `hierachain/network/network_client.py` | Giao tiếp & Trao đổi dữ liệu giữa các Node. |
| **ZMQ Transport** | `hierachain/network/zmq_transport.py` | Giao thức truyền tin trên nền ZeroMQ. |
| **Message Crypto** | `hierachain/network/message_cryptographic.py` | Mã hóa tin nhắn giữa các Node. |
| **Peer Trust Manager** | `hierachain/network/peer_trust_manager.py` | Quản lý độ tin cậy Peer-to-Peer. |
| **Secure Connection** | `hierachain/network/secure_connection.py` | Thiết lập kết nối an toàn giữa các node. |
| **Cluster Manager** | `hierachain/cluster/cluster_manager.py` | Quản lý trạng thái và thành viên trong cụm. |
| **State Sync** | `hierachain/cluster/state_sync_manager.py` | Đồng bộ trạng thái giữa các node trong cụm. |
| **Lockdown Protocol** | `hierachain/cluster/lockdown_protocol.py` | Giao thức phong tỏa cụm khi phát hiện sự cố nghiêm trọng. |
| **Cross-Chain Sync** | `hierachain/cluster/cross_level_sync.py` | Đồng bộ dữ liệu liên tầng (Main <-> Sub). |

## Giám sát & Quản lý Rủi ro

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **Alert System** | `hierachain/monitoring/alert_system.py` | Hệ thống cảnh báo thời gian thực. |
| **Performance Monitor**| `hierachain/monitoring/performance_monitor.py` | Giám sát hiệu năng hệ thống (CPU, RAM, TPS). |
| **Risk Analyzer** | `hierachain/risk_management/risk_analyzer.py` | Phân tích rủi ro dựa trên hành vi hệ thống. |
| **Audit Logger** | `hierachain/risk_management/audit_logger.py` | Ghi nhật ký kiểm toán cho khả năng truy vết. |

## CLI & Cấu hình

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **CLI Commands** | `hierachain/cli/` | Các lệnh quản trị: `chain`, `node`, `event`, `verify`. |
| **Configuration** | `hierachain/config/settings.py` | Quản lý biến môi trường và cấu hình hệ thống. |
| **Logging Config** | `hierachain/config/logging.py` | Cấu hình hệ thống ghi log tập trung. |

## Các Module Nâng cao

| Khái niệm | Đường dẫn File | Vai trò |
|---------|-----------|------|
| **Error Mitigation** | `hierachain/error_mitigation/` | Cơ chế tự phục hồi (Rollback, Journal). |
| **Integration (ERP)** | `hierachain/integration/enterprise.py` | Kết nối tới các hệ thống doanh nghiệp bên ngoài. |
| **Domains** | `hierachain/domains/` | Logic nghiệp vụ đặc thù tên miền (chains, events, utils). |
| **Units** | `hierachain/units/` | Quản lý phiên bản và Semantic Versioning. |
