---
title: "Mô hình Dữ liệu"
description: "Mô tả Event/Block/Transaction schemas dựa trên hierachain/core/schemas.py; ví dụ và bất biến."
icon: material/database-outline
---

# Mô hình dữ liệu

## Mục đích

Chuẩn hoá các cấu trúc dữ liệu lõi (Event, BlockHeader, Transaction, Block đầy đủ) giúp tương thích xuyên ngôn ngữ và đảm bảo toàn vẹn dữ liệu.

## Khái niệm & phạm vi

* Dựa trên Arrow Schema trong `hierachain/core/schemas.py`.
* Áp dụng cho: mô-đun Core, Sub-Chain/Main Chain, và API (serialize/deserialize).

## Lược đồ chính

### Event

Mô tả một sự kiện domain.

```python
EVENT_SCHEMA = schema([
  ('entity_id', string),          # ID thực thể
  ('event', string),              # loại sự kiện
  ('timestamp', float64),         # epoch giây (float)
  ('details', map<string,string>),# metadata key→string (On-chain)
  ('details_cid', string),        # IPFS CID (Off-chain reference)
  ('details_nonce', string),      # Encryption nonce
  ('data', binary),               # payload nhị phân (tuỳ chọn)
])
```

Ví dụ JSON (khi trả về qua API):

```json
{
  "entity_id": "PROD-001",
  "event": "production_complete",
  "timestamp": 1703088000.0,
  "details": null,
  "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
  "details_nonce": "a1b2c3d4e5f6...",
  "data": null
}
```

### Block Header

Metadata tối thiểu cho một block.

```python
BLOCK_HEADER_SCHEMA = schema([
  ('index', int64),
  ('timestamp', float64),
  ('previous_hash', string),
  ('nonce', int64),
  ('merkle_root', string),
  ('hash', string),
])
```

### Transaction

Chuẩn hoá giao dịch/sự kiện nâng cao (có chữ ký, ZK proof tuỳ chọn).

```python
TRANSACTION_SCHEMA = schema([
  ('tx_id', string),
  ('entity_id', string),
  ('event_type', string),
  ('arrow_payload', binary),        # tuần tự Arrow
  ('signature', string),            # chữ ký hex
  ('timestamp', float64),
  ('details', map<string,string>),
  ('zk_proof', binary),             # tuỳ chọn
  ('zk_public_inputs', binary),     # tuỳ chọn
])
```

### Block (đầy đủ)

Block đầy đủ gồm header + danh sách events + (tuỳ chọn) ZK proof ở cấp block.

```python
      previous_hash:string,
      nonce:int64,
      merkle_root:string,
      hash:string,
      events:list<struct<
          entity_id:string,
          event:string,
          timestamp:float64,
          details:map<string,string>,
          details_cid:string,
          details_nonce:string,
          data:binary
      >>),
      zk_proof:binary,
      zk_public_inputs:binary
  ])
```
```

## Mapping Pydantic (API Ledger)

Các mô hình Pydantic (`hierachain/api/ledger/schemas.py`) được sử dụng để validate dữ liệu API, ánh xạ với cấu trúc lõi:

```python
class EventRequest(BaseModel):
    entity_id: str
    event_type: str
    details: dict[str, Any] | None
    details_cid: str | None
    details_nonce: str | None
    details_metadata: dict[str, Any] | None

class ProofSubmissionRequest(BaseModel):
    sub_chain_name: str | None
    proof_hash: str | None
    metadata: dict[str, Any] | None
```

**Quy tắc chuyển đổi:**

* `EventRequest.details` (Dict) → `EVENT_SCHEMA.details` (Map<String, String>).
* `ProofSubmissionRequest` → đóng gói thành `Event` trên Main Chain với type `proof_submission`.

## Chuyển đổi & tuần tự hoá

* `Block.events` dùng `pyarrow.Table` nội bộ; khi trả về API có thể chuyển sang danh sách dict (`to_event_list()` hoặc `to_pylist()`).
* Trường `details` luôn là map<string,string>; giá trị phi chuỗi sẽ được chuyển thành chuỗi khi nhập liệu.
* Trường `data` là nhị phân; khi qua JSON cần base64 hoặc bỏ qua nếu không cần thiết.

### Thao tác với Dữ liệu Nhị phân (Trường `data`)

Do trường `data` được định nghĩa là `binary` trong Arrow Schema, bạn cần phải mã hóa các payload nhị phân của mình (chẳng hạn như file PDF nhỏ, chứng chỉ, hoặc các đối tượng được tuần tự hóa) thành một chuỗi Base64 khi gửi qua JSON API, và giải mã chúng ở phía nhận.

**Ví dụ Python:**
```python
import base64

# 1. Chuẩn bị dữ liệu nhị phân để gửi qua Event
raw_data = b"Enterprise visual quality report content"
encoded_data = base64.b64encode(raw_data).decode('utf-8')

event_payload = {
    "entity_id": "PROD-001",
    "event": "quality_inspection",
    "data": encoded_data
}

# 2. Đọc và giải mã dữ liệu nhị phân từ Block hoặc Event Response
received_encoded_data = event_payload["data"]
decoded_data = base64.b64decode(received_encoded_data)
print(decoded_data.decode('utf-8'))  # "Enterprise visual quality report content"
```

## Ví dụ thao tác (mô tả)

```python
# Tạo Block từ list sự kiện (dict)
blk = Block(index=1, events=[{...}, {...}], previous_hash="<hash>")

# Lấy danh sách sự kiện dạng dict
events = blk.to_event_list()

# Kiểm tra tính hợp lệ chuỗi
blockchain.is_chain_valid()
```

## Liên quan

* Core module: [Core](../modules/core.md)
* API Ledger: [API Ledger](api-ledger.md)
