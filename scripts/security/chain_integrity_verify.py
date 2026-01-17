"""
Blockchain Integrity Verification Script
----------------------------------------
This script performs a structural integrity check of the blockchain data stored
in the SQL backend. It verifies:
1. Block hashes (re-computed vs stored)
2. Merkle roots
3. Chain links (previous_hash continuity)
4. Block sequence (index continuity)

Usage:
    python scripts/security/chain_integrity_verify.py [connection_string]
"""

import os
import sys
import logging
import argparse
from typing import List

# Ensure hierachain package is in path
sys.path.append(os.getcwd())

from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import BlockVerifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ChainIntegrity")

def load_chain_from_db(backend: SqlStorageBackend) -> List[Block]:
    """
    Load all blocks from the database and convert to Block objects.
    Note: For very large chains, this should be paginated/streamed.
    """
    logger.info("Loading blockchain from database...")

    chain = []
    latest_block_dict = backend.get_latest_block()
    
    if not latest_block_dict:
        logger.warning("Database appears empty (no blocks found).")
        return []
        
    tip_index = latest_block_dict['index']
    logger.info(f"Chain tip index: {tip_index}")
    
    # Fetch blocks sequentially
    for i in range(tip_index + 1):
        block_dict = backend.get_block_by_index(i)
        if not block_dict:
            logger.error(f"Gap in chain! Missing block at index {i}")
            break
            
        try:
            block = Block.from_dict(block_dict)
            chain.append(block)
        except Exception as e:
            logger.error(f"Failed to reconstruct block at index {i}: {e}")
            break
            
    return chain

def verify_integrity(connection_string: str = None):
    """Run the integrity verification."""
    logger.info("Starting Chain Integrity Verification...")
    
    # Initialize backend
    try:
        backend = SqlStorageBackend(connection_string)
    except Exception as e:
        logger.critical(f"Failed to connect to storage: {e}")
        return

    # Load chain
    chain = load_chain_from_db(backend)
    backend.close()
    
    if not chain:
        logger.info("No blocks to verify.")
        return

    logger.info(f"Loaded {len(chain)} blocks. Verifying...")

    verifier = BlockVerifier(strict_mode=False) # Non-strict for basic integrity
    
    # Run verification
    result = verifier.verify_chain(chain)
    
    # Report results
    if result.is_valid:
        logger.info("✅ CHAIN INTEGRITY VERIFIED")
        logger.info(f"Summary: {result.message}")
    else:
        logger.error("❌ CHAIN VERIFICATION FAILED")
        logger.error(f"Reason: {result.message}")
        if result.details and "invalid_blocks" in result.details:
            logger.error("\nInvalid Blocks Details:")
            for error in result.details["invalid_blocks"]:
                logger.error(f"  - Block {error['index']}: {error['errors']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify HieraChain Integrity")
    parser.add_argument("--db", type=str, help="Database connection string", default=None)
    args = parser.parse_args()
    
    verify_integrity(args.db)
