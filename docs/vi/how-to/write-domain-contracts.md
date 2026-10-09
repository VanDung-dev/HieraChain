---
title: "Xây dựng Logic Miền Nghiệp vụ"
description: "Hướng dẫn triển khai quy tắc nghiệp vụ, kiểm tra tính hợp lệ của thao tác và vòng đời thực thể bằng DomainChain."
icon: material/file-document-edit
---

# Xây dựng Logic Miền Nghiệp vụ

## 1. Chuỗi nghiệp vụ (Domain Chains)

HieraChain xử lý logic nghiệp vụ thông qua các chuỗi nghiệp vụ. Thay vì triển khai các hợp đồng thông minh bytecode tùy ý, nhà phát triển thực hiện logic nghiệp vụ bằng cách mở rộng hoặc cấu hình `DomainChain` trong `hierachain/domains/chains/domain_chain.py`.

### Khởi tạo một Domain Chain

`DomainChain` kế thừa từ `BaseChain` và cung cấp sẵn cơ chế kiểm tra tính hợp lệ cho các thao tác phổ biến:

```python
from hierachain.domains.chains.domain_chain import DomainChain

chain = DomainChain(
    name="supply_chain_01",
    domain_type="supply_chain"
)
```

## 2. Kiểm tra tính hợp lệ của thao tác

`DomainChain` kiểm tra các trường bắt buộc trong dữ liệu thao tác trước khi tạo sự kiện:

* `quality_check`: Yêu cầu `check_type` và `check_result`.
* `approval`: Yêu cầu `approval_type` và `approver_id`.
* `resource_allocation`: Yêu cầu `resource_type` và `resource_id`.
* `compliance_check`: Yêu cầu `compliance_type`.

Các loại thao tác chưa định nghĩa mặc định được chấp thuận, giúp mở rộng tùy chỉnh dễ dàng:

```python
from hierachain.domains.chains.domain_chain import validate_operation_data

payload = {
    "check_type": "visual_inspection",
    "check_result": "passed"
}

is_valid = validate_operation_data("quality_check", payload)
assert is_valid is True
```

## 3. Ghi nhận thao tác nghiệp vụ

Sử dụng các hàm tạo sự kiện từ `hierachain/domains/events/event_creators.py`:

```python
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.domains.events.event_creators import create_quality_check

chain = DomainChain(name="logistics_chain", domain_type="logistics")
chain.register_entity("CONTAINER-409", {"origin": "Port A"})

# Create a validated quality check event
event = create_quality_check(
    entity_id="CONTAINER-409",
    check_type="temperature_compliance",
    check_result="passed",
    details={"temperature_c": 4.2}
)

# Append event to the domain chain
chain.add_domain_event(event)
```

## 4. Quản lý vòng đời thực thể

`DomainChain` theo dõi trạng thái thực thể qua các thao tác:

1. Đăng ký: Đăng ký thực thể mới cần theo dõi trên chuỗi.
2. Cập nhật trạng thái: Ghi nhận các trạng thái chuyển giao như `in_progress`, `quality_approved` và `completed`.
3. Chỉ số đo lường: `OperationMetricsTracker` ghi nhận tổng số thao tác và tỷ lệ thành công tổng hợp. Tracker không ghi nhận độ trễ thực thi hoặc phân nhóm kết quả theo loại thao tác.

```python
# Register an entity
chain.register_entity(
    entity_id="CONTAINER-409",
    entity_data={"origin": "Port A", "destination": "Port B"}
)

# Update entity status
chain.update_entity_status(
    entity_id="CONTAINER-409",
    status="in_transit",
    reason="Departed facility"
)
```

## Liên quan

* [Domains Module](../modules/domains.md)
* [Thêm một chuỗi nghiệp vụ](./add-domain-chain.md)
* [Thao tác liên chuỗi](./cross-chain-transactions.md)
