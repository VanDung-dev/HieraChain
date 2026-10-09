---
title: "Writing Domain Logic"
description: "Guide to implementing business rules, operation validation, and entity lifecycles using DomainChain."
icon: material/file-document-edit
---

# Writing Domain Logic

## 1. Domain Chains

HieraChain processes business logic through domain chains. Instead of deploying arbitrary bytecode smart contracts, developers implement domain logic by extending or configuring `DomainChain` in `hierachain/domains/chains/domain_chain.py`.

### Initializing a Domain Chain

`DomainChain` inherits from `BaseChain` and provides built-in validation for common operations:

```python
from hierachain.domains.chains.domain_chain import DomainChain

chain = DomainChain(
    name="supply_chain_01",
    domain_type="supply_chain"
)
```

## 2. Operation validation

`DomainChain` validates incoming operation payloads against required fields before creating events:

* `quality_check`: Requires `check_type` and `check_result`.
* `approval`: Requires `approval_type` and `approver_id`.
* `resource_allocation`: Requires `resource_type` and `resource_id`.
* `compliance_check`: Requires `compliance_type`.

Unknown operation types default to allowed, making custom extension straightforward:

```python
from hierachain.domains.chains.domain_chain import validate_operation_data

payload = {
    "check_type": "visual_inspection",
    "check_result": "passed"
}

is_valid = validate_operation_data("quality_check", payload)
assert is_valid is True
```

## 3. Recording domain operations

You record business operations using helper factories from `hierachain/domains/events/event_creators.py`:

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

## 4. Entity lifecycle management

`DomainChain` tracks entity state across operations:

1. Registration: Register a new tracked entity on the chain.
2. Status updates: Record transition states such as `in_progress`, `quality_approved`, and `completed`.
3. Metrics: `OperationMetricsTracker` records aggregate operation counts and success rates. It does not record execution latency or break results down by operation type.

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

## Related

* [Domains Module](../modules/domains.md)
* [Adding a Domain Chain](./add-domain-chain.md)
* [Cross-Chain Operations](./cross-chain-transactions.md)
