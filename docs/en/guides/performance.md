---
title: "Performance Guide"
description: "Performance optimization guide: L1/L2 cache, Apache Arrow, batch size, parallelization, benchmark tips."
icon: material/speedometer
---

# Performance Guide

## Purpose

Provides recommendations for achieving good performance when storing/processing events and submitting proofs.

## Principles

* Optimize data structure: use Arrow for columnar storage.
* Reduce IO/serialize overhead: batch events, avoid large binary payloads in `data`.
* Use caching wisely: L1 in memory, L2 persistent if needed.

## Related Settings (excerpt from `config/settings.py`)

* `ADVANCED_CACHING_ENABLED`: enable advanced caching.
* `BLOCK_CACHE_SIZE`, `EVENT_CACHE_SIZE`, `ENTITY_CACHE_SIZE`: cache sizes.
* Policies: `BLOCK_CACHE_POLICY` (lru/lfu/fifo/ttl), `EVENT_CACHE_POLICY`, `ENTITY_CACHE_POLICY`.
* Ordering batches: direct `OrderingService` defaults to 100 events and 2.0 seconds; the default Sub-Chain configuration uses 50 events and 1.0 second.

## Recommendations

* Tune `batch_size` or `block_size` and `batch_timeout` according to measured load and the service configuration in use.
* Use Arrow to reduce conversion overhead; avoid multiple conversions back and forth.

## Minimum Benchmark

1. **Write 10k events and measure time**: Run basic load test.
2. **Adjust configuration**: Try changing the ordering batch settings and `EVENT_CACHE_POLICY`.
3. **Compare results**: Measure throughput (events/sec) and latency (p50/p95).

## System Observation

* Use `monitoring/performance_monitor.py` to get CPU/RAM metrics.
* Enable `ResourceGuardMiddleware` for load shedding during peak load.
