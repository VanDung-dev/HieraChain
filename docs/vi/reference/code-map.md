---
title: "Bản đồ mã nguồn"
description: "Ánh xạ Khái niệm - Mã nguồn giúp AI và Developer nhanh chóng định vị tệp mã."
icon: material/map
---

# Bản đồ mã nguồn

Tài liệu này ánh xạ các khái niệm trong tài liệu kỹ thuật tới các tệp mã nguồn cụ thể. Giúp AI và Developer nhanh chóng định vị vị trí code dựa trên ngữ cảnh.

## Kiến trúc cốt lõi (core architecture)

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| Blockchain (Base) | `hierachain/core/blockchain.py` | Lớp cơ sở quản lý chuỗi, thêm khối, kiểm tra tính toàn vẹn. |
| Block Structure | `hierachain/core/block.py` | Định nghĩa cấu trúc Block (Index, Hash, Data, Proof). |
| Main Chain | `hierachain/hierarchical/main_chain/base.py` | Chuỗi chính (Layer 1), chỉ lưu Proof và quản lý Sub-chain. |
| Sub Chain | `hierachain/hierarchical/sub_chain/base.py` | Chuỗi con (Layer 2), xử lý dữ liệu Domain và tạo Proof. |
| Hierarchy Manager | `hierachain/hierarchical/hierarchy_manager/base.py` | Bộ điều phối quản lý vòng đời Main/Sub-chain. |

## Consensus & Ordering

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| Ordering Service | `hierachain/consensus/ordering/service.py` | Nhận Event, sắp xếp thứ tự trước khi tạo Block. |
| Block Builder | `hierachain/consensus/ordering/block_builder.py` | Xây dựng khối từ các event đã sắp xếp. |
| Block Manager | `hierachain/consensus/ordering/block_manager.py` | Quản lý vòng đời khối trong hệ thống ordering. |
| Proof of Authority | `hierachain/consensus/proof_of_authority.py` | Cơ chế đồng thuận PoA (Intra-Organization). |
| Proof of Federation | `hierachain/consensus/proof_of_federation.py` | Cơ chế đồng thuận PoF (Inter-Organization Consortium). |

## API and interfaces

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| API Server | `hierachain/api/server.py` | Điểm khởi chạy server FastAPI. |
| API Ledger | `hierachain/api/ledger/router.py` | API cơ bản (Blocks, Chain info). |
| API Business | `hierachain/api/business/router.py` | API nâng cao (Events, Domain). |
| API Admin | `hierachain/api/admin/` | API hệ thống (Admin, Health). |
| WebSocket Manager | `hierachain/api/websocket/manager.py` | Quản lý kết nối WebSocket real-time. |
| IPFS Client | `hierachain/api/storage/ipfs_client.py` | Tích hợp lưu trữ off-chain (AES-256-GCM). |
| API server entry | `hierachain/__main__.py` | `python -m hierachain` khởi chạy API; `hrc` điều phối lệnh CLI. |
| SDK Client | `hierachain/sdk/client.py` | Thư viện Python để ứng dụng ngoài tương tác với Chain. |

## Security and identity

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| ZK Prover | `hierachain/security/zk_prover.py` | Mock phát triển; backend production chưa triển khai. |
| Key Manager | `hierachain/security/key_manager.py` | Quản lý khóa mật mã. |
| Key Provider | `hierachain/security/key_provider.py` | Cung cấp khóa cho Node. |
| Block Verifier | `hierachain/security/verify/block_verifier.py` | Kiểm tra tính toàn vẹn của Block. |
| Signature Verifier | `hierachain/security/verify/signature_verifier.py` | Kiểm tra chữ ký số. |

## Storage and persistence

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| SQLite Adapter | `hierachain/adapters/database/sqlite_adapter.py` | Lưu trữ database SQLite nhẹ, hiệu năng cao. |
| Redis Adapter | `hierachain/adapters/database/redis_adapter.py` | Key-value store cho caching và consensus state. |

## Network and cluster

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| Network Client | `hierachain/network/network_client.py` | Giao tiếp & Trao đổi dữ liệu giữa các Node. |
| ZMQ Transport | `hierachain/network/zmq_transport.py` | Giao thức nhắn tin qua ZeroMQ. |
| Cross-Chain Sync | `hierachain/cluster/cross_level_sync.py` | Đồng bộ dữ liệu chéo cấp (Main <-> Sub). |

## CLI and configuration

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| CLI Commands | `hierachain/cli/` | Các lệnh admin do `hierachain/cli/__init__.py` điều phối, gồm `key`. |
| Configuration | `hierachain/config/settings.py` | Quản lý biến môi trường và cấu hình hệ thống. |
| Logging Config | `hierachain/config/logging.py` | Cấu hình hệ thống logging tập trung. |

## Advanced modules

| Khái niệm | Đường dẫn File | Vai trò |
|-----------|----------------|---------|
| Error Mitigation | `hierachain/error_mitigation/` | Ghi nhật ký bền vững (EventJournal). |
| Domains | `hierachain/domains/` | Logic nghiệp vụ theo miền (chains, events, utils). |
| Versioning | `hierachain/config/version.py` | Quản lý phiên bản và semantic versioning. |
