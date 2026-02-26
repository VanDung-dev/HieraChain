---
title: "Data Schema & Giao thức"
description: "Định nghĩa cấu trúc dữ liệu (Apache Arrow) và giao thức luồng dữ liệu trong HieraChain."
icon: material/file-tree
---

# Data Schema & Giao thức

Tài liệu này định nghĩa chi tiết cấu trúc dữ liệu (Data Schema) và các giao thức trao đổi thông tin (Protocol) trong HieraChain. Hệ thống sử dụng **Apache Arrow** làm định dạng lưu trữ và truyền tải chính để đảm bảo hiệu năng cao.

## Cấu trúc dữ liệu lõi

HieraChain tuân thủ nghiêm ngặt các định nghĩa Schema sau đây để đảm bảo tính nhất quán trên toàn mạng lưới (Main Chain & Sub Chains).

### 1.1 Event

Event là đơn vị dữ liệu nhỏ nhất, đại diện cho một hành động nghiệp vụ cụ thể.

**Schema Definition (`hierachain.core.schemas.EVENT_SCHEMA`):**

| Field Name | Type (Arrow) | Mô tả |
|------------|--------------|-------|
| `entity_id` | `string` | **Metadata Field**. Định danh thực thể chịu tác động (ví dụ: ProductID, OrderID). **Lưu ý:** Không dùng làm định danh Block. |
| `event` | `string` | Loại sự kiện (ví dụ: `CREATED`, `UPDATED`, `TRANSFERRED`). |
| `timestamp` | `float64` | Thời điểm xảy ra sự kiện (Unix timestamp). |
| `details` | `map<string, string>` | Các thông tin bổ sung dạng Key-Value (ít thay đổi). |
| `data` | `binary` | Payload dữ liệu chính (thường là JSON đã serialize hoặc binary data). |

### Transaction

Transaction là lớp bao (wrapper) chứa Event cùng với chữ ký số và bằng chứng xác thực (ZK Proof).

**Schema Definition (`hierachain.core.schemas.TRANSACTION_SCHEMA`):**

| Field Name | Type (Arrow) | Mô tả |
|------------|--------------|-------|
| `tx_id` | `string` | Định danh duy nhất của giao dịch (UUID hoặc Hash). |
| `entity_id` | `string` | Đồng bộ với Event entity_id. |
| `event_type` | `string` | Đồng bộ với Event event. |
| `arrow_payload` | `binary` | Dữ liệu Event đã được serialize theo chuẩn Arrow. |
| `signature` | `string` | Chữ ký số của người tạo giao dịch (Ed25519/ECDSA). |
| `timestamp` | `float64` | Thời điểm tạo giao dịch. |
| `zk_proof` | `binary` | (Optional) Bằng chứng Zero-Knowledge để xác thực tính đúng đắn mà không lộ dữ liệu. |
| `zk_public_inputs` | `binary` | (Optional) Input công khai đi kèm với ZK Proof. |

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

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**
    
    * Hệ thống sử dụng Apache Arrow (pyarrow) để định nghĩa Schema (`hierachain/core/schemas.py`).
    * Dữ liệu được lưu trữ dưới dạng Columnar để tối ưu hóa truy vấn phân tích (OLAP).

    **DECISION**
    
    * Sử dụng `entity_id` làm khóa chính logic thay vì `block_hash` để hỗ trợ truy xuất lịch sử thực thể (Traceability).
    * Tách biệt `Event` (Nghiệp vụ) và `Transaction` (Kỹ thuật/Bảo mật) để linh hoạt trong thiết kế API.
    * **Terminology**: `Transaction` được định nghĩa là **Technical Envelope** (gói dữ liệu kỹ thuật) chứa Event + Signature + Proof, **KHÔNG** phải là giao dịch tài chính (Financial Transfer).

    **ASSUMPTION**
    
    * Mọi dữ liệu đầu vào đều phải được validate qua `pydantic` hoặc `pyarrow` schema trước khi xử lý.

    **INVARIANT**
    
    * Block đã commit vào Chain là bất biến (Immutable).
    * Mọi Event trong Block phải có cùng `merkle_root` được ghi trong Header.
