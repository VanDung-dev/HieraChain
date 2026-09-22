"""PostgreSQL throughput benchmark for the Docker runtime."""

import argparse
import asyncio
import logging
import os
import time
from typing import Any

from hierachain.consensus import OrderingNode, OrderingService, OrderingStatus
from hierachain.security.security_utils import KeyPair


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.getenv("HRC_BENCHMARK_LOG_FILE", "/app/log/benchmark_debug.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def generate_events(count: int) -> list[dict[str, Any]]:
    key_pair = KeyPair.generate()
    events = []
    for index in range(count):
        payload = f"nonce_{index}"
        events.append(
            {
                "entity_id": "user1",
                "event": "benchmark_event",
                "timestamp": time.time(),
                "details": {"nonce": str(index), "payload": payload},
                "source": key_pair.public_key,
                "target": "user2",
                "quantity": 10,
                "signature": key_pair.sign(payload.encode()),
                "creator_id": "user1",
            }
        )
    return events


async def run_benchmark(event_count: int, batch_size: int) -> None:
    database_url = os.getenv("HRC_BENCHMARK_DB_URL")
    if not database_url or not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Docker benchmark requires HRC_BENCHMARK_DB_URL to point to PostgreSQL")

    config = {
        "block_size": batch_size,
        "batch_timeout": 0.5,
        "db_url": database_url,
        "storage_dir": os.getenv("HRC_BENCHMARK_JOURNAL_DIR", "/app/data/journal"),
        "chain_name": "benchmark-docker",
    }
    node = OrderingNode(
        node_id="benchmark_docker_node",
        endpoint="localhost",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time(),
    )
    service = OrderingService(nodes=[node], config=config)
    initial_blocks = service.blocks_created
    service.status = OrderingStatus.ACTIVE
    events = generate_events(event_count)
    service.start()
    baseline = service.get_statistics()
    baseline_processed = baseline["events_certified"]
    baseline_rejected = baseline["events_rejected"]

    try:
        start_time = time.time()
        for event in events:
            service.receive_event(event, "default", "org1")

        while True:
            stats = service.get_statistics()
            processed = stats["events_certified"] - baseline_processed
            rejected = stats["events_rejected"] - baseline_rejected
            completed = processed + rejected >= event_count
            required_blocks = initial_blocks + (processed + batch_size - 1) // batch_size
            if completed and service.blocks_created >= required_blocks:
                break
            if time.time() - start_time > 60:
                logger.warning("Timeout reached")
                break
            await asyncio.sleep(0.01)

        duration = time.time() - start_time
        logger.info("Benchmark complete")
        logger.info("Duration: %.2fs", duration)
        logger.info("Throughput: %.2f events/sec", event_count / duration)
        logger.info("Average latency: %.4fs", stats["average_processing_time"])
        logger.info("Blocks created: %d", service.blocks_created)
    finally:
        service.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="HieraChain Docker PostgreSQL throughput benchmark")
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.events, args.batch_size))


if __name__ == "__main__":
    main()
