---
title: "Integration module"
description: "Enterprise/ERP integration and Arrow client: arrow_client, enterprise, erp_ledger, types — bám sát hierachain/integration/*."
icon: material/puzzle
---

# Integration Module (`hierachain/integration/*`)

## Mục đích

Cung cấp lớp tích hợp với hệ thống doanh nghiệp/ERP và các client tiện ích (Arrow client) để trao đổi dữ liệu với HieraChain một cách ổn định và có kiểm soát.

## Kiến trúc & khái niệm

* Arrow Client: `hierachain/integration/arrow_client.py` — client thao tác dữ liệu dạng cột với Apache Arrow.
* ERP Ledger: `hierachain/integration/erp_ledger.py` — khung tích hợp ERP, chuẩn hoá adapter.
* Doanh nghiệp: `hierachain/integration/enterprise.py` — mẫu/khuôn cho tích hợp nghiệp vụ doanh nghiệp.
* Kiểu dữ liệu: `hierachain/integration/types.py` — các kiểu/contract dữ liệu tích hợp.
* ERP Adapters: `hierachain/integration/erp_adapters/*` — adapter cụ thể cho hệ thống ERP.

## API công khai (mang tính mô tả)

```python
class ERPAdapter:
  pull(domain, params) -> list[dict]
  push(domain, items) -> bool
```

#### Arrow Client Example

**File**: `hierachain/integration/arrow_client.py`

Xuất dữ liệu hiệu năng cao sang định dạng Apache Arrow:

```python
import pyarrow as pa
from hierachain.integration.arrow_client import ArrowClient

client = ArrowClient()
data = [pa.array([1, 2, 3]), pa.array(["A", "B", "C"])]
table = pa.Table.from_arrays(data, names=["id", "code"])

# Ghi dữ liệu ra file arrow
client.write_table(table, "export_data.arrow")
```

#### ERP Adapter Implementation

**File**: `hierachain/integration/erp_adapters/base.py`

Dự án cung cấp sẵn các adapter như `ODataAdapter`, `RestAdapter`. Bạn có thể tùy biến:

```python
from hierachain.integration.erp_ledger import ERPAdapter

class MyCustomERP(ERPAdapter):
    def pull(self, domain, params):
        # Logic gọi API từ SAP/Oracle...
        return [{"id": "1", "value": "data"}]
```

## Cấu hình

* Tham chiếu `hierachain/config/settings.py` phần Integration (`ERP_INTEGRATION_ENABLED`, `SUPPORTED_ERP_SYSTEMS`).
* Endpoint/API khoá bảo mật: xem trang Security/Config nếu adapter cần gọi HTTP bên ngoài.

## Tính năng & hạn chế

* Tính năng: chuẩn hoá giao diện tích hợp, hỗ trợ Arrow để hiệu quả IO.
* Hạn chế: adapter cụ thể cần hiện thực theo hệ thống đích; mặc định chỉ là khung.

## Liên quan

* Storage (Arrow/World State): [Storage](storage.md)
* Config: [Config](../reference/config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Thư mục: `hierachain/integration/{arrow_client.py, enterprise.py, erp_ledger.py, types.py, erp_adapters/*}`.

    **DECISION**

    * Ưu tiên chuẩn hoá adapter qua khung `erp_ledger.py` để giảm lệch giữa hệ thống.

    **ASSUMPTION**

    * Hệ thống đích có cơ chế xác thực/giới hạn tốc độ; adapter cần tôn trọng và log đầy đủ.

    **INVARIANT**

    * Dữ liệu qua adapter phải được chuẩn hoá schema trước khi ghi sự kiện vào Sub‑Chain.

    **EDGE CASES**

    * Sai khác schema giữa ERP và HieraChain → cần lớp ánh xạ/biến đổi rõ ràng.
