---
title: "Gửi Sự kiện"
description: "Chi tiết về đường truyền tiếp nhận dữ liệu cốt lõi: gửi sự kiện, xác thực, sắp xếp thứ tự, đóng gói và nối khối."
icon: material/tray-arrow-down
---

# Gửi sự kiện

## Tổng quan

API Ledger kiểm tra schema của request rồi `SubChain.add_event()` chuyển event tới `OrderingService`. Ordering Service ghi event vào journal và hàng đợi trước khi trả `event_id`. ID này xác nhận event đã được tiếp nhận; block được commit sau đó. Processor nền chứng thực và gom batch, rồi tạo block và đưa vào commit queue. Consumer của SubChain finalize và lưu từng block. Mặc định, SubChain gom 50 event và chờ 1 giây trước khi tạo block. MainChain dùng PoA hoặc PoF; BFT là thành phần riêng, không được chọn trong luồng API này.

Với sơ đồ PoA và PoF, xem [Cơ chế Đồng thuận](./consensus_mechanisms.md).

---

## Biểu đồ luồng

```mermaid
sequenceDiagram
    autonumber
    participant Client as 🖥️ Client / ERP
    participant API as 🌐 FastAPI
    participant SC as 📦 SubChain
    participant OS as ⚙️ OrderingService
    participant DB as 💾 Storage

    rect rgb(0, 0, 0, 0)
        Note over Client,API: Giai đoạn 1 — Gửi Sự kiện
        Client->>API: POST /api/ledger/chains/{chain_name}/events
        API->>SC: add_event(event_dict)
        SC->>SC: Thêm timestamp/entity_id/event mặc định nếu thiếu
        SC->>OS: receive_event(event_data, channel_id, submitter_org)
        OS->>OS: Ghi Event Journal và đưa vào event_pool
        OS-->>API: event_id
        API-->>Client: 200 OK (đã tiếp nhận; chưa phải block finality)
    end

    rect rgb(0, 0, 0, 0)
        Note over OS: Giai đoạn 2 — Gom batch và tạo block ở xử lý nền
        Note over OS: Đạt block_size hoặc batch_timeout

        OS->>OS: BlockBuilder._finalize_batch() trả về danh sách event
        OS->>OS: OrderingBlockManager.create_block_async(events) tạo block
        OS->>DB: Lưu block do Ordering tạo
        OS->>OS: Đưa block vào commit_queue sau khi lưu thành công
    end

    rect rgb(0, 0, 0, 0)
        Note over SC: Giai đoạn 3 — Finalize và cập nhật SubChain
        Note over SC: Consumer nền lấy block từ commit_queue

        SC->>OS: get_next_block()
        OS-->>SC: Block
        SC->>SC: _process_and_finalize_single_block()
        SC->>SC: Tính index, previous_hash, hash
        SC->>SC: Finalize bằng consensus PoA hoặc PoF
        SC->>DB: Lưu block đã finalize
        SC->>SC: add_block() và cập nhật world state
        SC->>SC: auto_submit_proof_if_needed()

        Note over SC: → Kích hoạt Neo giữ Bằng chứng
    end
```

---

