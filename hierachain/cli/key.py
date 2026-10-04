"""
Key management commands.
"""

import os

import click
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hierachain.serialization import dumps_json, loads_json


@click.group()
def key_group():
    """Key management commands."""


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

    data = {"private_key": private_key, "public_key": public_key}
    payload = (
        dumps_json(data, indent=2).encode("utf-8")
        if key_format == 'json'
        else f"{private_key}\n{public_key}\n".encode('ascii')
    )
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as file:
            file.write(payload)
    except OSError as exc:
        raise click.ClickException(f"Could not create key file {output}: {exc.strerror}") from exc

    click.echo(f"Key pair generated and saved to: {output}")
    click.echo(f"Public Key: {public_key}")


def _read_key_file(input_file: str) -> dict[str, str]:
    """Read a JSON key file or a two-line hex key file."""
    try:
        with open(input_file, 'rb') as file:
            payload = file.read()
        if payload.lstrip().startswith(b'{'):
            data = loads_json(payload)
            if not isinstance(data, dict):
                raise ValueError("Expected a key object")
        else:
            private_key, public_key = payload.decode('ascii').splitlines()
            data = {"private_key": private_key, "public_key": public_key}
        if not isinstance(data.get('private_key'), str) or not isinstance(data.get('public_key'), str):
            raise ValueError("Expected private_key and public_key strings")
        return data
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(f"Could not read key file {input_file}: {exc}") from exc


@key_group.command()
@click.option(
    '--input', '-i',
    'input_file',
    default='validator_key.json',
    help='Input file path containing the key pair (default: validator_key.json)'
)
def show(input_file: str) -> None:
    """Show key pair information from a key file."""
    data = _read_key_file(input_file)

    public_key = data.get("public_key", "N/A")
    click.echo(f"Key file: {input_file}")
    click.echo(f"Public Key:  {public_key}")
    click.echo("Private Key: (masked)")


@key_group.command()
@click.option(
    '--input', '-i',
    'input_file',
    default='validator_key.json',
    help='Input file path containing the key pair (default: validator_key.json)'
)
def verify(input_file: str) -> None:
    """Verify a key pair is valid."""
    data = _read_key_file(input_file)

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
