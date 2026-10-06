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

## Related configuration

* `AdvancedCache(max_size=..., eviction_policy=...)`: per-instance capacity and LRU/LFU/FIFO/TTL policy; entry TTL is supplied to `set()`. There is no global cache switch or automatically wired block/event/entity cache tier.
* Ordering's `block_cache_size` controls its local block-history deque (default: `100`).
* Ordering batches: direct `OrderingService` defaults to 100 events and 2.0 seconds; the default Sub-Chain configuration uses 50 events and 1.0 second.

## Recommendations

* Tune `batch_size` or `block_size` and `batch_timeout` according to measured load and the service configuration in use.
* Use Arrow to reduce conversion overhead; avoid multiple conversions back and forth.

## Minimum Benchmark

1. **Write 10k events and measure time**: Run basic load test.
2. **Adjust configuration**: Try changing the ordering batch settings; tune cache instances only where the measured workload uses them.
3. **Compare results**: Measure throughput (events/sec) and latency (p50/p95).

## System Observation

* Use `monitoring/performance_monitor.py` to get CPU/RAM metrics.
* Enable `ResourceGuardMiddleware` for load shedding during peak load.
