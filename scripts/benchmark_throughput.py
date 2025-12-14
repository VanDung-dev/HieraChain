"""
Benchmarking script for HieraChain Framework.

This script uses the OrderingService to simulate a high throughput scenario.
It generates a specified number of events, submits them to the service, and measures
the time taken to process them.
"""

import argparse
import time
import logging
import sys
import os
import asyncio
from typing import List, Dict, Any

from hierachain.consensus.ordering_service import OrderingService, OrderingNode, OrderingStatus
from hierachain.security.security_utils import KeyPair
from hierachain.config.settings import Settings

# Ensure project root is in path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("benchmark_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def generate_events(count: int) -> List[Dict[str, Any]]:
    events = []
    # Generate a keypair for signing
    kp = KeyPair.generate()
    public_key = kp.public_key
    
    for i in range(count):
        payload = f"nonce_{i}"
        signature = kp.sign(payload.encode())
        
        event = {
            "entity_id": "user1",
            "event": "transaction",
            "timestamp": time.time(),
            "details": {"nonce": str(i), "payload": payload},
            "sender": public_key,
            "receiver": "user2",
            "amount": 10,
            "signature": signature,
            "creator_id": "user1",
        }
        events.append(event)
    return events

async def run_benchmark(event_count: int, workers: int, batch_size: int):
    logger.info(f"Starting benchmark with {event_count} events, {workers} workers, batch size {batch_size}")
    
    # Configure settings override
    config = {
        "max_workers": workers,
        "block_size": batch_size,
        "batch_timeout": 0.5 # Low timeout to trigger block creation frequently
    }
    
    # Initialize Service with Dummy Node
    node = OrderingNode(
        node_id="benchmark_node",
        endpoint="localhost",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()
    )
    
    service = OrderingService(nodes=[node], config=config)
    # Force status to active
    service.status = OrderingStatus.ACTIVE
    
    # Generate Data
    logger.info("Generating events...")
    events = generate_events(event_count)
    logger.info("Events generated.")
    
    # Start Service
    service.start()
    
    try:
        start_time = time.time()
        
        # Submit events
        for event in events:
            service.receive_event(event, "default", "org1")
            
        logger.info(f"Submitted {event_count} events. Waiting for processing...")
        
        # Wait for completion
        while True:
            processed = service.statistics["events_certified"]
            rejected = service.statistics["events_rejected"]
            blocks = service.blocks_created
            
            if (processed + rejected) >= event_count:
                break
            
            if time.time() - start_time > 60: # 1 minute timeout
                logger.warning("Timeout reached!")
                break
                
            await asyncio.sleep(0.5)
            
        end_time = time.time()
        duration = end_time - start_time
        tps = event_count / duration
        
        logger.info("Benchmark Complete!")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Throughput: {tps:.2f} events/sec")
        logger.info(f"Average Latency: {service.statistics['average_processing_time']:.4f}s")
        logger.info(f"Blocks Created: {service.blocks_created}")
        
    finally:
        service.shutdown()

def main():
    parser = argparse.ArgumentParser(description="HieraChain Throughput Benchmark")
    parser.add_argument("--events", type=int, default=1000, help="Number of events")
    parser.add_argument("--workers", type=int, default=Settings.MAX_WORKERS, help="Number of workers")
    parser.add_argument("--batch-size", type=int, default=100, help="Events per block")
    
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(args.events, args.workers, args.batch_size))

if __name__ == "__main__":
    main()
