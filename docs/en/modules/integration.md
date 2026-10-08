---
title: "Integration Module"
description: "ERP mapping and scheduling primitives with explicitly gated synthetic vendor fixtures."
icon: material/puzzle
---

# Integration Module (`hierachain/integration/*`)

## 1. Overview

The `integration` module provides field mapping, change detection, and scheduling utilities for applications that connect an ERP adapter to a HieraChain event sink. It does not include a real SAP, Oracle, or Microsoft Dynamics transport, and the API server does not start ERP synchronization automatically. Callers register their own adapter and chain sink.

## 2. Core components

### 2.1 ERP Integration Ledger (`erp_ledger.py`, `erp/base.py`)

* Coordinates caller-provided adapters and translates their records through a mapping profile.
* Passes the profile's `config` to the registered adapter constructor.
* Requires a chain sink for scheduled delivery; use `translate_erp_to_blockchain()` for translation-only work.
* Accepts optional `detect_changes` and `key_fields` profile metadata. Key fields support dotted paths such as `material.document_number`.

An adapter registered with `register_adapter()` must provide `get_changes_since_last_sync()`. A sink's `add_event()` must return `True` or a non-empty event identifier for the event to count as accepted.

### 2.2 Exported vendor fixtures (`enterprise.py`)

`SAPIntegration`, `OracleIntegration`, and `DynamicsIntegration` return synthetic fixture records. `EnterpriseIntegration.connect_to_erp()` rejects them by default. Pass `{"simulation_mode": True}` to opt in during tests or demonstrations. These classes make no network requests and do not authenticate against a vendor system.

### 2.3 Change detector (`erp/change_detector.py`)

* Compares business fields against an in-memory snapshot scoped by profile and entity key.
* Ignores its own `changes` and `change_detected` metadata when taking the next snapshot, so an unchanged record remains unchanged.

## 3. Mapping engine

The mapping engine transforms source fields into event fields and builds nested objects from dotted destinations such as `details.quantity`.

| Transformer | Function | Example transformation |
| :--- | :--- | :--- |
| `date` | Standardizes timestamp formats | `12/04/2024` -> `ISO-8601` |
| `amount` | Normalizes numeric values | `5000` -> `5000.0` |
| `status` | Maps business status codes | `REQ` -> `REQUESTED` |
| `id` | Adds identifier prefixes | `123` -> `ERP_123` |
| `boolean` | Normalizes truth values | `1/Yes/On` -> `True` |

Mapping rules, adapter config, and key fields are copied when a profile is created and when it is read. Changes to caller-owned input objects do not alter the registered profile.

## 4. Synchronization and retries

`SyncScheduler` invokes a caller-provided adapter, translates each returned record, and submits it to the supplied chain sink. A record counts as processed only after the sink acknowledges it. A missing sink fails before the adapter is queried. Per-record translation or delivery errors make the run `failed`; `get_sync_status()` exposes accepted-event counts and errors.

Successful runs use the configured interval. Failed runs retry after 30, 60, then 120 seconds by default, with the delay capped at 300 seconds. After three retries beyond the initial attempt, the task reports `retry_exhausted` and stops scheduling further runs. Scheduler status is in memory and does not survive a process restart. Delivery is at least once when a batch is retried: records accepted during an earlier partial run can be submitted again. Use stable event identifiers, an adapter delivery cursor, and sink-side deduplication or operator reconciliation; this module does not provide exactly-once delivery.

Replacing or stopping a profile cancels its pending timer and prevents stale generations from starting another run. It cannot cancel an adapter call that is already running; that call may still deliver records before it returns, while its stale result is ignored by the scheduler.

## 5. Usage example

Register an adapter implemented by your application and provide a sink:

```python
from hierachain.integration.erp_ledger import ERPIntegrationLedger

ledger = ERPIntegrationLedger()
ledger.register_adapter("sap", MyConfiguredSapAdapter)  # application-provided
ledger.create_mapping_profile(
    "SAP_Logistics",
    "sap",
    {
        "entity_id": "material.document_number",
        "event": "material.event_type",
        "details.quantity": "material.qty",
    },
    config={"tenant": "example"},
    detect_changes=True,
    key_fields=["material.document_number"],
)
ledger.start_scheduled_sync(
    profile_name="SAP_Logistics",
    interval_seconds=60,
    chain=sub_chain_instance,
)
```

`MyConfiguredSapAdapter` and `sub_chain_instance` are supplied by the calling application. Vendor fixture classes are separate, simulation-only examples.

## 6. Runtime scope

The integration ledger is a library component; it is not wired into the REST server lifecycle. Applications must register adapters, choose a chain sink, manage credentials in their own adapter, and monitor the returned sync status.

## Related

* [Hierarchical Module](./hierarchical.md)
* [Core Module](./core.md)
* [Error Mitigation](./error-mitigation.md)

## Change detection identity

Configured `key_fields` must be a non-empty list of non-empty field paths. Missing, null or empty-string identity values raise `ValueError` before the detector mutates its snapshot or the record. Numeric `0` remains valid. Nested SAP paths such as `material.document_number` distinguish records; missing identities are never grouped under an `unknown` key. Scheduled synchronization reports such records as failed translation rather than successful delivery.
