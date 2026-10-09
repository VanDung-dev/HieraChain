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
3. **Compare results**: Measure committed-event throughput and latency (p95/p99), alongside rejected/unfinished events, batch wait, durability and I/O cost.

The signed-event benchmark uses the same implementation locally and in Docker:

```bash
python -m scripts.benchmark_throughput --events 10000 --batch-size 100
```

Configure the node signing identity and trusted keys, and use an isolated database and journal through `HRC_BENCHMARK_DB_URL` and `HRC_BENCHMARK_JOURNAL_DIR`. The Docker wrapper requires PostgreSQL. The result reports committed events per second, rejected/unfinished counts, p95/p99, a 0.5-second batch timeout and the journal/storage durability boundary. Rejections or a 60-second processing timeout make the command fail. Latency measures when the client observes a committed block, including synchronous submission and block-draining delays; it is not an internal database commit timestamp. This benchmark does not measure I/O cost or establish a production SLA.

## System Observation

* Use `monitoring/performance_monitor.py` to get CPU/RAM metrics.
* Inspect API payload/rate limits, Redis failures, ordering event-pool/RAM limits and storage error logs. The API has no CPU/RAM `ResourceGuardMiddleware`.
