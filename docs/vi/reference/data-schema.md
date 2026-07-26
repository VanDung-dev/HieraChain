---
title: "Data Schema & Giao thức"
description: "Định nghĩa cấu trúc dữ liệu (Apache Arrow) và giao thức luồng dữ liệu trong HieraChain."
icon: material/file-tree
---

# Data Schema & Giao thức

Tài liệu này định nghĩa chi tiết cấu trúc dữ liệu (Data Schema) và các giao thức trao đổi thông tin (Protocol) trong HieraChain. Hệ thống sử dụng **Apache Arrow** làm định dạng lưu trữ và truyền tải chính để đảm bảo hiệu năng cao.

## Cấu trúc dữ liệu lõi

HieraChain tuân thủ nghiêm ngặt các định nghĩa Schema sau đây để đảm bảo tính nhất quán trên toàn mạng lưới (Main Chain & Sub Chains).

### Event

Event là đơn vị dữ liệu nhỏ nhất, đại diện cho một hành động nghiệp vụ cụ thể.

**Schema Definition (`hierachain.core.schemas.EVENT_SCHEMA`):**

| Field Name | Type (Arrow) | Mô tả |
|------------|--------------|-------|
| `entity_id` | `string` | **Metadata Field**. Định danh thực thể chịu tác động (ví dụ: ProductID, OrderID). **Lưu ý:** Không dùng làm định danh Block. |
| `event` | `string` | Loại sự kiện (ví dụ: `CREATED`, `UPDATED`, `TRANSFERRED`). |
| `timestamp` | `float64` | Thời điểm xảy ra sự kiện (Unix timestamp). |
| `details` | `map<string, string>` | Các thông tin bổ sung dạng Key-Value (On-chain data). |
| `details_cid` | `string` | **IPFS CID**. Tham chiếu dữ liệu lớn được lưu off-chain. |
| `details_nonce` | `string` | **Encryption Nonce**. Khóa giải mã dữ liệu off-chain (dùng cho AES-GCM). |
| `data` | `binary` | Payload dữ liệu chính (thành phần JSON nội bộ, bao gồm cả on-chain và off-chain refs). |

### Giao thức Cấu trúc Sự kiện (Event Schema)

Các sự kiện (Event) được đóng gói cùng chữ ký số (Ed25519) và bằng chứng Zero-Knowledge trước khi gửi vào chuỗi:

**Định nghĩa Cấu trúc (`hierachain.core.schemas.EVENT_SCHEMA`):**

| Tên trường | Kiểu dữ liệu (Arrow) | Mô tả |
|------------|--------------|-------------|
| `entity_id` | `string` | Mã định danh thực thể ảnh hưởng (ProductID, OrderID...). |
| `event` | `string` | Tên loại sự kiện. |
| `signature` | `string` | Chữ ký số của bên khởi tạo sự kiện. |
| `timestamp` | `float64` | Thời gian khởi tạo sự kiện. |
| `zk_proof` | `binary` | (Tùy chọn) Dữ liệu bằng chứng Zero-Knowledge. |
| `zk_public_inputs` | `binary` | (Tùy chọn) Dữ liệu public inputs cho việc xác minh ZK Proof. |

### Block

Block là tập hợp các Event đã được sắp xếp thứ tự và đóng gói lại.

**Block Header Schema:**

| Field Name | Type (Arrow) | Mô tả |
|------------|--------------|-------|
| `index` | `int64` | Số thứ tự của Block trong chuỗi (Height). |
| `timestamp` | `float64` | Thời điểm Block được tạo. |
| `previous_hash` | `string` | Hash SHA-256 của Block liền trước (tạo liên kết chuỗi). |
| `nonce` | `int64` | Số ngẫu nhiên dùng trong Proof-of-Work (nếu có) hoặc để đảm bảo tính duy nhất. |
| `merkle_root` | `string` | Hash gốc của cây Merkle, đại diện cho toàn bộ Event trong Block. |
| `hash` | `string` | Hash định danh của chính Block này. |

**Block Body:**

* Chứa danh sách các **Event** (được lưu dưới dạng `pyarrow.Table` để tối ưu truy xuất).

## Giao thức dòng dữ liệu

Quy trình xử lý dữ liệu từ Client đến khi được lưu vào Chain:

1. **Submission (Gửi dữ liệu)**:

    * Client tạo `Event`.
    * SDK đóng gói Event thành `Transaction`, ký số (`signature`) và có thể tạo `zk_proof`.
    * Gửi `Transaction` tới **Ordering Service**.

2. **Ordering (Sắp xếp)**:

    * **Ordering Service** nhận Transaction, kiểm tra chữ ký và tính hợp lệ cơ bản.
    * Xếp Transaction vào hàng đợi để đảm bảo thứ tự nhất quán.
    * Gom nhóm các Transaction thành một lô (Batch) để tạo Block.

3. **Consensus & Commit (Đồng thuận & Ghi nhận)**:

    * Node tạo Block mới từ lô Transaction đã sắp xếp.
    * Tính toán `Merkle Root` và `Block Hash`.
    * Thực hiện thuật toán đồng thuận (PoA/PoF/BFT) để xác nhận Block.
    * Sau khi đồng thuận, Block được thêm vào `MainChain` hoặc `SubChain`.
    * Trạng thái `World State` được cập nhật.

## Serialization Standards

* **Apache Arrow**: Dùng cho lưu trữ nội bộ (Internal Storage) và truyền tải giữa các Node (Performance).
* **JSON**: Dùng cho Client API (REST) để dễ dàng tích hợp với Web/Mobile App.
* **Protobuf/gRPC**: (Tùy chọn) Dùng cho giao tiếp nội bộ giữa các microservices hiệu năng cao.
