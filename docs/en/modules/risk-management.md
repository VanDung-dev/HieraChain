---
title: "Risk Management Module"
description: "Audit logging and integrity reporting for operational events."
icon: material/alert-circle
---

# Risk Management Module (`hierachain/risk_management/*`)

## Overview

The **Risk Management** package currently provides audit logging and integrity reporting for operational events.

---

## Main Component

<div class="grid cards" markdown>

*   :material-file-lock:{ .lg .middle } __Audit Logger__

    ---

    __File__: `audit_logger.py`

    * Records the entire risk lifecycle in **JSONL** format.
    * Ensures data integrity using **SHA-256** hashing.
    * Supports querying and creating reports for compliance auditing.

</div>

---

## Audit Logging and Integrity

Every event in the module is stored with a unique Correlation ID and protected against tampering:

*   **Hashing**: Each audit record contains a SHA-256 hash of its content, enabling detection of log tampering.
*   **Rotation**: Automatic log rotation (100MB) and compression of old data for storage optimization.
*   **Retention**: Logs are stored by default for 90 days (configurable).

---

## Related

*   [Performance Monitoring](./monitoring.md)
*   [Security and Identity](./security.md)
*   [System Error Mitigation](./error-mitigation.md)
