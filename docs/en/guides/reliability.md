---
title: "Reliability Guide"
description: "Reliability patterns: journal, rollback, recovery, retry/idempotency, cross-level sync."
icon: material/check-decagram
---

# Reliability Guide

## Purpose

Provides practices to ensure stable system operation and easy recovery from failures.

## Related Components

* Journal/Recovery: `hierachain/error_mitigation/journal.py`, `error_classifier.py`, and BFT view change in `hierachain/consensus/bft/view_change.py`
* Cross-level Sync: `HRC_CROSS_LEVEL_SYNC` via `hierarchical/hierarchy_manager/base.py`, `hierachain/cluster/cross_level_sync.py`

## Patterns

* Durable Journal: write before applying changes.
* Operational Recovery: backups, snapshots, and node replacement are owned by deployment.
* Idempotency + Retry with backoff: repeat actions without duplicating effects.

## Implementation Recommendations

* Apply journal for important state-changing operations.
* Set reasonable thresholds and timeouts for retry; ensure idempotency keys.
* Use metrics/alert to detect abnormal retry loops.
