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
| Policy | Chính sách | Kiểm soát truy cập/tài nguyên; `hierachain/security/policy_engine.py`, `hierachain/security/policy_types.py`. Không có `resource_guard.py`. |
| World State | World State | Trạng thái hiện tại của dữ liệu; `hierachain/state/world_state.py`. |
| Journal | Nhật ký | Ghi log giao dịch; `hierachain/error_mitigation/journal.py`. |
| Rollback | Hoàn tác | Khôi phục trạng thái; `hierachain/error_mitigation/rollback_manager.py`. |
| Recovery | Phục hồi | Phục hồi lỗi qua `hierachain/error_mitigation/rollback_manager.py`, `consensus_recovery.py`, `network_recovery.py` (không có `recovery_engine.py`). |
| Ordering | Sắp xếp | Xếp thứ tự Event; `hierachain/consensus/ordering/*`. |
| Transport | Truyền tải | Giao tiếp mạng; `hierachain/network/zmq_transport.py`. |
| Byzantine Fault Tolerance | BFT | Chịu lỗi Byzantine; `hierachain/consensus/bft/*`. |
| Proof of Authority | PoA | Đồng thuận trong một tổ chức; `hierachain/consensus/proof_of_authority.py`. |
| Proof of Federation | PoF | Đồng thuận liên minh P2P giữa các MainChain độc lập; `hierachain/consensus/proof_of_federation.py`. |
| API Key | API key | Khóa truy cập API; `hierachain/security/verify/api_key_verifier.py`. |
| Resource Guard | Resource Guard | Middleware bảo vệ tài nguyên; `hierachain/security/brute_force_protector.py`. |
| Entity Tracer | Truy vết thực thể | Truy vết sự kiện theo entity; `hierachain/domains/utils/entity_tracer.py`. |
| Zero‑Knowledge Proof | Bằng chứng ZK | ZK Proof; `hierachain/security/zk_prover.py`, `hierachain/security/verify/zk_verifier.py`. |
| Channel | Kênh | Kênh riêng tư giữa các tổ chức; `hierachain/hierarchical/channel/channel.py`. |
| Multi‑Organization | Đa tổ chức | Mạng nhiều tổ chức; `hierachain/hierarchical/multi_org.py`. |
| Private Data | Dữ liệu riêng tư | Bộ sưu tập dữ liệu riêng tư; `hierachain/hierarchical/private_data.py`. |
| Performance Monitor | Performance Monitor | Giám sát hiệu năng; `hierachain/monitoring/performance_monitor.py`. |
| Rate Limiting | Rate limit | Giới hạn tần suất yêu cầu; cấu hình trong `hierachain/config/settings.py`. |
| HTTP Strict Transport Security | HSTS | HSTS; `hierachain/config/settings.py`. |
| Cross‑Origin Resource Sharing | CORS | CORS; `hierachain/config/settings.py`. |
| Command Line Interface | CLI | CLI công cụ `hrc`; `hierachain/cli/*`. |
| API Ledger | API Ledger | REST API Ledger; `hierachain/api/ledger/*`. |
| API business | API business | REST API business; `hierachain/api/business/*`. |
| API Admin | API Admin | REST API Admin; `hierachain/api/admin/*`. |
| Cross‑level State Sync | Đồng bộ liên tầng | Đồng bộ qua `hierachain/cluster/cross_level_sync.py` + `hierarchical/hierarchy_manager/` + `HRC_CROSS_LEVEL_*`. |
| Identity Manager | Quản lý danh tính | Quản lý tổ chức/người dùng/role; `hierachain/security/identity.py`. |
| Certificate | Chứng chỉ | Dataclass `Certificate` nội bộ trong `hierachain/security/msp.py` (không phải X.509, không có `certificate.py`). |

Mục này sẽ tiếp tục cập nhật và là nguồn tham chiếu cho việc dịch sang tiếng Anh.
