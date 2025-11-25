"""
Main entry point for the hierachain package.

This module allows running the HieraChain framework
as a module with `python -m hierachain`.
"""

from hierachain.api.server import run_server


def main():
    """Main entry point function"""
    run_server()


if __name__ == "__main__":
    main()