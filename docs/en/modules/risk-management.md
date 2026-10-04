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

    * Stores audit events in the configured backend; Arrow Parquet is the default, and `FileAuditStorage` writes JSONL.
    * Computes a **SHA-256** digest over every `AuditEvent` field.
    * Supports querying and creating reports for compliance auditing.

</div>

---

## Audit Logging and Integrity

Audit event integrity uses a separate trusted digest manifest:

*   Set `HRC_AUDIT_MANIFEST_WRITE_URL` to the PostgreSQL URL used to record digests. In production, `AuditLogger` refuses to start without this URL or an explicit `integrity_digest_writer(event_id, digest)` callback. To enable built-in read verification, set `HRC_AUDIT_MANIFEST_READ_URL` separately to a URL that can read the manifest; the writer URL is not reused as a reader credential.
*   Keep the manifest database outside the archive's mutable host or volume, with separate access controls. Give the application role only `INSERT` on the table and a separate verifier role only `SELECT`; both need schema `USAGE`. A sidecar that can be edited alongside the archive does not provide tamper evidence.
*   Create the two roles and the manifest table in that database before starting the logger:

    ```sql
    CREATE TABLE public.audit_event_digests (
        event_id TEXT PRIMARY KEY,
        digest TEXT NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    REVOKE ALL ON public.audit_event_digests FROM PUBLIC;
    GRANT USAGE ON SCHEMA public TO audit_manifest_writer, audit_manifest_reader;
    GRANT INSERT ON public.audit_event_digests TO audit_manifest_writer;
    GRANT SELECT ON public.audit_event_digests TO audit_manifest_reader;
    ```

*   `query_events()` and `generate_report()` return archive data without a trusted-manifest status. Do not treat those results as verified. Call `query_events_with_integrity(filter_criteria, limit)` for an explicit `AuditReadResult`: it returns `verified` only after checking the full archive against the manifest, returns `unverified` when no digest reader is configured, and returns `failed` with no events when the manifest cannot be read or any archive record is missing, extra, duplicated, or changed.
*   The explicit API can use `HRC_AUDIT_MANIFEST_READ_URL` or an `integrity_digest_reader()` callback. A write-only URL is not used to read digests. For lower-level verification, pass `manifest.load_hashes()` and the complete archive event set to `verify_integrity(events, expected_hashes)`.
*   `verify_integrity(events, expected_hashes)` returns `False` when the manifest is missing or when event IDs or digests differ. Pass the complete event set represented by the manifest; missing, extra, duplicate, or changed records fail verification.
*   If archive storage or the digest writer fails, the exception reaches the caller and no success statistics or alerts are emitted. A failure after archive storage can leave an event without a manifest entry; verification rejects it.
*   Arrow audit files rotate at 100 MB. `get_event_count()` uses Parquet row counts for an unfiltered count and scans only the selected filter columns in bounded batches otherwise. SQLite and Arrow apply the same event type, severity, source, user, and inclusive time-range filters.
*   Arrow retention is explicit: `ArrowAuditStorage.cleanup_old_events(max_age_seconds)` removes a Parquet archive only when every event in it is older than the cutoff. It returns the number of deleted events. Mixed-age archives and legacy `.arrow`, `.log`, or `.jsonl` files remain; no automatic cleanup runs. Coordinate archive deletion with the independently stored digest manifest before using full-manifest integrity verification.
*   `FileAuditStorage` writes daily JSONL files.
*   Audit retrieval and counting fail with `RuntimeError` when a database, archive, or decoded record cannot be read. They do not convert a failed search into `[]`, `0`, or a partial result. Corrupt Parquet files are not retried as legacy Arrow frames; truncated legacy frames and malformed JSONL records also fail. A valid empty search still returns `[]` or `0`. Consumers must handle the error before presenting a report. A limited query validates only the records it reads, and an unfiltered Parquet count uses metadata; neither replaces complete archive integrity verification.

---

## Related

*   [Performance Monitoring](./monitoring.md)
*   [Security and Identity](./security.md)
*   [System Error Mitigation](./error-mitigation.md)

## CSV report export

`AuditLogger.generate_report(..., output_format="csv")` uses CSV quoting for commas, quotes and line breaks in every cell. Text cells whose first non-whitespace character is `=`, `+`, `-` or `@` receive an apostrophe prefix to prevent spreadsheet formula interpretation. This export policy changes those CSV text cells; the stored events and JSON export retain the original values. CSV export does not imply trusted-manifest verification.
