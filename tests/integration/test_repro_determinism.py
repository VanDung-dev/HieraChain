"""
Test deterministic behavior of the OrderingService.

The test checks if the OrderingService is deterministic.
It does this by running the service twice with the same data directory.
The first run sends 3 events, each with a delay to force a new block.
The second run recovers from the journal and checks if it produces the same blocks.
If the service is deterministic, it should produce the same blocks.
If the service is not deterministic, it should produce different blocks.
"""

import time
import shutil
import os
from hierachain.consensus.ordering_service import OrderingService, OrderingNode, OrderingStatus

def test_determinism():
    data_dir = "data/test_determinism"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    os.makedirs(data_dir)

    print("=== Phase 1: Original Run ===")
    
    # 1. Config
    config = {
        "storage_dir": os.path.join(data_dir, "journal"),
        "block_size": 10,       # Large enough not to trigger immediately
        "batch_timeout": 0.5,   # Fast timeout
        "worker_threads": 1
    }
    
    node = OrderingNode("node1", "localhost", True, 1.0, OrderingStatus.ACTIVE, time.time())
    
    service = OrderingService([node], config)
    
    # Send 3 events with delays to force 3 separate blocks via timeout
    # Send 3 events, waiting for block creation explicitly to ensure deterministic journal order
    ids = []
    current_block_count = 0
    for i in range(3):
        event = {"event": "test", "entity_id": f"e{i}", "timestamp": time.time(), "val": i}
        service.receive_event(event, "ch1", "org1")
        print(f"Sent event {i}, waiting for block...")
        
        # Wait for block count to increase
        start_wait = time.time()
        while service.blocks_created == current_block_count:
            time.sleep(0.1)
            if time.time() - start_wait > 5.0:
                raise TimeoutError(f"Block not created for event {i}")
        
        current_block_count = service.blocks_created
        print(f"Block created (Total: {current_block_count})")
        
    # Wait for processing
    time.sleep(1.0)
    
    blocks_phase1 = service.get_blocks()
    print(f"Phase 1 Blocks Created: {len(blocks_phase1)}")
    for b in blocks_phase1:
        print(f"  Block {b.index}: {len(b.events)} events, Hash: {b.hash[:8]}")
        
    service.shutdown()
    
    print("\n=== Phase 2: Recovery Run ===")
    
    # Restart service with SAME data dir
    # It should replay the journal.
    # If deterministic, it should produce 3 blocks (even though replay is fast).
    # If not deterministic, it might batch them all into 1 block (since 3 < block_size 10).
    
    service2 = OrderingService([node], config)
    
    # Wait a bit for recovery to finish (it happens in __init__ -> _recover_state)
    time.sleep(1.0)
    
    blocks_phase2 = service2.get_blocks()
    print(f"Phase 2 Blocks Created: {len(blocks_phase2)}")
    for b in blocks_phase2:
        print(f"  Block {b.index}: {len(b.events)} events, Hash: {b.hash[:8]}")
        
    service2.shutdown()

    # Assertion
    assert len(blocks_phase1) == len(blocks_phase2), \
        f"[FAIL] Determinism check failed! Original: {len(blocks_phase1)} blocks, Recovered: {len(blocks_phase2)} blocks."
    
    print(f"\n[PASS] Block counts match.")

if __name__ == "__main__":
    test_determinism()
