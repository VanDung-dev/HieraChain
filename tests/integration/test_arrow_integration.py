import time
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from hierachain.integration.arrow_client import ArrowClient
from hierachain.integration.types import Transaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_integration")

def test_arrow_integration():
    logger.info("Starting Arrow Integration Test...")
    
    # Connect to local server
    # Assumes cmd/arrow-server/main.go is running on :50051
    client = ArrowClient(host="localhost", port=50051)
    
    try:
        client.connect()
        logger.info("Connected to server successfully.")
        
        # Create dummy transactions
        txs = [
            Transaction(
                tx_id=f"tx-{i}",
                entity_id=f"user-{i}",
                event_type="transfer",
                arrow_payload=b"dummy_data",
                timestamp=time.time()
            )
            for i in range(5)
        ]
        
        logger.info(f"Sending batch of {len(txs)} transactions...")
        
        start_time = time.time()
        response = client.submit_batch(txs)
        duration = time.time() - start_time
        
        logger.info(f"Received response: {response}")
        logger.info(f"Round-trip time: {duration*1000:.2f}ms")
        
        if response == b"OK":
            logger.info("✅ TEST PASSED: Server responded with OK")
        else:
            logger.error(f"❌ TEST FAILED: Unexpected response {response}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    test_arrow_integration()
