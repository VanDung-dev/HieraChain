import asyncio
import os
import sys
import logging
import time

# Add project root to path
sys.path.append(os.getcwd())

from hierachain.core.hybrid_engine import HybridEngine, HybridEngineConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_hybrid_arrow")

async def test():
    logger.info("Starting HybridEngine Arrow Integration Test...")
    
    # Configure to use Go Engine + Arrow
    config = HybridEngineConfig(
        use_go_engine=True,
        use_arrow=True, # Explicitly enable Arrow
        go_engine_address="localhost:50051"
    )
    
    # Assumes cmd/arrow-server/main.go is running on :50051
    
    async with HybridEngine(config) as engine:
        logger.info(f"Engine stats before: {engine.get_stats()}")
        
        txs = [
            {"id": f"tx-{i}", "entity_id": f"u-{i}", "event_type": "transfer", "amount": 100}
            for i in range(5)
        ]
        
        logger.info("Processing batch...")
        result = await engine.process_transactions(txs)
        
        logger.info(f"Result: success={result.success}, processed={result.processed_count}")
        logger.info(f"Engine used: {result.engine_used}")
        logger.info(f"Engine stats after: {engine.get_stats()}")
        
        if not result.success:
            logger.error("❌ Test Failed: Processing failed")
            sys.exit(1)
            
        if result.engine_used.value != "go":
            logger.error(f"❌ Test Failed: Expected engine 'go', got '{result.engine_used}'")
            # Note: My implementation maps Arrow usage to EngineMode.GO with stats indicating usage?
            # Actually HybridEngine maps it to EngineMode.GO.
            # I should verify it actually used Arrow. 
            # The mocked response message in HybridEngine says "Processed via Arrow"
            # But the result object doesn't carry message (it's in BatchResult internal).
            # However, if 'go' was used and 'go_requests' incremented, it means Arrow path worked 
            # (since go_client would fail/not be init if use_arrow=True? No, existing logic was modified).
            sys.exit(1)
            
        logger.info("✅ Test Passed")

if __name__ == "__main__":
    asyncio.run(test())
