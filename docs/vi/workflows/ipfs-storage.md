---
title: "Lưu trữ Mã hóa IPFS"
description: "Đẩy các dữ liệu nghiệp vụ có dung lượng lớn ra ngoài bộ lưu trữ mã hóa IPFS, chỉ neo giữ mã định danh CID trên chuỗi."
icon: material/harddisk
---

# Lưu trữ mã hóa IPFS

## Tổng quan

Dữ liệu lớn hoặc nhạy cảm ngoài chuỗi (ví dụ tệp đính kèm, bằng chứng kiểm toán, tài sản nhị phân) được lưu trên swarm IPFS riêng với mã hóa bắt buộc AES-256-GCM. Chỉ node có chung khóa mới giải mã được. CID do IPFS trả về được lưu trên chuỗi làm tham chiếu; plaintext không rời khỏi ranh giới mã hóa.

Điểm an toàn cốt lõi: ngay cả khi storage IPFS bị lộ vật lý, dữ liệu vẫn không đọc được nếu không có khóa AES-256-GCM.

---

## Biểu đồ luồng: tải lên (mã hóa và ghim)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 🖥️ API / SubChain
    participant IC as 🗄️ IPFSClient
    participant AES as 🔐 AESEncryption
    participant IPFS as 🌐 IPFS Daemon

    Caller->>IC: upload_json(data, encrypt=True, metadata)

    IC->>IC: json.dumps(data) → raw_bytes
    IC->>AES: encrypt(raw_bytes, aad=json(metadata))
    Note right of AES: Mã hóa AES-256-GCM<br/>nonce = ngẫu nhiên 96-bit (secrets.token_bytes(12))<br/>ciphertext = AESGCM.encrypt(nonce, plaintext, aad)<br/>output = nonce || ciphertext
    AES-->>IC: ciphertext, nonce

    IC->>IPFS: add_bytes(ciphertext)
    IPFS-->>IC: CID (Content Identifier - Mã định danh nội dung)

    alt auto_pin=True (mặc định)
        IC->>IPFS: pin.add(CID)
        Note right of IPFS: Ngăn chặn cơ chế dọn rác (GC) xóa file
    end

    IC-->>Caller: { cid, size, encrypted: True, nonce: hex(nonce) }
    Note over Caller: Lưu trữ CID + nonce lên chuỗi để truy xuất sau này
```

---

## Biểu đồ luồng: tải về (truy xuất và giải mã)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 🖥️ API / SubChain
    participant IC as 🗄️ IPFSClient
    participant AES as 🔐 AESEncryption
    participant IPFS as 🌐 IPFS Daemon

    Caller->>IC: download_json(cid, encrypted=True, nonce=hex, metadata)
    IC->>IPFS: cat(cid) → ciphertext bytes
    IPFS-->>IC: ciphertext

    IC->>AES: decrypt(ciphertext, nonce_bytes, aad=json(metadata))
    Note right of AES: Xác thực thẻ GCM trước<br/>Nếu thẻ không hợp lệ → ném lỗi DecryptionError
    AES-->>IC: plaintext bytes

    IC->>IC: json.loads(plaintext) → dict
    IC-->>Caller: Dữ liệu đã giải mã ✅
```

---

## Xử lý lỗi: IPFS ngoại tuyến

`IPFSClient.is_available(cid)` kiểm tra `/api/v0/files/stat` với `arg=/ipfs/<cid>`. Hàm trả về `False` khi phản hồi không thành công hoặc kết nối lỗi; không dùng endpoint `/api/v0/object/stat` đã bị loại bỏ.

```mermaid
flowchart LR
    CALL["upload_json(data)"]
    CONN["Kết nối tới IPFS daemon\n(HRC_IPFS_HOST)"]
    FAIL["❌ Kết nối bị từ chối\nhoặc hết hạn chờ"]
    RETRY["Thử lại với khoảng chờ tăng dần\n(tối đa 3 lần)"]
    ERR["Ném lỗi IPFSConnectionError\nGhi nhật ký + Cảnh báo qua Risk Alerts"]
    OK["✅ Nhận lại mã CID"]

    CALL --> CONN
    CONN -->|Thành công| OK
    CONN -->|Thất bại| FAIL --> RETRY
    RETRY -->|Quá số lần thử| ERR
    RETRY -->|Kết nối lại được| OK
```

---

## Các bước chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Tuần tự hóa** | `json.dumps(data)` thành bytes thô. |
| **2. Mã hóa** | AES-256-GCM với nonce ngẫu nhiên 96-bit. AAD được tạo từ metadata JSON. |
| **3. Tải lên** | Bytes mã hóa được gửi tới IPFS daemon qua Kubo RPC API (`httpx`). |
| **4. Ghim** | `pin.add(CID)` giữ dữ liệu trên đĩa, tránh GC của IPFS xóa. |
| **5. Trả kết quả** | Bên gọi nhận `{ cid, nonce }`; cả hai phải lưu trên chuỗi để truy xuất sau. |
| **6. Truy xuất** | `cat(cid)` tải bytes mã hóa; `decrypt()` kiểm tra thẻ GCM trước khi giải mã. |

---

## Thuộc tính an toàn

| Thuộc tính | Cơ chế |
|:-----------|:-------|
| **Bảo mật** | AES-256-GCM |
| **Toàn vẹn** | Xác thực thẻ GCM (authenticated encryption) |
| **Chống replay** | Mỗi lần tải lên dùng nonce 96-bit ngẫu nhiên riêng |
| **Quản lý khóa** | Cấu hình qua `HRC_IPFS_ENCRYPTION_KEY`; tự sinh nếu thiếu |
| **Kiểm soát quyền** | Policy engine kiểm soát quyền gọi API upload/download |

---

## Lớp và phương thức chính

| Bước | Lớp / Phương thức | Tệp |
|:-----|:--------------|:-----|
| Điểm tải lên | `IPFSClient.upload_json()` | `api/storage/ipfs_client.py` |
| Mã hóa | `AESEncryption.encrypt()` | `api/storage/encryption.py` |
| Tải bytes thô | `IPFSClient.upload_bytes()` | `api/storage/ipfs_client.py` |
| Ghim | `IPFSClient.pin()` | `api/storage/ipfs_client.py` |
| Tải về và giải mã | `IPFSClient.download_json()` | `api/storage/ipfs_client.py` |
| Tạo client | `create_ipfs_client_from_env()` | `api/storage/ipfs_client.py` |

---

## Liên quan

- [Thực thi Chính sách](./policy-enforcement.md): kiểm soát quyền upload/download
- [Cảnh báo Rủi ro](./risk-alerts.md): lỗi kết nối IPFS kích hoạt cảnh báo
- [Sao lưu & Khôi phục Khóa](./key-backup.md): cùng mô hình mã hóa AES-256-GCM cho bản sao lưu khóa
