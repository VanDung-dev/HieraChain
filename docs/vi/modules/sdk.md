---
title: "SDK module"
description: "SDK client: hierachain/sdk/client.py — truy cập HieraChain từ ứng dụng bên ngoài theo giao diện thuận tiện."
icon: material/tools
---

# SDK

## Mục đích

Cung cấp client SDK để ứng dụng bên ngoài tương tác với HieraChain theo giao diện lập trình thân thiện (khác với REST thuần hoặc CLI).

## Thành phần & khái niệm

* Client: `hierachain/sdk/client.py` — lớp client thực hiện các thao tác phổ biến (ghi sự kiện, gửi proof, truy vấn chuỗi...).

## API công khai (mang tính mô tả)

```python
class HieraClient:
  add_event(chain_name, entity_id, event_type, details=None) -> str
  submit_proof(chain_name) -> str | None
  get_chain_stats(chain_name) -> dict
```

## Cấu hình

* Endpoint/Host/Port lấy từ `hierachain/config/settings.py` hoặc tham số khởi tạo SDK.
* Nếu bật xác thực, SDK cần kèm API key theo `settings.API_KEY_NAME`.

## Tính năng & hạn chế

* Tính năng: rút gọn thao tác phổ biến; dễ tích hợp vào ứng dụng Python khác.
* Hạn chế: bọc trên các API lõi; hành vi phụ thuộc vào phiên bản server.

## Liên quan

* API v1/v2: [API v1](../reference/api-v1.md) · [API v2](../reference/api-v2.md)
* CLI: [CLI](cli.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn SDK chính: `hierachain/sdk/client.py`.

    **DECISION**

    * Ưu tiên giữ giao diện SDK ổn định tương thích API v1; mở rộng nhẹ cho v2 khi sẵn sàng.

    **ASSUMPTION**

    * Ứng dụng sử dụng SDK đã cấu hình endpoint/credential hợp lệ.

    **INVARIANT**

    * Phương thức SDK phản ánh hành vi API và trả lỗi rõ ràng khi thất bại.

    **EDGE CASES**

    * Sai API key/endpoint → ném lỗi kết nối/xác thực phù hợp, khuyến nghị retry/backoff.
