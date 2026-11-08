---
title: "Network Module"
description: "ZeroMQ transport và vòng đời peer cho các node HieraChain."
icon: material/access-point-network
---

# Network Module (`hierachain/network/*`)

## Tổng quan

Module **Network** quản lý giao tiếp giữa các node HieraChain qua **ZeroMQ**. `ZmqNode` sở hữu socket, bảo vệ replay và giới hạn framing; `NetworkClient` bổ sung đăng ký seed, vòng đời peer và báo cáo trạng thái. API server tạo trực tiếp `NetworkClient`.

---

## Các thành phần cốt lõi

### 1. ZMQ Transport (`zmq_transport.py`)
Hiện thực hóa mô hình P2P không đồng bộ sử dụng Socket **ROUTER** (để nhận) và **DEALER** (để gửi).

*   **Truyền tải**: Dùng socket không đồng bộ; broadcast gửi tuần tự tới các peer đã đăng ký.
*   **Identity Management**: Quản lý định danh các nút ở mức socket để định tuyến chính xác.
*   **Replay buffer**: Giữ tối đa 1.000 cặp timestamp/nonce với nonce dạng chuỗi dài tối đa 128 ký tự. Khi tất cả mục vẫn nằm trong cửa sổ 60 giây, thông điệp mới bị từ chối cho đến khi có mục hết hạn.

ZeroMQ nhận frame tối đa 1 MiB và đúng hai frame ứng dụng (định danh bên gửi và nội dung); frame thừa được đọc bỏ, không gom vào danh sách multipart Python. Transport plain yêu cầu peer ID đã cấu hình và tách cache replay theo peer; không bảo đảm danh tính bằng chữ ký. Các giới hạn này cần đi cùng kiểm soát kết nối và băng thông ở tầng triển khai.

### 2. Network Client (`network_client.py`)

`NetworkClient` theo dõi seed và peer đăng ký thủ công trong cùng registry. Gỡ peer cũng đóng socket DEALER gửi đi của peer đó. Peer được xem là healthy trong 60 giây đầu sau khi đăng ký; mỗi thông điệp nhận vào hợp lệ từ định danh socket đã đăng ký sẽ gia hạn khoảng này. Peer im lặng chuyển unhealthy khi đọc trạng thái hoặc danh sách peer. Chỉ báo health này không xác thực peer hay xác nhận thông điệp gửi đi đã được nhận.

Nếu `ZmqNode.start()` thất bại, nó đóng socket và context của transport trước khi ném `NetworkError`. `NetworkClient.start()` giải phóng transport khởi tạo dở và trả về `False`; sau khi xử lý nguyên nhân, gọi lại `start()` sẽ tạo transport mới. `NetworkClient.stop()` cũng dọn transport chưa chuyển sang trạng thái chạy và có thể được gọi nhiều lần.

---

## Cấu hình P2P (Environment Variables)

| Biến môi trường | Chức năng | Giá trị khuyến nghị (Prod) |
| :--- | :--- | :--- |
| `HRC_P2P_ENABLED` | Bật lớp mạng P2P | `true` khi dùng peer |
| `HRC_P2P_HOST` / `HRC_P2P_PORT` | Địa chỉ bind cục bộ | Theo môi trường triển khai |
| `HRC_PEERS` | Danh sách seed node phân tách bằng dấu phẩy (`node_id@ip:port`) | Danh sách peer đã biết |

---

## Liên quan

*   [Bảo mật (Security)](./security.md)
*   [Cấu hình (Configuration)](./config.md)
