---
title: "Lưu trữ Mã hóa IPFS"
description: "Đẩy các dữ liệu nghiệp vụ có dung lượng lớn ra ngoài bộ lưu trữ mã hóa IPFS, chỉ neo giữ mã định danh CID trên chuỗi."
icon: material/harddisk
---

# Lưu trữ mã hóa IPFS

## Tổng quan

`IPFSClient` tải byte hoặc JSON lên Kubo daemon đã cấu hình và trả về CID. `upload_bytes()` và `upload_json()` mặc định mã hóa bằng AES-256-GCM. Bên gọi trực tiếp có thể truyền `encrypt=False` để gửi dữ liệu rõ lên IPFS. Cấu hình daemon và quyền truy cập mạng riêng; client không bắt buộc sử dụng private swarm.

`create_ipfs_client_from_env()` yêu cầu `HRC_IPFS_ENCRYPTION_KEY` chứa đúng 64 ký tự thập lục phân (32 byte). Khóa thiếu hoặc sai định dạng gây `IPFSError`. Giữ khóa này qua các lần khởi động lại để đọc được các đối tượng đã mã hóa trước đó. Client được khởi tạo trực tiếp có thể tạo khóa trong bộ nhớ khi không được cấp khóa; khóa đó không phải cơ chế khôi phục bền vững.

## Tải lên và tải xuống

```mermaid
sequenceDiagram
    participant Caller as Application
    participant IC as IPFSClient
    participant AES as AESEncryption
    participant IPFS as Kubo daemon
    Caller->>IC: upload_json(data, encrypt=True, metadata=metadata)
    IC->>IC: Serialize JSON to bytes
    IC->>AES: encrypt(bytes, canonical metadata AAD)
    AES-->>IC: ciphertext, random 12-byte nonce
    IC->>IPFS: POST /api/v0/add (pin=auto_pin)
    IPFS-->>IC: CID
    IC-->>Caller: cid, size, encrypted, nonce, metadata if provided
    Note over Caller: Retain CID, nonce and metadata; protect key separately
    Caller->>IC: download_json(cid, nonce=nonce, metadata=metadata)
    IC->>IPFS: POST /api/v0/cat?arg=cid
    IPFS-->>IC: ciphertext
    IC->>AES: decrypt(ciphertext, nonce, same metadata AAD)
    AES-->>IC: Authenticated plaintext
    IC-->>Caller: Decoded JSON
```

Dữ liệu mã hóa bao gồm thẻ xác thực GCM. Nonce được trả về riêng dưới dạng 24 ký tự thập lục phân. Đây là metadata công khai, không phải khóa mã hóa. Nếu metadata đã được dùng làm dữ liệu xác thực bổ sung (AAD), hãy cung cấp cùng metadata khi tải xuống; client tuần tự hóa nó bằng `dumps_canonical_json()`.

Khi tải lên, client truyền `pin` vào RPC add của Kubo theo `auto_pin` (mặc định `True`). Có thể gọi `IPFSClient.pin()` để ghim rõ ràng. Duy trì các pin và bản sao lưu theo chính sách vận hành daemon.

## Bảo mật và tích hợp

| Thuộc tính | Triển khai |
|:---------|:---------------|
| Tính bí mật | AES-256-GCM khi `encrypt=True` |
| Tính toàn vẹn | Xác minh thẻ GCM với cùng khóa, nonce và AAD |
| Nonce | Nonce ngẫu nhiên 96 bit cho mỗi lần mã hóa; phát hiện phát lại cần trạng thái của ứng dụng |
| Cấu hình khóa | Factory từ môi trường yêu cầu `HRC_IPFS_ENCRYPTION_KEY` ổn định |
| Phân quyền | Bên gọi thực thi quyền; client không gọi `PolicyEngine` |

Giữ khóa trong hệ thống quản lý bí mật. Lưu CID, nonce, cờ mã hóa và metadata AAD cần thiết cho việc truy xuất. Mã hóa không ngăn người có khả năng phát lại CID cũ yêu cầu lại cùng đối tượng.

## Lỗi

Lỗi HTTP khi tải lên/tải xuống gây `IPFSError`; lỗi mã hóa được truyền ra dưới dạng `EncryptionError`. Client không tự động thử lại ba lần hay tích hợp cảnh báo rủi ro. Ứng dụng quyết định có thử lại hay không và cách báo cáo lỗi.

`IPFSClient.is_available(cid)` kiểm tra `/api/v0/files/stat` với `arg=/ipfs/<cid>` và trả về `False` khi phản hồi không thành công hoặc kết nối thất bại. Kết quả này không chứng minh bên gọi có khóa giải mã đúng.

## Lớp và phương thức chính

| Thao tác | Phương thức | Tệp |
|:----------|:-------|:-----|
| Tải JSON lên | `IPFSClient.upload_json()` | `hierachain/api/storage/ipfs_client.py` |
| Tải byte lên | `IPFSClient.upload_bytes()` | `hierachain/api/storage/ipfs_client.py` |
| Mã hóa | `AESEncryption.encrypt()` | `hierachain/api/storage/encryption.py` |
| Ghim | `IPFSClient.pin()` | `hierachain/api/storage/ipfs_client.py` |
| Tải JSON xuống | `IPFSClient.download_json()` | `hierachain/api/storage/ipfs_client.py` |
| Factory từ môi trường | `create_ipfs_client_from_env()` | `hierachain/api/storage/ipfs_client.py` |

## Liên quan

- [Thực thi chính sách](./policy-enforcement.md): phân quyền do bên gọi quản lý
- [Phân tích rủi ro và cảnh báo](./risk-alerts.md): báo cáo lỗi do ứng dụng quản lý
- [Sao lưu khóa](./key-backup.md): lưu khóa do người vận hành quản lý
