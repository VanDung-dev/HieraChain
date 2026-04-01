---
title: "Domains module"
description: "Miền nghiệp vụ chung: chains/events/utils — base_chain, domain_chain, base_event, domain_event, cross_chain_validator, entity_tracer."
icon: material/folder
---

# Domains Module (`hierachain/domains/generic/*`)

Mô‑đun cung cấp khung chung cho các miền nghiệp vụ (generic domains) để chuẩn hoá cách xây dựng chuỗi và sự kiện domain. Module này mở rộng từ SubChain và BaseEvent để cung cấp các tính năng nghiệp vụ chung.

## Kiến trúc & khái niệm

<div class="grid cards" markdown>

* :material-link-variant:{ .lg .middle } __BaseChain__

    ---

    __File__: `hierachain/domains/generic/chains/base_chain.py`

    * Lớp trừu tượng (abstract class) mở rộng SubChain.
    * Đăng ký entity, quản lý vòng đời entity.
    * Xử lý event mặc định: operation_start, operation_complete, status_update, resource_assigned, quality_check, approval, compliance_check.
    * Hỗ trợ domain_rules và event_handlers tùy biến.

* :material-source-branch:{ .lg .middle } __DomainChain__

    ---

    __File__: `hierachain/domains/generic/chains/domain_chain.py`

    * Hiện thực cụ thể của BaseChain cho các kịch bản business phổ biến.
    * OperationMetricsTracker: theo dõi metrics vận hành (started, completed, quality_passed, approvals_granted).
    * Cung cấp factory functions: `create_resource_allocation()`, `create_quality_check()`, `create_status_update()`, `create_approval()`, `create_compliance_check()`.

* :material-calendar-blank:{ .lg .middle } __BaseEvent__

    ---

    __File__: `hierachain/domains/generic/events/base_event.py`

    * Lớp trừu tượng cho tất cả event trong HieraChain.
    * Sử dụng `entity_id` làm metadata field (không phải block identifier).
    * Validate event structure theo Ledger guidelines.
    * Trường: entity_id, event_type, details, timestamp.

* :material-calendar:{ .lg .middle } __DomainEvent__

    ---

    __File__: `hierachain/domains/generic/events/domain_event.py`

    * Event domain-specific mở rộng BaseEvent.
    * Thêm trường `domain_type` để phân biệt domain.
    * Validation domain-specific: kiểm tra domain_type hợp lệ.

* :material-check-decagram:{ .lg .middle } __CrossChainValidator__

    ---

    __File__: `hierachain/domains/generic/utils/cross_chain_validator.py`

    * Validate tính nhất quán giữa Main Chain và Sub-Chains.
    * Kiểm tra operation consistency: operation_start/operation_complete khớp nhau.
    * Kiểm tra status consistency: trạng thái entity hợp lệ.
    * Sử dụng HierarchyManager và EntityTracer để truy vết cross-chain.

* :material-routes:{ .lg .middle } __EntityTracer__

    ---

    __File__: `hierachain/domains/generic/utils/entity_tracer.py`

    * Truy vết entity qua nhiều Sub-Chains.
    * Xây dựng timeline: stage tracking (in_progress, completed, quality_approved, approved).
    * Phương thức: `trace_entity_in_chain()`, `trace_entity_across_chains()`.

</div>

## API công khai

### BaseChain

```python
class BaseChain(SubChain, ABC):
    def __init__(self, name: str, domain_type: str)
    def register_entity(self, entity_id: str, entity_data: dict) -> bool
    def get_entity(self, entity_id: str) -> dict | None
    def get_domain_statistics(self) -> dict
    def add_event(self, event: BaseEvent) -> bool
    def _handle_operation_start(self, event)
    def _handle_operation_complete(self, event)
    def _handle_status_update(self, event)
    def _handle_resource_allocation(self, event)
    def _handle_quality_check(self, event)
    def _handle_approval(self, event)
    def _handle_compliance_check(self, event)
```

### DomainChain

```python
class DomainChain(BaseChain):
    def __init__(self, name: str, domain_type: str)
    def get_operation_metrics(self) -> dict  # started, completed, quality_passed ratio, approval ratio
    def get_compliance_summary(self) -> dict
```

