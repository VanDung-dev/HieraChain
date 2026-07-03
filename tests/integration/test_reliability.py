"""
Test Reliability (Recovery & Rehydration)

This test suite covers the reliability features of the hierarchical chain.
Specifically, it tests the recovery and rehydration capabilities of the chain.
"""

import os
import shutil
import time

import pytest

from hierachain.hierarchical import SubChain
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter


def _cleanup_chain(chain_name: str) -> None:
    """Clean up both filesystem journal and DB records for a chain."""
    data_dir = f"data/{chain_name}"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)
    # Also remove DB records so each run starts from a clean state
    try:
        db = SQLiteAdapter()
        db.delete_chain(chain_name)
        db.close()
    except Exception:
        pass


@pytest.mark.flaky(reruns=3)
def test_recovery_and_rehydration():
    chain_name = "test_reliability_chain"

    # Setup: Clean up previous runs (both filesystem AND database)
    _cleanup_chain(chain_name)

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
        # Set low block interval to allow fast block creation in test loop
        chain1.consensus.config["block_interval"] = 0
        time.sleep(0.5) # Allow genesis block to age
        
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
        phase1_max_index = latest_block_1.index
        print(f"[Test] Phase 1 max block index: {phase1_max_index}")

        # Stop Chain 1 (drain commit_queue + shutdown ordering service)
        chain1.stop()
        del chain1
        
        # 2. Second Run: Simulation of Crash/Restart
        print("[Test] Phase 2: Restarting (Simulating Crash)...")
        time.sleep(1.0)  # Allow sockets/files to close

        # Re-initialize with SAME config. Stop immediately to prevent consumer
        # thread from adding new blocks that differ from DB-persisted state.
        chain2 = SubChain(chain_name, "test_domain", config=config)
        chain2.stop()
        
        print("[Test]        # Verify Rehydration")
        latest_block_2 = chain2.get_latest_block()
        print(f"[Test] Restored Block Index: {latest_block_2.index}")

        assert latest_block_2.index >= 3, (
            f"Restored chain should have at least 3 blocks, got {latest_block_2.index}"
        )

        rehydrated_indices = [b.index for b in chain2.chain]
        print(f"[Test] Rehydrated block indices: {rehydrated_indices}")
        assert phase1_max_index in rehydrated_indices, (
            f"Phase 1 max block index {phase1_max_index} not found in rehydrated chain. "
            f"Available indices: {rehydrated_indices}"
        )

        # Verify Content Integrity: event count preserved
        total_events_2 = sum(len(b.events) for b in chain2.chain)
        assert total_events_2 >= total_events_1, (
            f"Total event count mismatch. Expected at least {total_events_1}, got {total_events_2}"
        )

        # Verify specific event detail in Block 1
        block_1 = chain2.chain[1]
        # Access events properly using to_event_list() because block.events is Arrow Table
        events_list = block_1.to_event_list()
        assert len(events_list) > 0
        
        evt = events_list[0]
        
        assert evt.get('event') == 'event_1', "Recovered event data content mismatch"
        print("[Test] Successfully verified integrity of 3 restored blocks.")

    finally:
        # Cleanup
        _cleanup_chain(chain_name)
