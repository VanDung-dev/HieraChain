"""
Verification tools for blockchain integrity.
"""

import logging

import click

from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.adapters.database.postgres_adapter import PostgresAdapter
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


def _open_backend(db_url: str) -> SQLBase:
    """Open the SQL adapter named by a CLI database URL or SQLite path."""
    if db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if db_url.startswith(("postgres://", "postgresql://")):
        return PostgresAdapter(database_url=db_url)
    if db_url.startswith(("sqlite:///", "sqlite://")):
        return SQLiteAdapter(_db_url_to_path(db_url))
    if "://" in db_url:
        raise ValueError("Unsupported database URL scheme")
    return SQLiteAdapter(db_url)


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
    click.echo("Verifying chain integrity")
    try:
        trusted_keys = load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    
    try:
        backend = _open_backend(db_url)
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


def _get_chain_names(backend: SQLBase) -> list[str]:
    """Get every chain that has stored blocks; never report empty verification as success."""
    names = backend.list_block_chain_names()
    if not names or any(not name for name in names):
        raise click.ClickException("No named block chains to verify")
    return names


def _load_blocks_from_backend(backend: SQLBase, chain_name: str) -> list[Block]:
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
    click.echo("Auditing signatures")
    try:
        trusted_keys = load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    
    try:
        backend = _open_backend(db_url)
    except Exception as e:
        raise click.ClickException(f"Failed to connect to storage: {e}") from e

    try:
        stats = {
            "blocks_valid": 0, "blocks_invalid": 0,
            "events_valid": 0, "events_invalid": 0, "events_unsigned": 0,
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
        if stats["blocks_invalid"] or stats["events_invalid"]:
            raise click.ClickException("Signature audit failed")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Error during audit: {e}") from e
    finally:
        backend.close()


def _run_audit_loop(
    backend: SQLBase,
    chain_name: str,
    start: int,
    tip: int,
    trusted_keys: dict[str, bytes],
) -> dict[str, int]:
    """Core logic to iterate through blocks and perform signature auditing."""
    block_verifier = BlockVerifier(strict_mode=True)
    sig_verifier = SignatureVerifier()
    stats = {
        "blocks_valid": 0, "blocks_invalid": 0,
        "events_valid": 0, "events_invalid": 0, "events_unsigned": 0,
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


def _audit_event_signatures(
    block: Block, sig_verifier: SignatureVerifier, stats: dict[str, int]
) -> None:
    """Unsigned events are allowed; incomplete or invalid signatures fail."""
    for event in block.to_event_list():
        result = _verify_single_event_signature(event, sig_verifier)
        if result is None:
            stats["events_unsigned"] += 1
        elif result:
            stats["events_valid"] += 1
        else:
            stats["events_invalid"] += 1


def _verify_single_event_signature(
    event: dict, sig_verifier: SignatureVerifier
) -> bool | None:
    """Return None for an unsigned event, false for incomplete signing data."""
    signature = event.get('signature')
    details = event.get('details', {})
    public_key = (
        details.get('public_key') or details.get('sender_public_key')
        if isinstance(details, dict) else None
    )
    if not signature and not public_key:
        return None
    if not signature or not public_key:
        return False
    return sig_verifier.verify_event_signature(event, public_key)


def _report_audit_stats(stats: dict[str, int]) -> None:
    """Helper to report the final audit statistics."""
    click.echo("\n Audit Complete:")
    click.echo(
        f"Blocks: {stats['blocks_valid']} Valid, {stats['blocks_invalid']} Invalid"
    )
    click.echo(
        f"Events: {stats['events_valid']} Valid, {stats['events_invalid']} Invalid"
    )
    click.echo(f"Unsigned events: {stats['events_unsigned']} (not verified)")
    
    if stats['blocks_invalid'] > 0 or stats['events_invalid'] > 0:
        click.secho("Audit found issues!", fg='red')
    else:
        click.secho("All checked signatures are valid.", fg='green')
