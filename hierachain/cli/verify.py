"""
Verification tools for blockchain integrity.
"""

import logging

import click

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.config.settings import settings
from hierachain.core.block import Block
from hierachain.security.identity_loader import load_trusted_block_keys
from hierachain.security.verify.block_verifier import BlockVerifier
from hierachain.security.verify.signature_verifier import SignatureVerifier

# Setup logging for CLI
logger = logging.getLogger("hrc.verify")


def _db_url_to_path(url: str | None) -> str:
    """Strip sqlite:/// prefix to get a plain file path."""
    if not url:
        return "hierachain.db"
    for prefix in ("sqlite:///", "sqlite://"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return url


@click.group(name="verify")
def verify_group() -> None:
    """Verification tools for blockchain integrity."""


@verify_group.command(name="chain")
@click.option(
    '--db',
    default=None,
    help='Database connection string (default: from settings)'
)
def verify_chain(db: str | None) -> None:
    """Verify chain integrity and every trusted block signature."""
    db_url = db or settings.DATABASE_URL
    click.echo(f"Verifying chain integrity from: {db_url}")
    try:
        trusted_keys = load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    
    try:
        backend = SQLiteAdapter(_db_url_to_path(db_url))
    except Exception as e:
        raise click.ClickException(f"Failed to connect to storage: {e}") from e

    try:
        invalid_chains = []
        for chain_name in _get_chain_names(backend):
            click.echo(f"Chain: {chain_name}")
            blocks = _load_blocks_from_backend(backend, chain_name)
            result = BlockVerifier().verify_chain(blocks, trusted_keys)
            _report_verification_result(result)
            if not result.is_valid:
                invalid_chains.append(chain_name)
        if invalid_chains:
            raise click.ClickException(
                f"Chain verification failed: {', '.join(invalid_chains)}"
            )
                    
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Error during verification: {e}") from e
    finally:
        backend.close()


def _get_chain_names(backend: SQLiteAdapter) -> list[str]:
    """Get every chain that has stored blocks; never report empty verification as success."""
    with backend._get_connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT chain_name FROM blocks ORDER BY chain_name"
        ).fetchall()
    names = [row[0] for row in rows]
    if not names or any(not name for name in names):
        raise click.ClickException("No named block chains to verify")
    return names


def _load_blocks_from_backend(backend: SQLiteAdapter, chain_name: str) -> list[Block]:
    """Helper to load all blocks from storage with a progress bar."""
    latest = backend.get_latest_block(chain_name=chain_name)
    if not latest:
        raise click.ClickException(f"Chain {chain_name} is empty")
        
    tip_index = latest['index']
    blocks = []
    
    with click.progressbar(range(tip_index + 1), label='Loading blocks') as bar:
        for i in bar:
            b_data = backend.get_block_by_index(i, chain_name=chain_name)
            if b_data:
                blocks.append(Block.from_dict(b_data))
            else:
                raise click.ClickException(f"Missing block at index {i}")
    return blocks


def _report_verification_result(result) -> None:
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
def verify_signatures(db: str | None, limit: int) -> None:
    """Audit cryptographic signatures of blocks and events."""
    db_url = db or settings.DATABASE_URL
    click.echo(f"Auditing signatures from: {db_url}")
    try:
        trusted_keys = load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    
    try:
        backend = SQLiteAdapter(_db_url_to_path(db_url))
    except Exception as e:
        raise click.ClickException(f"Failed to connect to storage: {e}") from e

    try:
        stats = {
            "blocks_valid": 0, "blocks_invalid": 0,
            "events_valid": 0, "events_invalid": 0,
        }
        for chain_name in _get_chain_names(backend):
            latest = backend.get_latest_block(chain_name=chain_name)
            if latest is None:
                raise click.ClickException(f"Chain {chain_name} is empty")
            click.echo(f"Chain: {chain_name}")
            start, tip = _get_audit_range(latest['index'], limit)
            chain_stats = _run_audit_loop(
                backend, chain_name, start, tip, trusted_keys
            )
            for key, value in chain_stats.items():
                stats[key] += value
        _report_audit_stats(stats)
        if stats["blocks_invalid"]:
            raise click.ClickException("Block signature audit failed")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Error during audit: {e}") from e
    finally:
        backend.close()


def _run_audit_loop(
    backend: SQLiteAdapter,
    chain_name: str,
    start: int,
    tip: int,
    trusted_keys: dict[str, bytes],
) -> dict[str, int]:
    """Core logic to iterate through blocks and perform signature auditing."""
    block_verifier = BlockVerifier(strict_mode=True)
    sig_verifier = SignatureVerifier()
    stats = {
        "blocks_valid": 0, "blocks_invalid": 0, "events_valid": 0, "events_invalid": 0
    }
    
    with click.progressbar(range(start, tip + 1), label='Auditing') as bar:
        for i in bar:
            b_data = backend.get_block_by_index(i, chain_name=chain_name)
            if not b_data:
                raise click.ClickException(f"Missing block at index {i}")
            
            block = Block.from_dict(b_data)
            _audit_block_signature(block, block_verifier, stats, trusted_keys)
            _audit_event_signatures(block, sig_verifier, stats)
    return stats


def _get_audit_range(tip, limit):
    """Helper to determine the range of blocks to audit."""
    start = 0
    if tip > limit > 0:
        start = tip - limit + 1
        click.echo(f"Verifying last {limit} blocks (Index {start}-{tip})")
    else:
        click.echo(f"Verifying all blocks (Index 0-{tip})")
    return start, tip


def _audit_block_signature(
    block: Block,
    block_verifier: BlockVerifier,
    stats: dict[str, int],
    trusted_keys: dict[str, bytes],
) -> None:
    """Helper to verify a single block's signature and update stats."""
    public_key = trusted_keys.get(block.creator_id)
    if block_verifier.verify_block_signature(block, public_key).is_valid:
        stats["blocks_valid"] += 1
    else:
        stats["blocks_invalid"] += 1


def _audit_event_signatures(block, sig_verifier, stats) -> None:
    """Helper to verify all events within a block and update stats."""
    # block.events is a PyArrow Table, convert to list of dicts
    events_list = (
        block.events.to_pylist()
        if hasattr(block.events, 'to_pylist') else block.events
    )
    
    for event in events_list:
        if _verify_single_event_signature(event, sig_verifier):
            stats["events_valid"] += 1
        else:
            if event.get('signature') and (
                event.get('details', {}).get('public_key')
                if isinstance(event.get('details'), dict) else None
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


def _report_audit_stats(stats) -> None:
    """Helper to report the final audit statistics."""
    click.echo("\n Audit Complete:")
    click.echo(
        f"Blocks: {stats['blocks_valid']} Valid, {stats['blocks_invalid']} Invalid"
    )
    click.echo(
        f"Events: {stats['events_valid']} Valid, {stats['events_invalid']} Invalid"
    )
    
    if stats['blocks_invalid'] > 0 or stats['events_invalid'] > 0:
        click.secho("Audit found issues!", fg='red')
    else:
        click.secho("All checked signatures are valid.", fg='green')
