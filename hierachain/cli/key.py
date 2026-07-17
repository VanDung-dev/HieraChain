"""
Key management commands.
"""

import click
import orjson
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@click.group()
def key_group():
    """Key management commands."""
    pass


@key_group.command()
@click.option(
    '--output', '-o',
    default='validator_key.json',
    help='Output file path for the generated key pair (default: validator_key.json)'
)
@click.option(
    '--format',
    'key_format',
    type=click.Choice(['json', 'hex']),
    default='json',
    help='Output format (default: json)'
)
def generate(output: str, key_format: str) -> None:
    """Generate a new Ed25519 key pair for validators."""
    key = Ed25519PrivateKey.generate()
    private_key = key.private_bytes_raw().hex()
    public_key = key.public_key().public_bytes_raw().hex()

    if key_format == 'json':
        data = {
            "private_key": private_key,
            "public_key": public_key
        }
        with open(output, "wb") as f:
            f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        click.echo(f"Key pair generated and saved to: {output}")
        click.echo(f"Public Key: {public_key}")
    else:
        click.echo(f"Private Key (hex): {private_key}")
        click.echo(f"Public Key (hex): {public_key}")


@key_group.command()
@click.option(
    '--input', '-i',
    'input_file',
    default='validator_key.json',
    help='Input file path containing the key pair (default: validator_key.json)'
)
def show(input_file: str) -> None:
    """Show key pair information from a key file."""
    if not os.path.exists(input_file):
        click.echo(f"Error: Key file not found: {input_file}", err=True)
        raise click.Abort()

    with open(input_file, "rb") as f:
        data = orjson.loads(f.read())

    public_key = data.get("public_key", "N/A")
    private_key = data.get("private_key", "N/A")

    click.echo(f"Key file: {input_file}")
    click.echo(f"Public Key:  {public_key}")
    click.echo(f"Private Key: {private_key[:16]}...{private_key[-8:]} (masked)")


@key_group.command()
@click.option(
    '--input', '-i',
    'input_file',
    default='validator_key.json',
    help='Input file path containing the key pair (default: validator_key.json)'
)
def verify(input_file: str) -> None:
    """Verify a key pair is valid."""
    if not os.path.exists(input_file):
        click.echo(f"Error: Key file not found: {input_file}", err=True)
        raise click.Abort()

    with open(input_file, "rb") as f:
        data = orjson.loads(f.read())

    try:
        private_key_hex = data["private_key"]
        private_key_bytes = bytes.fromhex(private_key_hex)
        key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key = key.public_key().public_bytes_raw().hex()

        if public_key == data.get("public_key"):
            click.echo("Key pair is valid.")
        else:
            click.echo("Key pair is INVALID: Public key mismatch.", err=True)
            raise click.Abort()
    except (KeyError, ValueError) as e:
        click.echo(f"Invalid key file format: {e}", err=True)
        raise click.Abort()
