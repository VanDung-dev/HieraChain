---
title: "Mô hình dữ liệu"
description: "Schema event nội bộ, input REST/SDK và biểu diễn block được tuần tự hóa trong HieraChain."
icon: material/database-outline
---

# Mô hình dữ liệu

## Schema event nội bộ

`EVENT_SCHEMA` trong `hierachain/core/block.py` định nghĩa biểu diễn Arrow:

```python
from hierachain.core.block import EVENT_SCHEMA

print(EVENT_SCHEMA)
```

| Field | Arrow type |
|-------|------------|
| `entity_id` | `string` |
| `event` | `string` |
| `timestamp` | `double` |
| `details` | `map<string, string>` |
| `details_cid` | `string` |
| `details_nonce` | `string` |
| `data` | `binary` |

Cột `data` chứa byte JSON chuẩn hóa của sự kiện do bước chuyển đổi khối tạo ra. Giá trị details trong Arrow là chuỗi, còn `Block.to_event_list()` khôi phục kiểu JSON và details lồng nhau từ các byte đó. Trường JSON bổ sung được giữ trong payload dù không có cột Arrow riêng. `serialize_event_payload()` bỏ trường cấp cao nhất chứa `bytes` hoặc `bytearray`; giá trị lồng nhau phải tuần tự hóa được thành JSON. `data` là cột payload nội bộ, không phải trường upload file REST.

## Input REST và SDK

`EventRequest` trong `hierachain/api/ledger/schemas.py` dùng `event_type`; server tạo event nội bộ với `event` và timestamp server. `entity_id` và `event_type` bắt buộc. Field tùy chọn gồm `details`, `details_cid`, `details_nonce`, `details_metadata`, `sender` và `signature`.

```python
from hierachain.api.ledger.schemas import EventRequest

request = EventRequest(
    entity_id="PROD-001",
    event_type="production_complete",
    details={"quantity": 100, "passed": True},
)
print(request.model_dump(exclude_none=True))
```

Details giới hạn khoảng 1 MiB JSON serialize và độ sâu lồng 10. Nonce được cung cấp phải có 24 ký tự hex (12 byte). Dùng nonce và metadata xác thực trả về khi upload IPFS mã hóa; CID/nonce minh họa không phải fixture giải mã được. Field mật mã được validate khi cung cấp.

Endpoint proof dùng tên chain trong URL và trả `ProofSubmissionResponse`. Không có class `ProofSubmissionRequest` trong module schema ledger.

## Biểu diễn block

`Block` là class Python có bảng Arrow `events`. `to_dict()` trả `index`, `events`, `timestamp`, `previous_hash`, `nonce`, `merkle_root`, `hash`, `creator_id` và `signature`. Không có `BLOCK_HEADER_SCHEMA` riêng hoặc bảng event cho loại operation khác.

Ví dụ dựng block này chỉ minh họa chuyển đổi payload:

```python
import time
from hierachain.core.block import Block

block = Block(
    index=1,
    previous_hash="previous-block-hash",
    events=[{
        "entity_id": "PROD-001",
        "event": "production_complete",
        "timestamp": time.time(),
        "details": {"quantity": 100},
    }],
)
assert block.to_event_list()[0]["details"]["quantity"] == 100
```

Khối mới dựng chưa phải khối đã được ledger chấp nhận. `Blockchain.add_block()` của lớp cơ sở yêu cầu chữ ký tin cậy, liên kết hợp lệ và toàn vẹn Merkle/hash; MainChain/SubChain bổ sung kiểm tra đồng thuận. Genesis cũng cần chữ ký tin cậy.

`Block.from_dict()` dựng lại dữ liệu và so sánh `hash` dạng chuỗi được cung cấp với hash header tính lại. Hàm chấp nhận `merkle_root` được cung cấp mà không tính lại, nên byte sự kiện bị thay đổi vẫn có thể vượt qua bước chỉ kiểm tra header này. Dùng `BlockVerifier` với khóa công khai tin cậy hoặc phương thức xác thực của chuỗi để kiểm tra toàn vẹn sự kiện và chữ ký. `Block.validate_structure()` kiểm tra bảng sự kiện có `entity_id`, `event` và `timestamp`; hàm không xác thực mọi kiểu Arrow hay giá trị sự kiện.

## Liên quan

* [Schema dữ liệu](data-schema.md)
* [API Ledger](api-ledger.md)
* [Module Core](../modules/core.md)
