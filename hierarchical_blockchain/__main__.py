"""
Main entry point for the hierarchical_blockchain package.

This module allows running the hierarchical blockchain framework
as a module with `python -m hierarchical_blockchain`.
"""

from hierarchical_blockchain.api.server import run_server


def main():
    """Main entry point function"""
    run_server()


if __name__ == "__main__":
    main()