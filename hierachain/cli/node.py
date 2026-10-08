"""
Node management commands.
"""

import os

import click
import uvicorn

from hierachain.config.settings import settings
from hierachain.serialization import dumps_json


@click.group(name="node")
def node_group() -> None:
    """Node management commands."""


@node_group.command(name="start")
@click.option('--host', default=settings.API_HOST, help='Bind socket to this host.')
@click.option('--port', default=settings.API_PORT, help='Bind socket to this port.')
@click.option('--reload', is_flag=True, help='Enable auto-reload.')
def start_node(host: str, port: int, reload: bool) -> None:
    """Start the HieraChain API node."""
    click.echo(f"Starting HieraChain Node on {host}:{port}...")
    
    # We use uvicorn directly to run the FastAPI app
    from hierachain.config.logging import LOGGING_CONFIG
    
    uvicorn.run(
        "hierachain.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        log_config=LOGGING_CONFIG
    )


@node_group.command(name="init")
@click.option('--data-dir', default="./data", help='Directory for node configuration and hierarchy storage.')
def init_node(data_dir: str) -> None:
    """Initialize node configuration and directories."""
    absolute_data_dir = os.path.abspath(data_dir)
    click.echo(f"Initializing node at {absolute_data_dir}...")
    try:
        os.makedirs(absolute_data_dir, exist_ok=True)
    except OSError as exc:
        raise click.ClickException(f"Could not create data directory: {exc}") from exc

    absolute_config_path = os.path.join(absolute_data_dir, "config.yaml")
    database_path = os.path.join(absolute_data_dir, "hierachain.db")
    config = {
        "database_url": f"sqlite:///{database_path}",
        "node_id": "node_1",
    }
    try:
        with open(absolute_config_path, "x", encoding="utf-8") as config_file:
            config_file.write("# HieraChain Configuration\n")
            database_url = dumps_json(config["database_url"])
            node_id = dumps_json(config["node_id"])
            config_file.write(f"database_url: {database_url}\n")
            config_file.write(f"node_id: {node_id}\n")
    except FileExistsError:
        click.echo(f"Configuration already exists: {absolute_config_path}")
    except OSError as exc:
        raise click.ClickException(f"Could not write node configuration: {exc}") from exc

    click.echo("Initialization complete.")
