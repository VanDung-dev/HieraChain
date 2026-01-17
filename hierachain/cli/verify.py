"""
Verification tools for blockchain integrity.
"""

import click
import logging
from hierachain.storage.sql_backend import SqlStorageBackend
from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import BlockVerifier
from hierachain.security.verify.signature_verifier import SignatureVerifier
from hierachain.config.settings import settings

# Setup logging for CLI
logger = logging.getLogger("hrc.verify")

@click.group(name="verify")
def verify_group():
    """Verification tools for blockchain integrity."""
    pass

@verify_group.command(name="chain")
@click.option('--db', default=None, help='Database connection string (default: from settings)')
def verify_chain(db):
    """Verify the structural integrity of the blockchain."""
    db_url = db or settings.DATABASE_URL
    click.echo(f"Verifying chain integrity from: {db_url}")
    
    try:
        backend = SqlStorageBackend(db_url)
    except Exception as e:
        click.report_migration_error(f"Failed to connect to storage: {e}")
        return

    # Load chain blocks
    # Note: Reusing logic similar to scripts/security/chain_integrity_verify.py
    # For a CLI tool, we might want pagination or progress bars for large chains
    try:
        latest = backend.get_latest_block()
        if not latest:
            click.echo("Blockchain is empty.")
            return
            
        tip_index = latest['index']
        blocks = []
        
        with click.progressbar(range(tip_index + 1), label='Loading blocks') as bar:
            for i in bar:
                b_data = backend.get_block_by_index(i)
                if b_data:
                    blocks.append(Block.from_dict(b_data))
                else:
                    click.secho(f"Warning: Missing block at index {i}", fg='yellow')
        
        verifier = BlockVerifier(strict_mode=False)
        result = verifier.verify_chain(blocks)
        
        if result.is_valid:
            click.secho("✅ CHAIN INTEGRITY VERIFIED", fg='green', bold=True)
            click.echo(result.message)
        else:
            click.secho("❌ CHAIN VERIFICATION FAILED", fg='red', bold=True)
            click.echo(result.message)
            if result.details and "invalid_blocks" in result.details:
                for err in result.details["invalid_blocks"]:
                    click.echo(f"  - Block {err['index']}: {err['errors']}")
                    
    except Exception as e:
        click.echo(f"Error during verification: {e}")
    finally:
        backend.close()

@verify_group.command(name="signatures")
@click.option('--db', default=None, help='Database connection string')
@click.option('--limit', default=0, help='Check only last N blocks')
def verify_signatures(db, limit):
    """Audit cryptographic signatures of blocks and events."""
    db_url = db or settings.DATABASE_URL
    click.echo(f"Auditing signatures from: {db_url}")
    
    try:
        backend = SqlStorageBackend(db_url)
    except Exception as e:
        click.echo(f"Failed to connect to storage: {e}")
        return

    try:
        latest = backend.get_latest_block()
        if not latest:
            click.echo("Blockchain is empty.")
            return

        tip = latest['index']
        start = 0
        if limit > 0 and tip > limit:
            start = tip - limit + 1
            click.echo(f"Verifying last {limit} blocks (Index {start}-{tip})")
        else:
            click.echo(f"Verifying all blocks (Index 0-{tip})")

        block_verifier = BlockVerifier(strict_mode=True)
        sig_verifier = SignatureVerifier()
        
        stats = {"blocks_valid": 0, "blocks_invalid": 0, "events_valid": 0, "events_invalid": 0}
        
        with click.progressbar(range(start, tip + 1), label='Auditing') as bar:
            for i in bar:
                b_data = backend.get_block_by_index(i)
                if not b_data:
                    continue
                
                block = Block.from_dict(b_data)
                
                # Check Block Sig
                if hasattr(block, 'signature') and block.signature:
                    if block_verifier.verify_block_signature(block).is_valid:
                        stats["blocks_valid"] += 1
                    else:
                        stats["blocks_invalid"] += 1
                
                # Check Events
                # block.events is a PyArrow Table, convert to list of dicts
                events_list = block.events.to_pylist() if hasattr(block.events, 'to_pylist') else block.events
                
                for event in events_list:
                    signature = event.get('signature')
                    details = event.get('details', {})
                    public_key = details.get('public_key') if isinstance(details, dict) else None
                    
                    if signature and public_key:
                        if sig_verifier.verify_event_signature(event, public_key):
                            stats["events_valid"] += 1
                        else:
                            stats["events_invalid"] += 1
        
        click.echo("\n Audit Complete:")
        click.echo(f"Blocks: {stats['blocks_valid']} Valid, {stats['blocks_invalid']} Invalid")
        click.echo(f"Events: {stats['events_valid']} Valid, {stats['events_invalid']} Invalid")
        
        if stats['blocks_invalid'] > 0 or stats['events_invalid'] > 0:
            click.secho("Audit found issues!", fg='red')
        else:
            click.secho("All checked signatures are valid.", fg='green')

    except Exception as e:
        click.echo(f"Error during audit: {e}")
    finally:
        backend.close()
