---
title: "Domains module"
description: "Miền nghiệp vụ chung: chains/events/utils — base_chain, domain_chain, base_event, domain_event, cross_chain_validator, entity_tracer."
icon: material/domain
---

# Domains (Generic)

Mô‑đun cung cấp khung chung cho các miền nghiệp vụ (generic domains) để chuẩn hoá cách xây dựng chuỗi và sự kiện domain.

## Thành phần & khái niệm

* Domain Chain: `hierachain/domains/generic/chains/{base_chain.py, domain_chain.py}` — lớp cơ sở và hiện thực Chain theo domain.
* Domain Event: `hierachain/domains/generic/events/{base_event.py, domain_event.py}` — lớp cơ sở và hiện thực Event theo domain.
* Tiện ích: `hierachain/domains/generic/utils/{cross_chain_validator.py, entity_tracer.py}` — kiểm tra liên chuỗi và truy vết thực thể.

## API công khai (mang tính mô tả)

```python
class BaseDomainChain:
  add_event(event) -> bool
  get_domain_statistics() -> dict

class EntityTracer:
  trace_entity_in_chain(entity_id, chain_name) -> dict
  trace_entity_across_chains(entity_id) -> dict[str, list[dict]]
```

## Tính năng & hạn chế

* Tính năng: khung sẵn có giúp xây dựng domain nhanh, có sẵn tiện ích truy vết.
* Hạn chế: tuỳ chỉnh sâu cho domain cụ thể cần mở rộng lớp cơ sở.

## Liên quan

* Hierarchical module: [Hierarchical](hierarchical.md)
* API v1: [API v1](../reference/api-v1.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Thư mục: `hierachain/domains/generic/{chains, events, utils}`.

    **DECISION**

    * Chuẩn hoá domain qua lớp cơ sở để tăng khả năng tái sử dụng và kiểm thử.

    **ASSUMPTION**

    * Mỗi domain sẽ định nghĩa schema sự kiện tối thiểu tương thích với Core/Event.

    **INVARIANT**

    * Domain Event khi ghi vào Chain phải đáp ứng schema và bất biến Core (hash/Merkle xác định).

    **EDGE CASES**

    * Truy vết thực thể qua nhiều sub‑chain cần ràng buộc định danh nhất quán (entity_id).
