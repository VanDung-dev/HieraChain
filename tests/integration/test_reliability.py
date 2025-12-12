"""
Test Reliability (Recovery & Rehydration)

This test suite covers the reliability features of the hierarchical chain.
Specifically, it tests the recovery and rehydration capabilities of the chain.
"""

import os
import shutil
import time
from hierachain.hierarchical.sub_chain import SubChain

def test_recovery_and_rehydration():
    chain_name = "test_reliability_chain"
    data_dir = f"data/{chain_name}"
    
    # Setup: Clean up previous runs
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)

    try:
        print("\n[Test] Starting Recovery & Rehydration Test")
        
        # 1. First Run: Generate Data
        print("[Test] Phase 1: Generating Data...")
        config = {
            "node_id": "test_node_1",
            "block_size": 1,
            "batch_timeout": 0.5
        }
        chain1 = SubChain(chain_name, "test_domain", config=config)
        
        # Add 3 events to generate 3 blocks
        print("[Test] Adding 3 events...")
        for i in range(1, 4):
            chain1.add_event({
                "event": f"event_{i}", 
                "entity_id": f"e{i}", 
                "details": {"val": i}
            })
            time.sleep(0.1) # Small delay to ensure ordering
        
        # Wait for block finalization
        print("[Test] Waiting for block finalization...")
        max_retries = 50
        while chain1.get_latest_block().index < 3 and max_retries > 0:
            time.sleep(0.1)
            max_retries -= 1
            
        latest_block_1 = chain1.get_latest_block()
        print(f"[Test] Phase 1 Complete. Block Index: {latest_block_1.index}")
        assert latest_block_1.index >= 3, "Phase 1 failed to finalize 3 blocks"
        
        # Capture stats before stopping
        total_events_1 = sum(len(b.events) for b in chain1.chain)
        last_block_hash = latest_block_1.hash
        
        # Stop Chain 1
        chain1.stop()
        del chain1
        
        # 2. Second Run: Simulation of Crash/Restart
        print("[Test] Phase 2: Restarting (Simulating Crash)...")
        time.sleep(1.0) # Allow sockets/files to close
        
        # Re-initialize with SAME config to ensure same block formation rules
        chain2 = SubChain(chain_name, "test_domain", config=config)
        
        print("[Test]        # Verify Rehydration")
        latest_block_2 = chain2.get_latest_block()
        print(f"[Test] Restored Block Index: {latest_block_2.index}")
        
        assert latest_block_2.index == 3, f"Restored chain height mismatch. Expected 3, got {latest_block_2.index}"
        
        # Verify Content Integrity
        total_events_2 = sum(len(b.events) for b in chain2.chain)
        assert total_events_2 == total_events_1, f"Total event count mismatch. Expected {total_events_1}, got {total_events_2}"
        
        # Verify specific event detail in Block 1
        block_1 = chain2.chain[1]
        # Access events properly using to_event_list() because block.events is Arrow Table
        events_list = block_1.to_event_list()
        assert len(events_list) > 0
        
        evt = events_list[0]
        
        assert evt.get('event') == 'event_1', "Recovered event data content mismatch"
        
        print(f"[Test] Successfully verified integrity of {latest_block_2.index} restored blocks.")
        chain2.stop()

    finally:
        if os.path.exists(data_dir):
            try:
                shutil.rmtree(data_dir, ignore_errors=True)
            except Exception:
                pass
