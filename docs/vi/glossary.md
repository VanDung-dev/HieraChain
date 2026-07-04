---
title: Thuật ngữ (VI/EN)
description: Bảng thuật ngữ dùng trong tài liệu, duy trì nhất quán dịch Việt ↔ Anh.
icon: material/alphabetical
---

# Thuật ngữ

Ghi chú: Khi một thuật ngữ xuất hiện lần đầu trong mỗi trang, cần kèm định nghĩa ngắn gọn và liên kết về đây.

| Thuật ngữ | Tiếng Việt | Mô tả |
|---|---|---|
| Chain | Chuỗi | Chuỗi khối logic gồm các Block; HieraChain có Main Chain và Sub-Chain. |
| Block | Khối | Đơn vị dữ liệu chứa Event; định nghĩa trong `hierachain/core/block.py`. |
| Blockchain | Chuỗi khối | Quản trị chuỗi Block; `hierachain/core/blockchain.py`. |
| Consensus | Đồng thuận | Cơ chế chấp thuận Block (PoA, PoF, BFT); `hierachain/consensus/*`, `hierachain/hierarchical/consensus/*`. |
| Membership Service Provider | MSP | Quản lý danh tính/tổ chức; `hierachain/security/msp.py`, `hierachain/security/identity.py`. |
| Policy | Chính sách | Kiểm soát truy cập/tài nguyên; `hierachain/security/policy_engine.py`, `hierachain/security/resource_guard.py`. |
| World State | World State | Trạng thái hiện tại của dữ liệu; `hierachain/state/world_state.py`. |
| Journal | Nhật ký | Ghi log giao dịch; `hierachain/error_mitigation/journal.py`. |
| Rollback | Hoàn tác | Khôi phục trạng thái; `hierachain/error_mitigation/rollback_manager.py`. |
| Recovery | Phục hồi | Cơ chế phục hồi lỗi; `hierachain/error_mitigation/recovery_engine.py`. |
| Ordering | Sắp xếp | Xếp thứ tự Event; `hierachain/consensus/ordering/*`. |
| Transport | Truyền tải | Giao tiếp mạng; `hierachain/network/zmq_transport.py`. |
| Byzantine Fault Tolerance | BFT | Chịu lỗi Byzantine; `hierachain/consensus/bft/*`. |
| Proof of Authority | PoA | Đồng thuận validator tĩnh; `hierachain/consensus/proof_of_authority.py`. |
| Proof of Federation | PoF | Đồng thuận liên minh; `hierachain/consensus/proof_of_federation.py`. |
| API Key | API key | Khóa truy cập API; `hierachain/security/verify/api_key_verifier.py`. |
| Resource Guard | Resource Guard | Middleware bảo vệ tài nguyên; `hierachain/security/resource_guard.py`. |
| Entity Tracer | Truy vết thực thể | Truy vết Event theo thực thể; `hierachain/domains/generic/utils/entity_tracer.py`. |
| Zero‑Knowledge Proof | Bằng chứng ZK | Bằng chứng không tiết lộ; `hierachain/security/zk_prover.py`, `hierachain/security/verify/zk_verifier.py`. |
| Proof Aggregation | Gộp bằng chứng | Gộp/đóng gói nhiều proof; `hierachain/hierarchical/proof_aggregation.py`. |
| Rebalancer | Rebalancer | Tự động chia tách/cân bằng Sub‑Chain; `hierachain/hierarchical/rebalancer.py`. |
| Channel | Kênh | Kênh riêng tư liên tổ chức; `hierachain/hierarchical/channel.py`. |
| Multi‑Organization | Đa tổ chức | Mạng đa tổ chức; `hierachain/hierarchical/multi_org.py`. |
| Private Data | Dữ liệu riêng tư | Bộ sưu tập dữ liệu riêng tư; `hierachain/hierarchical/private_data.py`. |
| Performance Monitor | Performance Monitor | Giám sát hiệu năng; `hierachain/monitoring/performance_monitor.py`. |
| Rate Limiting | Rate limit | Giới hạn tốc độ request; cấu hình trong `hierachain/config/settings.py`. |
| HTTP Strict Transport Security | HSTS | Chính sách bắt buộc HTTPS; `hierachain/config/settings.py`. |
| Cross‑Origin Resource Sharing | CORS | Cấu hình nguồn gốc chéo; `hierachain/config/settings.py`. |
| Command Line Interface | CLI | Công cụ dòng lệnh `hrc`; `hierachain/cli/*`. |
| API Ledger | API Ledger | REST API Ledger; `hierachain/api/ledger/*`. |
| API business | API business | REST API business; `hierachain/api/business/*`. |
| API Admin | API Admin | REST API Admin; `hierachain/api/admin/*`. |
| Cross‑level State Sync | Đồng bộ liên tầng | Đồng bộ trạng thái giữa các tầng; `hierachain/cluster/state_sync_manager.py`. |
| Kubernetes Namespace | Kubernetes Namespace | Cô lập Sub‑Chain theo namespace; `hierachain/hierarchical/k8s_namespace_manager.py`. |
| Identity Manager | Quản lý danh tính | Quản lý tổ chức/người dùng/role; `hierachain/security/identity.py`. |
| Certificate | Chứng chỉ | Quản lý chứng chỉ X.509; `hierachain/security/certificate.py`. |

Mục này sẽ tiếp tục cập nhật và là nguồn tham chiếu cho việc dịch sang tiếng Anh.
