---
title: "Data Models"
description: "Describes Event/Block/Transaction schemas based on hierachain/core/schemas.py; examples and invariants."
icon: material/database-outline
---

# Data Models

## Purpose

Standardize core data structures (Event, BlockHeader, Transaction, full Block) for cross-language compatibility and data integrity.

## Concepts & Scope

* Based on Arrow Schema in `hierachain/core/schemas.py`.
* Applies to: Core module, Sub-Chain/Main Chain, and API (serialize/deserialize).

## Main Schemas

### Event

Describes a domain event.

```python
EVENT_SCHEMA = schema([
  ('entity_id', string),          # Entity ID
  ('event', string),              # Event type
  ('timestamp', float64),         # epoch seconds (float)
  ('details', map<string,string>),# metadata key->string (On-chain)
  ('details_cid', string),        # IPFS CID (Off-chain reference)
  ('details_nonce', string),      # Encryption nonce
  ('data', binary),               # optional binary payload
])
```

Example JSON (when returned via API):

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

Minimal metadata for a block.

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

Standardized transaction/event (with signature, optional ZK proof).

```python
TRANSACTION_SCHEMA = schema([
  ('tx_id', string),
  ('entity_id', string),
  ('event_type', string),
  ('arrow_payload', binary),        # Arrow serialized
  ('signature', string),            # hex signature
  ('timestamp', float64),
  ('details', map<string,string>),
  ('zk_proof', binary),             # optional
  ('zk_public_inputs', binary),     # optional
])
```

### Block (full)

Full block consists of header + event list + (optional) block-level ZK proof.

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

## Pydantic Mapping (API v1)

Pydantic models (`hierachain/api/v1/schemas.py`) are used for API data validation, mapped to core structures:

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

**Conversion rules:**

* `EventRequest.details` (Dict) -> `EVENT_SCHEMA.details` (Map<String, String>).
* `ProofSubmissionRequest` -> wrapped as `Event` on Main Chain with type `proof_submission`.

## Serialization & Conversion

* `Block.events` uses `pyarrow.Table` internally; when returned via API it can be converted to a list of dicts (`to_event_list()` or `to_pylist()`).
* `details` field is always map<string,string>; non-string values will be converted to strings upon input.
* `data` field is binary; when passing through JSON it needs base64 encoding or can be omitted if not needed.

## Example Operations (Description)

```python
# Create Block from event list (dict)
blk = Block(index=1, events=[{...}, {...}], previous_hash="<hash>")

# Get event list as dict
events = blk.to_event_list()

# Check chain validity
blockchain.is_chain_valid()
```

## Related

* Core module: [Core](../modules/core.md)
* API v1: [API v1](api-v1.md)
