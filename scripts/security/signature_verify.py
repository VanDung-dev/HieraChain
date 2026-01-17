"""
Blockchain Signature Verification Script
----------------------------------------
This script performs a cryptographic audit of the blockchain.
It verifies:
1. Block creator signatures (if available)
2. Event issuer signatures (on every event in every block)

Usage:
    python scripts/security/signature_verify.py [--db connection_string] [--limit N]
"""

import os
import sys
import logging
import argparse

# Ensure hierachain package is in path
sys.path.append(os.getcwd())

from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import BlockVerifier
from hierachain.security.verify.signature_verifier import SignatureVerifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SigAudit")

def run_signature_audit(connection_string: str = None, limit: int = 0):
    """Run the signature audit."""
    logger.info("Starting Cryptographic Signature Audit...")
    
    try:
        backend = SqlStorageBackend(connection_string)
    except Exception as e:
        logger.critical(f"Failed to connect to storage: {e}")
        return

    # Use BlockVerifier just for block sigs, SignatureVerifier for strict logic
    block_verifier = BlockVerifier(strict_mode=True)
    sig_verifier = SignatureVerifier()
    
    latest_block_dict = backend.get_latest_block()
    if not latest_block_dict:
        logger.info("Database empty.")
        backend.close()
        return

    tip_index = latest_block_dict['index']
    start_index = 0
    
    # If limit applied, verify last N blocks
    if limit > 0 and tip_index > limit:
        start_index = tip_index - limit + 1
        logger.info(f"Verifying last {limit} blocks (Index {start_index} to {tip_index})")
    else:
        logger.info(f"Verifying all blocks (Index 0 to {tip_index})")

    stats = {
        "blocks_checked": 0,
        "blocks_valid": 0,
        "blocks_invalid_sig": 0,
        "blocks_no_sig": 0,
        "events_checked": 0,
        "events_valid": 0,
        "events_invalid": 0,
        "events_no_sig": 0
    }

    for i in range(start_index, tip_index + 1):
        block_dict = backend.get_block_by_index(i)
        if not block_dict:
            logger.error(f"Missing block at index {i}")
            continue
            
        try:
            block = Block.from_dict(block_dict)
            stats["blocks_checked"] += 1
            
            # 1. Verify Block Signature
            # Note: Many early blocks or PoW blocks might not have signatures if not enforced
            if hasattr(block, 'signature') and block.signature:
                res = block_verifier.verify_block_signature(block)
                if res.is_valid:
                    stats["blocks_valid"] += 1
                else:
                    logger.error(f"❌ Block {block.index} signature invalid: {res.message}")
                    stats["blocks_invalid_sig"] += 1
            else:
                stats["blocks_no_sig"] += 1
                
            # 2. Verify Event Signatures
            events_list = block.events.to_pylist() if hasattr(block.events, 'to_pylist') else block.events
            for event in events_list:
                stats["events_checked"] += 1
                sender_id = event.get('sender_id') or event.get('sender')
                signature = event.get('signature')
                
                # Check for public key in event details
                details = event.get('details', {})
                public_key = (
                    details.get('public_key') if isinstance(details, dict) else None
                )
                
                if not public_key and not signature:
                    stats["events_no_sig"] += 1
                    continue
                    
                if not public_key:
                    # Can't verify without key
                    logger.debug(f"Event {event.get('event_id')} has sig but no public key found.")
                    stats["events_no_sig"] += 1
                    continue
                
                if sig_verifier.verify_event_signature(event, public_key):
                    stats["events_valid"] += 1
                else:
                    logger.error(f"❌ Event {event.get('event_id', '?')} in Block {block.index} has INVALID signature.")
                    stats["events_invalid"] += 1
                    
        except Exception as e:
            logger.error(f"Error processing block {i}: {e}")

    backend.close()
    
    # Report
    logger.info("-" * 40)
    logger.info("AUDIT COMPLETE")
    logger.info("-" * 40)
    logger.info(f"Blocks Checked:      {stats['blocks_checked']}")
    logger.info(f"  - Valid Sig:       {stats['blocks_valid']}")
    logger.info(f"  - Invalid Sig:     {stats['blocks_invalid_sig']}")
    logger.info(f"  - No Sig/Skipped:  {stats['blocks_no_sig']}")
    logger.info("-" * 40)
    logger.info(f"Events Checked:      {stats['events_checked']}")
    logger.info(f"  - Valid:           {stats['events_valid']}")
    logger.info(f"  - Invalid:         {stats['events_invalid']}")
    logger.info(f"  - No Key/Sig:      {stats['events_no_sig']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HieraChain Signature Audit")
    parser.add_argument("--db", type=str, help="Database connection string", default=None)
    parser.add_argument("--limit", type=int, help="Check only last N blocks", default=0)
    args = parser.parse_args()
    
    run_signature_audit(args.db, args.limit)
