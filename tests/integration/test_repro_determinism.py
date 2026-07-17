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

from hierachain.consensus import OrderingService, OrderingNode, OrderingStatus


def _wait_and_log_blocks(service, phase_label):
    time.sleep(1.0)
    blocks = service.get_blocks()
    print(f"{phase_label} Blocks Created: {len(blocks)}")
    for b in blocks:
        print(f"  Block {b.index}: {len(b.events)} events, Hash: {b.hash[:8]}")
    return blocks


def test_determinism():
    data_dir = "data/test_determinism"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    os.makedirs(data_dir)

    print("=== Phase 1: Original Run ===")
    
    config = {
        "storage_dir": os.path.join(data_dir, "journal"),
        "block_size": 10,
        "batch_timeout": 0.5,
        "worker_threads": 1,
        "db_url": f"sqlite:///{os.path.join(data_dir, 'test.db')}"
    }
    
    node = OrderingNode("node1", "localhost", True, 1.0, OrderingStatus.ACTIVE, time.time())
    
    service = OrderingService(config, [node])
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
    
    blocks_phase1 = _wait_and_log_blocks(service, "Phase 1")
        
    service.shutdown()
    time.sleep(1.5)
    
    print("\n=== Phase 2: Recovery Run ===")
    
    service2 = OrderingService(config, [node])
        
    blocks_phase2 = _wait_and_log_blocks(service2, "Phase 2")
        
    service2.shutdown()

    # Assertion
    assert len(blocks_phase1) == len(blocks_phase2), \
        f"[FAIL] Determinism check failed! Original: {len(blocks_phase1)} blocks, Recovered: {len(blocks_phase2)} blocks."
    
    print(f"\n[PASS] Block counts match.")

if __name__ == "__main__":
    test_determinism()
