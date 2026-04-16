"""
Test Data Flow

This test suite verifies the data flow from the API to the journal, and then to the block.
"""

import os
import shutil
import time
import pyarrow as pa
import struct

from hierachain.hierarchical import SubChain
from hierachain.core import schemas


def _read_first_journal_row(journal_path, schema):
    if not os.path.exists(journal_path):
        return None

    for file in os.listdir(journal_path):
        if "journal" not in file:
            continue

        file_path = os.path.join(journal_path, file)

        with open(file_path, "rb") as f:
            len_bytes = f.read(4)
            if len(len_bytes) != 4:
                continue

            length = struct.unpack("<I", len_bytes)[0]
            batch_data = f.read(length)

            # Detect format: JSON starts with '{'
            if batch_data.startswith(b'{'):
                import json
                row = json.loads(batch_data)
                return row

            try:
                # Fallback: standalone RecordBatch
                batch = pa.ipc.read_record_batch(batch_data, schema)
                return batch.to_pylist()[0]
            except Exception:
                # Fallback: Arrow stream
                try:
                    reader = pa.ipc.open_stream(batch_data)
                    batch = reader.read_next_batch()
                    return batch.to_pylist()[0]
                except Exception:
                    continue

    return None


def _wait_for_latest_block(chain, max_retries=20, delay=0.1):
    latest_block = chain.get_latest_block()

    while latest_block.index == 0 and max_retries > 0:
        time.sleep(delay)
        latest_block = chain.get_latest_block()
        max_retries -= 1

    return latest_block


def test_end_to_end_flow():
    chain_name = "test_flow_chain"
    data_dir = f"data/{chain_name}"
    schema = schemas.get_event_schema()
    
    # Setup: Clean up previous runs
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
        
    chain = SubChain(chain_name, "test_domain")
    chain.consensus.config["block_interval"] = 0
    time.sleep(0.05)

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
        
        time.sleep(1.0)
        
        journal_path = os.path.join(data_dir, "journal")
        journal_row = _read_first_journal_row(journal_path, schema)
        assert journal_row is not None, "No valid Arrow journal data found on disk!"
        assert journal_row["entity_id"] == "entity_123"
        
        print("[Test] Waiting for Block generation (timeout 1.0s)...")
        time.sleep(1.5) 
        
        print("[Test] waiting check...")
        
        latest_block = _wait_for_latest_block(chain)
            
        print(f"[Test] Latest Block Index: {latest_block.index}")
        assert latest_block.index >= 1, "SubChain did not finalize any blocks (auto or manual)!"
        
        # Verify Block Data is also Arrow
        assert isinstance(latest_block.events, pa.Table)
        print("[Test] Block internally holds Arrow Table.")
        
        print("[Test] SUCCESS: Data flowed from API(simulated) -> Journal(Arrow) -> Block(Arrow)")

    finally:
        # Cleanup
        chain.stop()
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir, ignore_errors=True)
