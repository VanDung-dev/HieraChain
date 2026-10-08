"""Measure signed-event throughput and observed submit-to-commit latency."""

import argparse
import asyncio
import logging
import math
import os
import time
from typing import Any

from hierachain.consensus import OrderingNode, OrderingService, OrderingStatus
from hierachain.security.security_utils import KeyPair
from hierachain.serialization import dumps_json

logger = logging.getLogger(__name__)


def generate_events(count: int) -> list[dict[str, Any]]:
    key_pair = KeyPair.generate()
    events = []
    for index in range(count):
        payload = f"nonce_{index}"
        events.append({
            "entity_id": "benchmark-entity", "event": "benchmark_event",
            "timestamp": time.time(), "details": {"payload": payload},
            "sender": key_pair.public_key,
            "signature": key_pair.sign(payload.encode()),
        })
    return events


async def run_benchmark(event_count: int, batch_size: int) -> dict[str, Any]:
    if event_count < 1 or batch_size < 1:
        raise ValueError("Event count and batch size must be positive")
    service = OrderingService(nodes=[OrderingNode(
        node_id="benchmark_node", endpoint="localhost", is_leader=True,
        weight=1.0, status=OrderingStatus.ACTIVE, last_heartbeat=time.time(),
    )], config={
        "block_size": batch_size, "batch_timeout": 0.5,
        "db_url": os.getenv("HRC_BENCHMARK_DB_URL", "hierachain.db"),
        "storage_dir": os.getenv("HRC_BENCHMARK_JOURNAL_DIR", "journal"),
        "chain_name": "benchmark",
    })
    try:
        if not service.wait_for_active():
            raise RuntimeError("Ordering service did not finish recovery")
        events = generate_events(event_count)
        baseline_rejected = service.get_statistics()["events_rejected"]
        submitted: dict[str, float] = {}
        latencies: list[float] = []
        start = time.perf_counter()
        for event in events:
            received_at = time.perf_counter()
            event_id = service.receive_event(event, "default", "org1")
            submitted[event_id] = received_at

        # ponytail: observations include submission/draining delay; sample at commit for internal latency.
        while True:
            block = service.get_next_block()
            while block is not None:
                observed_at = time.perf_counter()
                for event in block.to_event_list():
                    received_at = submitted.pop(event.get("event_id"), None)
                    if received_at is not None:
                        latencies.append(observed_at - received_at)
                block = service.get_next_block()
            rejected = service.get_statistics()["events_rejected"] - baseline_rejected
            if not submitted or rejected or time.perf_counter() - start >= 60:
                break
            await asyncio.sleep(0.01)

        duration = time.perf_counter() - start
        latencies.sort()
        result = {
            "events_submitted": event_count, "events_committed": len(latencies),
            "events_rejected": rejected,
            "events_unfinished": max(0, event_count - len(latencies) - rejected),
            "duration_seconds": duration,
            "committed_events_per_second": len(latencies) / duration,
            "latency_p95_seconds": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
            "latency_p99_seconds": latencies[math.ceil(len(latencies) * 0.99) - 1] if latencies else None,
            "batch_timeout_seconds": 0.5,
            "durability": "journal fsync and storage adapter commit",
        }
        logger.info("Benchmark result: %s", dumps_json(result))
        if submitted or rejected:
            raise RuntimeError("Benchmark incomplete: rejected or uncommitted events remain")
        return result
    finally:
        service.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO, handlers=[
        logging.FileHandler(os.getenv("HRC_BENCHMARK_LOG_FILE", "benchmark_debug.log")),
        logging.StreamHandler(),
    ])
    parser = argparse.ArgumentParser(description="HieraChain signed-event throughput benchmark")
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.events, args.batch_size))


if __name__ == "__main__":
    main()