### EntityTracer

```python
class EntityTracer:
    def __init__(self, hierarchy_manager: HierarchyManager)
    def trace_entity_in_chain(self, entity_id: str, chain_name: str) -> dict
    def trace_entity_across_chains(self, entity_id: str) -> dict[str, list[dict]]
```

### CrossChainValidator

```python
class CrossChainValidator:
    def __init__(self, hierarchy_manager: HierarchyManager, entity_tracer: EntityTracer)
    def validate_chain_consistency(self, chain_name: str) -> dict
    def validate_cross_chain_operations(self, entity_id: str) -> list[dict]

#### Entity Tracer Example

Truy vết một lô hàng (Shipment) qua nhiều phòng ban (Sub-chains):

```python
from hierachain.domains.generic.utils.entity_tracer import EntityTracer

tracer = EntityTracer(hierarchy_manager)

# Truy vết thực thể "SHIPMENT-123" trên toàn mạng lưới
history = tracer.trace_entity_across_chains("SHIPMENT-123")

for chain, events in history.items():
    print(f"Chain: {chain}, Events count: {len(events)}")
```

#### Cross-Chain Validation

Kiểm tra xem dữ liệu ở Sub-chain có khớp với Proof ở Main chain không:

```python
from hierachain.domains.generic.utils.cross_chain_validator import CrossChainValidator

validator = CrossChainValidator(hierarchy_manager, tracer)
report = validator.validate_chain_consistency("logistics_chain")

if report["is_consistent"]:
    print("Dữ liệu chuỗi logistics hoàn toàn nhất quán.")
```

## Event Types được hỗ trợ

| Event Type | Mô tả | Details keys |
|---|---|---|
| operation_start | Bắt đầu thao tác | operation_type, operator |
| operation_complete | Hoàn thành thao tác | operation_type, result |
| status_update | Cập nhật trạng thái | status, previous_status |
| resource_assigned | Phân bổ tài nguyên | resource_type, quantity |
| quality_check | Kiểm tra chất lượng | check_result, checker |
| approval | Phê duyệt | approval_status, approver |
| compliance_check | Kiểm tra tuân thủ | compliance_type, compliance_status |

## Tính năng & hạn chế

* **Tính năng**: 

    * Khung sẵn có giúp xây dựng domain nhanh
    * Có sẵn tiện ích truy vết entity cross-chain
    * Validation nhất quán giữa các chain
    * Operation metrics tự động

* **Hạn chế**: 

    * Tuỳ chỉnh sâu cho domain cụ thể cần mở rộng lớp cơ sở
    * Domain chain phụ thuộc vào SubChain và HierarchyManager

## Liên quan

* Hierarchical module: [Hierarchical](hierarchical.md)
* API v1: [API v1](../reference/api-v1.md)
* Glossary: [Thuật ngữ](../glossary.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Thư mục: `hierachain/domains/generic/{chains, events, utils}`.
    * BaseChain mở rộng `hierachain.hierarchical.sub_chain.SubChain`.
    * BaseEvent sử dụng `hierachain.core.utils.validate_event_structure`.

    **DECISION**

    * Chuẩn hoá domain qua lớp cơ sở để tăng khả năng tái sử dụng và kiểm thử.
    * Entity ID là metadata field, không phải block identifier.
    * Sử dụng factory functions cho việc tạo event thay vì trực tiếp gọi constructor.

    **ASSUMPTION**

    * Mỗi domain sẽ định nghĩa schema sự kiện tối thiểu tương thích với Core/Event.
    * HierarchyManager đã được khởi tạo trước khi sử dụng EntityTracer.

    **INVARIANT**

    * Domain Event khi ghi vào Chain phải đáp ứng schema và bất biến Core (hash/Merkle xác định).
    * entity_id phải nhất quán khi truy vết across chains.

    **EDGE CASES**

    * Truy vết thực thể qua nhiều sub‑chain cần ràng buộc định danh nhất quán (entity_id).
    * Operation without start: báo warning nhưng không reject.
    * Concurrent operations: ghi nhận inconsistency.