## Các bước chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Nhận qua API** | FastAPI kiểm tra schema `EventRequest`, gồm `entity_id` và `event_type`; endpoint trả `event_id` sau khi sự kiện được tiếp nhận, chưa xác nhận block finality. |
| **2. Thêm sự kiện vào SubChain** | `SubChain.add_event()` bổ sung giá trị mặc định cho lời gọi nội bộ rồi gọi `OrderingService.receive_event()`; API vẫn bắt buộc `entity_id` và `event_type`. Hàm này không gọi `validate_event_for_consensus()`. |
| **3. Chứng thực nền** | Ordering Service chuyển sự kiện qua certifier sau phản hồi API; sự kiện bị từ chối không được đưa vào block. |
| **4. Gom batch** | `BlockBuilder.add_event()` thêm event đã chứng thực vào batch; khi đủ `block_size`, hết `batch_timeout` hoặc được flush, `_finalize_batch()` trả danh sách event và reset batch. |
| **5. Tạo và commit block Ordering** | `OrderingBlockManager.create_block_async()` tạo block; `commit_block()` lưu block vào storage rồi mới đưa vào `commit_queue`. |
| **6. Finalize ở SubChain** | Consumer nền lấy block từ `commit_queue`; `_process_and_finalize_single_block()` đặt index và các hash liên kết, gọi consensus đã cấu hình của SubChain (PoA mặc định hoặc PoF), rồi lưu block đã finalize. |
| **7. Cập nhật chuỗi** | Khi lưu thành công, SubChain thêm block vào chuỗi và cập nhật world state. |
| **8. Kích hoạt proof** | `auto_submit_proof_if_needed()` có thể gửi proof lên Main Chain khi đạt ngưỡng đã cấu hình. |

---

## Cấu trúc sự kiện

```python
event = {
    "entity_id": "product-SKU-001",    # Định danh thực thể nghiệp vụ
    "event_type": "quality_check",      # Loại sự kiện
    "timestamp": 1714000000.0,
    "details": {                        # Payload nghiệp vụ
        "check_type": "visual",
        "check_result": "passed",
        "inspector": "station-7"
    }
}
```

> **Lưu ý**: API yêu cầu `entity_id` và `event_type`; khi chuyển sang event nội bộ, `event_type` được biểu diễn bằng khóa `event`. Không nên coi `event_id` API trả về là bằng chứng block đã được finalize.

---

## Xử lý lỗi

| Tình huống | Hành vi |
|:-----------|:--------|
| Thiếu trường bắt buộc hoặc chain không tồn tại | API từ chối request; schema yêu cầu `entity_id` và `event_type`. |
| Ghi event journal thất bại | `OrderingService.receive_event()` ném lỗi và không xếp sự kiện vào `event_pool`. |
| Chứng thực event thất bại | Processor đánh dấu event bị từ chối; event không được thêm vào block. |
| Lưu block Ordering thất bại | Lỗi được ghi log và Ordering Service chuyển sang `MAINTENANCE`; block chưa được đưa vào `commit_queue`. |
| Lưu block đã finalize thất bại | Consumer đã lấy block khỏi `commit_queue`; `_process_and_finalize_single_block()` trả về lỗi và mã hiện tại không đưa block trở lại hàng đợi để thử lại. |

---

## Lớp và phương thức chính

| Bước | Lớp / Phương thức | Tệp |
|:-----|:--------------|:-----|
| Kiểm tra và nhận request | `EventRequest`; `SubChain.add_event()` | `hierachain/api/ledger/schemas.py`; `hierachain/api/ledger/events.py` |
| Journal và xếp hàng | `OrderingService.receive_event()` | `hierachain/consensus/ordering/service.py` |
| Chứng thực và gom batch | `OrderingProcessor`; `BlockBuilder.add_event()` | `hierachain/consensus/ordering/processor.py`; `hierachain/consensus/ordering/block_builder.py` |
| Tạo và commit block Ordering | `OrderingBlockManager.create_block_async()`; `commit_block()` | `hierachain/consensus/ordering/block_manager.py` |
| Finalize và lưu block SubChain | `_process_and_finalize_single_block()` | `hierachain/hierarchical/sub_chain/block.py` |
| Storage adapter | Database adapters | `hierachain/adapters/database/` |

---

## Liên quan

- [Cơ chế Đồng thuận](./consensus_mechanisms.md): sơ đồ phụ PoA và PoF
- [Neo giữ Bằng chứng](./proof-anchoring.md): kích hoạt sau khi khối hoàn tất
- [Đồng thuận BFT](./bft-consensus.md): luồng PBFT 3 pha đầy đủ
- [Thực thi Chính sách](./policy-enforcement.md): cổng kiểm soát trước `add_event()`
- [Danh tính MSP](./msp-identity.md): gọi `authorize_action()` trước khi gửi
