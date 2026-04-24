# WF-14: ERP Integration Sync

**Group**: E — Operational & Integration Layer
**Trigger**: `SyncScheduler` timer fires (configurable `interval_seconds`) or manual `sync_now()` call
**Output**: ERP change events translated and submitted to HieraChain Sub-Chain via WF-1
**Key modules**: `integration/erp_ledger.py`, `integration/erp_adapters/`

> [← WF-13: Risk Alerts](./wf-13-risk-alerts.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-15: MSP Identity →](./wf-15-msp-identity.md)

---

## Overview

HieraChain integrates with enterprise ERP systems (SAP, Oracle, Dynamics) via an **adapter + mapping engine** architecture. The `SyncScheduler` polls ERP adapters on a configurable interval, translates native ERP events into HieraChain event format via `EventTranslator`, detects meaningful field changes, and submits them as business events. Failed syncs use exponential backoff retry.

This workflow acts as the **ingestion bridge** between Web2 ERP systems and the HieraChain ledger.

---

## Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant ERP as 🏢 ERP System (SAP / Oracle)
    participant EIL as 🔗 ERPIntegrationLedger
    participant ME as 🗺️ MappingEngine
    participant CD as 🔄 ChangeDetector
    participant ET as 🔀 EventTranslator
    participant SS as ⏰ SyncScheduler
    participant SC as 📦 SubChain

    Note over SS: SyncScheduler fires every interval_seconds

    SS->>EIL: _execute_sync(profile_name, profile, adapter, chain)
    EIL->>ERP: adapter.get_changes_since_last_sync()
    ERP-->>EIL: [erp_event_1, erp_event_2, ...]

    loop Each ERP event
        EIL->>ME: get_profile(profile_name)
        ME-->>EIL: MappingProfile { erp_system, mapping_rules, detect_changes }

        alt detect_changes=True
            EIL->>CD: detect_changes(erp_event, profile)
            CD->>CD: compare_states(previous_state, erp_event)
            CD->>CD: Annotate { change_detected, changes: { field: { old, new, type } } }
            CD-->>EIL: Annotated erp_event
        end

        EIL->>ET: translate(erp_event, mapping_rules)
        ET->>ET: Apply field mapping (simple path or transformer function)
        ET->>ET: add_blockchain_metadata()<br/>{ timestamp, event: "erp_integration", source: erp_system }
        ET-->>EIL: blockchain_event dict

        EIL->>SC: add_event(blockchain_event)
        Note right of SC: Enters WF-1 pipeline
    end

    EIL->>SS: update_last_sync(profile_name, now)
    SS->>SS: Schedule next execution (now + interval_seconds)

    alt Sync fails
        SS->>SS: schedule_retry(profile_name)<br/>Exponential backoff: min(300, 30 × 2^retry_count)
    end
```

---

## Flow Diagram — Retry on Failure

```mermaid
flowchart LR
    SYNC["_execute_sync()"] -->|Success| UPD["update_last_sync()\nnext = now + interval"]
    SYNC -->|Exception| RETRY["schedule_retry(profile)\nbackoff = min(300s, 30 × 2^n)"]
    RETRY --> WAIT["Wait backoff duration"]
    WAIT --> SYNC
    RETRY -->|retry_count > max| ALERT["Alert via WF-13\nSync failure escalation"]
```

---

## ERP Event Translation Example

```python
# Raw SAP event (before translation)
erp_event = {
    "MBLNR": "5000012345",       # Material document number
    "BUDAT": "2024-04-23",       # Posting date
    "MATNR": "MAT-00789",        # Material number
    "MENGE": 150,                 # Quantity
    "WERKS": "PLANT-01"          # Plant
}

# After EventTranslator.translate() using SAP mapping profile
blockchain_event = {
    "entity_id": "MAT-00789",            # mapped from MATNR
    "event": "erp_integration",
    "timestamp": 1714000000.0,           # added by add_blockchain_metadata()
    "details": {
        "document_number": "5000012345", # mapped from MBLNR
        "posting_date": "2024-04-23",    # mapped from BUDAT
        "quantity": 150,                  # mapped from MENGE
        "plant": "PLANT-01",             # mapped from WERKS
        "source": "SAP",
        "changes": {                      # added by ChangeDetector if enabled
            "quantity": {"old": 100, "new": 150, "type": "numeric_change"}
        }
    }
}
```

---

## Supported ERP Systems

| ERP | Adapter Class | Config Key |
|:----|:-------------|:-----------|
| SAP S/4HANA | `SAPAdapter` | `erp_system: "SAP"` |
| Oracle ERP Cloud | `OracleAdapter` | `erp_system: "Oracle"` |
| Microsoft Dynamics 365 | `DynamicsAdapter` | `erp_system: "Dynamics"` |
| Generic REST | `GenericERPAdapter` | `erp_system: "Generic"` |

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Scheduler fires** | `SyncScheduler` calls `_execute_sync()` for each registered profile |
| **2. Fetch changes** | ERP adapter calls `get_changes_since_last_sync()` using last sync timestamp |
| **3. Change detection** | `ChangeDetector` compares new state vs previous, annotates changed fields |
| **4. Translation** | `EventTranslator` applies `mapping_rules` to produce a valid HieraChain event dict |
| **5. Metadata injection** | `add_blockchain_metadata()` adds `timestamp`, `source`, `event: "erp_integration"` |
| **6. Submit** | `SubChain.add_event(blockchain_event)` — enters WF-1 pipeline |
| **7. Update timestamp** | `last_sync` updated per profile; next run scheduled |
| **8. Failure retry** | Exception → exponential backoff up to 300s; after max retries → WF-13 alert |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| ERP adapter connection fails | Retry with exponential backoff (30s, 60s, 120s, 240s, 300s max) |
| Field mapping key missing | Logged as warning; event submitted with partial data |
| `add_event()` validation fails (forbidden term) | Event discarded; logged with raw ERP data |
| Max retries exceeded | WF-13 alert triggered: `erp_sync_failure` |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Sync entry | `ERPIntegrationLedger.start_scheduled_sync()` | `integration/erp_ledger.py` |
| Execute sync | `ERPIntegrationLedger._execute_sync()` | `integration/erp_ledger.py` |
| Change detection | `ChangeDetector.detect_changes()` | `integration/erp_ledger.py` |
| Field translation | `EventTranslator.translate()` | `integration/erp_ledger.py` |
| Profile management | `MappingEngine.create_profile()` | `integration/erp_ledger.py` |
| Retry scheduling | `SyncScheduler.schedule_retry()` | `integration/erp_ledger.py` |

---

## See Also

- [WF-1: Event Submission](./wf-01-event-submission.md) — translated events enter here
- [WF-7: Entity Tracing](./wf-07-entity-tracing.md) — ERP-originated events are traceable by `entity_id`
- [WF-13: Risk Analysis & Alerts](./wf-13-risk-alerts.md) — sync failures escalated here
