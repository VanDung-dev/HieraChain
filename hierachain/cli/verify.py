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
        # Note: using echo instead of report_migration_error which might not exist on click
        click.echo(f"Failed to connect to storage: {e}")
        return

    try:
        blocks = _load_blocks_from_backend(backend)
        if not blocks:
            return
        
        verifier = BlockVerifier(strict_mode=False)
        result = verifier.verify_chain(blocks)
        
        _report_verification_result(result)
                    
    except Exception as e:
        click.echo(f"Error during verification: {e}")
    finally:
        backend.close()

def _load_blocks_from_backend(backend):
    """Helper to load all blocks from storage with a progress bar."""
    latest = backend.get_latest_block()
    if not latest:
        click.echo("Blockchain is empty.")
        return []
        
    tip_index = latest['index']
    blocks = []
    
    with click.progressbar(range(tip_index + 1), label='Loading blocks') as bar:
        for i in bar:
            b_data = backend.get_block_by_index(i)
            if b_data:
                blocks.append(Block.from_dict(b_data))
            else:
                click.secho(f"Warning: Missing block at index {i}", fg='yellow')
    return blocks

def _report_verification_result(result):
    """Helper to format and display verification results."""
    if result.is_valid:
        click.secho("✅ CHAIN INTEGRITY VERIFIED", fg='green', bold=True)
        click.echo(result.message)
    else:
        click.secho("❌ CHAIN VERIFICATION FAILED", fg='red', bold=True)
        click.echo(result.message)
        if result.details and "invalid_blocks" in result.details:
            for err in result.details["invalid_blocks"]:
                click.echo(f"  - Block {err['index']}: {err['errors']}")

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

        start, tip = _get_audit_range(latest['index'], limit)
        stats = _run_audit_loop(backend, start, tip)
        _report_audit_stats(stats)

    except Exception as e:
        click.echo(f"Error during audit: {e}")
    finally:
        backend.close()

def _run_audit_loop(backend, start, tip):
    """Core logic to iterate through blocks and perform signature auditing."""
    block_verifier = BlockVerifier(strict_mode=True)
    sig_verifier = SignatureVerifier()
    stats = {"blocks_valid": 0, "blocks_invalid": 0, "events_valid": 0, "events_invalid": 0}
    
    with click.progressbar(range(start, tip + 1), label='Auditing') as bar:
        for i in bar:
            b_data = backend.get_block_by_index(i)
            if not b_data:
                continue
            
            block = Block.from_dict(b_data)
            _audit_block_signature(block, block_verifier, stats)
            _audit_event_signatures(block, sig_verifier, stats)
    return stats

def _get_audit_range(tip, limit):
    """Helper to determine the range of blocks to audit."""
    start = 0
    if limit > 0 and tip > limit:
        start = tip - limit + 1
        click.echo(f"Verifying last {limit} blocks (Index {start}-{tip})")
    else:
        click.echo(f"Verifying all blocks (Index 0-{tip})")
    return start, tip

def _audit_block_signature(block, block_verifier, stats):
    """Helper to verify a single block's signature and update stats."""
    if hasattr(block, 'signature') and block.signature:
        if block_verifier.verify_block_signature(block).is_valid:
            stats["blocks_valid"] += 1
        else:
            stats["blocks_invalid"] += 1

def _audit_event_signatures(block, sig_verifier, stats):
    """Helper to verify all events within a block and update stats."""
    # block.events is a PyArrow Table, convert to list of dicts
    events_list = block.events.to_pylist() if hasattr(block.events, 'to_pylist') else block.events
    
    for event in events_list:
        if _verify_single_event_signature(event, sig_verifier):
            stats["events_valid"] += 1
        else:
            if event.get('signature') and (
                event.get('details', {}).get('public_key') if isinstance(event.get('details'), dict) else None
            ):
                stats["events_invalid"] += 1

def _verify_single_event_signature(event, sig_verifier):
    """Helper to verify the signature of a single event."""
    signature = event.get('signature')
    details = event.get('details', {})
    public_key = details.get('public_key') if isinstance(details, dict) else None
    
    if signature and public_key:
        return sig_verifier.verify_event_signature(event, public_key)
    return False

def _report_audit_stats(stats):
    """Helper to report the final audit statistics."""
    click.echo("\n Audit Complete:")
    click.echo(f"Blocks: {stats['blocks_valid']} Valid, {stats['blocks_invalid']} Invalid")
    click.echo(f"Events: {stats['events_valid']} Valid, {stats['events_invalid']} Invalid")
    
    if stats['blocks_invalid'] > 0 or stats['events_invalid'] > 0:
        click.secho("Audit found issues!", fg='red')
    else:
        click.secho("All checked signatures are valid.", fg='green')
