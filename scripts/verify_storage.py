"""
This script verifies the persistence of the SqlStorageBackend by simulating the ordering service
saving blocks and then verifying that the blocks can be retrieved after the backend is closed and reopened.
"""

import os
import sys
import time
import logging

from hierachain.storage.sql_backend import SqlStorageBackend

# Add project root to path
sys.path.append(os.getcwd())

# Setup logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("VerifyPersistence")

def run_verification():
    logger.info("--- Starting Storage Persistence Verification ---")
    
    # 1. Clean previous DB
    if os.path.exists("hierachain.db"):
        os.remove("hierachain.db")
        logger.info("Cleaned up old database.")

    # 2. Initialize Backend
    backend = SqlStorageBackend("sqlite:///hierachain.db")
    
    # 3. Simulate Saving Blocks
    logger.info("Simulating OrderingService saving blocks...")
    for i in range(10):
        block_data = {
            "index": i,
            "hash": f"hash_{i}",
            "previous_hash": f"hash_{i-1}",
            "timestamp": time.time(),
            "events": [
                {"event": "test_event", "timestamp": time.time(), "sender": "user1", "data": f"value_{i}"}
            ],
            "metadata": {"consensus": "PoA"}
        }
        backend.save_block(block_data)
    
    # 4. Close Backend
    backend.close()
    logger.info("Backend closed. Verifying persistence...")
    
    # 5. Re-open Backend and Check Data
    new_backend = SqlStorageBackend("sqlite:///hierachain.db")
    
    latest = new_backend.get_latest_block()
    if latest and latest['index'] == 9:
        logger.info(f"SUCCESS: Latest block index {latest['index']} verified.")
    else:
        logger.error(f"FAILURE: Expected index 9, got {latest}")
        
    # Check random block
    block_5 = new_backend.get_block_by_index(5)
    if block_5 and block_5['hash'] == "hash_5":
        logger.info("SUCCESS: Block 5 retrieval verified.")
    else:
        logger.error("FAILURE: Block 5 retrieval failed.")
        
    start_size = os.path.getsize("hierachain.db")
    logger.info(f"Database size: {start_size} bytes")
    
    new_backend.close()
    logger.info("Verification Complete.")

if __name__ == "__main__":
    run_verification()
