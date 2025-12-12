"""
Test Data Flow

This test suite verifies the data flow from the API to the journal, and then to the block.
"""

import os
import shutil
import time
import pyarrow as pa
import struct

from hierachain.hierarchical.sub_chain import SubChain
from hierachain.core import schemas

def test_end_to_end_flow():
    chain_name = "test_flow_chain"
    data_dir = f"data/{chain_name}"
    schema = schemas.get_event_schema()
    
    # Setup: Clean up previous runs
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
        
    chain = SubChain(chain_name, "test_domain")

    try:
        print(f"\n[Test] Starting End-to-End Data Flow verification for {chain_name}")
        
        # 1. Ingestion
        event_data = {
            "event": "test_event",
            "entity_id": "entity_123",
            "details": {"foo": "bar"}
        }
        print("[Test] Adding event to SubChain...")
        chain.add_event(event_data)
        
        # 2. Verify Persistence (Journal)
        time.sleep(1.0) # Wait for thread to write
        
        found_journal_data = False
        journal_path = os.path.join(data_dir, "journal")
        
        if os.path.exists(journal_path):
            for file in os.listdir(journal_path):
                # OrderingService configures journal name as "node_{id}_journal.log"
                if "journal" in file:
                    print(f"[Test] Found journal file: {file}")
                    # Verify content
                    with open(os.path.join(journal_path, file), 'rb') as f:
                        # Read length prefix
                        len_bytes = f.read(4)
                        if len(len_bytes) == 4:
                            length = struct.unpack('<I', len_bytes)[0]
                            print(f"[Test] Journal entry length: {length}")
                            batch_data = f.read(length)
                            # Use read_record_batch with schema
                            batch = pa.ipc.read_record_batch(batch_data, schema)
                            rows = batch.to_pylist()
                            print(f"[Test] Journal Data (First Row): {rows[0]}")
                            
                            # Verify data content
                            assert rows[0]['entity_id'] == "entity_123"
                            found_journal_data = True
                            
        assert found_journal_data, "No valid Arrow journal data found on disk!"
        
        # 3. Verify Block Construction
        print("[Test] Waiting for Block generation (timeout 1.0s)...")
        time.sleep(1.5) 
        
        # Trigger SubChain to pull blocks
        print("[Test] waiting check...")
        
        # With auto-pulling background thread, the block might already be there.
        max_retries = 20
        latest_block = chain.get_latest_block()
        while latest_block.index == 0 and max_retries > 0:
            time.sleep(0.1)
            latest_block = chain.get_latest_block()
            max_retries -= 1
            
        print(f"[Test] Latest Block Index: {latest_block.index}")
        assert latest_block.index >= 1, "SubChain did not finalize any blocks (auto or manual)!"
        
        # Verify Block Data is also Arrow
        assert isinstance(latest_block.events, pa.Table)
        print("[Test] Block internally holds Arrow Table.")
        
        print("[Test] SUCCESS: Data flowed from API(simulated) -> Journal(Arrow) -> Block(Arrow)")

    finally:
        # Cleanup
        try:
            chain.stop()
        except Exception:
            pass
            
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir, ignore_errors=True)
