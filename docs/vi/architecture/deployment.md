---
title: Kiến trúc Triển khai (Deployment Architecture)
description: Mô hình triển khai HieraChain, cấu hình mạng ZMQ, tài nguyên Kubernetes và giới hạn vận hành hiện tại.
icon: material/server-network
---

# Kiến trúc Triển khai (Deployment Architecture)

## Giới hạn runtime

Một process API khởi tạo `HierarchyManager` gồm MainChain và các Sub-Chain đã đăng ký. MainChain/Sub-Chain dùng PoA hoặc PoF; engine BFT là thành phần riêng cần tích hợp rõ ràng. Chỉ triển khai bốn replica API không tạo PBFT finality hoặc failover leader. Xem [Phạm vi đồng thuận](../workflows/consensus_mechanisms.md).

## Mạng và cấu hình

| Cấu hình | Mặc định runtime | Mục đích |
|----------|------------------|----------|
| `HRC_API_PORT` | `2661` | API REST, GraphQL và WebSocket |
| `HRC_P2P_PORT` | `5555` | Transport ZeroMQ; manifest container ghi đè |
| `HRC_PEERS` | Rỗng | Seed peer phân tách dấu phẩy; `peer-id@host:port` định danh peer |
| `HRC_P2P_ENABLED` | `true` | Khởi động lớp mạng trong lifecycle API |

Dùng `python -m hierachain` hoặc `hrc node start`. Cấp identity riêng, trusted block key, API key production và credential SQL trước khi khởi động. Phản hồi health là liveness; readiness dùng `/api/ledger/ready`. Lưu bền database và journal `data/` từng node. Registry SQL dùng chung không loại bỏ yêu cầu quyền sở hữu writer của journal ordering.

Terminate HTTPS và cấu hình giới hạn truy cập công khai ở gateway. Giới hạn P2P trong mạng dự kiến. `ProductionSettings` đặt `P2P_TRUST_POLICY = "strict"` và `P2P_REQUIRE_SIGNATURES = True`, nhưng luồng khởi động P2P hiện tại của API chỉ truyền seed node và transport key vào `NetworkClient`, không nối hai cấu hình này vào runtime đó. Chỉ đặt các giá trị này không kích hoạt strict peer trust hoặc xác minh chữ ký message trong runtime API. IPFS tùy chọn cần daemon và encryption key thật dài 32 byte. Xem [Triển khai an toàn](../how-to/secure-deployment.md) và [Cấu hình](../reference/config.md).

## Tài nguyên Kubernetes

`docker/k8s/` có ví dụ Deployment/StatefulSet, service, storage và cấu hình. Kustomization cơ bản dùng namespace `hierachain`; `templates/` có template Sub-Chain riêng. `HierarchyManager` không tạo namespace hoặc pod khi tạo Sub-Chain Python. Namespace riêng không tự cô lập CPU, bộ nhớ hay mạng; cần cấu hình requests/limits và network policy ở deployment.

Tài nguyên phụ thuộc manifest: `node-deployment.yaml` dùng requests và limits 1 CPU/1 GiB; `node-statefulset.yaml` request 500m CPU/1 GiB và limit 2 CPU/2 GiB. Đây là giá trị manifest, không phải yêu cầu runtime hoặc bảo đảm capacity đã kiểm thử.

Đọc manifest được chọn trước khi triển khai. Ví dụ `node-deployment.yaml` hiện gọi `hrc start`, trong khi CLI cung cấp `hrc node start`; file cũng có placeholder encryption key IPFS. StatefulSet có mount identity secret riêng. Các file là ví dụ triển khai, chưa phải môi trường production đã cấp đủ cấu hình. Lần sửa tài liệu này không sửa hoặc xác minh chạy cluster manifest.

## Liên quan

* [Phục hồi](../how-to/disaster-recovery.md)
* [Kiểm thử và workload triển khai biệt lập](../dev/testing.md)
