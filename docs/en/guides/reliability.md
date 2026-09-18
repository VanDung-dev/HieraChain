---
title: "Reliability Guide"
description: "Reliability patterns: journal, rollback, recovery, retry/idempotency, cross-level sync."
icon: material/check-decagram
---

# Reliability Guide

## Purpose

Provides practices to ensure stable system operation and easy recovery from failures.

## Related Components

* Journal/Recovery: `hierachain/error_mitigation/journal.py`, `rollback_manager.py`, `consensus_recovery.py`, `network_recovery.py`, `backup_recovery.py`
* Cross-level Sync: `HRC_CROSS_LEVEL_SYNC` via `hierarchical/hierarchy_manager/base.py`, `hierachain/cluster/cross_level_sync.py`

## Patterns

* Durable Journal: write before applying changes.
* Safe Rollback: state can return to a safe point.
* Automatic Recovery: standard scenarios for connection loss/DB errors.
* Idempotency + Retry with backoff: repeat actions without duplicating effects.

## Implementation Recommendations

* Apply journal for important state-changing operations.
* Set reasonable thresholds and timeouts for retry; ensure idempotency keys.
* Use metrics/alert to detect abnormal retry loops.
