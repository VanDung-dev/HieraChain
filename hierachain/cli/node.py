"""
Node management commands.
"""

import click
import os
import uvicorn

from hierachain.config.settings import settings


@click.group(name="node")
def node_group() -> None:
    """Node management commands."""
    pass


@node_group.command(name="start")
@click.option('--host', default=settings.API_HOST, help='Bind socket to this host.')
@click.option('--port', default=settings.API_PORT, help='Bind socket to this port.')
@click.option('--reload', is_flag=True, help='Enable auto-reload.')
def start_node(host, port, reload) -> None:
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
@click.option('--data-dir', default="./data", help='Directory to store chain data.')
def init_node(data_dir) -> None:
    """Initialize node configuration and directories."""
    click.echo(f"Initializing node at {os.path.abspath(data_dir)}...")
    
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            click.echo(f"Created data directory: {data_dir}")
        except Exception as e:
            click.echo(f"Error creating directory: {e}")
            return
    else:
        click.echo(f"Data directory already exists: {data_dir}")
    
    # Create a default config file if needed
    config_path = os.path.join(data_dir, "config.yaml")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(f"""# HieraChain Configuration
database_url: "sqlite:///{os.path.join(data_dir, 'hierachain.db')}"
node_id: "node_1"
""")
        click.echo(f"Created default config: {config_path}")
    else:
        click.echo("Config file already exists.")

    click.echo("Initialization complete.")
